import copy
import json
import unittest

from ambient_loop.motion import (new_plan, parse_landmarks, validate_plan,
                                 review_plan, require_review, canvas_transform,
                                 canvas_tracks, plan_fingerprint)


class MotionTests(unittest.TestCase):
    def plan(self, size=(600, 1000)):
        return new_plan('abc', size, 'gentle hair motion', ['hair tip'],
                        [{'label': 'hair tip', 'x': .5, 'y': .5}], 6, 24, .01, 720)

    def test_portrait_and_landscape_alignment_survives_reopen(self):
        for size in [(600, 1000), (1600, 900)]:
            p = json.loads(json.dumps(self.plan(size)))
            p = review_plan(p)
            transform = canvas_transform(size, 720)
            tracks = canvas_tracks(p)
            self.assertEqual(len(tracks[0]), 145)
            self.assertEqual(tracks[0][0], tracks[0][-1])
            point = tracks[0][0]
            x, y, w, h = transform['content']
            self.assertAlmostEqual((point['x']-x)/(w-1), .5)
            self.assertAlmostEqual((point['y']-y)/(h-1), .5)
            require_review(p, 'abc', size, p['prompt'], 6, 24, .01, 720)

    def test_canvas_and_half_resolution_guide_are_aligned(self):
        cases = [
            ((1312, 736), 720, [1344, 768], [30, 24, 1283, 720]),
            ((736, 1312), 720, [768, 1344], [24, 30, 720, 1283]),
            ((1600, 900), 720, [1280, 768], [0, 24, 1280, 720]),
            ((1000, 1000), 720, [768, 768], [24, 24, 720, 720]),
            ((1280, 704), 704, [1280, 704], [0, 0, 1280, 704]),
        ]
        for size, short_side, canvas, content in cases:
            with self.subTest(size=size, short_side=short_side):
                transform = canvas_transform(size, short_side)
                self.assertEqual(transform['canvas'], canvas)
                self.assertEqual(transform['content'], content)
                self.assertTrue(all(dimension % 64 == 0 for dimension in canvas))
                self.assertTrue(all((dimension // 2) % 32 == 0 for dimension in canvas))

    def test_padded_canvas_keeps_normalized_tracks_and_returning_path(self):
        plan = self.plan((1312, 736))
        transform = plan['transform']
        self.assertEqual(plan['landmarks'][0]['x'], .5)
        self.assertEqual(plan['landmarks'][0]['y'], .5)
        tracks = canvas_tracks(plan)[0]
        self.assertEqual(tracks[0], tracks[-1])
        self.assertAlmostEqual(tracks[0]['x'], transform['content'][0] + (transform['content'][2]-1)/2)
        self.assertAlmostEqual(tracks[0]['y'], transform['content'][1] + (transform['content'][3]-1)/2)
        self.assertGreater(tracks[72]['x'], tracks[0]['x'])

    def test_old_reviewed_canvas_requires_new_preparation(self):
        plan = self.plan((1312, 736))
        plan['transform'] = {'source': [1312, 736], 'canvas': [1312, 736],
                             'content': [14, 8, 1283, 720]}
        plan['review'] = {'state': 'reviewed', 'fingerprint': plan_fingerprint(plan)}
        with self.assertRaisesRegex(ValueError, 'prepare and review again'):
            require_review(plan, 'abc', (1312, 736), plan['prompt'], 6, 24, .01, 720)

    def test_edits_and_motion_settings_invalidate_review(self):
        p = review_plan(self.plan())
        for key, value in [('prompt', 'new'), ('strength', .02), ('short_side', 800)]:
            edited = copy.deepcopy(p)
            edited[key] = value
            with self.assertRaisesRegex(ValueError, 'review'):
                require_review(edited, 'abc', (600, 1000), edited['prompt'], 6, 24,
                               edited['strength'], edited['short_side'])
        p['landmarks'][0]['path'][1]['x'] += .001
        self.assertNotEqual(p['review']['fingerprint'], plan_fingerprint(p))

    def test_invalid_suggestions_and_paths_are_actionable(self):
        for raw in ['nonsense', '{"landmarks":[]}',
                    '{"landmarks":[{"label":"hair tip","x":1001,"y":500}]}']:
            with self.assertRaises(ValueError):
                parse_landmarks(raw, ['hair tip'])
        p = self.plan()
        p['landmarks'][0]['path'][1]['x'] = 2
        with self.assertRaisesRegex(ValueError, 'bounds'):
            validate_plan(p)

    def test_grounding_uses_explicit_thousand_coordinate_scale(self):
        points = parse_landmarks('{"landmarks":[{"label":"hair tip","x":1,"y":500}]}', ['hair tip'])
        self.assertEqual(points[0]['x'], .001)

    def test_timing_must_fit_ltx_and_playback_exactly(self):
        with self.assertRaises(ValueError):
            new_plan('abc', (600,1000), 'motion', ['tip'], [], 6.1,24,.01,720)


if __name__ == '__main__':
    unittest.main()
