from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter

from .project import atomic_json


def create_examples(destination):
    """Synthetic fixtures, deliberately not represented as approved artwork."""
    destination = Path(destination)
    for preset in ('calm-wind', 'rainy-window', 'sunset-field'):
        root = destination / preset
        root.mkdir(parents=True, exist_ok=True)
        width, height = 640, 360
        y, x = np.mgrid[:height, :width]
        rgb = np.stack([70 + y * .25, 110 + y * .2, 170 - y * .18], -1).astype('uint8')
        image = Image.fromarray(rgb)
        draw = ImageDraw.Draw(image)
        draw.ellipse((430, 35, 500, 105), fill=(255, 228, 140))
        draw.rectangle((0, 280, width, height), fill=(40, 102, 62))
        for i in range(15):
            px = 20 + i * 39
            draw.line((px, 330, px + 20, 225), fill=(24, 63, 36), width=2)
        if preset == 'rainy-window':
            for px in (8, 315, 627):
                draw.rectangle((px, 0, px + 5, 359), fill=(32, 32, 40))
        image.save(root / 'source.png')
        support = np.zeros((height, width), 'uint8')
        support[120:265, 35:605] = 255
        if preset == 'sunset-field':
            support[:] = 0
            support[25:110, 415:515] = 255
        if preset == 'rainy-window':
            for px in (8, 315, 627):
                support[:, px:px+6] = 0
        alpha = gaussian_filter(support.astype('float32'), 3)
        alpha[support == 0] = 0
        weight = np.clip((265 - y) / 145, 0, 1) * alpha
        roots = np.zeros_like(support)
        roots[260:265, 35:605] = 255
        weight[roots > 0] = 0
        guard = np.zeros_like(support)
        guard[280:] = 255
        if preset == 'rainy-window':
            for px in (8, 315, 627):
                guard[:, px:px+6] = 255
        for name, arr in [('support', support), ('mask', alpha), ('guard', guard),
                          ('weight', weight), ('roots', roots)]:
            Image.fromarray(arr.astype('uint8')).save(root / f'{name}.png')
        kind = {'calm-wind': 'foliage', 'rainy-window': 'rain', 'sunset-field': 'shimmer'}[preset]
        region = {'id': 'ambient', 'kind': kind, 'mask': 'mask.png',
                  'support': 'support.png', 'depth': 0}
        if kind == 'foliage':
            region.update(root_weight='weight.png', roots='roots.png', amplitude=2)
        elif kind == 'rain':
            region.update(particles=80, strength=.15)
        else:
            region['strength'] = .04
        atomic_json(root / 'project.json', {
            'schema': 'ambient-loop/1', 'source': 'source.png', 'guard': 'guard.png',
            'working_mode': '1080p', 'output_resolution': '1440p', 'duration': 6,
            'fps': 24, 'preset': preset, 'seed': 42, 'regions': [region]})
