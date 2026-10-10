import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

from comfy_ltx_loop.project import Project
from comfy_ltx_loop.renderer import Renderer


class ResolutionIntegrationTests(unittest.TestCase):
    def test_real_rasters_all_six_pairs_landscape_and_portrait(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for portrait in (False, True):
                size = (18, 32) if portrait else (32, 18)
                source = np.zeros((*size[::-1], 3), 'uint8')
                source[..., 1] = 90
                source[::2, ::2] = (230, 20, 180)
                Image.fromarray(source).save(root / 'source.png')
                support = np.zeros(size[::-1], 'uint8')
                support[4:-4, 4:-4] = 255
                Image.fromarray(support).save(root / 'support.png')
                Image.fromarray(np.zeros_like(support)).save(root / 'guard.png')
                for working in ('720p', '1080p'):
                    for output in ('1080p', '1440p', '4K'):
                        with self.subTest(portrait=portrait, working=working, output=output):
                            data = {'schema': 'comfy-ltx-loop/1', 'source': 'source.png',
                                    'guard': 'guard.png', 'working_mode': working,
                                    'output_resolution': output, 'regions': [
                                        {'id': 'light', 'kind': 'shimmer', 'depth': 0,
                                         'mask': 'support.png', 'support': 'support.png'}]}
                            path = root / 'project.json'
                            path.write_text(json.dumps(data))
                            p = Project.load(path)
                            renderer = Renderer(p)
                            arr = renderer.frame(17)
                            self.assertEqual((arr.shape[1], arr.shape[0]), p.output_size)
                            np.testing.assert_array_equal(arr[~renderer.allowed], renderer.reference[~renderer.allowed])
                            if working == output:
                                self.assertEqual(renderer.timings['enlargement_seconds'], 0)
                            else:
                                self.assertGreater(renderer.timings['enlargement_seconds'], 0)
                            del renderer, arr
