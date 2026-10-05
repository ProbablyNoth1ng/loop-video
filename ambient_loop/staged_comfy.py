"""ComfyUI stage nodes; optional GPU imports are deferred to their own stages."""
import base64
import hashlib
import json
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

from .motion import new_plan, require_review, canvas_tracks
from .vision import analyze
from .candidates import save_candidate, load_handle, finish_candidate, list_candidates


def output_root():
    import folder_paths
    return Path(folder_paths.get_output_directory())/'ambient-loop'


def image_array(image):
    if len(image) != 1:
        raise ValueError('Load exactly one source image')
    value = image[0]
    if hasattr(value,'detach'):
        value = value.detach().cpu().numpy()
    if not np.isfinite(value).all():
        raise ValueError('Source image contains invalid pixels')
    return np.rint(np.clip(value[:,:,:3],0,1)*255).astype(np.uint8)


def canvas_image(image, transform):
    import torch
    x,y,w,h = transform['content']
    image = image.resize((w,h),Image.Resampling.LANCZOS)
    # Edge padding does not stretch the original image or alter track mapping.
    cw,ch = transform['canvas']
    pixels = np.pad(np.asarray(image),((y,ch-h-y),(x,cw-w-x),(0,0)),mode='edge')
    return torch.from_numpy(pixels.astype(np.float32)/255).unsqueeze(0)


def preview_ui(record):
    directory = Path(record['directory']).relative_to(output_root()).as_posix()
    return {'render_handle':[record], 'preview_paths':[
        f'ambient-loop/{directory}/loop.mp4',f'ambient-loop/{directory}/seam.mp4']}


class AmbientMotionEditor:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{
            'image':('IMAGE',),
            'motion_prompt':('STRING',{'default':'Gentle hair sway. Stationary camera.','multiline':True}),
            'requested_parts':('STRING',{'default':'hair tip, hair root, head, shoulder'}),
            'duration':('FLOAT',{'default':6.,'min':1.,'max':30.,'step':1/24}),
            'fps':('INT',{'default':24,'min':8,'max':60}),
            'strength':('FLOAT',{'default':.01,'min':0.,'max':.1,'step':.001}),
            'short_side':('INT',{'default':720,'min':256,'max':2160,'step':8}),
            'seed':('INT',{'default':42,'min':0,'max':2**63-1,'control_after_generate':False}),
            'vision_model':('STRING',{'default':'models/Qwen3-VL-8B-Instruct'}),
            'preparation':(['local Qwen','manual'],),
            'plan_json':('STRING',{'default':'{}','multiline':True}),
            'stage':(['render','prepare'],)},
            'hidden':{'extra_pnginfo':'EXTRA_PNGINFO','unique_id':'UNIQUE_ID'}}

    RETURN_TYPES = ('IMAGE','STRING','MOTION_PLAN','FLOAT','FLOAT','INT','STRING')
    RETURN_NAMES = ('canvas','tracks','motion_plan','fps','duration','seed','prompt')
    FUNCTION = 'execute'
    CATEGORY = 'ambient-loop/staged'
    OUTPUT_NODE = True

    @classmethod
    def IS_CHANGED(cls,**kwargs):
        return float('nan')

    def execute(self,image,motion_prompt,requested_parts,duration,fps,strength,short_side,
                seed,vision_model,preparation,plan_json,stage,extra_pnginfo=None,unique_id=None):
        pixels = image_array(image)
        source = Image.fromarray(pixels)
        identity = hashlib.sha256(pixels.tobytes()+str(source.size).encode()).hexdigest()
        requested = [v.strip() for v in requested_parts.split(',') if v.strip()]
        if stage == 'prepare':
            points,feedback = [],[]
            if preparation == 'local Qwen':
                try:
                    points = analyze(source,motion_prompt,requested,vision_model)
                except Exception as error:
                    feedback = [f'Automatic preparation failed: {error}. Add/edit points manually or retry.']
            plan = new_plan(identity,source.size,motion_prompt,requested,points,
                            duration,fps,strength,short_side,feedback)
        elif stage == 'render':
            try:
                plan = json.loads(plan_json)
            except json.JSONDecodeError as error:
                raise ValueError('Invalid saved plan; Prepare and review points') from error
            require_review(plan,identity,source.size,motion_prompt,duration,fps,strength,short_side)
            if plan['requested'] != requested:
                raise ValueError('Requested landmarks changed; prepare and review points again')
        else:
            raise ValueError('Choose Prepare or Render')
        canvas = canvas_image(source,plan['transform'])
        buffer = BytesIO()
        source.save(buffer,format='PNG')
        ui = {'motion_plan':[plan], 'bg_image':[base64.b64encode(buffer.getvalue()).decode()]}
        if extra_pnginfo is not None:
            workflow = extra_pnginfo.setdefault('workflow',{})
            workflow.setdefault('extra',{}).setdefault('ambient_motion_plans',{})[str(unique_id)] = plan
        return {'ui':ui,'result':(canvas,json.dumps(canvas_tracks(plan)),plan,
                                 float(fps),float(duration),seed,motion_prompt)}


class AmbientSaveCandidate:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'video':('VIDEO',),'motion_plan':('MOTION_PLAN',),
                            'seed':('INT',{'default':42})},
                'hidden':{'prompt':'PROMPT','extra_pnginfo':'EXTRA_PNGINFO'}}
    RETURN_TYPES = ('RENDER_HANDLE',)
    RETURN_NAMES = ('candidate',)
    FUNCTION = 'execute'
    CATEGORY = 'ambient-loop/staged'
    OUTPUT_NODE = True
    @classmethod
    def IS_CHANGED(cls,**kwargs):
        return float('nan')
    def execute(self,video,motion_plan,seed,prompt=None,extra_pnginfo=None):
        components = video.get_components()
        if float(components.frame_rate) != motion_plan['fps']:
            raise ValueError('Decoded FPS differs from the reviewed plan')
        settings = {'recipe':'LTX-2.5-single-stage-motion-track',
                    'api_graph':prompt,'workflow':(extra_pnginfo or {}).get('workflow')}
        record = save_candidate(components.images,motion_plan,seed,output_root(),settings)
        return {'ui':preview_ui(record),'result':(record,)}


class AmbientSavedCandidate:
    @classmethod
    def INPUT_TYPES(cls):
        records = list_candidates(output_root())
        return {'required':{'candidate':(records or ['Select a saved candidate'],)}}
    RETURN_TYPES = ('RENDER_HANDLE',)
    FUNCTION = 'execute'
    CATEGORY = 'ambient-loop/staged'
    @classmethod
    def IS_CHANGED(cls,**kwargs):
        return float('nan')
    def execute(self,candidate):
        return (load_handle(output_root()/candidate,output_root()),)


class AmbientUpscale:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required':{'candidate':('RENDER_HANDLE',),
                 'resolution':(['1440p','4K'],),
                 'chunk_size':('INT',{'default':4,'min':1,'max':32})}}
    RETURN_TYPES = ('RENDER_HANDLE',)
    FUNCTION = 'execute'
    CATEGORY = 'ambient-loop/staged'
    OUTPUT_NODE = True
    @classmethod
    def IS_CHANGED(cls,**kwargs):
        return float('nan')
    def execute(self,candidate,resolution,chunk_size):
        record = finish_candidate(candidate,output_root(),resolution,chunk_size)
        return {'ui':preview_ui(record),'result':(record,)}


NODE_CLASS_MAPPINGS = {'AmbientMotionEditor':AmbientMotionEditor,
                       'AmbientSaveCandidate':AmbientSaveCandidate,
                       'AmbientSavedCandidate':AmbientSavedCandidate,
                       'AmbientUpscale':AmbientUpscale}
NODE_DISPLAY_NAME_MAPPINGS = {'AmbientMotionEditor':'Ambient Loop · Prepare and review',
    'AmbientSaveCandidate':'Ambient Loop · Render preview',
    'AmbientSavedCandidate':'Ambient Loop · Select saved candidate',
    'AmbientUpscale':'Ambient Loop · Upscale preview'}
