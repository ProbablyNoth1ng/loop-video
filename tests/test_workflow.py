import copy
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

import numpy as np
from PIL import Image

from ambient_loop.project import Project, dimensions, approve
from ambient_loop.renderer import Renderer, displacement, rain_state
from ambient_loop.jobs import render


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        y, x = np.mgrid[:36, :64]
        source = np.stack([x * 4, y * 7, x * 2 + y * 2], -1).astype('uint8')
        Image.fromarray(source).save(self.root / 'source.png')
        support = np.zeros((36, 64), 'uint8')
        support[8:28, 12:52] = 255
        for name, data in [('support', support), ('guard', np.zeros_like(support)),
                           ('weight', support)]:
            Image.fromarray(data).save(self.root / (name + '.png'))
        self.data = {'schema': 'ambient-loop/1', 'source': 'source.png',
                     'guard': 'guard.png', 'working_mode': '1080p',
                     'output_resolution': '1440p', 'duration': 4, 'seed': 42,
                     'preset': 'sunset-field', 'regions': [
                         {'id': 'light', 'kind': 'shimmer', 'mask': 'support.png',
                          'support': 'support.png', 'depth': 0, 'strength': .04}]}
        self.path = self.root / 'project.json'
        self.save()

    def save(self):
        self.path.write_text(json.dumps(self.data))
        return Project.load(self.path)

    def test_all_resolution_pairs_and_portrait(self):
        for working in ['720p', '1080p']:
            for output, height in [('1080p', 1080), ('1440p', 1440), ('4K', 2160)]:
                p = copy.deepcopy(self.data)
                p.update(working_mode=working, output_resolution=output)
                self.data = p
                project = self.save()
                self.assertEqual(project.output_size, (height * 16 // 9, height))
                self.assertEqual(project.upscale, working != output)
                self.assertEqual(dimensions((36, 64), height), (height, height * 16 // 9))

    def test_duration_and_fractional_frames(self):
        for duration in [4, 6, 30, 4.125]:
            self.data['duration'] = duration
            self.assertEqual(self.save().frames, round(duration * 24))
        for duration in [3, 31, 4.01, float('nan')]:
            self.data['duration'] = duration
            with self.assertRaises(ValueError):
                self.save()

    def test_approval_binds_assets_and_motion(self):
        approve(self.path, 'masks', 'tester')
        approve(self.path, 'motion', 'tester')
        Project.load(self.path).require_approvals()
        data = json.loads(self.path.read_text())
        data['seed'] = 43
        self.path.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            Project.load(self.path).require_approvals()

    def test_periodic_float_displacement_and_fixed_roots(self):
        weight = np.linspace(0, 1, 64, dtype='float32').reshape(8, 8)
        first = displacement(weight, 2, 0, 6)
        np.testing.assert_allclose(first, displacement(weight, 2, 6, 6), atol=1e-6)
        self.assertEqual(first.dtype, np.float32)
        self.assertEqual(float(first[0, 0, 0]), 0)
        eps = 1e-3
        np.testing.assert_allclose(
            (displacement(weight, 2, eps, 6) - first) / eps,
            (displacement(weight, 2, 6 + eps, 6) - first) / eps, atol=1e-4)

    def test_downward_rain_closes_with_constant_population(self):
        a = rain_state(42, 40, 64, 36, 0, 6)
        b = rain_state(42, 40, 64, 36, 6, 6)
        np.testing.assert_allclose(a, b, atol=1e-5)
        c = rain_state(42, 40, 64, 36, .001, 6)
        self.assertTrue(np.all((c[:, 1] - a[:, 1]) % 36 > 0))

    def test_restores_locked_pixels_and_closes(self):
        renderer = Renderer(self.save(), working_size=(64, 36), output_size=(128, 72))
        a = renderer.frame(0)
        np.testing.assert_array_equal(a[~renderer.allowed], renderer.reference[~renderer.allowed])
        np.testing.assert_array_equal(a, renderer.frame(renderer.project.frames))
        self.assertFalse(np.array_equal(a, renderer.frame(1)))

    def test_missing_asset_and_guard_overlap_rejected(self):
        self.data['regions'][0]['mask'] = 'absent.png'
        with self.assertRaises(ValueError):
            self.save()
        self.data['regions'][0]['mask'] = 'support.png'
        Image.open(self.root / 'support.png').save(self.root / 'guard.png')
        with self.assertRaisesRegex(ValueError, 'immutable guards'):
            self.save()

    def test_repeated_oom_stops_and_marks_failure(self):
        approve(self.path, 'masks', 'tester')
        approve(self.path, 'motion', 'tester')
        p = Project.load(self.path)
        out = self.root / 'oom'
        with patch.object(Renderer, 'frame', side_effect=MemoryError('out of memory')) as frame:
            with self.assertRaisesRegex(RuntimeError, 'three failures'):
                render(p, out, encode=False, sizes=((64, 36), (64, 36)))
            self.assertEqual(frame.call_count, 3)
        self.assertEqual(json.loads((out / 'manifest.json').read_text())['state'], 'failed')
        self.assertFalse((out / '.render.lock').exists())

    def test_changed_mask_stales_approval(self):
        approve(self.path, 'masks', 'tester')
        approve(self.path, 'motion', 'tester')
        with Image.open(self.root / 'support.png') as image:
            arr = np.asarray(image).copy()
        arr[8, 12] = 254
        Image.fromarray(arr).save(self.root / 'alpha.png')
        self.data['regions'][0]['mask'] = 'alpha.png'
        self.save()
        approve(self.path, 'masks', 'tester')
        approve(self.path, 'motion', 'tester')
        arr[8, 12] = 253
        Image.fromarray(arr).save(self.root / 'alpha.png')
        with self.assertRaisesRegex(ValueError, 'stale'):
            Project.load(self.path).require_approvals()

    def test_root_weight_and_disocclusion_rejected(self):
        self.data['regions'][0].update(kind='foliage', root_weight='weight.png', roots='support.png')
        with self.assertRaisesRegex(ValueError, 'Root weights'):
            self.save()
        self.data['regions'][0]['expose_background'] = True
        with self.assertRaisesRegex(ValueError, 'disocclusion'):
            self.save()

    def test_resume_checks_hashes_and_acceptance_is_not_automatic(self):
        approve(self.path, 'masks', 'tester')
        approve(self.path, 'motion', 'tester')
        p = Project.load(self.path)
        out = self.root / 'output'
        result = render(p, out, encode=False, sizes=((64, 36), (64, 36)))
        self.assertEqual(result['state'], 'awaiting_review')
        self.assertEqual(len(list((out / 'frames').glob('*.png'))), 96)
        (out / 'frames' / '000001.png').write_bytes(b'partial')
        render(p, out, encode=False, sizes=((64, 36), (64, 36)))
        Image.open(out / 'frames' / '000001.png').verify()


if __name__ == '__main__':
    unittest.main()
