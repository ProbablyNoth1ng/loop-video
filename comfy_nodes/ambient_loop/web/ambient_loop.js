import { app } from '../../../scripts/app.js';
import { api } from '../../../scripts/api.js';
import { stageGraph } from './stages.mjs';

const widget = (node,name) => node.widgets?.find(w => w.name === name);
const nodes = () => app.graph._nodes;
const find = type => nodes().find(n => n.comfyClass === type || n.type === type);
const viewURL = path => api.apiURL('/view?'+new URLSearchParams({filename:path,type:'output'}));

async function queue(stage, target, status) {
    try {
        if (!target) throw new Error('Load the Ambient Loop motion workflow first.');
        if(stage==='render') {
            const editor=find('AmbientMotionEditor');
            checkSettings(editor);
            if(JSON.parse(widget(editor,'plan_json').value).review?.state!=='reviewed') {
                throw new Error('Review points and click Accept point review before Render.');
            }
        }
        const {workflow,output} = await app.graphToPrompt();
        const selected = stageGraph(output,target.id,stage);
        workflow.extra ??= {};
        workflow.extra.ambient_motion_plans = Object.fromEntries(nodes()
            .filter(n => widget(n,'plan_json')).map(n => [n.id,JSON.parse(widget(n,'plan_json').value)]));
        const result = await api.queuePrompt(0,{output:selected,workflow});
        if (result.node_errors && Object.keys(result.node_errors).length) throw new Error(JSON.stringify(result.node_errors));
        status.textContent = `${stage} queued. Progress appears in ComfyUI.`;
    } catch (error) { status.textContent = error.message; }
}

function checkSettings(node) {
    if(!node)throw new Error('Load the motion editor first.');
    const p=JSON.parse(widget(node,'plan_json').value);
    for(const [key,name] of [['prompt','motion_prompt'],['duration','duration'],['fps','fps'],['strength','strength'],['short_side','short_side']]) {
        if(p[key]!==widget(node,name).value)throw new Error('Motion settings changed. Prepare again, edit points and review.');
    }
    const requested=widget(node,'requested_parts').value.split(',').map(v=>v.trim()).filter(Boolean);
    if(JSON.stringify(p.requested)!==JSON.stringify(requested))throw new Error('Requested parts changed. Prepare and review again.');
    if(widget(find('LoadImage')??{},'image')?.value!==node.properties.ambient_source_image) {
        throw new Error('Source image changed. Prepare and review points again.');
    }
    return p;
}

function element(tag,parent,text) {
    const el = document.createElement(tag);
    if (text) el.textContent = text;
    parent?.append(el);
    return el;
}

function panel(node,height) {
    const root = document.createElement('div');
    Object.assign(root.style,{background:'#151a22',color:'#eee',padding:'10px',font:'13px system-ui',overflow:'auto'});
    const dom = node.addDOMWidget('ambient_panel','div',root,{serialize:false,hideOnZoom:false});
    dom.computeSize = () => [480,height];
    node.setSize([520,Math.max(node.size[1],height+220)]);
    return root;
}

function button(parent,label,action) {
    const b = element('button',parent,label);
    b.type = 'button'; b.style.margin = '3px';
    b.onclick = action;
    return b;
}

function hide(node,name) {
    const w=widget(node,name);
    if (!w) return;
    w.type='hidden';w.computeSize=()=>[0,-4];w.draw=()=>{};
}

function editor(node) {
    hide(node,'plan_json');hide(node,'stage');
    const root = panel(node,540);
    const controls=element('div',root);
    const status=element('p',root,'Load an image, then Prepare points. Choose manual preparation to skip Qwen.');
    const canvas=element('canvas',root);canvas.width=480;canvas.height=300;
    Object.assign(canvas.style,{width:'100%',height:'300px',objectFit:'contain',touchAction:'none',background:'#080a0f'});
    const tools=element('div',root);
    const label=element('input',tools);label.placeholder='Point label';label.style.width='130px';
    const enabled=element('input',tools);enabled.type='checkbox';enabled.title='Enable selected point';
    element('span',tools,' Enabled · strength ');
    const strength=element('input',tools);strength.type='number';strength.min=0;strength.max=2;strength.step=.1;strength.style.width='55px';
    const pathTools=element('div',root);
    element('span',pathTools,'Path key · ');
    const pathKey=element('select',pathTools);pathKey.title='Trajectory time';
    element('span',pathTools,' x ');
    const pathX=element('input',pathTools);pathX.type='number';pathX.min=0;pathX.max=1;pathX.step=.001;pathX.style.width='70px';pathX.title='Normalized path x';
    element('span',pathTools,' y ');
    const pathY=element('input',pathTools);pathY.type='number';pathY.min=0;pathY.max=1;pathY.step=.001;pathY.style.width='70px';pathY.title='Normalized path y';
    const hint=element('p',root,'Drag landmarks to move. Select a landmark, then drag its path handles. Add points by clicking the image.');
    const timeline=element('input',root);timeline.type='range';timeline.min=0;timeline.max=1;timeline.step=.005;timeline.value=0;timeline.style.width='100%';
    let background=new Image(),selected=-1,adding=false,drag=null,timer=null,rect=null;
    function plan() { try { return JSON.parse(widget(node,'plan_json').value); } catch { return {}; } }
    function save(p) {
        p.review={state:'pending'};
        widget(node,'plan_json').value=JSON.stringify(p);
        persist(p);
        status.textContent='Points changed. Review trajectories and click Accept point review.';
        app.graph.setDirtyCanvas(true,true);pathSelection();draw();
    }
    function persist(p) {
        app.graph.extra??={};
        app.graph.extra.ambient_motion_plans??={};
        app.graph.extra.ambient_motion_plans[String(node.id)]=p;
    }
    function selection(p) {
        const point=p.landmarks?.[selected];
        label.value=point?.label??'';enabled.checked=point?.enabled??false;strength.value=point?.strength??1;
        pathKey.replaceChildren();
        for(const [index,key] of (point?.path??[]).entries()) {
            if(index===0||index===point.path.length-1)continue;
            const option=element('option',pathKey,`${Math.round(key.t*100)}%`);option.value=index;
        }
        pathSelection();
    }
    function pathSelection() {
        const key=plan().landmarks?.[selected]?.path[Number(pathKey.value)];
        pathX.value=key?.x??'';pathY.value=key?.y??'';
    }
    pathKey.onchange=pathSelection;
    const applyPath=()=>{
        const p=plan(),key=p.landmarks?.[selected]?.path[Number(pathKey.value)];if(!key)return;
        key.x=Number(pathX.value);key.y=Number(pathY.value);save(p);
    };
    button(pathTools,'Apply path key',applyPath);
    function position(path,t) {
        let i=0;while(i<path.length-2 && t>path[i+1].t)i++;
        const a=path[i],b=path[i+1],u=(t-a.t)/(b.t-a.t);
        return {x:a.x+(b.x-a.x)*u,y:a.y+(b.y-a.y)*u};
    }
    function draw() {
        const ctx=canvas.getContext('2d');ctx.clearRect(0,0,480,300);
        if (!background.naturalWidth) return;
        const scale=Math.min(480/background.naturalWidth,300/background.naturalHeight);
        rect={x:(480-background.naturalWidth*scale)/2,y:(300-background.naturalHeight*scale)/2,
              w:background.naturalWidth*scale,h:background.naturalHeight*scale};
        ctx.drawImage(background,rect.x,rect.y,rect.w,rect.h);
        const p=plan();
        for(const [index,point] of (p.landmarks??[]).entries()) {
            const project=(x,y)=>[rect.x+x*rect.w,rect.y+y*rect.h];
            ctx.strokeStyle=point.enabled?'#7ce7dc':'#888';ctx.fillStyle=index===selected?'#ffcb66':'#7ce7dc';
            ctx.globalAlpha=point.enabled?1:.4;ctx.beginPath();
            for(const [k,key] of point.path.entries()) {
                const xy=project(point.x+(key.x-point.x)*point.strength,point.y+(key.y-point.y)*point.strength);
                if(k===0)ctx.moveTo(...xy);else ctx.lineTo(...xy);
            }
            ctx.stroke();
            if(index===selected)for(const key of point.path.slice(1,-1)) {
                const [x,y]=project(key.x,key.y);ctx.strokeRect(x-3,y-3,6,6);
            }
            const [x,y]=project(point.x,point.y);ctx.beginPath();ctx.arc(x,y,5,0,Math.PI*2);ctx.fill();
            ctx.fillText(point.label,x+7,y-5);
            const moving=position(point.path,Number(timeline.value));
            const [mx,my]=project(point.x+(moving.x-point.x)*point.strength,point.y+(moving.y-point.y)*point.strength);
            ctx.beginPath();ctx.arc(mx,my,3,0,Math.PI*2);ctx.fill();
        }
        ctx.globalAlpha=1;
    }
    background.onload=draw;
    function eventPoint(event) {
        const box=canvas.getBoundingClientRect();
        const x=(event.clientX-box.left)*480/box.width,y=(event.clientY-box.top)*300/box.height;
        if(!rect)return null;
        return {x:(x-rect.x)/rect.w,y:(y-rect.y)/rect.h};
    }
    canvas.onpointerdown=event=>{
        const p=plan(),where=eventPoint(event);
        if(!where||!p.landmarks||where.x<0||where.x>1||where.y<0||where.y>1)return;
        if(adding) {
            const path=Array.from({length:17},(_,i)=>({t:i/16,x:where.x+Math.min(.01,1-where.x)*(1-Math.cos(2*Math.PI*i/16))/2,y:where.y}));
            path[16]={t:1,...where};
            p.landmarks.push({...where,label:label.value||`point ${p.landmarks.length+1}`,enabled:true,strength:1,path});
            selected=p.landmarks.length-1;adding=false;selection(p);save(p);return;
        }
        const distance=key=>Math.hypot((key.x-where.x)*rect.w,(key.y-where.y)*rect.h);
        const active=p.landmarks[selected];
        if(active&&distance(active)<6)drag={index:selected,key:-1};
        else if(active) {
            const k=active.path.findIndex((key,i)=>i>0&&i<active.path.length-1&&distance(key)<8);
            if(k>=0)drag={index:selected,key:k};
        }
        if(!drag) {
            selected=p.landmarks.findIndex(point=>distance(point)<10);
            if(selected>=0)drag={index:selected,key:-1};
        }
        selection(p);draw();canvas.setPointerCapture(event.pointerId);
    };
    canvas.onpointermove=event=>{
        if(!drag)return;
        const where=eventPoint(event);if(!where)return;
        where.x=Math.max(0,Math.min(1,where.x));where.y=Math.max(0,Math.min(1,where.y));
        const p=plan(),point=p.landmarks[drag.index];
        if(drag.key>=0)Object.assign(point.path[drag.key],where);
        else {
            const dx=where.x-point.x,dy=where.y-point.y;
            if(point.path.some(k=>k.x+dx<0||k.x+dx>1||k.y+dy<0||k.y+dy>1))return;
            for(const key of point.path){key.x+=dx;key.y+=dy;}
            Object.assign(point,where);
        }
        save(p);
    };
    canvas.onpointerup=()=>{drag=null;};canvas.onpointercancel=()=>{drag=null;};
    for(const control of [label,enabled,strength])control.onchange=()=>{
        const p=plan(),point=p.landmarks?.[selected];if(!point)return;
        point.label=label.value;point.enabled=enabled.checked;point.strength=Number(strength.value);save(p);
    };
    timeline.oninput=draw;
    button(tools,'Add point',()=>{adding=true;status.textContent='Click the image to add a labeled point.';});
    button(tools,'Delete',()=>{const p=plan();if(selected<0)return;p.landmarks.splice(selected,1);selected=-1;save(p);selection(p);});
    button(tools,'Play paths',()=>{
        if(timer){clearInterval(timer);timer=null;return;}
        timer=setInterval(()=>{timeline.value=(Number(timeline.value)+.05/(plan().duration||6))%1;draw();},50);
    });
    button(controls,'Prepare points',()=>queue('prepare',node,status));
    button(controls,'Accept point review',async()=>{
        try {
            const p=checkSettings(node);
            const response=await api.fetchApi('/ambient-loop/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});
            const reviewed=await response.json();if(!response.ok)throw new Error(reviewed.error);
            widget(node,'plan_json').value=JSON.stringify(reviewed);persist(reviewed);status.textContent='Point review accepted. Render a candidate when ready.';
        }catch(error){status.textContent=error.message;}
    });
    button(controls,'Render',()=>queue('render',find('AmbientSaveCandidate'),status));
    const executed=node.onExecuted;
    node.onExecuted=function(message){
        executed?.apply(this,arguments);
        if(message.motion_plan){widget(node,'plan_json').value=JSON.stringify(message.motion_plan[0]);selected=-1;
            persist(message.motion_plan[0]);
            node.properties.ambient_source_image=widget(find('LoadImage')??{},'image')?.value;
            status.textContent=message.motion_plan[0].feedback.join(' ')||'Review and edit points, then accept point review.';}
        if(message.bg_image)background.src='data:image/png;base64,'+message.bg_image[0];draw();
    };
    const configured=node.onConfigure;
    node.onConfigure=function(){configured?.apply(this,arguments);
        const stored=app.graph.extra?.ambient_motion_plans?.[String(node.id)];
        if(!plan().schema&&stored)widget(node,'plan_json').value=JSON.stringify(stored);
        const load=find('LoadImage'),name=widget(load??{},'image')?.value;
        if(name)background.src=api.apiURL('/view?'+new URLSearchParams({filename:name,type:'input'}));
        status.textContent=plan().review?.state==='reviewed'?'Saved point review loaded. Inspect before rendering.':'Prepare or review saved points.';
    };
    const removed=node.onRemoved;
    node.onRemoved=function(){clearInterval(timer);removed?.apply(this,arguments);};
}

function previews(node,upscale=false) {
    const root=panel(node,390),status=element('p',root,'Render a candidate to preview continuous and seam playback.');
    const controls=element('div',root);
    if(upscale)button(controls,'Upscale',()=>queue('upscale',node,status));
    const row=element('div',root);row.style.display='flex';row.style.gap='8px';
    const videos=['Continuous playback','Loop seam'].map(text=>{
        const column=element('div',row);column.style.width='48%';element('p',column,text);
        return element('video',column);
    });
    for(const video of videos){video.controls=true;video.loop=true;video.muted=true;video.playsInline=true;video.style.width='100%';}
    const download=element('a',root,'Save silent MP4');download.style.color='#7ce7dc';download.style.display='none';download.download='';
    function show(paths,record) {
        videos.forEach((v,i)=>{v.src=viewURL(paths[i]);});download.href=viewURL(paths[0]);download.style.display='block';
        status.textContent=`${record.frame_count} frames · ${record.fps} FPS · ${record.dimensions.join(' × ')}. ${record.feedback?.join(' ')??''}`;
        // Save only preview metadata, not a render record containing past workflows.
        const summary={frame_count:record.frame_count,fps:record.fps,
                       dimensions:record.dimensions,feedback:record.feedback};
        node.properties.ambient_preview={paths,record:summary};
    }
    const executed=node.onExecuted;
    node.onExecuted=function(message){executed?.apply(this,arguments);
        if(message.preview_paths)show(message.preview_paths,message.render_handle[0]);};
    const configured=node.onConfigure;
    node.onConfigure=function(){configured?.apply(this,arguments);const saved=node.properties.ambient_preview;if(saved)show(saved.paths,saved.record);};
    node.ambientShowPreview=show;
}

function selector(node) {
    const root=panel(node,110),status=element('p',root,'Select a candidate saved on the persistent output volume.');
    button(root,'Refresh candidates',async()=>{
        try {
            const response=await api.fetchApi('/ambient-loop/candidates');const records=await response.json();
            const w=widget(node,'candidate');w.options.values=records.length?records:['Select a saved candidate'];
            if(!records.includes(w.value))w.value=records[0]??'Select a saved candidate';
            status.textContent=`${records.length} saved candidates available.`;
        }catch(error){status.textContent=error.message;}
    });
    button(root,'Preview selected',async()=>{
        try {
            const candidate=widget(node,'candidate').value;
            const response=await api.fetchApi('/ambient-loop/record?'+new URLSearchParams({candidate}));
            if(!response.ok)throw new Error(await response.text());const record=await response.json();
            const directory=candidate.substring(0,candidate.lastIndexOf('/'));
            const target=find('AmbientSaveCandidate');
            target?.ambientShowPreview([`ambient-loop/${directory}/loop.mp4`,`ambient-loop/${directory}/seam.mp4`],record);
        }catch(error){status.textContent=error.message;}
    });
}

app.registerExtension({name:'ambient-loop.staged',
    async setup(){
        const original=api.queuePrompt.bind(api);
        api.queuePrompt=async function(number,prompt){
            const classes=Object.values(prompt.output??{}).map(n=>n.class_type);
            if(classes.includes('AmbientUpscale')&&classes.includes('AmbientSaveCandidate')) {
                throw new Error('Use the separate Prepare, Render or Upscale buttons to queue one stage.');
            }
            if(classes.includes('AmbientSaveCandidate')&&Object.values(prompt.output).some(n=>n.class_type==='AmbientMotionEditor'&&n.inputs.stage==='prepare')) {
                throw new Error('Preparing points cannot start generation. Use Prepare points.');
            }
            return original(number,prompt);
        };
    },
    nodeCreated(node){
        const type=node.comfyClass??node.type;
        if(type==='AmbientMotionEditor')editor(node);
        if(type==='AmbientSaveCandidate')previews(node);
        if(type==='AmbientUpscale')previews(node,true);
        if(type==='AmbientSavedCandidate')selector(node);
    }
});
