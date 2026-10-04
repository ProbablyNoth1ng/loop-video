import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from cloud import install, runpod_entrypoint
from tools.build_runpod_command import build_command


class CloudInstallTests(unittest.TestCase):
    def test_workflow_models_have_correct_unique_destinations(self):
        workflow = Path(__file__).resolve().parents[1] / 'workflows/ltx-2.5-motion-track.official.json'
        assets = install.model_assets(json.loads(workflow.read_text(encoding='utf-8')))
        self.assertEqual(len(assets), 6)
        lora = next(a for a in assets if a['target'].startswith('loras/'))
        self.assertEqual(lora['repo'], 'Lightricks/LTX-2.3-22b-IC-LoRA-Motion-Track-Control')
        self.assertEqual(lora['filename'], 'ltx-2.3-22b-ic-lora-motion-track-control-ref0.5.safetensors')
        self.assertIn('text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors',
                      [a['target'] for a in assets])

    def test_model_metadata_cannot_escape_models_directory(self):
        item = {'name': 'weights.safetensors', 'directory': '../outside',
                'url': 'https://huggingface.co/Org/Model/resolve/main/weights.safetensors'}
        with self.assertRaises(ValueError):
            install.model_assets({'properties': {'models': [item]}})

    def test_conflicting_sources_for_one_model_are_rejected(self):
        item = {'name': 'weights.safetensors', 'directory': 'vae',
                'url': 'https://huggingface.co/Org/Model/resolve/main/weights.safetensors'}
        other = dict(item, url='https://huggingface.co/Other/Model/resolve/main/weights.safetensors')
        with self.assertRaises(ValueError):
            install.model_assets({'properties': {'models': [item, other]}})

    def test_missing_or_truncated_file_invalidates_completed_download(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            records = [{'target': 'model.safetensors', 'size': 4}]
            self.assertFalse(install.files_complete(root, records))
            (root / 'model.safetensors').write_bytes(b'1234')
            self.assertTrue(install.files_complete(root, records))
            (root / 'model.safetensors').write_bytes(b'12')
            self.assertFalse(install.files_complete(root, records))

    def test_start_hook_runs_installer_before_launch_in_active_environment(self):
        source = '#!/bin/bash\nsource "$VENV_DIR/bin/activate"\npython main.py $FIXED_ARGS &\nCOMFY_PID=$!\nwait $COMFY_PID\n'
        patched = runpod_entrypoint.patch_start_script(source)
        lines = patched.splitlines()
        install_index = next(i for i, line in enumerate(lines) if 'cloud/install.py' in line)
        self.assertLess(lines.index('source "$VENV_DIR/bin/activate"'), install_index)
        self.assertLess(install_index, lines.index('python main.py $FIXED_ARGS --cache-none &'))
        self.assertIn('|| exit', lines[install_index])

    def test_setup_failure_prevents_comfyui_start(self):
        git_bash = Path('C:/Program Files/Git/bin/bash.exe')
        bash = str(git_bash) if git_bash.is_file() else shutil.which('bash')
        if not bash:
            self.skipTest('Bash unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            posix_root = subprocess.check_output(
                [bash, '-c', 'cygpath -u "$1"', '--', tmp], text=True).strip() if os.name == 'nt' else tmp
            trace = root / 'trace'
            fake_python = root / 'python'
            fake_python.write_text('#!/bin/bash\nif [[ "$1" == *install.py ]]; then\n'
                                   'echo setup >> "$TRACE"\nexit "$SETUP_EXIT"\nfi\n'
                                   'echo launch >> "$TRACE"\n', encoding='utf-8', newline='\n')
            fake_python.chmod(0o755)
            source = '#!/bin/bash\nset -e\npython main.py $FIXED_ARGS &\nCOMFY_PID=$!\nwait $COMFY_PID\n'
            launcher = root / 'start.sh'
            launcher.write_text(runpod_entrypoint.patch_start_script(source), encoding='utf-8', newline='\n')
            env = dict(os.environ, TRACE=posix_root + '/trace', PROJECT_ROOT=posix_root,
                       COMFYUI_DIR=posix_root, FIXED_ARGS='--port 8188')
            for code, expected in [('7', ['setup']), ('0', ['setup', 'launch'])]:
                trace.unlink(missing_ok=True)
                env['SETUP_EXIT'] = code
                result = subprocess.run([bash, '-c', 'export PATH="$1:$PATH"; bash "$1/start.sh"',
                                         '--', posix_root], env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, int(code), result.stderr)
                self.assertEqual(trace.read_text().splitlines(), expected)

    def test_unknown_base_launcher_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'launcher'):
            runpod_entrypoint.patch_start_script('python3 main.py\n')

    def test_start_command_fits_runpod_limit(self):
        command = build_command()
        self.assertLessEqual(len(json.dumps(command, indent=2) + '\n'), 4000)

    def test_generated_command_clones_and_executes_repository_installer(self):
        import sys
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / 'repository'
            (project / 'cloud').mkdir(parents=True)
            (project / 'cloud/install.py').write_text('VALUE = 42\n', encoding='utf-8')
            (project / 'cloud/runpod_entrypoint.py').write_text(
                'from install import VALUE\nprint("installed", VALUE)\n', encoding='utf-8')
            subprocess.run(['git', 'init', '--quiet', str(project)], check=True)
            subprocess.run(['git', '-C', str(project), 'add', '.'], check=True)
            subprocess.run(['git', '-C', str(project), '-c', 'user.name=Test',
                            '-c', 'user.email=test@example.invalid', 'commit', '--quiet', '-m', 'fixture'], check=True)
            target = Path(tmp) / 'pod/workspace/ambient-loop'
            env = dict(os.environ, AMBIENT_REPO=project.as_uri(), PROJECT_ROOT=str(target))
            env.pop('AMBIENT_REVISION', None)
            command = build_command()
            for attempt in range(2):
                result = subprocess.run([sys.executable, '-c', command['cmd'][0]],
                                        env=env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), 'installed 42')
                self.assertTrue((target / 'cloud/install.py').is_file())


if __name__ == '__main__':
    unittest.main()
