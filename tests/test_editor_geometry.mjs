import test from 'node:test';
import assert from 'node:assert/strict';
import {imageRect, normalizedPoint} from '../comfy_nodes/comfy_ltx_loop/web/geometry.mjs';

test('portrait image maps content corners and rejects side letterboxing',()=>{
  const rect=imageRect(600,900,480,300);
  assert.deepEqual(rect,{x:140,y:0,w:200,h:300});
  const box={left:20,top:40,width:480,height:300};
  assert.deepEqual(normalizedPoint(160,40,box,rect,480,300),{x:0,y:0});
  assert.deepEqual(normalizedPoint(360,340,box,rect,480,300),{x:1,y:1});
  assert.equal(normalizedPoint(159,100,box,rect,480,300),null);
});

test('landscape image maps content corners with a scaled canvas',()=>{
  const rect=imageRect(900,600,480,300);
  assert.deepEqual(rect,{x:15,y:0,w:450,h:300});
  const box={left:20,top:40,width:240,height:150};
  assert.deepEqual(normalizedPoint(27.5,40,box,rect,480,300),{x:0,y:0});
  assert.deepEqual(normalizedPoint(252.5,190,box,rect,480,300),{x:1,y:1});
  assert.equal(normalizedPoint(20,100,box,rect,480,300),null);
});

test('CSS contain padding is excluded from pointer mapping',()=>{
  const rect=imageRect(600,900,480,300);
  const box={left:20,top:40,width:500,height:300};
  assert.deepEqual(normalizedPoint(170,40,box,rect,480,300),{x:0,y:0});
  assert.deepEqual(normalizedPoint(370,340,box,rect,480,300),{x:1,y:1});
  assert.equal(normalizedPoint(169,100,box,rect,480,300),null);
});
