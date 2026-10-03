import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from ambient_loop.examples import create_examples
from ambient_loop.project import Project
from ambient_loop.comfy import export_graphs
from ambient_loop.regional import transform_tracks
from ambient_loop.regional import candidate
from ambient_loop.assets import cache_weight
from ambient_loop.project import sha
from ambient_loop.queue import submit


class OperationTests(unittest.TestCase):
    def test_examples_and_matching_graph_controls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_examples(root)
            for preset in ('calm-wind', 'rainy-window', 'sunset-field'):
                project = root / preset / 'project.json'
                Project.load(project)
                export_graphs(project, root / 'graphs', root / 'output')
                api = json.loads((root / 'graphs/workflow-a.api.json').read_text())
                ui = json.loads((root / 'graphs/workflow-a.json').read_text())
                self.assertEqual(ui['nodes'][0]['widgets_values'], list(api['1']['inputs'].values()))

    def test_single_coordinate_transform_and_outside_tracks(self):
        self.assertEqual(transform_tracks([[{'x': 100, 'y': 200}]], [100, 200, 256, 256]),
                         [[{'x': 0., 'y': 0.}]])
        with self.assertRaises(ValueError):
            transform_tracks([[{'x': 99, 'y': 200}]], [100, 200, 256, 256])

    def test_exhausted_regional_attempts_do_not_prepare_another_guide(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'attempts.json').write_text(json.dumps([{'seed': seed} for seed in (42,43,44)]))
            with patch('ambient_loop.regional.check_fallback'), patch('ambient_loop.regional.prepare') as prepare:
                with self.assertRaisesRegex(ValueError, 'exhausted'):
                    candidate('project.json', 'accepted-a', root, 'reviewer')
                prepare.assert_not_called()

    def test_cached_weight_is_verified_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'weight'
            path.write_bytes(b'fixture')
            self.assertTrue(cache_weight('https://example.invalid/weight', path, sha(path))['cached'])
            with self.assertRaisesRegex(ValueError, 'differs'):
                cache_weight('https://example.invalid/weight', path, '0' * 64)

    def test_lost_submission_response_is_never_resubmitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            graph = root / 'graph.json'
            graph.write_text('{"1": {"class_type": "AmbientLoopRender", "inputs": {}}}')
            receipt = root / 'receipt.json'
            with patch('ambient_loop.queue.request', side_effect=OSError('disconnected')) as request:
                with self.assertRaises(OSError):
                    submit(graph, receipt, 'http://localhost:8188')
                self.assertEqual(submit(graph, receipt, 'http://localhost:8188')['state'], 'submission_pending')
                self.assertEqual(request.call_count, 1)
