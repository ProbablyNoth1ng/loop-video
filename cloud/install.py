"""Install the saved Ambient Loop workflow in an initialized ComfyUI environment."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlparse
from urllib.request import urlopen


QWEN_REPO = 'Qwen/Qwen3-VL-8B-Instruct'
# ComfyUI v0.38.0 includes the LTX-2.5 diffusion video VAE loader.
COMFY_COMPAT_REVISION = '6b747c0428c343e1417219641db93a4fb7cb69ae'
UPSCALER = 'upscale_models/realesr-animevideov3.pth'
UPSCALER_URL = ('https://github.com/xinntao/Real-ESRGAN/releases/download/'
                'v0.2.5.0/realesr-animevideov3.pth')


def relative_path(value):
    path = PurePosixPath(value)
    if not value or path.is_absolute() or '..' in path.parts or '\\' in value:
        raise ValueError('Unsafe model path')
    return path


def model_assets(workflow):
    assets = {}

    def visit(value):
        if isinstance(value, dict):
            for item in value.get('models', []):
                url = urlparse(item['url'])
                parts = url.path.strip('/').split('/')
                if url.scheme != 'https' or url.netloc != 'huggingface.co' or len(parts) < 5 or parts[2] != 'resolve':
                    raise ValueError('Expected a Hugging Face model URL')
                filename = str(relative_path('/'.join(parts[4:])))
                name = str(relative_path(item['name']))
                if '/' in name or PurePosixPath(filename).name != name:
                    raise ValueError('Model filename does not match URL')
                target = str(relative_path(item['directory']) / name)
                source_parent = PurePosixPath(filename).parent
                target_parent = PurePosixPath(target).parent
                if source_parent == target_parent:
                    local_dir = '.'
                elif str(source_parent) == '.':
                    local_dir = str(target_parent)
                else:
                    raise ValueError('Unsupported model directory mapping')
                asset = dict(repo='/'.join(parts[:2]), revision=parts[3], filename=filename,
                             target=target, local_dir=local_dir)
                if target in assets and assets[target] != asset:
                    raise ValueError('Conflicting sources for model: ' + target)
                assets[target] = asset
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)

    visit(workflow)
    if not assets:
        raise ValueError('Workflow has no model metadata')
    return sorted(assets.values(), key=lambda a: a['target'])


def files_complete(root, records):
    return bool(records) and all(
        (root / relative_path(r['target'])).is_file()
        and (root / r['target']).stat().st_size == r['size'] > 0 for r in records)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None


def write_json(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def resolve_plan(assets):
    from huggingface_hub import HfApi
    api = HfApi()
    repositories = {}
    for repo, revision in sorted({(a['repo'], a['revision']) for a in assets} | {(QWEN_REPO, 'main')}):
        print('Checking model access: ' + repo, flush=True)
        try:
            info = api.model_info(repo, revision=revision, files_metadata=True)
        except Exception as error:
            raise RuntimeError('Cannot access ' + repo + '. Check HF_TOKEN, access terms and network ('
                               + type(error).__name__ + ').') from None
        repositories[repo, revision] = info

    records = []
    for asset in assets:
        info = repositories[asset['repo'], asset['revision']]
        sibling = next((s for s in info.siblings if s.rfilename == asset['filename']), None)
        if sibling is None or not sibling.size:
            raise RuntimeError('Missing model at source: ' + asset['target'])
        records.append(dict(asset, revision=info.sha, size=sibling.size,
                            sha256=getattr(sibling.lfs, 'sha256', None)))
    info = repositories[QWEN_REPO, 'main']
    qwen_files = [s for s in info.siblings if s.rfilename.endswith(
        ('.json', '.safetensors', '.txt', '.model', '.jinja'))]
    if not any(s.rfilename == 'config.json' for s in qwen_files) or not any(
            s.rfilename.endswith('.safetensors') for s in qwen_files):
        raise RuntimeError('Qwen snapshot has no config or weights')
    for sibling in qwen_files:
        if not sibling.size:
            raise RuntimeError('Qwen file size unavailable: ' + sibling.rfilename)
        records.append(dict(repo=QWEN_REPO, revision=info.sha, filename=sibling.rfilename,
                            target='Qwen3-VL-8B-Instruct/' + sibling.rfilename,
                            local_dir='Qwen3-VL-8B-Instruct', size=sibling.size,
                            sha256=getattr(sibling.lfs, 'sha256', None)))
    return records


def download_models(project, comfy, state):
    from huggingface_hub import hf_hub_download
    assets = model_assets(read_json(project / 'workflows/ltx-2.5-motion-track.official.json'))
    signature = hashlib.sha256(json.dumps(assets, sort_keys=True).encode()).hexdigest()
    root = comfy / 'models'
    root.mkdir(exist_ok=True)
    ready = read_json(state / 'models-ready.json')
    if ready and ready['signature'] == signature and files_complete(root, ready['files']):
        upscaler = next(r for r in ready['files'] if r['target'] == UPSCALER)
        if sha256(root / UPSCALER) == upscaler['sha256']:
            print('Models already downloaded; using existing files on this disk.', flush=True)
            return
    plan = read_json(state / 'models-plan.json')
    if not plan or plan['signature'] != signature:
        plan = dict(signature=signature, files=resolve_plan(assets))
        write_json(state / 'models-plan.json', plan)
    missing_bytes = sum(r['size'] for r in plan['files']
                        if not files_complete(root, [r]))
    if shutil.disk_usage(root).free < missing_bytes + 5 * 1024 ** 3:
        raise RuntimeError(f'Insufficient disk space: need about {missing_bytes / 1024**3 + 5:.1f} GiB free.')
    completed = []
    for record in plan['files']:
        print('Downloading/checking: ' + record['target'], flush=True)
        try:
            path = Path(hf_hub_download(repo_id=record['repo'], filename=record['filename'],
                                       revision=record['revision'], local_dir=root / record['local_dir']))
        except Exception as error:
            raise RuntimeError('Download failed for ' + record['target']
                               + '. Check HF_TOKEN/access/network and restart to resume ('
                               + type(error).__name__ + ').') from None
        if path.resolve() != (root / record['target']).resolve() or path.stat().st_size != record['size']:
            raise RuntimeError('Incomplete model: ' + record['target'])
        print('Verifying SHA256: ' + record['target'], flush=True)
        digest = sha256(path)
        if record['sha256'] and digest != record['sha256']:
            raise RuntimeError('Model checksum mismatch: ' + record['target'])
        completed.append(dict(record, sha256=digest))
    upscaler = root / UPSCALER
    upscaler.parent.mkdir(exist_ok=True)
    if not ready or not files_complete(root, [r for r in ready['files'] if r['target'] == UPSCALER]) or (
            sha256(upscaler) != next(r['sha256'] for r in ready['files'] if r['target'] == UPSCALER)):
        temporary = upscaler.with_suffix('.part.pth')
        for attempt in range(3):
            try:
                with urlopen(UPSCALER_URL, timeout=120) as response, temporary.open('wb') as stream:
                    if 'text/html' in response.headers.get('Content-Type', ''):
                        raise RuntimeError('Upscale download returned HTML')
                    shutil.copyfileobj(response, stream)
                # Validate the actual checkpoint before accepting it as complete.
                from spandrel import ModelLoader
                ModelLoader().load_from_file(str(temporary))
                temporary.replace(upscaler)
                break
            except Exception:
                if attempt == 2:
                    raise RuntimeError('Real-ESRGAN download/validation failed. Restart to retry.') from None
                time.sleep(3)
    completed.append(dict(target=UPSCALER, size=upscaler.stat().st_size, sha256=sha256(upscaler)))
    write_json(state / 'models-ready.json', dict(signature=signature, files=completed))


def clone_once(repo, destination, revision=None):
    if destination.exists():
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=destination.name + '.installing-', dir=destination.parent))
    subprocess.run(['git', 'clone', '--depth', '1', repo, str(temporary)], check=True)
    subprocess.run(['git', '-C', str(temporary), 'rev-parse', '--verify', 'HEAD'], check=True)
    if revision:
        subprocess.run(['git', '-C', str(temporary), 'fetch', '--depth', '1', 'origin', revision], check=True)
        subprocess.run(['git', '-C', str(temporary), 'checkout', '--detach', 'FETCH_HEAD'], check=True)
    temporary.rename(destination)


def ensure_comfy_compatibility(comfy):
    def supports_diffusion_vae():
        source = comfy / 'comfy/sd.py'
        decoder = comfy / 'comfy/ldm/lightricks/vae/na_diffusion_decoder.py'
        if not source.is_file() or not decoder.is_file():
            return False
        loader = source.read_text(encoding='utf-8')
        return ('"decoder.conv_in_x_t.weight" in sd' in loader
                and 'na_diffusion_decoder.CausalDiffusionVAE(' in loader)

    if supports_diffusion_vae():
        return
    git = ['git', '-C', str(comfy)]
    changes = subprocess.check_output(git + ['status', '--porcelain', '--untracked-files=no'])
    if changes.strip():
        raise RuntimeError('ComfyUI lacks the LTX-2.5 diffusion VAE loader and has local changes. '
                           'Save those changes and update ComfyUI before restarting setup.')
    previous = subprocess.check_output(git + ['rev-parse', 'HEAD'], text=True).strip()
    print('Updating ComfyUI to v0.38.0 for LTX-2.5 diffusion VAE support.', flush=True)
    subprocess.run(git + ['fetch', '--depth', '1', 'origin', COMFY_COMPAT_REVISION], check=True)
    subprocess.run(git + ['checkout', '--detach', 'FETCH_HEAD'], check=True)
    if not supports_diffusion_vae():
        subprocess.run(git + ['checkout', '--detach', previous], check=True)
        raise RuntimeError('ComfyUI update lacks LTX-2.5 diffusion VAE support; previous revision restored.')


def install(project, comfy):
    if sys.version_info < (3, 12):
        raise RuntimeError('Use Python 3.12+ from the ComfyUI environment.')
    if not (comfy / 'main.py').is_file() or not (project / 'pyproject.toml').is_file():
        raise RuntimeError('ComfyUI or Ambient Loop installation is missing.')
    if Path(sys.prefix).resolve() == Path(sys.base_prefix).resolve():
        candidates = [comfy / name / 'bin/python' for name in ('.venv-cu128', '.venv-cu130', '.venv')]
        python = next((p for p in candidates if p.is_file()), None)
        if python is None:
            raise RuntimeError('Wait for the official image to initialize its ComfyUI virtual environment.')
        os.execv(str(python), [str(python), __file__, '--project-root', str(project), '--comfy-root', str(comfy)])
    state = comfy / '.ambient-loop-install'
    state.mkdir(exist_ok=True)
    ensure_comfy_compatibility(comfy)
    for command in ('ffmpeg', 'ffprobe'):
        if not shutil.which(command):
            subprocess.run(['apt-get', 'update'], check=True)
            subprocess.run(['apt-get', 'install', '-y', '--no-install-recommends', 'ffmpeg'], check=True)
            break
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError('CUDA is unavailable. Check host driver compatibility with this CUDA 13 image.')
    print('GPU: ' + torch.cuda.get_device_name(0) + '; Torch ' + torch.__version__, flush=True)
    ltx = comfy / 'custom_nodes/ComfyUI-LTXVideo'
    clone_once('https://github.com/Lightricks/ComfyUI-LTXVideo.git', ltx, os.environ.get('LTX_REVISION'))
    constraints = state / 'torch-constraints.txt'
    versions = {p: importlib.metadata.version(p) for p in ('torch', 'torchvision', 'torchaudio')}
    constraints.write_text(''.join(f'{p}=={v}\n' for p, v in versions.items()), encoding='utf-8')
    fingerprint = hashlib.sha256()
    for path in (project / 'pyproject.toml', comfy / 'requirements.txt', ltx / 'requirements.txt'):
        fingerprint.update(path.read_bytes())
    fingerprint.update((str(sys.version_info[:3]) + json.dumps(versions, sort_keys=True)).encode())
    fingerprint.update(str(project).encode())
    fingerprint.update(subprocess.check_output(['git', '-C', str(comfy), 'rev-parse', 'HEAD']))
    fingerprint.update(subprocess.check_output(['git', '-C', str(ltx), 'rev-parse', 'HEAD']))
    expected = fingerprint.hexdigest()
    installed = read_json(state / 'dependencies.json')
    changed = not installed or installed['fingerprint'] != expected
    if changed:
        print('Installing Ambient Loop and LTX dependencies in ' + sys.prefix, flush=True)
        subprocess.run([sys.executable, '-m', 'pip', 'install', '-c', str(constraints),
                        '-r', str(comfy / 'requirements.txt'), '-r', str(ltx / 'requirements.txt'),
                        '-e', str(project) + '[vision]'], check=True)
    subprocess.run([sys.executable, '-c', 'import numpy, PIL, scipy, accelerate, spandrel; '
                    'from transformers import AutoProcessor, Qwen3VLForConditionalGeneration; '
                    'import ambient_loop.comfy'], cwd=comfy, check=True)
    write_json(state / 'dependencies.json', dict(fingerprint=expected, torch=versions))
    if changed:
        # pip may have replaced packages already imported by torch in this process.
        os.execv(sys.executable, [sys.executable, __file__, '--project-root', str(project),
                                '--comfy-root', str(comfy)])
    link = comfy / 'custom_nodes/ambient_loop'
    source = project / 'comfy_nodes/ambient_loop'
    if link.is_symlink():
        if link.resolve() != source.resolve():
            raise RuntimeError('Existing Ambient Loop node points to another project.')
    elif link.exists():
        raise RuntimeError('Existing ambient_loop custom node is not this project symlink.')
    else:
        link.symlink_to(source, target_is_directory=True)
    download_models(project, comfy, state)
    workflows = comfy / 'user/default/workflows'
    workflows.mkdir(parents=True, exist_ok=True)
    for name in ('ambient-motion.json', 'ltx-2.5-motion-track.official.json'):
        destination = workflows / name
        if not destination.exists():
            shutil.copy2(project / 'workflows' / name, destination)
    (state / 'packages.txt').write_bytes(subprocess.check_output([sys.executable, '-m', 'pip', 'freeze']))
    print('AMBIENT LOOP INSTALLED. Starting ComfyUI; GPU rendering still needs qualification.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--comfy-root', default='/workspace/runpod-slim/ComfyUI')
    parser.add_argument('--project-root', default='/workspace/ambient-loop')
    args = parser.parse_args()
    os.environ.setdefault('HF_HOME', '/workspace/.cache/huggingface')
    try:
        install(Path(args.project_root).resolve(), Path(args.comfy_root).resolve())
    except (RuntimeError, ValueError, OSError, subprocess.CalledProcessError) as error:
        print('AMBIENT LOOP SETUP FAILED: ' + str(error), file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
