import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from PIL import Image

from ambient_loop.candidates import save_candidate, load_handle, finish_candidate
from ambient_loop.motion import new_plan, review_plan


class CandidateTests(unittest.TestCase):
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
