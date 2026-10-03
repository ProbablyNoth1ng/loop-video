"""Local-only Qwen preparation. Never retains model tensors between stages."""
import gc
import json

from .motion import parse_landmarks


def analyze(image, prompt, requested, model_path):
    import torch
    from transformers import AutoProcessor, Qwen3VLForConditionalGeneration
    model = processor = inputs = generated = None
    try:
        import comfy.model_management as management
        management.unload_all_models()
        model = Qwen3VLForConditionalGeneration.from_pretrained(
            model_path, local_files_only=True, dtype='auto', device_map='auto')
        processor = AutoProcessor.from_pretrained(model_path, local_files_only=True)
        instruction = ('Locate the requested anime landmarks for this motion: '+prompt+
                       '. Requested labels: '+json.dumps(requested)+
                       '. Return ONLY JSON {"landmarks":[{"label":"hair tip","x":500,"y":500}]}.'
                       ' Coordinates MUST be integers in [0,1000], relative to the full image.'
                       ' Label each requested part; omit uncertain points rather than invent them.')
        inputs = processor.apply_chat_template([{'role':'user','content':[
            {'type':'image','image':image}, {'type':'text','text':instruction}]}],
            tokenize=True, add_generation_prompt=True, return_dict=True,
            return_tensors='pt').to(model.device)
        with torch.inference_mode():
            generated = model.generate(**inputs, max_new_tokens=2048, do_sample=False)
        raw = processor.batch_decode(generated[:,inputs['input_ids'].shape[-1]:],
                                     skip_special_tokens=True)[0]
        return parse_landmarks(raw, requested)
    finally:
        del model, processor, inputs, generated
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
