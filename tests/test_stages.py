import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ambient_loop.staged_comfy import AmbientMotionEditor, AmbientSavedCandidate, AmbientUpscale, AmbientFinish


class StageTests(unittest.TestCase):
    def test_new_finish_defaults_and_old_upscale_contract(self):
        modern = AmbientFinish.INPUT_TYPES()['required']
        legacy = AmbientUpscale.INPUT_TYPES()['required']
        self.assertEqual(modern['resolution'][1]['default'],'1080p')
        self.assertEqual(modern['method'][1]['default'],'Fast')
        self.assertEqual(modern['method'][0],['Fast','Balanced AI','Original AI'])
        self.assertEqual(list(legacy),['candidate','resolution','chunk_size'])
        self.assertEqual(legacy['resolution'][1]['default'],'1440p')
        candidate = {'record':'saved'}
        with patch('ambient_loop.staged_comfy.output_root',return_value=Path('output')), \
             patch('ambient_loop.staged_comfy.finish_candidate',return_value={'directory':'output/finish','record':'output/finish/record.json'}) as finish, \
             patch('ambient_loop.staged_comfy.preview_ui',return_value={}):
            AmbientFinish().execute(candidate,'1080p','Balanced AI',4)
            self.assertEqual(finish.call_args.kwargs,{'method':'balanced_ai'})
            AmbientUpscale().execute(candidate,'1440p',4)
            self.assertEqual(finish.call_args.kwargs,{})

    def test_combined_prepare_builds_both_groups_in_one_plan(self):
        import numpy as np
        image = np.zeros((1,100,80,3),dtype=np.float32)
        suggestions = [
            [dict(label='tip',x=.3,y=.4,body_part='hair',motion_role='move',reason='sway')],
            [dict(label='leaf',x=.7,y=.3,body_part='foliage',motion_role='move',reason='wind')],
        ]
        with patch('ambient_loop.staged_comfy.canvas_image',return_value=image), \
             patch('ambient_loop.staged_comfy.analyze',side_effect=suggestions) as analyze:
            plan = AmbientMotionEditor().execute(image,'hair','auto',6,24,.01,720,
                42,'model','local Qwen','{}','prepare',background_prompt='Leaves sway',
                background_preparation='model',prepare_target='both')['result'][2]
        self.assertEqual(analyze.call_count,2)
        self.assertEqual([point.get('group','character') for point in plan['landmarks']],
                         ['character','background'])
        self.assertEqual(plan['review']['state'],'pending')
        self.assertEqual(plan['background']['enabled'],True)

    def test_background_model_replaces_only_background_and_render_combines_guidance(self):
        import hashlib
        import numpy as np
        from ambient_loop.motion import new_plan, review_plan
        image = np.zeros((1,100,80,3),dtype=np.float32)
        identity = hashlib.sha256(image[0].astype(np.uint8).tobytes()+str((80,100)).encode()).hexdigest()
        old = new_plan(identity,(80,100),'hair',['auto'],[{'label':'tip','x':.3,'y':.4}])
        old['analysis'] = {'preparation':'manual','model_path':'model','prepared_prompt':'hair',
                           'prepared_requested':['auto'],'prepared_preparation':'manual','prepared_model_path':'model'}
        old['landmarks'][0]['path'][1]['x'] = .304
        old['background'] = {'enabled':True,'prompt':'Old leaves','preparation':'model',
            'prepared_prompt':'Old leaves','prepared_preparation':'model'}
        old['landmarks'].append({**old['landmarks'][0],'label':'old leaf','group':'background'})
        suggestion = [dict(label='leaf',x=.6,y=.3,body_part='foliage',motion_role='move',reason='sway')]
        with patch('ambient_loop.staged_comfy.canvas_image',return_value=image), \
             patch('ambient_loop.staged_comfy.analyze',return_value=suggestion) as analyze:
            prepared = AmbientMotionEditor().execute(image,'hair','auto',6,24,.01,720,
                42,'model','manual',json.dumps(old),'prepare',animate_background=True,
                background_prompt='Leaves sway',background_preparation='model',prepare_target='background')['result'][2]
        self.assertEqual(analyze.call_args.kwargs['target'],'background')
        self.assertEqual(prepared['landmarks'][0],old['landmarks'][0])
        self.assertEqual([p['label'] for p in prepared['landmarks']],['tip','leaf'])
        self.assertEqual(prepared['analysis'],old['analysis'])
        reviewed = review_plan(prepared)
        with patch('ambient_loop.staged_comfy.canvas_image',return_value=image):
            result = AmbientMotionEditor().execute(image,'hair','auto',6,24,.01,720,
                42,'model','manual',json.dumps(reviewed),'render',animate_background=True,
                background_prompt='Leaves sway',background_preparation='model')
        self.assertEqual(len(json.loads(result['result'][1])),2)
        self.assertIn('Background motion: Leaves sway',result['result'][6])
        self.assertIn('Stationary camera',result['result'][6])
        reviewed['background']['enabled'] = False
        reviewed = review_plan(reviewed)
        with patch('ambient_loop.staged_comfy.canvas_image',return_value=image):
            off = AmbientMotionEditor().execute(image,'hair','auto',6,24,.01,720,
                42,'model','manual',json.dumps(reviewed),'render',animate_background=False,
                background_prompt='',background_preparation='model')
        self.assertEqual(len(json.loads(off['result'][1])),1)
        self.assertEqual(len(off['result'][2]['landmarks']),2)
        self.assertIn('stationary background',off['result'][6])

    def test_failed_background_model_preserves_existing_points_and_stale_preparation(self):
        import hashlib
        import numpy as np
        from ambient_loop.motion import new_plan
        image = np.zeros((1,100,80,3),dtype=np.float32)
        identity = hashlib.sha256(image[0].astype(np.uint8).tobytes()+str((80,100)).encode()).hexdigest()
        old = new_plan(identity,(80,100),'hair',['auto'],[{'label':'tip','x':.3,'y':.4}])
        old['landmarks'].append({**old['landmarks'][0],'label':'leaf','group':'background'})
        old['background'] = {'enabled':True,'prompt':'Old leaves','preparation':'model',
            'prepared_prompt':'Old leaves','prepared_preparation':'model'}
        with patch('ambient_loop.staged_comfy.canvas_image',return_value=image), \
             patch('ambient_loop.staged_comfy.analyze',side_effect=RuntimeError('GPU failed')):
            plan = AmbientMotionEditor().execute(image,'hair','auto',6,24,.01,720,
                42,'model','manual',json.dumps(old),'prepare',animate_background=True,
                background_prompt='New leaves',background_preparation='model',prepare_target='background')['result'][2]
        self.assertEqual(plan['landmarks'],old['landmarks'])
        self.assertEqual(plan['background']['prepared_prompt'],'Old leaves')
        self.assertIn('GPU failed',plan['feedback'][0])
        with self.assertRaisesRegex(ValueError, 'Prepare background'):
            from ambient_loop.motion import review_plan
            review_plan(plan)

    def test_background_prepare_does_not_refresh_changed_character_prompt(self):
        import hashlib
        import numpy as np
        from ambient_loop.motion import new_plan, review_plan
        image = np.zeros((1,100,80,3),dtype=np.float32)
        identity = hashlib.sha256(image[0].astype(np.uint8).tobytes()+str((80,100)).encode()).hexdigest()
        old = new_plan(identity,(80,100),'old hair',['auto'],[{'label':'tip','x':.3,'y':.4}])
        old['analysis'] = {'preparation':'manual','model_path':'model','prepared_prompt':'old hair',
            'prepared_requested':['auto'],'prepared_preparation':'manual','prepared_model_path':'model'}
        with patch('ambient_loop.staged_comfy.canvas_image',return_value=image):
            plan = AmbientMotionEditor().execute(image,'new hair','auto',6,24,.01,720,
                42,'model','manual',json.dumps(old),'prepare',animate_background=True,
                background_prompt='Leaves sway',background_preparation='manual',prepare_target='background')['result'][2]
        self.assertEqual(plan['analysis'],old['analysis'])
        with self.assertRaisesRegex(ValueError, 'Prepare character'):
            review_plan(plan)

    def test_background_manual_prepare_preserves_character_without_model(self):
        import numpy as np
        from ambient_loop.motion import new_plan
        image = np.zeros((1,100,80,3),dtype=np.float32)
        import hashlib
        identity = hashlib.sha256(image[0].astype(np.uint8).tobytes()+str((80,100)).encode()).hexdigest()
        old = new_plan(identity,(80,100),'hair',['auto'],[{'label':'tip','x':.3,'y':.4}])
        old['landmarks'][0]['path'][1]['x'] = .305
        with patch('ambient_loop.staged_comfy.canvas_image',return_value=image), \
             patch('ambient_loop.staged_comfy.analyze') as analyze:
            result = AmbientMotionEditor().execute(image,'hair','auto',6,24,.01,720,
                42,'model','manual',json.dumps(old),'prepare',animate_background=True,
                background_prompt='Leaves sway',background_preparation='manual',prepare_target='background')
        analyze.assert_not_called()
        plan = result['result'][2]
        self.assertEqual(plan['landmarks'][0],old['landmarks'][0])
        self.assertEqual(plan['background']['prepared_prompt'],'Leaves sway')

    def test_new_qwen_choice_keeps_widget_order_and_blocks_stale_analysis_settings(self):
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
            self.assertEqual(prepared['analysis']['prepared_prompt'], 'hair')
            reviewed = json.dumps(review_plan(prepared))
            for model, mode in [('other','local Qwen3.5'),('models/Qwen3.5-9B','manual')]:
                with self.assertRaisesRegex(ValueError, 'prepare'):
                    AmbientMotionEditor().execute(image,'hair','auto',6,24,.01,720,
                         43,model,mode,reviewed,'render')

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

    def test_manual_accepted_points_reject_new_image(self):
        import numpy as np
        from ambient_loop.motion import new_plan, review_plan
        old = review_plan(new_plan('old', (80, 100), 'old prompt', ['tip'],
                    [{'label':'tip','x':.25,'y':.4}], 6, 24, .01, 720))
        image = np.zeros((1,60,90,3), dtype=np.float32)
        with patch('ambient_loop.staged_comfy.canvas_image', return_value=image):
            with self.assertRaisesRegex(ValueError, 'Source image changed'):
                AmbientMotionEditor().execute(image, 'new prompt', 'head', 3, 24,
                    .02, 800, 99, 'unused', 'manual', json.dumps(old), 'render')

    def test_render_never_analyzes_and_stale_review_fails(self):
        import numpy as np
        image = np.zeros((1,100,80,3),dtype=np.float32)
        with patch('ambient_loop.staged_comfy.image_array',return_value=image[0].astype(np.uint8)), \
             patch('ambient_loop.staged_comfy.analyze') as analysis:
            with self.assertRaises(ValueError):
                AmbientMotionEditor().execute(image,'hair','hair tip',6,24,.01,720,
                             42,'Qwen3-VL-8B-Instruct','local Qwen','{}','render')
        analysis.assert_not_called()
