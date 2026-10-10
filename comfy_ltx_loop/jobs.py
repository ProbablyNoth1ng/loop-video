import html
import os
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from PIL import Image

from .project import atomic_json, sha, digest
from .renderer import Renderer


def save_png(path, array):
    temporary = path.with_suffix('.tmp')
    Image.fromarray(array).save(temporary, format='PNG')
    with temporary.open('rb+') as f:
        os.fsync(f.fileno())
    os.replace(temporary, path)


def encode_video(out, frames, size, name='loop.mp4', start=0):
    temporary = out / (name + '.tmp.mp4')
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                    '-framerate', '24', '-start_number', str(start),
                    '-i', str(out / 'frames' / '%06d.png'), '-frames:v', str(frames),
                    '-an', '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p',
                    '-r', '24', '-fps_mode', 'cfr', '-movflags', '+faststart', str(temporary)], check=True)
    probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-show_streams',
                            '-of', 'json', str(temporary)], capture_output=True, text=True, check=True)
    import json
    streams = json.loads(probe.stdout)['streams']
    if len(streams) != 1:
        raise ValueError('Silent video must contain exactly one video stream')
    s = streams[0]
    if ((s['width'], s['height']) != size or int(s['nb_read_frames']) != frames or
            s['r_frame_rate'] != '24/1' or s['pix_fmt'] != 'yuv420p'):
        raise ValueError('Encoded dimensions, frames, FPS or pixel format failed QC')
    os.replace(temporary, out / name)


def review_package(out, project, renderer):
    overlay = renderer.reference.copy()
    overlay[renderer.allowed] = (overlay[renderer.allowed] * .5 + np.array([0, 128, 0])).astype('uint8')
    save_png(out / 'support-overlay.png', overlay)
    text = f'''<!doctype html><html lang="en"><meta charset="utf-8">
<meta name="viewport" content="width=device-width"><title>Comfy LTX loop review</title>
<style>body{{font:16px system-ui;margin:24px;background:#fafafa;color:#222}}
video,img{{max-width:100%;max-height:70vh}}section{{margin:24px 0}}</style>
<h1>{html.escape(project.path.stem)}</h1><p>Awaiting visual acceptance</p>
<section><h2>Repeated playback</h2><video src="loop.mp4" controls loop muted></video></section>
<section><h2>Slowed playback</h2><video id="slow" src="loop.mp4" controls loop muted></video></section>
<section><h2>Boundary playback</h2><video src="seam.mp4" controls loop muted></video></section>
<section><h2>Approved support</h2><img src="support-overlay.png"></section>
<p><a href="qc.json">QC</a> | <a href="manifest.json">Manifest</a></p>
<script>document.getElementById('slow').playbackRate=.25;</script></html>'''
    (out / 'review.html').write_text(text, encoding='utf-8')


def render(project, out, encode=True, chunk_size=4, sizes=None, preview=False):
    import json
    if not preview:
        project.require_approvals()
    if not 1 <= chunk_size <= 32:
        raise ValueError('Chunk size must be between 1 and 32')
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    # Exclusive writer lock protects frame/checkpoint atomicity across processes.
    lock = out / '.render.lock'
    try:
        handle = lock.open('x')
    except FileExistsError:
        raise ValueError('Render lock exists; verify the previous process stopped before removing it')
    try:
        handle.write(str(os.getpid()))
        handle.close()
        return _render(project, out, encode, chunk_size, sizes, preview)
    finally:
        lock.unlink(missing_ok=True)


def _render(project, out, encode, chunk_size, sizes, preview):
    import json
    started = time.perf_counter()
    renderer = Renderer(project, *(sizes or (None, None)))
    identity = digest({'project': project.fingerprint, 'working': renderer.working_size,
                       'output': renderer.output_size, 'preview': preview})
    checkpoint_path = out / 'checkpoint.json'
    cp = json.loads(checkpoint_path.read_text()) if checkpoint_path.exists() else {'hash': identity, 'frames': {}}
    if cp['hash'] != identity:
        raise ValueError('Output belongs to different assets/settings; use a new output directory')
    frames = out / 'frames'
    frames.mkdir(exist_ok=True)
    manifest = {'schema': 'comfy-ltx-loop-output/1', 'project_hash': project.fingerprint,
                'render_hash': identity, 'state': 'rendered', 'preview': preview,
                'working_size': renderer.working_size, 'output_size': renderer.output_size,
                'fps': 24, 'frame_count': project.frames, 'duration': project.data['duration'],
                'enlargement': renderer.working_size != renderer.output_size,
                'approvals': project.data.get('approvals', {}), 'assets': project.assets,
                'timings': {}, 'encoding': {'codec': 'h264', 'crf': 18, 'pixel_format': 'yuv420p', 'audio': False}}
    atomic_json(out / 'manifest.json', manifest)
    render_start = time.perf_counter()
    failures = 0
    index = 0
    try:
        while index < project.frames:
            end = min(index + chunk_size, project.frames)
            try:
                for j in range(index, end):
                    path = frames / f'{j:06d}.png'
                    existing = cp['frames'].get(str(j))
                    if path.exists() and existing and sha(path) == existing:
                        index = j + 1
                        continue
                    frame = renderer.frame(j)
                    save_png(path, frame)
                    cp['frames'][str(j)] = sha(path)
                    atomic_json(checkpoint_path, cp)
                    index = j + 1
                failures = 0
            except MemoryError:
                failures += 1
                chunk_size = max(1, chunk_size // 2)
                if failures >= 3:
                    raise RuntimeError('Repeated OOM; stopped after three failures')
        manifest['timings']['render_resize_restore_seconds'] = time.perf_counter() - render_start
        manifest['timings'].update(renderer.timings)
        qc_start = time.perf_counter()
        first = renderer.frame(0)
        endpoint = renderer.frame(project.frames)
        max_locked = 0
        differences = []
        previous = None
        for j in range(project.frames):
            with Image.open(frames / f'{j:06d}.png') as im:
                if im.size != renderer.output_size:
                    raise ValueError('Frame dimensions changed')
                arr = np.asarray(im.convert('RGB'))
            if np.any(~renderer.allowed):
                max_locked = max(max_locked, int(np.abs(arr[~renderer.allowed].astype(int) -
                                                       renderer.reference[~renderer.allowed].astype(int)).max()))
            if previous is not None:
                differences.append(float(np.mean(np.abs(arr.astype(float) - previous))))
            previous = arr.astype(float)
        seam_difference = float(np.mean(np.abs(first.astype(float) - previous)))
        closure = int(np.max(np.abs(first.astype(int) - endpoint.astype(int))))
        # Compare the seam step with ordinary temporal steps, not endpoint equality alone.
        seam_limit = max(.5, 4 * float(np.percentile(differences, 95)))
        qc = {'passed': max_locked == 0 and closure == 0 and seam_difference <= seam_limit,
              'locked_pixel_max_error': max_locked, 'conceptual_endpoint_max_error': closure,
              'seam_step_mean': seam_difference, 'seam_step_limit': seam_limit,
              'frame_count': project.frames, 'terminal_endpoint_omitted': True,
              'visual_review_required': True,
              'limitations': ['Occlusion, naturalness and feathered boundaries require human review']}
        atomic_json(out / 'qc.json', qc)
        manifest['timings']['qc_seconds'] = time.perf_counter() - qc_start
        if not qc['passed']:
            manifest['state'] = 'failed_qc'
        elif encode:
            encode_start = time.perf_counter()
            encode_video(out, project.frames, renderer.output_size)
            # Eight frames on either side of the seam, without introducing a hold.
            seam_dir = out / 'seam-encode'
            (seam_dir / 'frames').mkdir(parents=True, exist_ok=True)
            for k, j in enumerate(list(range(project.frames - 8, project.frames)) + list(range(8))):
                shutil.copyfile(frames / f'{j:06d}.png', seam_dir / 'frames' / f'{k:06d}.png')
            encode_video(seam_dir, 16, renderer.output_size, 'seam.mp4')
            os.replace(seam_dir / 'seam.mp4', out / 'seam.mp4')
            # This directory is created exclusively by this job, beneath its verified output root.
            shutil.rmtree(seam_dir)
            manifest['timings']['encoding_seconds'] = time.perf_counter() - encode_start
            manifest['state'] = 'awaiting_review'
        else:
            manifest['state'] = 'awaiting_review'
        review_package(out, project, renderer)
        manifest['frame_hashes'] = cp['frames']
        manifest['artifacts'] = {p.name: sha(p) for p in out.iterdir()
                                 if p.is_file() and p.name in ('loop.mp4', 'seam.mp4', 'review.html', 'support-overlay.png', 'qc.json')}
        manifest['timings']['total_seconds'] = time.perf_counter() - started
        manifest['storage_bytes'] = sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
        atomic_json(out / 'manifest.json', manifest)
        return manifest
    except Exception as error:
        manifest['state'] = 'failed'
        manifest['error'] = str(error)
        atomic_json(out / 'manifest.json', manifest)
        raise


def accept(out, reviewer):
    import json
    out = Path(out)
    p = out / 'manifest.json'
    manifest = json.loads(p.read_text())
    if manifest['state'] != 'awaiting_review' or manifest['preview'] or not reviewer.strip():
        raise ValueError('Only a non-preview output awaiting review can be accepted by a named reviewer')
    if not (out / 'loop.mp4').is_file():
        raise ValueError('Encoded production output required for acceptance')
    for name, expected in manifest['artifacts'].items():
        if sha(out / name) != expected:
            raise ValueError('Review artifact changed')
    for j, expected in manifest['frame_hashes'].items():
        if sha(out / 'frames' / f'{int(j):06d}.png') != expected:
            raise ValueError('Frame changed after review')
    manifest['state'] = 'accepted'
    manifest['visual_review'] = {'reviewer': reviewer, 'at': datetime.now(timezone.utc).isoformat(),
                                  'hash': digest(manifest['artifacts'])}
    atomic_json(p, manifest)
