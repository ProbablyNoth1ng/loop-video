import importlib.metadata
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

import numpy as np

from .project import atomic_json, sha

DEPENDENCIES = {'numpy': '2.2.6', 'Pillow': '11.3.0', 'scipy': '1.15.3'}


def revision(path):
    rev = subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()
    dirty = subprocess.check_output(['git', '-C', str(path), 'status', '--porcelain'], text=True).strip()
    if dirty:
        raise ValueError(f'Dependency repository must be clean for qualification: {path}')
    return rev


def environment(action, comfy, lock, image_digest=None):
    import torch
    comfy, lock = Path(comfy).resolve(), Path(lock)
    if not comfy.is_relative_to(Path('/workspace').resolve()):
        raise ValueError('RunPod ComfyUI must reside under /workspace')
    if not re.fullmatch(r'.+@sha256:[0-9a-f]{64}', image_digest or '') and action == 'record':
        raise ValueError('Supply the actual container image@sha256 digest')
    if not torch.cuda.is_available():
        raise ValueError('GPU access required for RunPod qualification')
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        raise ValueError('ffmpeg and ffprobe required')
    versions = {k: importlib.metadata.version(k) for k in DEPENDENCIES}
    if versions != DEPENDENCIES:
        raise ValueError(f'Dependency pins differ: {versions}')
    if shutil.disk_usage(comfy).free < 2 * 1024**3:
        raise ValueError('At least 2 GiB free storage required for startup smoke test')
    from .comfy import NODE_CLASS_MAPPINGS
    if 'ComfyLTXLoopRender' not in NODE_CLASS_MAPPINGS:
        raise ValueError('ComfyLTXLoopRender node missing')
    current = {'comfy_revision': revision(comfy), 'dependencies': versions,
               'torch': torch.__version__, 'cuda': torch.version.cuda,
               'node_code_sha256': sha(Path(__file__).with_name('comfy.py')),
               'renderer_sha256': sha(Path(__file__).with_name('renderer.py')),
               'gpu': torch.cuda.get_device_name(0)}
    ltx = comfy / 'custom_nodes' / 'ComfyUI-LTXVideo'
    if (ltx / '.git').exists():
        current['ltx_revision'] = revision(ltx)
    saved = None
    if action == 'check':
        saved = json.loads(lock.read_text())
        for k in ('comfy_revision', 'dependencies', 'torch', 'cuda', 'node_code_sha256', 'renderer_sha256'):
            if saved.get(k) != current[k]:
                raise ValueError(f'Environment drift: {k}')
        if saved.get('ltx_revision') != current.get('ltx_revision'):
            raise ValueError('Environment drift: LTX revision')
    # Allocate on the actual GPU before declaring GPU health.
    tensor = torch.zeros((16, 16), device='cuda')
    if tensor.sum().item() != 0:
        raise ValueError('GPU smoke failed')
    from .examples import create_examples
    from .project import Project
    from .jobs import render
    import tempfile
    with tempfile.TemporaryDirectory(dir=comfy.parent) as tmp:
        root = Path(tmp)
        create_examples(root / 'assets')
        p = Project.load(root / 'assets/sunset-field/project.json')
        result = render(p, root / 'output', sizes=((64, 36), (128, 72)), preview=True)
        if result['state'] != 'awaiting_review':
            raise ValueError('Tiny rendering/encoding smoke test failed')
    if action == 'record':
        # Qualification also confirms the running server registered the custom node.
        with urlopen('http://127.0.0.1:8188/object_info', timeout=15) as response:
            nodes = json.load(response)
        if 'ComfyLTXLoopRender' not in nodes:
            raise ValueError('Running ComfyUI has not registered ComfyLTXLoopRender')
        current.update(image_digest=image_digest, tested_at=datetime.now(timezone.utc).isoformat(),
                       smoke={'render': True, 'encode': True, 'gpu': True, 'node_registered': True})
        atomic_json(lock, current)
    return saved or current
