import copy
import json
import unittest

from comfy_ltx_loop.motion import new_plan, parse_landmarks, review_plan, require_review, canvas_tracks


class SemanticPointTests(unittest.TestCase):
    def test_roles_override_legacy_label_guesses(self):
        points = [dict(label='hair tip', x=.3, y=.4, body_part='hair',
                       motion_role='anchor', reason='Prompt keeps this strand still'),
                  dict(label='head', x=.5, y=.2, body_part='head',
                       motion_role='move', reason='Requested head sway')]
        plan = new_plan('abc', (600, 1000), 'head sway, stationary hair', ['auto'], points)
        tracks = canvas_tracks(plan)
        self.assertTrue(all(key == tracks[0][0] for key in tracks[0]))
        self.assertGreater(tracks[1][72]['x'], tracks[1][0]['x'])
        self.assertEqual(tracks[1][0], tracks[1][-1])

    def test_valid_partial_response_keeps_points_and_explains_omissions(self):
        feedback = []
        raw = json.dumps({'landmarks': [dict(label='left hair tip', x=300, y=400,
            body_part='hair', motion_role='move', reason='Requested sway'),
            dict(label='hidden shoulder', x=2000, y=500)], 'omissions': ['Right eye hidden by hair']})
        points = parse_landmarks(raw, ['hair tip', 'shoulder'], feedback=feedback)
        self.assertEqual(len(points), 1)
        self.assertEqual(points[0]['motion_role'], 'move')
        self.assertEqual(points[0]['x'], .3)
        self.assertTrue(any('shoulder' in note for note in feedback))
        self.assertTrue(any('Right eye hidden' in note for note in feedback))

    def test_invalid_semantics_and_boolean_coordinates_are_not_accepted(self):
        for point in [dict(label='tip', x=True, y=500),
                      dict(label='tip', x=300, y=500, motion_role='dance', body_part='hair', reason='sway')]:
            with self.subTest(point=point), self.assertRaises(ValueError):
                parse_landmarks(json.dumps({'landmarks': [point]}), ['auto'])

    def test_auto_has_no_missing_label_error_and_semantics_are_required_for_new_analysis(self):
        raw = '{"landmarks":[{"label":"hair tip","x":300,"y":400}]}'
        self.assertEqual(len(parse_landmarks(raw, ['auto'])), 1)
        with self.assertRaises(ValueError):
            parse_landmarks(raw, ['auto'], require_semantics=True)

    def test_semantic_edits_invalidate_review_but_analysis_context_can_change(self):
        point = dict(label='tip', x=.3, y=.4, motion_role='move', body_part='hair', reason='sway')
        plan = review_plan(new_plan('abc', (600,1000), 'hair', ['auto'], [point],
                                   analysis={'preparation':'local Qwen3.5','model_path':'snapshot'}))
        for key, value in [('body_part','face'), ('reason','updated'), ('motion_role','anchor')]:
            edited = copy.deepcopy(plan)
            edited['landmarks'][0][key] = value
            with self.assertRaises(ValueError):
                require_review(edited, 'abc', (600,1000), 'hair', 6,24,.01,720)
        plan['analysis']['model_path'] = 'other'
        require_review(plan, 'abc', (600,1000), 'hair', 6,24,.01,720)

    def test_anchor_cannot_carry_a_moving_path(self):
        from comfy_ltx_loop.motion import validate_plan
        plan = new_plan('abc',(600,1000),'hair',['auto'],
            [dict(label='eye',x=.3,y=.4,motion_role='anchor',body_part='face',reason='still')])
        plan['landmarks'][0]['path'][3]['x'] += .01
        with self.assertRaises(ValueError):
            validate_plan(plan)

    def test_legacy_plan_still_loads_and_reviews(self):
        plan = new_plan('abc',(600,1000),'hair',['tip'],
                        [dict(label='hair root',x=.3,y=.4),dict(label='tip',x=.5,y=.4)])
        reopened = review_plan(json.loads(json.dumps(plan)))
        require_review(reopened,'abc',(600,1000),'hair',6,24,.01,720)
        self.assertEqual(reopened['landmarks'][0]['path'][8]['x'], .3)
        self.assertGreater(reopened['landmarks'][1]['path'][8]['x'], .5)
