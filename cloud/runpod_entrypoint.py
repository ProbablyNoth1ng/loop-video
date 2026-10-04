"""Run the official image launcher with setup inserted before its ComfyUI process."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile


def patch_start_script(source):
    array_launch = 'python main.py "${COMFY_ARGS[@]}" &'
    string_launch = 'python main.py $FIXED_ARGS &'
    lines = source.splitlines(keepends=True)
    matches = [(index, line.strip()) for index, line in enumerate(lines)
               if line.strip() in (array_launch, string_launch)]
    if len(matches) != 1:
        raise RuntimeError('Unsupported official image launcher; expected one ComfyUI launch.')
    hook = ('python "${AMBIENT_INSTALLER:-$PROJECT_ROOT/cloud/install.py}" '
            '--project-root "$PROJECT_ROOT" --comfy-root "$COMFYUI_DIR" || exit $?\n')
    index, launch = matches[0]
    if launch == array_launch:
        lines[index] = hook + 'COMFY_ARGS+=(--cache-none)\n' + lines[index]
    else:
        lines[index] = hook + lines[index].replace('$FIXED_ARGS', '$FIXED_ARGS --cache-none')
    return ''.join(lines)


def main():
    project = Path(os.environ.get('PROJECT_ROOT', '/workspace/ambient-loop'))
    os.environ['PROJECT_ROOT'] = str(project)
    os.environ['AMBIENT_INSTALLER'] = str(Path(__file__).with_name('install.py').resolve())
    os.environ.setdefault('HF_HOME', '/workspace/.cache/huggingface')
    try:
        # Check compatibility before downloading or starting any official services.
        patched = patch_start_script(Path('/start.sh').read_text(encoding='utf-8'))
        from install import clone_once
        clone_once(os.environ.get('AMBIENT_REPO', 'https://github.com/ProbablyNoth1ng/loop-video.git'),
                   project, os.environ.get('AMBIENT_REVISION'))
        if not (project / 'pyproject.toml').is_file():
            raise RuntimeError('Repository does not contain the Ambient Loop project.')
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False, encoding='utf-8') as stream:
            stream.write(patched)
            launcher = stream.name
        os.execv('/bin/bash', ['/bin/bash', launcher])
    except (OSError, RuntimeError, subprocess.CalledProcessError) as error:
        print('AMBIENT LOOP STARTUP FAILED: ' + str(error), file=sys.stderr, flush=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
