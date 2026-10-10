import json
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from .project import Project, atomic_json, digest, mask, sha


def transform_tracks(tracks, crop):
    x, y, w, h = crop
    if w <= 0 or h <= 0:
        raise ValueError('Invalid crop dimensions')
    result = []
    for track in tracks:
        converted = []
        for point in track:
            px, py = (point['x'] - x) * 512 / w, (point['y'] - y) * 512 / h
            if not math.isfinite(px + py) or not 0 <= px < 512 or not 0 <= py < 512:
                raise ValueError('Track point is outside recorded crop')
            converted.append({'x': float(px), 'y': float(py)})
        if not converted:
            raise ValueError('Empty track')
        result.append(converted)
    if not result:
        raise ValueError('At least one track required')
    return result


def check_fallback(project, accepted_a):
    p = Project.load(project)
    p.require_approvals()
    fallback = Path(accepted_a)
    manifest = json.loads((fallback / 'manifest.json').read_text())
    if manifest['state'] != 'accepted' or manifest['project_hash'] != p.fingerprint:
        raise ValueError('Regional work requires an accepted A matching this project')
    for name, expected in manifest['artifacts'].items():
        if sha(fallback / name) != expected:
            raise ValueError('Accepted fallback was modified')
    for index, expected in manifest['frame_hashes'].items():
        if sha(fallback / 'frames' / f'{int(index):06d}.png') != expected:
            raise ValueError('Accepted fallback frame was modified')
    if p.data['duration'] != 6:
        raise ValueError('Initial regional experiment supports six-second projects only')
    return p


def prepare(project, accepted_a, destination):
    p = check_fallback(project, accepted_a)
    settings = p.data.get('regional', {})
    required = ('crop', 'support', 'protected', 'tracks', 'official_api', 'bindings', 'smoke_record')
    if any(k not in settings for k in required):
        raise ValueError('regional requires crop, support, protected, tracks, official_api, bindings and smoke_record')
    root = p.path.parent
    support = mask(root / settings['support'], p.source_size)
    protected = mask(root / settings['protected'], p.source_size)
    guard = mask(root / p.data['guard'], p.source_size)
    for r in p.data['regions']:
        if r['kind'] == 'foliage':
            guard = np.maximum(guard, mask(root / r['roots'], p.source_size))
    if np.any((support != 0) & (support != 1)) or np.mean(support > 0) > .1:
        raise ValueError('Regional binary support must cover at most 10% of source')
    if np.any((support > 0) & ((protected > 0) | (guard > 0))):
        raise ValueError('Regional support overlaps protected anatomy/text/linework')
    x, y, w, h = settings['crop']
    if any(not isinstance(v, int) for v in (x, y, w, h)) or min(x, y) < 0 or min(w, h) < 1:
        raise ValueError('Crop requires integer x,y,width,height')
    if x + w > p.source_size[0] or y + h > p.source_size[1]:
        raise ValueError('Crop exceeds source bounds')
    outside = support.copy()
    outside[y:y+h, x:x+w] = 0
    if np.any(outside):
        raise ValueError('Regional support exceeds crop')
    tracks = transform_tracks(settings['tracks'], settings['crop'])
    if any(len(track) != 145 for track in tracks):
        raise ValueError('Tracks must contain 145 positions, including conceptual endpoint')
    dest = Path(destination)
    dest.mkdir(parents=True, exist_ok=True)
    image = Image.open(root / p.data['source']).convert('RGB').crop((x, y, x+w, y+h)).resize((512, 512), Image.Resampling.LANCZOS)
    image.save(dest / 'crop.png')
    guide = image.copy()
    draw = ImageDraw.Draw(guide)
    for track in tracks:
        draw.line([(pt['x'], pt['y']) for pt in track], fill=(255, 64, 64), width=2)
    guide.save(dest / 'track-guide.png')
    from .jobs import save_png, encode_video
    import shutil
    guide_job = dest / 'guide-encode'
    (guide_job / 'frames').mkdir(parents=True, exist_ok=True)
    for index in range(145):
        frame = image.copy()
        painter = ImageDraw.Draw(frame)
        for track in tracks:
            tail = track[max(0, index-8):index+1]
            if len(tail) > 1:
                painter.line([(pt['x'], pt['y']) for pt in tail], fill=(255, 64, 64), width=2)
            point = track[index]
            px, py = point['x'], point['y']
            painter.ellipse((px-3, py-3, px+3, py+3), fill=(255, 220, 0))
        save_png(guide_job / 'frames' / f'{index:06d}.png', np.asarray(frame))
    encode_video(guide_job, 145, (512, 512), 'track-guide.mp4')
    shutil.move(str(guide_job / 'track-guide.mp4'), str(dest / 'track-guide.mp4'))
    shutil.rmtree(guide_job)
    api_path = root / settings['official_api']
    smoke = json.loads((root / settings['smoke_record']).read_text())
    if (not smoke.get('passed') or smoke.get('recipe') != 'BF16-single-stage-motion-track' or
            smoke.get('workflow_sha256') != sha(api_path) or not smoke.get('weights')):
        raise ValueError('Official BF16 recipe smoke evidence is missing/stale')
    for weight in smoke['weights']:
        if sha(root / weight['path']) != weight['sha256']:
            raise ValueError('Model weight hash differs from smoke-tested weights')
    record = {'project_hash': p.fingerprint, 'fallback': str(Path(accepted_a).resolve()),
              'transform': {'crop': settings['crop'], 'target': [512, 512]},
              'tracks': tracks, 'support_hash': sha(root / settings['support']),
              'protected_hash': sha(root / settings['protected']), 'workflow_hash': sha(api_path),
              'guide_hash': sha(dest / 'track-guide.png'), 'crop_hash': sha(dest / 'crop.png'),
              'animated_guide_hash': sha(dest / 'track-guide.mp4'),
              'recipe': {'width': 512, 'height': 512, 'frames': 145, 'fps': 24,
                         'cfg': 1, 'adapter_strength': 1, 'prompt_enhancement': False},
              'seeds': [42, 43, 44]}
    record['hash'] = digest(record)
    atomic_json(dest / 'regional-plan.json', record)
    return record


def candidate(project, accepted_a, destination, reviewer):
    """Emit a bounded, reviewable API job; actual GPU execution uses ComfyUI queue."""
    p = check_fallback(project, accepted_a)
    dest = Path(destination)
    attempts_path = dest / 'attempts.json'
    attempts = json.loads(attempts_path.read_text()) if attempts_path.exists() else []
    if len(attempts) >= 3:
        raise ValueError('Three regional candidates exhausted; retain accepted Workflow A')
    plan = json.loads((dest / 'regional-plan.json').read_text())
    previous_hash = plan['hash']
    current = prepare(project, accepted_a, destination)
    if current['hash'] != previous_hash:
        raise ValueError('Regional assets changed; review the new guide before continuing')
    if not reviewer or not reviewer.strip():
        raise ValueError('Named human track-guide reviewer required')
    settings = p.data['regional']
    graph = json.loads((p.path.parent / settings['official_api']).read_text())
    if not isinstance(graph, dict) or any('class_type' not in v for v in graph.values()):
        raise ValueError('Supply the official graph exported in API format')
    values = {**current['recipe'], 'seed': 42 + len(attempts),
              'tracks': json.dumps(current['tracks']), 'image': str((dest / 'crop.png').resolve())}
    bindings = settings['bindings']
    if any(k not in bindings for k in values):
        raise ValueError('Provide explicit node/input bindings for every recorded recipe setting')
    for key, value in values.items():
        node, input_name = bindings[key]
        if str(node) not in graph or input_name not in graph[str(node)]['inputs']:
            raise ValueError(f'Official graph binding missing: {key}')
        graph[str(node)]['inputs'][input_name] = value
    attempt = {'seed': values['seed'], 'plan_hash': current['hash'], 'reviewer': reviewer,
               'state': 'prepared', 'fallback': str(accepted_a)}
    job = dest / f'candidate-{values["seed"]}.api.json'
    atomic_json(job, graph)
    attempt['graph_hash'] = sha(job)
    attempts.append(attempt)
    atomic_json(attempts_path, attempts)
    return {'job': str(job), **attempt, 'next': 'Queue in smoke-tested ComfyUI; raw drift/closure and final composite review required'}


def finish(project, accepted_a, destination, seed, raw_frames):
    from .jobs import save_png, encode_video, review_package
    from .renderer import Renderer, linear, srgb, resize_float
    p = check_fallback(project, accepted_a)
    destination = Path(destination)
    plan = json.loads((destination / 'regional-plan.json').read_text())
    if plan['hash'] != digest({k: v for k, v in plan.items() if k != 'hash'}) or plan['project_hash'] != p.fingerprint:
        raise ValueError('Regional plan was modified or belongs to a different project')
    for name, key in [('crop.png', 'crop_hash'), ('track-guide.png', 'guide_hash'),
                      ('track-guide.mp4', 'animated_guide_hash')]:
        if sha(destination / name) != plan[key]:
            raise ValueError('Reviewed crop/guide changed')
    attempts_path = destination / 'attempts.json'
    attempts = json.loads(attempts_path.read_text())
    attempt = next((a for a in attempts if a['seed'] == seed), None)
    if attempt is None or attempt['plan_hash'] != plan['hash']:
        raise ValueError('Candidate was not reserved under this regional plan')
    try:
        raw = sorted(Path(raw_frames).glob('*.png'), key=lambda path: int(path.stem))
    except ValueError:
        raise ValueError('Raw PNG filenames must be numeric frame indices') from None
    if len(raw) != 145:
        raise ValueError('Regional candidate requires exactly 145 raw PNG frames')
    indices = [int(path.stem) for path in raw]
    if indices != list(range(indices[0], indices[0] + 145)):
        raise ValueError('Raw candidate frame indices must be contiguous')
    first = np.asarray(Image.open(raw[0]).convert('RGB'), dtype='float32') / 255
    last = np.asarray(Image.open(raw[-1]).convert('RGB'), dtype='float32') / 255
    second = np.asarray(Image.open(raw[1]).convert('RGB'), dtype='float32') / 255
    before_last = np.asarray(Image.open(raw[-2]).convert('RGB'), dtype='float32') / 255
    if any(a.shape != (512, 512, 3) for a in (first, last, second, before_last)):
        raise ValueError('Candidate must be 512x512')
    closure = float(np.mean(np.abs(last - first)))
    velocity = float(np.mean(np.abs((second - first) - (last - before_last))))
    root = p.path.parent
    x, y, w, h = plan['transform']['crop']
    support = mask(root / p.data['regional']['support'], p.source_size)
    raw_support = resize_float(support[y:y+h, x:x+w], (512, 512), Image.Resampling.NEAREST) > 0
    crop = np.asarray(Image.open(destination / 'crop.png').convert('RGB'), dtype='float32') / 255
    raw_hashes = {}
    max_drift = 0.
    for path in raw:
        arr = np.asarray(Image.open(path).convert('RGB'), dtype='float32') / 255
        if arr.shape != first.shape:
            raise ValueError('Raw candidate frame dimensions changed')
        if np.any(~raw_support):
            max_drift = max(max_drift, float(np.mean(np.abs(arr[~raw_support] - crop[~raw_support]))))
        raw_hashes[path.name] = sha(path)
    qc = {'raw_closure_mean': closure, 'raw_boundary_velocity_mean': velocity,
          'raw_unchanged_region_drift_mean_max': max_drift,
          'limits': {'closure': 2/255, 'velocity': 3/255, 'drift': 8/255},
          'passed': closure <= 2/255 and velocity <= 3/255 and max_drift <= 8/255,
          'visual_review_required': True, 'raw_hashes': raw_hashes}
    output = destination / f'candidate-{seed}-output'
    output.mkdir(parents=True, exist_ok=True)
    atomic_json(output / 'raw-qc.json', qc)
    if not qc['passed']:
        attempt['state'] = 'failed_qc'
        atomic_json(attempts_path, attempts)
        return {'state': 'failed_qc', 'qc': qc, 'fallback': str(accepted_a)}
    renderer = Renderer(p)
    target_support = resize_float(support, p.output_size, Image.Resampling.NEAREST) > 0
    renderer.allowed |= target_support
    # Preserve the one recorded source->crop->output transform; resize the whole patch
    # into the output raster before applying its approved support.
    sx, sy = p.output_size[0] / p.source_size[0], p.output_size[1] / p.source_size[1]
    from scipy.ndimage import map_coordinates, distance_transform_edt
    oy, ox = np.mgrid[:p.output_size[1], :p.output_size[0]].astype('float32')
    cx = ((ox + .5) / sx - x) * 512 / w - .5
    cy = ((oy + .5) / sy - y) * 512 / h - .5
    feather = np.minimum(distance_transform_edt(target_support) / max(1, min(sx, sy) * 3), 1).astype('float32')
    frames_dir = output / 'frames'
    frames_dir.mkdir(exist_ok=True)
    hashes = {}
    locked_error = 0
    for j, path in enumerate(raw[:-1]):
        patch = linear(np.asarray(Image.open(path).convert('RGB'), dtype='float32') / 255)
        projected = np.stack([map_coordinates(patch[..., c], [cy, cx], order=1, mode='nearest') for c in range(3)], -1)
        base = np.asarray(Image.open(Path(accepted_a) / 'frames' / f'{j:06d}.png').convert('RGB'))
        if (base.shape[1], base.shape[0]) != p.output_size:
            raise ValueError('Fallback resolution differs')
        result = np.rint(srgb(projected * feather[..., None] + linear(base.astype('float32')/255) * (1-feather[..., None])) * 255).astype('uint8')
        result[~target_support] = base[~target_support]
        locked_error = max(locked_error, int(np.max(np.abs(result[~renderer.allowed].astype(int) - renderer.reference[~renderer.allowed].astype(int))))) if np.any(~renderer.allowed) else locked_error
        dest = frames_dir / f'{j:06d}.png'
        save_png(dest, result)
        hashes[str(j)] = sha(dest)
    qc.update(locked_pixel_max_error=locked_error, frame_count=144, terminal_endpoint_omitted=True)
    qc['passed'] = qc['passed'] and locked_error == 0
    atomic_json(output / 'qc.json', qc)
    if not qc['passed']:
        attempt['state'] = 'failed_qc'
        atomic_json(attempts_path, attempts)
        return {'state': 'failed_qc', 'fallback': str(accepted_a)}
    encode_video(output, 144, p.output_size)
    import shutil
    seam = output / 'seam-encode'
    (seam / 'frames').mkdir(parents=True, exist_ok=True)
    for k, j in enumerate(list(range(136, 144)) + list(range(8))):
        shutil.copyfile(frames_dir / f'{j:06d}.png', seam / 'frames' / f'{k:06d}.png')
    encode_video(seam, 16, p.output_size, 'seam.mp4')
    shutil.move(str(seam / 'seam.mp4'), str(output / 'seam.mp4'))
    shutil.rmtree(seam)
    review_package(output, p, renderer)
    manifest = {'schema': 'comfy-ltx-loop-output/1', 'state': 'awaiting_review',
                'project_hash': p.fingerprint, 'preview': False, 'seed': seed,
                'frame_hashes': hashes, 'output_size': p.output_size, 'fps': 24,
                'frame_count': 144, 'fallback': str(accepted_a), 'regional_plan_hash': plan['hash'],
                'artifacts': {name: sha(output / name) for name in
                              ('loop.mp4', 'seam.mp4', 'qc.json', 'raw-qc.json', 'review.html', 'support-overlay.png')}}
    atomic_json(output / 'manifest.json', manifest)
    attempt['state'] = 'awaiting_review'
    atomic_json(attempts_path, attempts)
    return manifest
