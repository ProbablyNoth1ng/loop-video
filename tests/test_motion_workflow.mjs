import fs from 'node:fs';
import test from 'node:test';
import assert from 'node:assert/strict';

const official=JSON.parse(fs.readFileSync('workflows/ltx-2.5-motion-track.official.json','utf8'));
const adapted=JSON.parse(fs.readFileSync('workflows/ambient-motion.json','utf8'));
test('Official generation, guide injection and decode remain unchanged',()=>{
  for(const name of ['Load Models','Sampler - Distilled (8 steps)','Preprocess','Decode']) {
    assert.deepEqual(adapted.definitions.subgraphs.find(s=>s.name===name),
                     official.definitions.subgraphs.find(s=>s.name===name));
  }
});
test('Every top-level socket link is consistent',()=>{
  for(const [id,source,slot,target,input] of adapted.links) {
    assert.ok(adapted.nodes.find(n=>n.id===source).outputs[slot].links.includes(id));
    assert.equal(adapted.nodes.find(n=>n.id===target).inputs[input].link,id);
  }
});
test('Preparation uses original image and saved selection has no generation links',()=>{
  const editor=adapted.nodes.find(n=>n.type==='AmbientMotionEditor');
  const link=adapted.links.find(l=>l[0]===editor.inputs[0].link);
  assert.equal(adapted.nodes.find(n=>n.id===link[1]).type,'LoadImage');
  const selector=adapted.nodes.find(n=>n.type==='AmbientSavedCandidate');
  assert.equal(selector.inputs.length,0);
  const upscale=adapted.nodes.find(n=>n.type==='AmbientUpscale');
  assert.equal(adapted.links.find(l=>l[0]===upscale.inputs[0].link)[1],selector.id);
});
test('Recorded canvas bypasses official resizes',()=>{
  const input=adapted.definitions.subgraphs.find(s=>s.name==='Input Parameters');
  assert.equal(input.nodes.some(n=>n.type==='ResizeImageMaskNode'),false);
  const link=input.links.find(l=>l.target_id===-20&&l.target_slot===1);
  assert.equal(link.origin_id,-10);assert.equal(link.origin_slot,2);
});
