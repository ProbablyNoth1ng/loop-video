import json
import tempfile
import unittest
from pathlib import Path

from cloud import install, runpod_entrypoint


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
        self.assertLess(install_index, lines.index('python main.py $FIXED_ARGS &'))
        self.assertIn('|| exit', lines[install_index])

    def test_unknown_base_launcher_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'launcher'):
            runpod_entrypoint.patch_start_script('python3 main.py\n')


if __name__ == '__main__':
    unittest.main()
