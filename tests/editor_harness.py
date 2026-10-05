"""Local browser fixture for the real editor extension, without GPU/ComfyUI.

Run python tests/editor_harness.py then open http://127.0.0.1:8766.
Queueing is simulated; this does not qualify a deployed ComfyUI frontend.
"""
import base64
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from io import BytesIO
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image, ImageDraw
from ambient_loop.motion import new_plan, review_plan

ROOT = Path(__file__).resolve().parents[1]
image = Image.new('RGB',(600,900),'#354860')
painter = ImageDraw.Draw(image)
painter.ellipse((140,130,460,500),fill='#e1c3b0')
painter.polygon([(130,370),(160,110),(450,120),(480,470),(390,260),(250,210)],fill='#25233f')
painter.polygon([(100,850),(180,510),(410,510),(530,850)],fill='#7092a4')
buffer=BytesIO();image.save(buffer,format='PNG');PNG=buffer.getvalue()
PLAN = new_plan('fixture',(600,900),'Gentle hair sway. Stationary camera.',
                ['hair tip','hair root','head','shoulder'],[],6,24,.01,720)
QWEN_PLAN = new_plan('fixture',(600,900),'Gentle hair sway. Stationary camera.',
                ['hair tip','hair root','head','shoulder'],[
                    {'label':'hair tip','x':.28,'y':.18},
                    {'label':'hair root','x':.49,'y':.19},
                    {'label':'head','x':.5,'y':.32},
                    {'label':'shoulder','x':.52,'y':.58}],6,24,.01,720)
FAILED_PLAN = new_plan('fixture',(600,900),'Gentle hair sway. Stationary camera.',
                ['hair tip','hair root','head','shoulder'],[],6,24,.01,720,
                ['Automatic preparation failed: missing hair tip. Add/edit points manually or retry.'])

HTML = '''<!doctype html><meta charset="utf-8"><title>Ambient Loop editor test fixture</title>
<style>body{background:#0d1117;color:white;font:14px system-ui;margin:20px}.panels{display:flex;gap:16px;align-items:start;overflow-x:auto}.panel{flex:0 0 520px}pre{white-space:pre-wrap}input{margin:3px}</style>
<h1>Ambient Loop · local editor fixture</h1><p>Real extension; simulated queue. No GPU generation.</p>
<button id="qwen-fixture">Show Qwen points</button><button id="failed-fixture">Show Qwen failure</button>
<button id="invalid-fixture">Show invalid Prepare</button><button id="run-fixture">Run</button><button id="run-again-fixture">Run again</button><button id="auto-fixture">Auto queue</button>
<button id="reopen-fixture">Simulate reopen</button>
<div class="panels"><section id="editor" class="panel"></section><section id="outputs" class="panel"></section></div>
<pre id="queue">No stage queued</pre>
<script type="module">
import {app} from '/scripts/app.js';import {api} from '/scripts/api.js';
import '/extensions/ambient_loop/ambient_loop.js';
const make=(id,type,values,parent)=>({id,type,comfyClass:type,size:[520,300],properties:{},
 widgets:Object.entries(values).map(([name,value])=>({name,value,options:{values:[]}})),
 addDOMWidget(name,type,root){parent.append(root);return{};},setSize(size){this.size=size;}});
const editor=make(2,'AmbientMotionEditor',{motion_prompt:'Gentle hair sway. Stationary camera.',
 requested_parts:'hair tip, hair root, head, shoulder',duration:6,fps:24,strength:.01,short_side:720,seed:42,
 vision_model:'models/Qwen3-VL-8B-Instruct',preparation:'manual',plan_json:'{}',stage:'render'},document.querySelector('#editor'));
const saver=make(5,'AmbientSaveCandidate',{},document.querySelector('#outputs'));
const selector=make(6,'AmbientSavedCandidate',{candidate:'Select a saved candidate'},document.querySelector('#outputs'));
const upscale=make(7,'AmbientUpscale',{resolution:'1440p',chunk_size:4},document.querySelector('#outputs'));
const load=make(1,'LoadImage',{image:'fixture.png'},document.querySelector('#editor'));
app.graph._nodes=[load,editor,saver,selector,upscale];
await app.extension.setup();for(const node of app.graph._nodes)app.extension.nodeCreated(node);
api.executed=message=>editor.onExecuted(message);
for(const [id,path] of [['qwen-fixture','/fixture-qwen-plan'],['failed-fixture','/fixture-failed-plan']])
 document.getElementById(id).onclick=async()=>editor.onExecuted({motion_plan:[await(await fetch(path)).json()],
 bg_image:[await(await fetch('/fixture-image')).text()]});
document.getElementById('reopen-fixture').onclick=()=>{editor.widgets.find(w=>w.name==='plan_json').value='{}';editor.onConfigure();};
document.getElementById('invalid-fixture').onclick=()=>editor.onExecuted({motion_plan:[{schema:'invalid'}]});
document.getElementById('run-fixture').onclick=()=>app.queuePrompt(0,1);
document.getElementById('run-again-fixture').onclick=()=>app.queuePrompt(0,1);
document.getElementById('auto-fixture').onclick=()=>app.queuePrompt(0,1,{autoQueue:true});
editor.onExecuted({motion_plan:[await(await fetch('/fixture-plan')).json()],bg_image:[await(await fetch('/fixture-image')).text()]});
</script>'''

APP = '''export const app={graph:{_nodes:[],setDirtyCanvas(){}},registerExtension(extension){this.extension=extension;},
 async queuePrompt(number,batchCount,options){const {workflow,output}=await this.graphToPrompt();return globalThis.fixtureApi.queuePrompt(number,{output,workflow},options);},
 async graphToPrompt(){const editor=this.graph._nodes.find(n=>n.id===2);
 const inputs=Object.fromEntries(editor.widgets.map(w=>[w.name,w.value]));inputs.image=['1',0];
 return{workflow:{extra:{}},output:{1:{class_type:'LoadImage',inputs:{image:'fixture.png'}},
 2:{class_type:'AmbientMotionEditor',inputs},3:{class_type:'UNETLoader',inputs:{}},
 4:{class_type:'Sampler',inputs:{model:['3',0],canvas:['2',0]}},
 5:{class_type:'AmbientSaveCandidate',inputs:{video:['4',0],motion_plan:['2',2]}},
 6:{class_type:'AmbientSavedCandidate',inputs:{candidate:'fixture/record.json'}},
 7:{class_type:'AmbientUpscale',inputs:{candidate:['6',0]}}}};}};'''

API = '''export const api={apiURL:path=>path,fetchApi:(path,options)=>fetch(path,options),
 async queuePrompt(number,prompt){document.querySelector('#queue').textContent=JSON.stringify(prompt.output,null,2);
 const data=await(await fetch('/fixture-queue',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(prompt)})).json();
 if(data.ui)this.executed(data.ui);return{prompt_id:'fixture',node_errors:{}};}};globalThis.fixtureApi=api;'''

class Handler(BaseHTTPRequestHandler):
    def reply(self,data,mime='application/json',status=200):
        payload=data if isinstance(data,bytes) else data.encode() if isinstance(data,str) else json.dumps(data).encode()
        self.send_response(status);self.send_header('Content-Type',mime);self.end_headers();self.wfile.write(payload)
    def do_GET(self):
        path=self.path.split('?')[0]
        if path=='/':self.reply(HTML,'text/html')
        elif path=='/scripts/app.js':self.reply(APP,'text/javascript')
        elif path=='/scripts/api.js':self.reply(API,'text/javascript')
        elif path=='/fixture-plan':self.reply(PLAN)
        elif path=='/fixture-qwen-plan':self.reply(QWEN_PLAN)
        elif path=='/fixture-failed-plan':self.reply(FAILED_PLAN)
        elif path=='/fixture-image':self.reply(base64.b64encode(PNG),'text/plain')
        elif path=='/view':self.reply(PNG,'image/png')
        elif path=='/ambient-loop/candidates':self.reply([])
        elif path.startswith('/extensions/ambient_loop/'):
            name=path.rsplit('/',1)[-1]
            if name not in ('ambient_loop.js','stages.mjs','geometry.mjs','queue_control.mjs'):self.reply({},status=404);return
            self.reply((ROOT/'comfy_nodes/ambient_loop/web'/name).read_bytes(),'text/javascript')
        else:self.reply({},status=404)
    def do_POST(self):
        data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        if self.path=='/ambient-loop/review':
            try:self.reply(review_plan(data))
            except (ValueError,KeyError,TypeError) as error:self.reply({'error':str(error)},status=400)
        elif self.path=='/fixture-queue':
            editor=next((n for n in data['output'].values() if n['class_type']=='AmbientMotionEditor'),None)
            self.reply({'ui':{'motion_plan':[PLAN],'bg_image':[base64.b64encode(PNG).decode()]}} if editor and editor['inputs']['stage']=='prepare' else {})
        else:self.reply({},status=404)

if __name__=='__main__':
    print('Editor fixture at http://127.0.0.1:8766',flush=True)
    HTTPServer(('127.0.0.1',8766),Handler).serve_forever()
