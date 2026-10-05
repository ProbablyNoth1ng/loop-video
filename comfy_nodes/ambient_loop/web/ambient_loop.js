import { app } from '../../../scripts/app.js';
import { api } from '../../../scripts/api.js';
import { stageGraph } from './stages.mjs';
import { imageRect, normalizedPoint } from './geometry.mjs';
import { installStageQueueControl, installUnsafePromptGuard, resolveStageTargets, isCurrentStageSelection, requireQueueSuccess } from './queue_control.mjs';

const widget = (node,name) => node.widgets?.find(w => w.name === name);
const nodes = () => graphNodes(app.rootGraph ?? app.graph);
const find = type => nodes().find(n => n.comfyClass === type || n.type === type);
const graphNodes = graph => graph?._nodes ?? graph?.nodes ?? [];
const portablePath = path => path.replaceAll('\\','/');
const viewURL = path => {
    const normalized=portablePath(path),split=normalized.lastIndexOf('/');
    return api.apiURL('/view?'+new URLSearchParams({
        filename:normalized.slice(split+1),subfolder:normalized.slice(0,Math.max(0,split)),type:'output'
    }));
};

async function queue(stage, target, status, expectedGraph) {
    try {
        if (!target) throw new Error('Load the Ambient Loop motion workflow first.');
        if(expectedGraph && !isCurrentStageSelection(app,expectedGraph,target,stage)) {
            throw new Error('Workflow changed or its target was removed. Reopen Run for the current workflow.');
        }
        console.info('[ambient-loop] queue', {stage,targetId:target.id,targetClass:target.comfyClass??target.type});
        if(stage==='render') {
            const editor=find('AmbientMotionEditor');
            checkSettings(editor);
            if(JSON.parse(widget(editor,'plan_json').value).review?.state!=='reviewed') {
                throw new Error('Review points and click Accept point review before Render.');
            }
        }
        let workflow, output;
        try { ({workflow,output} = await app.graphToPrompt()); }
        catch (error) { throw new Error(`${stage} workflow conversion failed: ${error.stack ?? error}`); }
        if(expectedGraph && !isCurrentStageSelection(app,expectedGraph,target,stage)) {
            throw new Error('Workflow changed or its target was removed. Reopen Run for the current workflow.');
        }
        if(stage==='render') {
            const editor=find('AmbientMotionEditor');
            checkSettings(editor);
            if(JSON.parse(widget(editor,'plan_json').value).review?.state!=='reviewed') {
                throw new Error('Review points and click Accept point review before Render.');
            }
        }
        console.info('[ambient-loop] converted', {stage,targetId:target.id,nodeCount:Object.keys(output).length});
        let selected;
        try { selected = stageGraph(output,target.id,stage); }
        catch (error) { throw new Error(`${stage} stage graph failed at target ${target.id}: ${error.message}`); }
        console.info('[ambient-loop] selected', {stage,targetId:target.id,nodes:Object.entries(selected).map(([id,node])=>({id,class_type:node.class_type}))});
        workflow.extra ??= {};
        workflow.extra.ambient_motion_plans = Object.fromEntries(nodes()
            .filter(n => widget(n,'plan_json')).map(n => [n.id,JSON.parse(widget(n,'plan_json').value)]));
        let result;
        try { result = await api.queuePrompt(0,{output:selected,workflow}); }
        catch (error) { throw new Error(`${stage} queue failed at target ${target.id}: ${error.message}`); }
        try { requireQueueSuccess(result); }
        catch (error) { throw new Error(`${stage} ${error.message}`); }
        status.textContent = `${stage} queued. Progress appears in ComfyUI.`;
        return true;
    } catch (error) {
        console.error('[ambient-loop] stage failed', {stage,targetId:target?.id,stack:error.stack});
        status.textContent = error.message;
        return false;
    }
}

let stageChooser;

function closeStageChooser() {
    if(!stageChooser)return;
    const {dialog,previous}=stageChooser;
    stageChooser=undefined;
    dialog.close?.();dialog.remove?.();previous?.focus?.();
}

function showReopenRunNotice() {
    const notice=document.createElement('p');
    notice.setAttribute('role','status');
    notice.textContent='Workflow changed. Reopen Run for the current workflow.';
    document.body.append(notice);
}

function showStageChooser(graph) {
    if(stageChooser) return;
    const previous=document.activeElement;
    const dialog=document.createElement('dialog');
    dialog.setAttribute('aria-label','Choose an Ambient Loop stage');
    const title=element('h2',dialog,'Choose an Ambient Loop stage');
    title.id='ambient-stage-title';dialog.setAttribute('aria-labelledby',title.id);
    const copy=element('p',dialog,'Prepare points, review them, then Render. Upscale uses a saved candidate. Each choice queues one stage.');
    copy.id='ambient-stage-copy';dialog.setAttribute('aria-describedby',copy.id);
    const status=element('p',dialog);status.setAttribute('role','status');
    const actions=element('div',dialog);
    const controls=[];let pending=false;
    const targets=resolveStageTargets(graph);
    const choose=(stage,label)=>{
        const state=targets[stage];
        const control=button(actions,label,async()=>{
            if(!state.target)return;
            if(!isCurrentStageSelection(app,graph,state.target,stage)) {
                closeStageChooser();showReopenRunNotice();return;
            }
            pending=true;
            controls.forEach(item=>item.disabled=true);
            const accepted=await queue(stage,state.target,status,graph);
            if(accepted)closeStageChooser();else {
                pending=false;
                controls.forEach(item=>item.disabled=item.dataset.stage ? !targets[item.dataset.stage]?.target : false);
            }
        });
        control.dataset.stage=stage;
        if(!state.target) { control.disabled=true;control.title=state.reason; }
        controls.push(control);
    };
    choose('prepare','Prepare points');choose('render','Render');choose('upscale','Upscale');
    const cancel=button(actions,'Cancel',closeStageChooser);controls.push(cancel);
    const reasons=Object.values(targets).map(state=>state.reason).filter(Boolean);
    if(reasons.length)status.textContent=reasons.join(' ');
    dialog.addEventListener('cancel',event=>{event.preventDefault();if(!pending)closeStageChooser();});
    document.body.append(dialog);stageChooser={dialog,previous};
    dialog.showModal?.();
    (controls.find(control=>!control.disabled)??cancel).focus?.();
}

function showAutoQueueNotice() {
    const notice=document.createElement('p');
    notice.setAttribute('role','status');
    notice.textContent='Ambient Loop auto-queue is paused. Use Run and choose one stage.';
    document.body.append(notice);
}

function checkSettings(node) {
    if(!node)throw new Error('Load the motion editor first.');
    const p=JSON.parse(widget(node,'plan_json').value);
    if(p.schema!=='ambient-motion-plan/1')throw new Error('Prepare a valid motion plan before Render.');
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
    const pointList=element('div',root);
    pointList.setAttribute('aria-label','Landmarks');
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
    let background=new Image(),selected=-1,adding=false,drag=null,timer=null,rect=null,reviewButton=null;
    function plan() { try { return JSON.parse(widget(node,'plan_json').value); } catch { return {}; } }
    function validPlan(p) {
        return p?.schema==='ambient-motion-plan/1' && Array.isArray(p.landmarks) &&
            Array.isArray(p.requested) && Array.isArray(p.source_size) &&
            Array.isArray(p.transform?.canvas) && Number.isInteger(p.frames) &&
            p.landmarks.every(point=>point && typeof point.label==='string' && point.label.trim() &&
                Number.isFinite(point.x) && point.x>=0 && point.x<=1 &&
                Number.isFinite(point.y) && point.y>=0 && point.y<=1 &&
                typeof point.enabled==='boolean' && Number.isFinite(point.strength) &&
                Array.isArray(point.path) && point.path.length>=2 &&
                point.path.every(key=>key && Number.isFinite(key.t) &&
                    Number.isFinite(key.x) && Number.isFinite(key.y)));
    }
    function save(p) {
        p.review={state:'pending'};
        widget(node,'plan_json').value=JSON.stringify(p);
        persist(p);
        status.textContent='Points changed. Review trajectories and click Accept point review.';
        app.graph.setDirtyCanvas(true,true);pathSelection();draw();renderList();
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
        renderList();
    }
    function renderList() {
        pointList.replaceChildren();
        const current=plan(),points=current.landmarks;
        if(reviewButton)reviewButton.disabled=!validPlan(current)||!points.some(point=>point.enabled);
        if(!validPlan(current)) {
            element('p',pointList,'No valid motion plan. Run Prepare points.');
            return;
        }
        if(!points.length) {
            element('p',pointList,'No landmarks yet. Click Add point, then click the image. Review requires at least one enabled point.');
            return;
        }
        for(const [index,point] of points.entries()) {
            const row=button(pointList,`${index+1}. ${point.label} (${point.x.toFixed(3)}, ${point.y.toFixed(3)}) · ${point.enabled?'enabled':'disabled'}`,()=>{
                selected=index;selection(plan());draw();
            });
            row.setAttribute('aria-label',`Select landmark ${index+1}: ${point.label}`);
            Object.assign(row.style,{display:'block',width:'100%',textAlign:'left',padding:'5px',
                color:point.enabled?'#a7ff69':'#aaa',background:index===selected?'#315119':'#202831',
                border:index===selected?'2px solid #a7ff69':'1px solid #56606c'});
        }
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
        rect=imageRect(background.naturalWidth,background.naturalHeight,480,300);
        ctx.drawImage(background,rect.x,rect.y,rect.w,rect.h);
        const p=plan();
        if(!validPlan(p))return;
        for(const [index,point] of (p.landmarks??[]).entries()) {
            const project=(x,y)=>[rect.x+x*rect.w,rect.y+y*rect.h];
            ctx.strokeStyle=point.enabled?'#a7ff69':'#777';ctx.fillStyle=point.enabled?'#a7ff69':'#999';
            ctx.globalAlpha=1;ctx.beginPath();
            for(const [k,key] of point.path.entries()) {
                const xy=project(point.x+(key.x-point.x)*point.strength,point.y+(key.y-point.y)*point.strength);
                if(k===0)ctx.moveTo(...xy);else ctx.lineTo(...xy);
            }
            ctx.stroke();
            if(index===selected)for(const key of point.path.slice(1,-1)) {
                const [x,y]=project(key.x,key.y);ctx.strokeRect(x-3,y-3,6,6);
            }
            const [x,y]=project(point.x,point.y);ctx.beginPath();ctx.arc(x,y,index===selected?8:6,0,Math.PI*2);
            ctx.lineWidth=3;ctx.strokeStyle='#101710';ctx.stroke();ctx.fill();
            if(index===selected){ctx.beginPath();ctx.arc(x,y,10,0,Math.PI*2);ctx.strokeStyle='#fff';ctx.lineWidth=2;ctx.stroke();}
            ctx.font='bold 13px system-ui';ctx.lineWidth=3;ctx.strokeStyle='#101710';
            ctx.strokeText(point.label,x+10,y-8);ctx.fillText(point.label,x+10,y-8);
            const moving=position(point.path,Number(timeline.value));
            const [mx,my]=project(point.x+(moving.x-point.x)*point.strength,point.y+(moving.y-point.y)*point.strength);
            ctx.beginPath();ctx.arc(mx,my,3,0,Math.PI*2);ctx.fill();
        }
        ctx.globalAlpha=1;
    }
    background.onload=draw;
    function eventPoint(event) {
        const box=canvas.getBoundingClientRect();
        return normalizedPoint(event.clientX,event.clientY,box,rect,480,300);
    }
    canvas.onpointerdown=event=>{
        const p=plan(),where=eventPoint(event);
        if(!where||!validPlan(p))return;
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
    reviewButton=button(controls,'Accept point review',async()=>{
        try {
            const p=checkSettings(node);
            const response=await api.fetchApi('/ambient-loop/review',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(p)});
            const reviewed=await response.json();if(!response.ok)throw new Error(reviewed.error);
            widget(node,'plan_json').value=JSON.stringify(reviewed);persist(reviewed);renderList();status.textContent='Point review accepted. Render a candidate when ready.';
        }catch(error){status.textContent=error.message;}
    });
    button(controls,'Render',()=>queue('render',find('AmbientSaveCandidate'),status));
    const executed=node.onExecuted;
    node.onExecuted=function(message){
        executed?.apply(this,arguments);
        const incoming=message?.motion_plan?.[0];
        if(!validPlan(incoming)) {
            widget(node,'plan_json').value='{}';
            delete app.graph.extra?.ambient_motion_plans?.[String(node.id)];
            delete node.properties.ambient_source_image;
            selected=-1;selection({});
            background=new Image();background.onload=draw;rect=null;draw();
            app.graph.setDirtyCanvas(true,true);
            status.textContent='Prepare returned an invalid motion plan. Retry Prepare or inspect the backend log.';
            return;
        }
        widget(node,'plan_json').value=JSON.stringify(incoming);selected=-1;
        persist(incoming);selection(incoming);
        node.properties.ambient_source_image=widget(find('LoadImage')??{},'image')?.value;
        status.textContent=(Array.isArray(incoming.feedback)?incoming.feedback:[]).join(' ')||(incoming.landmarks.length
            ?'Review and edit points, then accept point review.'
            :'No landmarks proposed. Add at least one point manually before review.');
        if(message.bg_image)background.src='data:image/png;base64,'+message.bg_image[0];draw();
    };
    const configured=node.onConfigure;
    node.onConfigure=function(){configured?.apply(this,arguments);
        const stored=app.graph.extra?.ambient_motion_plans?.[String(node.id)];
        if(!plan().schema&&stored)widget(node,'plan_json').value=JSON.stringify(stored);
        const load=find('LoadImage'),name=widget(load??{},'image')?.value;
        if(name)background.src=api.apiURL('/view?'+new URLSearchParams({filename:name,type:'input'}));
        renderList();
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
    for(const video of videos){
        video.controls=true;video.loop=true;video.muted=true;video.autoplay=true;
        video.playsInline=true;video.preload='auto';video.style.width='100%';
        video.onerror=()=>{status.textContent='Video preview failed to load. Check that the saved MP4 is available, then refresh candidates.';};
    }
    const download=element('a',root,'Save silent MP4');download.style.color='#7ce7dc';download.style.display='none';download.download='';
    function show(paths,record) {
        paths=paths.map(portablePath);
        status.textContent=`${record.frame_count} frames · ${record.fps} FPS · ${record.dimensions.join(' × ')}. ${record.feedback?.join(' ')??''}`;
        videos.forEach((video,i)=>{
            video.src=viewURL(paths[i]);video.load();
            video.play()?.catch(error=>{
                if(error.name==='NotAllowedError')status.textContent='Automatic playback was blocked by the browser. Use the player controls to play.';
            });
        });
        download.href=viewURL(paths[0]);download.style.display='block';
        // Save only preview metadata, not a render record containing past workflows.
        const summary={frame_count:record.frame_count,fps:record.fps,
                       dimensions:record.dimensions,feedback:record.feedback};
        node.properties.ambient_preview={paths,record:summary};
    }
    const executed=node.onExecuted;
    node.onExecuted=function(message){executed?.apply(this,arguments);
        if(message.preview_paths) {
            show(message.preview_paths,message.render_handle[0]);
            if(!upscale) {
                const path=portablePath(message.preview_paths[0]);
                const candidate=path.slice('ambient-loop/'.length,path.lastIndexOf('/'))+'/record.json';
                for(const selector of nodes().filter(n=>(n.comfyClass??n.type)==='AmbientSavedCandidate')) {
                    selector.ambientSelectCandidate?.(candidate);
                }
            }
        }};
    const configured=node.onConfigure;
    node.onConfigure=function(){configured?.apply(this,arguments);const saved=node.properties.ambient_preview;if(saved)show(saved.paths,saved.record);};
    node.ambientShowPreview=show;
    const removed=node.onRemoved;
    node.onRemoved=function(){videos.forEach(video=>video.pause());removed?.apply(this,arguments);};
}

function selector(node) {
    const root=panel(node,110),status=element('p',root,'The last render is selected for upscale. Choose another saved candidate to preview it.');
    const choice=widget(node,'candidate');
    let revision=0,removed=false;
    function select(candidate) {
        revision++;
        candidate=portablePath(candidate);
        choice.options.values=[candidate,...(choice.options.values??[])
            .filter(value=>value!==candidate&&value!=='Select a saved candidate')];
        choice.value=candidate;
        status.textContent=`Selected ${candidate.split('/')[0]} for upscale.`;
        app.graph.setDirtyCanvas(true,true);
    }
    async function previewSelected() {
        const current=++revision,candidate=portablePath(choice.value);
        if(candidate==='Select a saved candidate')return;
        try {
            const response=await api.fetchApi('/ambient-loop/record?'+new URLSearchParams({candidate}));
            if(!response.ok)throw new Error(await response.text());const record=await response.json();
            if(removed||current!==revision)return;
            const directory=candidate.substring(0,candidate.lastIndexOf('/'));
            const target=find('AmbientSaveCandidate');
            target?.ambientShowPreview([`ambient-loop/${directory}/loop.mp4`,`ambient-loop/${directory}/seam.mp4`],record);
            status.textContent=`Selected ${directory} for upscale.`;
        }catch(error){if(!removed&&current===revision)status.textContent=error.message;}
    }
    async function refresh() {
        const current=++revision;
        try {
            const response=await api.fetchApi('/ambient-loop/candidates');
            if(!response.ok)throw new Error(await response.text());
            const records=(await response.json()).map(portablePath);
            if(removed||current!==revision)return;
            choice.options.values=records.length?records:['Select a saved candidate'];
            choice.value=portablePath(choice.value);
            if(!records.includes(choice.value))choice.value=records[0]??'Select a saved candidate';
            app.graph.setDirtyCanvas(true,true);
            status.textContent=records.length?`${records.length} saved candidates available.`:'No completed renders yet. Render a candidate first.';
            await previewSelected();
        }catch(error){if(!removed&&current===revision)status.textContent=error.message;}
    }
    button(root,'Refresh candidates',refresh);
    const changed=choice.callback;
    choice.callback=function(){changed?.apply(this,arguments);return previewSelected();};
    node.ambientSelectCandidate=select;
    const configured=node.onConfigure;
    node.onConfigure=function(){configured?.apply(this,arguments);void refresh();};
    const onRemoved=node.onRemoved;
    node.onRemoved=function(){removed=true;revision++;onRemoved?.apply(this,arguments);};
    void refresh();
}

app.registerExtension({name:'ambient-loop.staged',
    async setup(){
        installUnsafePromptGuard(api);
        installStageQueueControl(app,showStageChooser,showAutoQueueNotice);
    },
    nodeCreated(node){
        const type=node.comfyClass??node.type;
        if(type==='AmbientMotionEditor')editor(node);
        if(type==='AmbientSaveCandidate')previews(node);
        if(type==='AmbientUpscale')previews(node,true);
        if(type==='AmbientSavedCandidate')selector(node);
    }
});
