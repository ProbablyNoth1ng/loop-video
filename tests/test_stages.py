import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ambient_loop.staged_comfy import AmbientMotionEditor, AmbientSavedCandidate


class StageTests(unittest.TestCase):
    def test_new_qwen_choice_keeps_widget_order_and_reuses_review_across_analysis_settings(self):
        import numpy as np
        from ambient_loop.motion import review_plan
        image = np.zeros((1,100,80,3),dtype=np.float32)
        inputs = AmbientMotionEditor.INPUT_TYPES()['required']
        self.assertEqual(list(inputs)[8:12], ['vision_model','preparation','plan_json','stage'])
        self.assertIn('local Qwen3.5', inputs['preparation'][0])
        self.assertEqual(inputs['requested_parts'][1]['default'], 'auto')
        points = [dict(label='tip',x=.3,y=.4,body_part='hair',motion_role='move',reason='sway')]
        with patch('ambient_loop.staged_comfy.canvas_image',return_value=image), \
             patch('ambient_loop.staged_comfy.analyze',return_value=points):
            prepared = AmbientMotionEditor().execute(image,'hair','auto',6,24,.01,720,
                         42,'models/Qwen3.5-9B','local Qwen3.5','{}','prepare')['result'][2]
            self.assertEqual(prepared['analysis'], {'preparation':'local Qwen3.5','model_path':'models/Qwen3.5-9B'})
            reviewed = json.dumps(review_plan(prepared))
            for model, mode in [('other','local Qwen3.5'),('models/Qwen3.5-9B','manual')]:
                rendered = AmbientMotionEditor().execute(image,'new prompt','head',3,24,.02,800,
                     43,model,mode,reviewed,'render')['result'][2]
                self.assertEqual(rendered['analysis'], {'preparation':mode,'model_path':model})
                self.assertEqual(rendered['requested'], ['head'])
                self.assertEqual(rendered['prompt'], 'new prompt')
                self.assertEqual(rendered['landmarks'], prepared['landmarks'])

    def test_qwen35_partial_feedback_and_load_failure_leave_manual_editor_available(self):
        import numpy as np
        image = np.zeros((1,100,80,3),dtype=np.float32)
        def partial(source,prompt,requested,model,feedback=None):
            feedback.append('Omitted: shoulder hidden')
            return [dict(label='eye',x=.4,y=.3,body_part='face',motion_role='anchor',reason='stationary face')]
        with patch('ambient_loop.staged_comfy.canvas_image',return_value=image):
            for analyzer in [partial, RuntimeError('loading failed')]:
                with patch('ambient_loop.staged_comfy.analyze',side_effect=analyzer):
                    plan = AmbientMotionEditor().execute(image,'hair','auto',6,24,.01,720,
                        42,'models/Qwen3.5-9B','local Qwen3.5','{}','prepare')['result'][2]
                self.assertEqual(plan['review']['state'],'pending')
                self.assertTrue(plan['feedback'])
                self.assertEqual(len(plan['landmarks']), 0 if isinstance(analyzer,Exception) else 1)

    def test_saved_candidates_are_complete_and_newest_first_with_portable_paths(self):
        from ambient_loop.candidates import list_candidates
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name, state, stamp in [('candidate-a-new','awaiting_visual_review',300),
                                       ('candidate-z-old','awaiting_visual_review',100),
                                       ('candidate-pending','encoding',400)]:
                directory = root/name
                directory.mkdir()
                path = directory/'record.json'
                path.write_text(json.dumps({'schema':'ambient-render-handle/1','kind':'candidate','state':state}))
                (directory/'loop.mp4').write_bytes(b'video')
                (directory/'seam.mp4').write_bytes(b'video')
                os.utime(path, ns=(stamp,stamp))
            corrupt = root/'candidate-corrupt'
            corrupt.mkdir()
            (corrupt/'record.json').write_text('{')
            missing = root/'candidate-missing'
            missing.mkdir()
            (missing/'record.json').write_text(json.dumps({'schema':'ambient-render-handle/1',
                'kind':'candidate','state':'awaiting_visual_review'}))
            expected = ['candidate-a-new/record.json','candidate-z-old/record.json']
            self.assertEqual(list_candidates(root),expected)
            with patch('ambient_loop.staged_comfy.output_root',return_value=root):
                self.assertEqual(AmbientSavedCandidate.INPUT_TYPES()['required']['candidate'][0],expected)

    def test_interfaces_have_no_upstream_generation_for_finishing(self):
        with tempfile.TemporaryDirectory() as tmp, patch('ambient_loop.staged_comfy.output_root',return_value=Path(tmp)):
            inputs = AmbientSavedCandidate.INPUT_TYPES()['required']
        self.assertEqual(set(inputs),{'candidate'})
        self.assertEqual(AmbientMotionEditor.RETURN_TYPES[2],'MOTION_PLAN')

    def test_prepare_failure_keeps_manual_plan(self):
        import numpy as np
        image = np.zeros((1,100,80,3),dtype=np.float32)
        with patch('ambient_loop.staged_comfy.image_array',return_value=image[0].astype(np.uint8)), \
             patch('ambient_loop.staged_comfy.canvas_image',return_value=image), \
             patch('ambient_loop.staged_comfy.analyze',side_effect=ValueError('Missing hair tip')):
            result = AmbientMotionEditor().execute(image,'hair','hair tip',6,24,.01,720,
                         42,'Qwen3-VL-8B-Instruct','local Qwen','{}','prepare')
        plan = result['result'][2]
        self.assertEqual(plan['landmarks'],[])
        self.assertIn('Missing hair tip',plan['feedback'][0])
        self.assertEqual(plan['review']['state'],'pending')
        self.assertEqual(result['ui']['motion_plan'][0], plan)
        self.assertTrue(result['ui']['bg_image'][0])

    def test_manual_prepare_exposes_the_same_plan_in_ui_and_result(self):
        import numpy as np
        image = np.zeros((1,100,80,3),dtype=np.float32)
        with patch('ambient_loop.staged_comfy.image_array',return_value=image[0].astype(np.uint8)), \
             patch('ambient_loop.staged_comfy.canvas_image',return_value=image):
            result = AmbientMotionEditor().execute(image,'hair','hair tip',3,24,.01,720,
                         42,'Qwen3-VL-8B-Instruct','manual','{}','prepare')
        self.assertEqual(result['ui']['motion_plan'][0], result['result'][2])
        self.assertEqual(result['result'][2]['frames'],73)
        self.assertEqual(result['result'][2]['landmarks'],[])
        self.assertTrue(result['ui']['bg_image'][0])

    def test_manual_accepted_points_render_on_new_image(self):
        import numpy as np
        from ambient_loop.motion import new_plan, review_plan
        old = review_plan(new_plan('old', (80, 100), 'old prompt', ['tip'],
                    [{'label':'tip','x':.25,'y':.4}], 6, 24, .01, 720))
        image = np.zeros((1,60,90,3), dtype=np.float32)
        with patch('ambient_loop.staged_comfy.canvas_image', return_value=image):
            rendered = AmbientMotionEditor().execute(image, 'new prompt', 'head', 3, 24,
                .02, 800, 99, 'unused', 'manual', json.dumps(old), 'render')['result'][2]
        self.assertEqual(rendered['landmarks'], old['landmarks'])
        self.assertEqual(rendered['source_size'], [90,60])
        self.assertEqual(rendered['analysis']['preparation'], 'manual')
        self.assertEqual(rendered['review']['state'], 'reviewed')

    def test_render_never_analyzes_and_stale_review_fails(self):
        import numpy as np
        image = np.zeros((1,100,80,3),dtype=np.float32)
        with patch('ambient_loop.staged_comfy.image_array',return_value=image[0].astype(np.uint8)), \
             patch('ambient_loop.staged_comfy.analyze') as analysis:
            with self.assertRaises(ValueError):
                AmbientMotionEditor().execute(image,'hair','hair tip',6,24,.01,720,
                             42,'Qwen3-VL-8B-Instruct','local Qwen','{}','render')
        analysis.assert_not_called()
