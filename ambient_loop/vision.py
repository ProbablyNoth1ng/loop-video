"""Local-only Qwen preparation. Never retains model tensors between stages."""
import gc
import json
import re
import traceback
from pathlib import Path

from .motion import parse_landmarks


def snapshot_path(model_path):
    path = Path(model_path).expanduser()
    if path.is_absolute() or (path/'config.json').is_file():
        return path
    # ComfyUI may start from a different cwd; resolve bundled defaults there.
    try:
        import folder_paths
        relative = path.parts[1:] if path.parts and path.parts[0] == 'models' else path.parts
        return Path(folder_paths.models_dir).joinpath(*relative)
    except ImportError:
        return path


def analyze(image, prompt, requested, model_path, feedback=None):
    path = snapshot_path(model_path)
    try:
        config = json.loads((path/'config.json').read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise ValueError(f'Install a complete local Qwen snapshot including config.json at {path}') from error
    classes = {'qwen3_vl':'Qwen3VLForConditionalGeneration',
               'qwen3_5':'Qwen3_5ForConditionalGeneration'}
    architecture = classes.get(config.get('model_type'))
    if architecture is None or architecture not in config.get('architectures', []):
        raise ValueError('Unsupported vision snapshot; use Qwen3-VL or Qwen3.5 multimodal weights')
    import torch
    import transformers
    version = re.match(r'^(\d+)\.(\d+)', transformers.__version__)
    if not version or not (5, 2) <= tuple(map(int, version.groups())) < (6, 0):
        raise ValueError('Local Qwen analysis requires transformers>=5.2,<6')
    model = processor = inputs = generated = None
    try:
        import comfy.model_management as management
        management.unload_all_models()
        model = getattr(transformers, architecture).from_pretrained(
            str(path), local_files_only=True, dtype='auto', device_map='auto')
        processor = transformers.AutoProcessor.from_pretrained(str(path), local_files_only=True)
        instruction = ('Identify visible character parts and propose control points for this motion prompt: '+prompt+
                       '. Requested parts: '+json.dumps(requested)+
                       '. With auto, choose useful visible points adapted to this image; explicit lists remain priorities.'
                       ' Aim for 16–24 distinct useful points, fewer when visibility is limited. Never fill a quota.'
                       ' Include distinct left/right hair tips, intermediate points along visible strands, roots,'
                       ' and visible face/body anchors (eyes, eyebrows, nose, jaw, neck, shoulders where visible).'
                       ' Label each point uniquely with side and location. Omit hidden or uncertain anatomy and explain omissions.'
                       ' Set motion_role to move ONLY for motion requested by the prompt; unrequested motion and explicitly'
                       ' stationary parts MUST be anchor. Roots normally anchor hair sway; intermediate points may move.'
                       ' Explain each role in reason using the prompt. Do not infer motion from a label alone.'
                       ' Return ONLY JSON {"landmarks":[{"label":"left hair tip","x":500,"y":500,'
                       '"body_part":"hair","motion_role":"move","reason":"Requested hair sway"}],'
                       '"omissions":["Right shoulder is hidden"]}.'
                       ' Coordinates MUST be integers in [0,1000], relative to the full image.'
                       ' Never duplicate locations or invent obscured parts.')
        template_options = {'enable_thinking':False} if config['model_type'] == 'qwen3_5' else {}
        inputs = processor.apply_chat_template([{'role':'user','content':[
            {'type':'image','image':image}, {'type':'text','text':instruction}]}],
            tokenize=True, add_generation_prompt=True, return_dict=True,
            return_tensors='pt', **template_options).to(model.device)
        with torch.inference_mode():
            generated = model.generate(**inputs, max_new_tokens=4096, do_sample=False)
        raw = processor.batch_decode(generated[:,inputs['input_ids'].shape[-1]:],
                                     skip_special_tokens=True)[0]
        return parse_landmarks(raw, requested, feedback=feedback, require_semantics=True)
    except Exception as error:
        # Failed generate/load frames may retain `self` and device tensors.
        pending, seen = [error], set()
        while pending:
            failure = pending.pop()
            if id(failure) in seen:
                continue
            seen.add(id(failure))
            traceback.clear_frames(failure.__traceback__)
            pending.extend(cause for cause in (failure.__cause__, failure.__context__) if cause is not None)
        raise
    finally:
        del model, processor, inputs, generated
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
