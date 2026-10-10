import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

// Exercise the real extension; only the browser DOM and ComfyUI boundary are doubles.
class Element {
  constructor(tag) { this.tag=tag;this.style={};this.children=[];this.dataset={};this.playCalls=0; }
  append(child) { this.children.push(child); }
  setAttribute(name,value) { this[name]=value; }
  play() { this.playCalls++;this.paused=false;return Promise.resolve(); }
  load() { this.loaded=true; }
  pause() { this.paused=true; }
}
const descendants = root => [root,...root.children.flatMap(descendants)];
const flush = async () => { await new Promise(setImmediate);await new Promise(setImmediate); };
const record = {schema:'comfy-ltx-loop-render-handle/1',kind:'candidate',state:'awaiting_visual_review',
  directory:'/workspace/ComfyUI/output/comfy-ltx-loop/candidate-new',
  record:'/workspace/ComfyUI/output/comfy-ltx-loop/candidate-new/record.json',
  frame_count:72,fps:24,dimensions:[1280,720],feedback:[]};
let instance=0;

async function fixture(fetchApi = async path => ({ok:true,json:async()=>path.startsWith('/comfy-ltx-loop/candidates')
  ? ['candidate-new/record.json','candidate-old/record.json'] : record}), finishType='ComfyLTXLoopUpscale') {
  globalThis.document={createElement:tag=>new Element(tag),body:new Element('body')};
  const make=(id,type,values={})=>({id,type,comfyClass:type,size:[520,300],properties:{},
    widgets:Object.entries(values).map(([name,value])=>({name,value,options:{values:[]}})),
    addDOMWidget(name,type,root){this.root=root;return{};},setSize(size){this.size=size;}});
  const saver=make(5,'ComfyLTXLoopSaveCandidate');
  const selector=make(6,'ComfyLTXLoopSavedCandidate',{candidate:'Select a saved candidate'});
  const upscale=make(7,finishType,{resolution:'1440p',chunk_size:4});
  const submissions=[];
  const app={graph:{_nodes:[saver,selector,upscale],setDirtyCanvas(){}},
    registerExtension(extension){this.extension=extension;},
    async graphToPrompt(){return{workflow:{extra:{}},output:{
      4:{class_type:'Sampler',inputs:{}},
      5:{class_type:'ComfyLTXLoopSaveCandidate',inputs:{video:['4',0]}},
      6:{class_type:'ComfyLTXLoopSavedCandidate',inputs:{candidate:selector.widgets[0].value}},
      7:{class_type:finishType,inputs:{candidate:['6',0],resolution:'1440p',chunk_size:4}}
    }};}};
  const api={apiURL:path=>'/comfy'+path,fetchApi,async queuePrompt(number,prompt){
    submissions.push(prompt.output);return{prompt_id:'test',node_errors:{}};
  }};
  globalThis.comfy_ltx_loopPreviewFixture={app,api};
  const source=await readFile(new URL('../comfy_nodes/comfy_ltx_loop/web/comfy_ltx_loop.js',import.meta.url),'utf8');
  const modified=source.replace(/import \{ app \}[^\n]+\nimport \{ api \}[^\n]+/, 'const {app,api}=globalThis.comfy_ltx_loopPreviewFixture;')
    .replace(/from '(\.\/[^']+)'/g,(_,path)=>`from '${new URL('../comfy_nodes/comfy_ltx_loop/web/'+path,import.meta.url).href}'`);
  await import('data:text/javascript;base64,'+Buffer.from(modified+`\n// fixture ${instance++}`).toString('base64'));
  for(const node of app.graph._nodes)app.extension.nodeCreated(node);
  return{saver,selector,upscale,submissions,choice:selector.widgets[0],
    videos:()=>descendants(saver.root).filter(el=>el.tag==='video'),
    buttons:node=>descendants(node.root).filter(el=>el.tag==='button')};
}

test('executed previews use ComfyUI filename/subfolder URLs and begin muted loop playback',async()=>{
  const f=await fixture();await flush();
  f.saver.onExecuted({preview_paths:['comfy-ltx-loop/candidate-new/loop.mp4','comfy-ltx-loop/candidate-new/seam.mp4'],render_handle:[record]});
  for(const [index,video] of f.videos().entries()) {
    const url=new URL(video.src,'http://fixture');
    assert.equal(url.pathname,'/comfy/view');
    assert.equal(url.searchParams.get('filename'),index===0?'loop.mp4':'seam.mp4');
    assert.equal(url.searchParams.get('subfolder'),'comfy-ltx-loop/candidate-new');
    assert.equal(url.searchParams.get('type'),'output');
    assert.equal(video.autoplay,true);assert.equal(video.muted,true);assert.equal(video.loop,true);
    assert.ok(video.playCalls>0);
  }
  const download=descendants(f.saver.root).find(el=>el.tag==='a');
  assert.equal(download.href,f.videos()[0].src);
});

test('candidate loading and changing the dropdown automatically preview without a preview button',async()=>{
  const requests=[];
  const f=await fixture(async path=>{requests.push(path);return{ok:true,json:async()=>path.startsWith('/comfy-ltx-loop/candidates')
    ? ['candidate-new/record.json','candidate-old/record.json'] : record};});
  await flush();
  assert.equal(f.choice.value,'candidate-new/record.json');
  assert.ok(f.videos()[0].src.includes('candidate-new'));
  assert.deepEqual(f.buttons(f.selector).map(b=>b.textContent),['Refresh candidates']);
  f.choice.value='candidate-old/record.json';
  await f.choice.callback(f.choice.value);
  assert.ok(f.videos()[0].src.includes('candidate-old'));
  assert.ok(requests.includes('/comfy-ltx-loop/record?candidate=candidate-old%2Frecord.json'));
});

test('the last render is selected immediately and upscale queues that saved render only',async()=>{
  const f=await fixture();await flush();
  f.choice.value='candidate-old/record.json';
  f.saver.onExecuted({preview_paths:['comfy-ltx-loop/candidate-last/loop.mp4','comfy-ltx-loop/candidate-last/seam.mp4'],render_handle:[record]});
  assert.equal(f.choice.value,'candidate-last/record.json');
  assert.ok(f.choice.options.values.includes(f.choice.value));
  await f.buttons(f.upscale).find(b=>b.textContent==='Upscale').onclick();
  assert.deepEqual(Object.keys(f.submissions[0]),['6','7']);
  assert.equal(f.submissions[0]['6'].inputs.candidate,'candidate-last/record.json');
});

test('new finish preview displays the recorded method and queues only disk nodes',async()=>{
  const f=await fixture(undefined,'ComfyLTXLoopFinish');await flush();
  const finished={...record,kind:'finish',finish_method:'fast'};
  f.upscale.onExecuted({preview_paths:['comfy-ltx-loop/finish-new/loop.mp4','comfy-ltx-loop/finish-new/seam.mp4'],render_handle:[finished]});
  assert.match(f.upscale.root.children.filter(el=>el.tag==='p').map(el=>el.textContent).join(' '),/Fast/);
  await f.buttons(f.upscale).find(b=>b.textContent==='Upscale').onclick();
  assert.deepEqual(Object.keys(f.submissions[0]),['6','7']);
});

test('saved preview paths reopen with folder normalization and automatic playback',async()=>{
  const f=await fixture();await flush();
  f.saver.properties.comfy_ltx_loop_preview={paths:['comfy-ltx-loop\\candidate-old\\loop.mp4','comfy-ltx-loop\\candidate-old\\seam.mp4'],record};
  f.saver.onConfigure();
  const video=f.videos()[0],url=new URL(video.src,'http://fixture');
  assert.equal(url.searchParams.get('filename'),'loop.mp4');
  assert.equal(url.searchParams.get('subfolder'),'comfy-ltx-loop/candidate-old');
  assert.ok(video.playCalls>0);
});

test('an older record response cannot overwrite a newly completed render',async()=>{
  let respond;
  const f=await fixture(path=>path.startsWith('/comfy-ltx-loop/candidates')
    ? Promise.resolve({ok:true,json:async()=>['candidate-old/record.json']})
    : new Promise(resolve=>{respond=resolve;}));
  await flush();
  assert.equal(typeof respond,'function');
  f.saver.onExecuted({preview_paths:['comfy-ltx-loop/candidate-last/loop.mp4','comfy-ltx-loop/candidate-last/seam.mp4'],render_handle:[record]});
  respond({ok:true,json:async()=>record});await flush();
  assert.equal(f.choice.value,'candidate-last/record.json');
  assert.ok(f.videos()[0].src.includes('candidate-last'));
});

test('media failures expose an error instead of leaving a blank unexplained player',async()=>{
  const f=await fixture();await flush();
  f.saver.onExecuted({preview_paths:['comfy-ltx-loop/candidate-new/loop.mp4','comfy-ltx-loop/candidate-new/seam.mp4'],render_handle:[record]});
  const video=f.videos()[0];video.error={code:4};video.onerror();
  assert.match(descendants(f.saver.root).filter(el=>el.tag==='p').map(el=>el.textContent).join(' '),/preview.*(failed|unavailable|load)/i);
});
