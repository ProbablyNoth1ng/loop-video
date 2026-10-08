import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from ambient_loop.candidates import save_candidate, save_record, load_handle, finish_candidate
from ambient_loop.motion import new_plan, review_plan


class CandidateTests(unittest.TestCase):
    def test_near_widescreen_export_center_crops_pixels_and_record(self):
        with tempfile.TemporaryDirectory() as tmp, patch('ambient_loop.candidates.encode_previews'):
            plan = review_plan(new_plan('abc', (1290,720), 'hair', ['tip'],
                               [{'label':'tip','x':.5,'y':.5}], duration=1, fps=8, short_side=720))
            canvas_w,canvas_h = plan['transform']['canvas']
            images = np.zeros((9,canvas_h,canvas_w,3),dtype=np.uint8)
            content_x,content_y,content_w,content_h = plan['transform']['content']
            images[:,content_y:content_y+content_h,content_x:content_x+content_w,0] = np.arange(content_w,dtype=np.uint16).astype(np.uint8)
            handle = save_candidate(images,plan,42,Path(tmp),{})
            with Image.open(Path(handle['directory'])/'frames/000000.png') as frame:
                frame_size = frame.size
                first_pixel = frame.getpixel((0,0))[0]
                last_pixel = frame.getpixel((1279,0))[0]
            with Image.open(Path(handle['directory'])/'raw/000000.png') as raw:
                raw_size = raw.size
            self.assertEqual(frame_size,(1280,720))
            self.assertEqual(handle['dimensions'],[1280,720])
            self.assertEqual(raw_size,(canvas_w,canvas_h))
            self.assertEqual(first_pixel,5)
            self.assertEqual(last_pixel,4)

    def test_legacy_near_widescreen_candidate_finishes_exactly_without_modifying_source(self):
        with tempfile.TemporaryDirectory() as tmp, patch('ambient_loop.candidates.encode_previews'):
            root = Path(tmp)
            legacy = root/'candidate-legacy'
            (legacy/'frames').mkdir(parents=True)
            (legacy/'raw').mkdir()
            pixels = np.zeros((720,1290,3),dtype=np.uint8)
            pixels[...,0] = np.arange(1290,dtype=np.uint16).astype(np.uint8)
            for index in range(8):
                Image.fromarray(pixels).save(legacy/'frames'/f'{index:06d}.png')
            Image.fromarray(pixels).save(legacy/'raw'/'000000.png')
            original = save_record(legacy,{'kind':'candidate','dimensions':[1290,720],
                'fps':8,'frame_count':8,'generated_frames':9,'seed':42,
                'generation_settings':{},'state':'awaiting_visual_review'})
            record_bytes = Path(original['record']).read_bytes()
            frame_bytes = (Path(original['directory'])/'frames/000000.png').read_bytes()
            raw_bytes = (Path(original['directory'])/'raw/000000.png').read_bytes()
            calls = []
            def enhance(image, target):
                calls.append((image.size,image.getpixel((0,0))[0],target))
                return image.resize(target)
            for resolution, expected in [('1080p',(1920,1080)),('1440p',(2560,1440)),('4K',(3840,2160))]:
                final = finish_candidate(original,root,resolution,32,enhance)
                self.assertEqual(final['dimensions'],list(expected))
                with Image.open(Path(final['directory'])/'frames/000000.png') as frame:
                    self.assertEqual(frame.size,expected)
            self.assertEqual(calls, [((1280,720),5,(1920,1080))]*8 +
                                    [((1280,720),5,(2560,1440))]*8 +
                                    [((1280,720),5,(3840,2160))]*8)
            self.assertEqual(Path(original['record']).read_bytes(),record_bytes)
            self.assertEqual((Path(original['directory'])/'frames/000000.png').read_bytes(),frame_bytes)
            self.assertEqual((Path(original['directory'])/'raw/000000.png').read_bytes(),raw_bytes)

    def test_exact_widescreen_portrait_and_outside_tolerance_size_rules(self):
        cases = [((1600,900),(1600,900)),((720,1290),(720,1280)),
                 ((1307,720),(1308,720))]
        with tempfile.TemporaryDirectory() as tmp, patch('ambient_loop.candidates.encode_previews'):
            for source, expected in cases:
                with self.subTest(source=source):
                    plan = review_plan(new_plan('abc',source,'hair',['tip'],
                                       [{'label':'tip','x':.5,'y':.5}],duration=1,fps=8,short_side=min(source)))
                    width,height = plan['transform']['canvas']
                    handle = save_candidate(np.zeros((9,height,width,3),dtype=np.uint8),plan,42,Path(tmp),{})
                    self.assertEqual(handle['dimensions'],list(expected))
    def test_all_resolutions_preserve_orientation_frames_timing_and_original(self):
        from ambient_loop.staged_comfy import AmbientUpscale
        options = AmbientUpscale.INPUT_TYPES()['required']['resolution']
        self.assertIn('1080p', options[0])
        self.assertEqual(options[1]['default'], '1440p')
        for source, expected in [((1600,900),[(1920,1080),(2560,1440),(3840,2160)]),
                                 ((900,1600),[(1080,1920),(1440,2560),(2160,3840)])]:
            with tempfile.TemporaryDirectory() as tmp, patch('ambient_loop.candidates.encode_previews'):
                root = Path(tmp)
                plan = review_plan(new_plan('abc',source,'hair',['tip'],
                    [dict(label='tip',x=.5,y=.5)],duration=1,fps=8,short_side=288))
                w,h = plan['transform']['canvas']
                original = save_candidate(np.zeros((9,h,w,3),dtype=np.uint8),plan,42,root,{'cfg':1})
                original_record = Path(original['record']).read_bytes()
                for resolution, size in zip(['1080p','1440p','4K'],expected):
                    calls = []
                    def enhance(image, target):
                        calls.append(target)
                        return Image.new('RGB', target)
                    final = finish_candidate(original,root,resolution,3,enhance)
                    self.assertEqual(final['dimensions'],list(size))
                    self.assertEqual(calls, [size]*8)
                    self.assertEqual(final['fps'],8)
                    self.assertEqual(final['frame_count'],8)
                    self.assertEqual(final['parent'],original['record'])
                    self.assertEqual(final['generation_settings'],{'cfg':1})
                    self.assertEqual(Path(original['record']).read_bytes(),original_record)
                    self.assertEqual(load_handle(Path(final['record']),root)['frame_count'],8)
                self.assertEqual(load_handle(Path(original['record']),root)['frame_hashes'],original['frame_hashes'])

    def test_real_preview_encoding_preserves_fps_and_count(self):
        import shutil
        if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
            self.skipTest('ffmpeg/ffprobe unavailable')
        with tempfile.TemporaryDirectory() as tmp:
            plan = review_plan(new_plan('abc',(32,32),'hair',['tip'],
                               [{'label':'tip','x':.5,'y':.5}],duration=1,fps=8,short_side=256))
            frames = np.zeros((9,256,256,3),dtype=np.uint8)
            frames[4] = 40
            h = save_candidate(frames,plan,42,Path(tmp),{})
            self.assertEqual(h['frame_count'],8)
            self.assertEqual(h['closure_mean'],0)
            self.assertTrue((Path(h['directory'])/'loop.mp4').is_file())
            self.assertTrue((Path(h['directory'])/'seam.mp4').is_file())

    def test_saved_candidate_reopens_and_finishes_without_generation(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = review_plan(new_plan('abc', (32,32), 'hair', ['tip'],
                               [{'label':'tip','x':.5,'y':.5}], short_side=256))
            images = np.zeros((145,256,256,3), dtype=np.uint8)
            with patch('ambient_loop.candidates.encode_previews'):
                handle = save_candidate(images, plan, 42, Path(tmp), {'cfg':1})
                reopened = load_handle(Path(handle['record']), Path(tmp))
                calls = []
                def enhance(image, size):
                    calls.append(image.size)
                    return image.resize(size)
                final = finish_candidate(reopened, Path(tmp), '1440p', 3, enhance)
            self.assertEqual(final['frame_count'], 144)
            self.assertEqual(final['fps'],24)
            self.assertEqual(len(calls),144)
            self.assertNotEqual(handle['record'],final['record'])
            self.assertEqual(len(list(Path(handle['directory']).joinpath('raw').glob('*.png'))),145)
            self.assertNotIn('images',reopened)

    def test_invalid_count_and_external_record_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = review_plan(new_plan('abc',(32,32),'hair',['tip'],
                               [{'label':'tip','x':.5,'y':.5}],short_side=256))
            with self.assertRaisesRegex(ValueError,'145'):
                save_candidate(np.zeros((144,256,256,3),dtype=np.uint8),plan,42,Path(tmp),{})
            with self.assertRaises(ValueError):
                load_handle(Path(tmp).parent/'record.json',Path(tmp))

    def test_modified_frame_blocks_finishing(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = review_plan(new_plan('abc',(32,32),'hair',['tip'],
                               [{'label':'tip','x':.5,'y':.5}],short_side=256))
            with patch('ambient_loop.candidates.encode_previews'):
                h = save_candidate(np.zeros((145,256,256,3),dtype=np.uint8),plan,42,Path(tmp),{})
            Image.new('RGB',(256,256),'white').save(Path(h['directory'])/'frames/000001.png')
            with self.assertRaisesRegex(ValueError,'modified'):
                load_handle(Path(h['record']),Path(tmp))
