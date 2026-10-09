import test from 'node:test';
import assert from 'node:assert/strict';
import {stageGraph} from '../comfy_nodes/ambient_loop/web/stages.mjs';

const graph = {
  1:{class_type:'LoadImage', inputs:{image:'anime.png'}},
  2:{class_type:'AmbientMotionEditor',inputs:{image:['1',0],stage:'render'}},
  3:{class_type:'UNETLoader',inputs:{}},
  4:{class_type:'Sampler',inputs:{model:['3',0],image:['2',0]}},
  5:{class_type:'AmbientSaveCandidate',inputs:{video:['4',0],motion_plan:['2',2]}},
  6:{class_type:'AmbientSavedCandidate',inputs:{candidate:'candidate-42/record.json'}},
  7:{class_type:'AmbientUpscale',inputs:{candidate:['6',0]}}
};
test('Prepare excludes generation and finishing',()=>{
  const result=stageGraph(graph,2,'prepare');
  assert.deepEqual(Object.keys(result),['1','2']);
  assert.equal(result[2].inputs.stage,'prepare');
  assert.equal(graph[2].inputs.stage,'render');
});
test('Render excludes finishing',()=>assert.deepEqual(Object.keys(stageGraph(graph,5,'render')),['1','2','3','4','5']));
test('Upscale uses only disk selection',()=>assert.deepEqual(Object.keys(stageGraph(graph,7,'upscale')),['6','7']));
test('new finishing node uses only saved candidate and rejects render ancestors',()=>{
  const next=structuredClone(graph);
  next[8]={class_type:'AmbientFinish',inputs:{candidate:['6',0],resolution:'1080p',method:'fast'}};
  assert.deepEqual(Object.keys(stageGraph(next,8,'upscale')),['6','8']);
  next[8].inputs.candidate=['5',0];
  assert.throws(()=>stageGraph(next,8,'upscale'),/saved candidate/i);
  next[8].inputs.candidate=['7',0];
  assert.throws(()=>stageGraph(next,8,'upscale'),/saved candidate/i);
  delete next[8].inputs.candidate;
  assert.throws(()=>stageGraph(next,8,'upscale'),/saved candidate/i);
  assert.deepEqual(Object.keys(stageGraph(next,5,'render')),['1','2','3','4','5']);
});
test('Unsafe stage connections fail before queueing',()=>{
  assert.throws(()=>stageGraph(graph,5,'prepare'));
  const bad=structuredClone(graph);bad[7].inputs.candidate=['5',0];
  assert.throws(()=>stageGraph(bad,7,'upscale'));
});
test('Stage target has the expected output class',()=>{
  assert.throws(()=>stageGraph(graph,5,'prepare'),/target.*AmbientMotionEditor/i);
  assert.throws(()=>stageGraph(graph,2,'render'),/target.*AmbientSaveCandidate/i);
  assert.throws(()=>stageGraph(graph,6,'upscale'),/target.*AmbientUpscale/i);
});
test('Dangling upstream references fail before queueing',()=>{
  const bad=structuredClone(graph);bad[5].inputs.video=['99',0];
  assert.throws(()=>stageGraph(bad,5,'render'),/missing.*99/i);
});
