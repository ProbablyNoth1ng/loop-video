import hashlib
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

HEIGHTS = {'720p': 720, '1080p': 1080, '1440p': 1440, '4K': 2160}
PRESETS = ('calm-wind', 'rainy-window', 'sunset-field')


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                                     separators=(',', ':')).encode()).hexdigest()


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, allow_nan=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporary, path)


def dimensions(source, short_side):
    w, h = source
    divisor = math.gcd(w, h)
    rw, rh = w // divisor, h // divisor
    if short_side % min(rw, rh):
        raise ValueError('Aspect ratio cannot map exactly to requested short side')
    k = short_side // min(rw, rh)
    result = rw * k, rh * k
    if any(v % 2 for v in result):
        raise ValueError('Exact aspect ratio requires odd dimensions; yuv420p needs even dimensions')
    return result


def mask(path, size):
    with Image.open(path) as im:
        if im.size != size or im.mode not in ('L', '1', 'I;16'):
            raise ValueError(f'Mask must be grayscale at source dimensions: {path}')
        return np.asarray(im.convert('L'), dtype=np.float32) / 255


@dataclass
class Project:
    path: Path
    data: dict
    source_size: tuple
    assets: dict

    @classmethod
    def load(cls, path):
        path = Path(path).resolve()
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.get('schema') != 'ambient-loop/1':
            raise ValueError('Expected ambient-loop/1')
        for key, default in [('working_mode', '1080p'), ('output_resolution', '1440p'),
                             ('duration', 6), ('seed', 42), ('preset', 'calm-wind')]:
            data.setdefault(key, default)
        if data['working_mode'] not in ('720p', '1080p'):
            raise ValueError('working_mode must be 720p or 1080p')
        if data['output_resolution'] not in ('1080p', '1440p', '4K'):
            raise ValueError('output_resolution must be 1080p, 1440p or 4K')
        duration = data['duration']
        if not isinstance(duration, (int, float)) or not math.isfinite(duration) or not 4 <= duration <= 30:
            raise ValueError('Duration must be finite and between 4 and 30 seconds')
        if abs(duration * 24 - round(duration * 24)) > 1e-8:
            raise ValueError('Duration must contain a whole number of 24 FPS frames')
        if data.get('fps', 24) != 24 or data['preset'] not in PRESETS:
            raise ValueError('Only 24 FPS and the documented presets are supported')
        if not isinstance(data['seed'], int) or not 0 <= data['seed'] < 2**63:
            raise ValueError('Seed must be a nonnegative 63-bit integer')
        assets = {}
        names = [data.get('source'), data.get('guard')]
        if any(not n for n in names):
            raise ValueError('Source and immutable guard are required')
        regions = data.get('regions', [])
        if not regions:
            raise ValueError('At least one explicitly masked region is required')
        depths, ids = [], set()
        for r in regions:
            if r.get('kind') not in ('foliage', 'rain', 'shimmer'):
                raise ValueError('Unknown region kind')
            if not r.get('id') or r['id'] in ids:
                raise ValueError('Unique region IDs required')
            ids.add(r['id'])
            if not isinstance(r.get('depth'), int):
                raise ValueError('Explicit integer depth required')
            depths.append(r['depth'])
            for k in ('mask', 'support'):
                if not r.get(k):
                    raise ValueError(f'Region requires {k}')
                names.append(r[k])
            if r['kind'] == 'foliage':
                for k in ('root_weight', 'roots'):
                    if not r.get(k):
                        raise ValueError(f'Foliage requires {k}')
                    names.append(r[k])
                if r.get('expose_background', False):
                    # Silhouette movement is refused until a cutout compositor is qualified.
                    raise ValueError('Silhouette disocclusion is not qualified; constrain motion to interiors')
            for k, value in r.items():
                if k in ('amplitude', 'strength') and (not isinstance(value, (int, float)) or
                        not math.isfinite(value) or not 0 <= value <= (8 if k == 'amplitude' else .2)):
                    raise ValueError(f'Unsafe {k}')
            if r['kind'] == 'rain' and (not isinstance(r.get('particles', 80), int) or
                                       not 1 <= r.get('particles', 80) <= 2000):
                raise ValueError('Rain particles must be 1-2000')
        regional = data.get('regional', {})
        for key in ('support', 'protected', 'official_api', 'smoke_record'):
            if key in regional:
                names.append(regional[key])
        if len(set(depths)) != len(depths):
            raise ValueError('Depth order must be unambiguous')
        for name in names:
            asset = (path.parent / name).resolve()
            if not asset.is_file():
                raise ValueError(f'Missing asset: {name}')
            assets[name] = sha(asset)
        with Image.open(path.parent / data['source']) as im:
            size = im.size
            if im.mode not in ('RGB', 'RGBA') or min(size) < 16:
                raise ValueError('Source must be an RGB/RGBA image at least 16px per side')
            if im.mode == 'RGBA' and np.any(np.asarray(im)[..., 3] != 255):
                raise ValueError('Flatten source transparency before preparing assets')
        guard = mask(path.parent / data['guard'], size)
        for r in regions:
            alpha, support = (mask(path.parent / r[k], size) for k in ('mask', 'support'))
            if not np.any(alpha > 0) or np.any((alpha > 0) & (support < 1)):
                raise ValueError('Active mask must be contained in binary safe support')
            if np.any((support != 0) & (support != 1)) or np.any((support > 0) & (guard > 0)):
                raise ValueError('Safe support must be binary and exclude immutable guards')
            if r['kind'] == 'foliage':
                weight = mask(path.parent / r['root_weight'], size)
                roots = mask(path.parent / r['roots'], size)
                if not np.any(roots > 0) or np.any(weight[roots > 0] != 0):
                    raise ValueError('Root weights must be zero at all fixed roots')
        p = cls(path, data, size, assets)
        p.working_size
        p.output_size
        return p

    @property
    def frames(self):
        return round(self.data['duration'] * 24)

    @property
    def working_size(self):
        return dimensions(self.source_size, HEIGHTS[self.data['working_mode']])

    @property
    def output_size(self):
        return dimensions(self.source_size, HEIGHTS[self.data['output_resolution']])

    @property
    def upscale(self):
        return self.output_size != self.working_size

    @property
    def fingerprint(self):
        return digest({'project': {k: v for k, v in self.data.items() if k != 'approvals'},
                       'assets': self.assets, 'renderer': sha(Path(__file__).with_name('renderer.py')),
                       'contract': sha(Path(__file__))})

    def require_approvals(self):
        for stage in ('masks', 'motion'):
            a = self.data.get('approvals', {}).get(stage, {})
            if a.get('hash') != self.fingerprint or not a.get('reviewer'):
                raise ValueError(f'Missing or stale human {stage} approval')


def approve(path, stage, reviewer):
    if stage not in ('masks', 'motion') or not reviewer.strip():
        raise ValueError('Named reviewer and masks/motion stage required')
    p = Project.load(path)
    p.data.setdefault('approvals', {})[stage] = {
        'hash': p.fingerprint, 'reviewer': reviewer,
        'at': datetime.now(timezone.utc).isoformat()}
    atomic_json(p.path, p.data)
