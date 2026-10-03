import copy
import json
import shutil
import time
from pathlib import Path

from .jobs import render
from .project import Project, atomic_json, dimensions


def benchmark(project_path, destination, transfer_to):
    project = Project.load(project_path)
    project.require_approvals()
    destination = Path(destination).resolve()
    transfer_to = Path(transfer_to).resolve()
    if destination == transfer_to or destination.is_relative_to(transfer_to) or transfer_to.is_relative_to(destination):
        raise ValueError('Transfer target must be separate from benchmark output')
    reports = []
    # These are non-production comparison renders; original approvals do not authorize new modes.
    for mode in ('720p', '1080p', 'direct-1440p'):
        p = copy.deepcopy(project)
        working = dimensions(p.source_size, 1440 if mode == 'direct-1440p' else (720 if mode == '720p' else 1080))
        output_size = dimensions(p.source_size, 1440) if mode == 'direct-1440p' else p.output_size
        out = destination / mode
        manifest = render(p, out, sizes=(working, output_size), preview=True)
        start = time.perf_counter()
        transferred = 0
        target = transfer_to / mode
        target.mkdir(parents=True, exist_ok=True)
        for name in ('loop.mp4', 'review.html', 'seam.mp4', 'qc.json', 'manifest.json', 'support-overlay.png'):
            source = out / name
            if source.exists():
                shutil.copy2(source, target / name)
                transferred += source.stat().st_size
        elapsed = time.perf_counter() - start
        # Peak RSS is process-wide on Unix; explicitly label this rather than claiming per-stage peaks.
        try:
            import resource
            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        except ImportError:
            peak = None
        reports.append({'mode': mode, 'output_size': output_size,
                        'timings': manifest['timings'], 'storage_bytes': manifest['storage_bytes'],
                        'transfer_seconds': elapsed, 'transfer_bytes': transferred,
                        'process_high_water_rss_bytes': peak,
                        'memory_note': 'Cumulative process high-water mark; unavailable on Windows',
                        'renderer_device': 'CPU', 'gpu_render_bytes': 0,
                        'state': manifest['state'], 'quality_approved': False})
    result = {'reports': reports, 'default_working_mode': '1080p',
              'promotion_requires': 'Measured savings and human pilot quality approval',
              'transfer_kind': 'Measured file copy to supplied target; network only if target is a network mount'}
    atomic_json(destination / 'benchmark.json', result)
    return result
