import json
from pathlib import Path

from .jobs import render
from .project import Project, atomic_json, PRESETS


class ComfyLTXLoopRender:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {
            'project_path': ('STRING', {'default': '/workspace/comfy-ltx-loop/assets/project.json'}),
            'output_directory': ('STRING', {'default': '/workspace/comfy-ltx-loop/outputs/loop'}),
            'working_mode': (['720p', '1080p'], {'default': '1080p'}),
            'output_resolution': (['1080p', '1440p', '4K'], {'default': '1440p'}),
            'duration': ('FLOAT', {'default': 6, 'min': 4, 'max': 30, 'step': 1 / 24}),
            'preset': (list(PRESETS), {'default': 'calm-wind'}),
            'seed': ('INT', {'default': 42, 'min': 0, 'max': 2**63 - 1}),
            'chunk_size': ('INT', {'default': 4, 'min': 1, 'max': 32})}}

    RETURN_TYPES = ('STRING',)
    RETURN_NAMES = ('manifest',)
    FUNCTION = 'execute'
    CATEGORY = 'comfy-ltx-loop'
    OUTPUT_NODE = True

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        # File hashes, not path strings, determine invalidation. Also rerun on output loss.
        return float('nan')

    def execute(self, project_path, output_directory, working_mode, output_resolution,
                duration, preset, seed, chunk_size):
        p = Project.load(project_path)
        p.data.update(working_mode=working_mode, output_resolution=output_resolution,
                      duration=duration, preset=preset, seed=seed)
        # Revalidate controls through the same parser, without changing the approved project.
        import tempfile
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=p.path.parent, suffix='.json', delete=False) as f:
                temporary = Path(f.name)
            atomic_json(temporary, p.data)
            checked = Project.load(temporary)
            checked.path = p.path
            return (json.dumps(render(checked, output_directory, chunk_size=chunk_size)),)
        finally:
            if temporary:
                temporary.unlink(missing_ok=True)


NODE_CLASS_MAPPINGS = {'ComfyLTXLoopRender': ComfyLTXLoopRender}
NODE_DISPLAY_NAME_MAPPINGS = {'ComfyLTXLoopRender': 'Comfy LTX Loop - Workflow A'}

# Keep the legacy node/API graphs available for existing CLI clients.
from .staged_comfy import NODE_CLASS_MAPPINGS as STAGED_NODES
from .staged_comfy import NODE_DISPLAY_NAME_MAPPINGS as STAGED_NAMES
NODE_CLASS_MAPPINGS.update(STAGED_NODES)
NODE_DISPLAY_NAME_MAPPINGS.update(STAGED_NAMES)


def export_graphs(project, destination, output_directory, project_path=None):
    p = Project.load(project)
    inputs = {'project_path': str(project_path or p.path), 'output_directory': str(output_directory),
              **{k: p.data[k] for k in ('working_mode', 'output_resolution', 'duration', 'preset', 'seed')},
              'chunk_size': 4}
    dest = Path(destination)
    atomic_json(dest / 'workflow-a.api.json', {'1': {'class_type': 'ComfyLTXLoopRender', 'inputs': inputs}})
    atomic_json(dest / 'workflow-a.json', {
        'last_node_id': 1, 'last_link_id': 0,
        'nodes': [{'id': 1, 'type': 'ComfyLTXLoopRender', 'pos': [120, 120], 'size': [430, 330],
                   'flags': {}, 'order': 0, 'mode': 0, 'inputs': [],
                   'outputs': [{'name': 'manifest', 'type': 'STRING', 'links': None}],
                   'properties': {'Node name for S&R': 'ComfyLTXLoopRender'},
                   'widgets_values': list(inputs.values())}],
        'links': [], 'groups': [], 'config': {}, 'extra': {}, 'version': .4})
