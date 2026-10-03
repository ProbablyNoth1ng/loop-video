"""Run an exported official API graph unchanged and record actual cloud evidence.

Run on the ComfyUI host after installation. An existing record is never reused.
"""
import argparse
import json
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from ambient_loop.project import atomic_json, sha


def command(args):
    return subprocess.check_output(args,text=True).strip()


def gpu_snapshot():
    lines = command(['nvidia-smi','--query-gpu=name,uuid,memory.used,memory.total,driver_version',
                     '--format=csv,noheader,nounits']).splitlines()
    return [dict(zip(('name','uuid','used_mib','total_mib','driver'),
                     [part.strip() for part in line.split(',')])) for line in lines]


def request(base,path,payload=None):
    req = Request(base.rstrip('/')+path,
                  data=json.dumps(payload).encode() if payload is not None else None,
                  headers={'Content-Type':'application/json'})
    with urlopen(req,timeout=30) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--comfy',required=True,type=Path)
    parser.add_argument('--api-graph',required=True,type=Path)
    parser.add_argument('--image-digest',required=True)
    parser.add_argument('--record',required=True,type=Path)
    parser.add_argument('--server',default='http://127.0.0.1:8188')
    parser.add_argument('--timeout',type=int,default=3600)
    args = parser.parse_args()
    if args.record.exists():
        parser.error('Record exists. Reconcile queue/history; choose a new record for a new run.')
    graph = json.loads(args.api_graph.read_text(encoding='utf-8'))
    if not isinstance(graph,dict) or not graph or any('class_type' not in node for node in graph.values()):
        parser.error('Export the official workflow in API format')
    if any(node['class_type'].startswith('Ambient') for node in graph.values()):
        parser.error('Baseline requires the unchanged official workflow, without Ambient nodes')
    comfy = args.comfy.resolve()
    official = Path(__file__).resolve().parents[1]/'workflows/ltx-2.5-motion-track.official.json'
    record = {'state':'submission_intent','client_id':str(uuid.uuid4()),
              'started_at':datetime.now(timezone.utc).isoformat(),
              'image_digest':args.image_digest,'api_graph_sha256':sha(args.api_graph),
              'official_workflow_sha256':sha(official),
              'comfy_revision':command(['git','-C',str(comfy),'rev-parse','HEAD']),
              'ltx_revision':command(['git','-C',str(comfy/'custom_nodes/ComfyUI-LTXVideo'),'rev-parse','HEAD']),
              'pip_freeze':command(['python','-m','pip','freeze']).splitlines(),
              'gpu':gpu_snapshot(), 'models':{}}
    for path in sorted((comfy/'models').rglob('*')):
        if path.is_file() and path.suffix in ('.safetensors','.pth','.bin','.json'):
            record['models'][str(path.relative_to(comfy))] = sha(path)
    atomic_json(args.record,record)
    started = time.monotonic()
    try:
        response = request(args.server,'/prompt',{'prompt':graph,'client_id':record['client_id']})
    except Exception as error:
        record.update(state='submission_uncertain',error=str(error))
        atomic_json(args.record,record)
        raise
    record.update(state='queued',prompt_id=response['prompt_id'],queue_response=response)
    atomic_json(args.record,record)
    peaks = {gpu['uuid']:int(gpu['used_mib']) for gpu in record['gpu']}
    try:
        while time.monotonic()-started < args.timeout:
            for gpu in gpu_snapshot():
                peaks[gpu['uuid']] = max(peaks.get(gpu['uuid'],0),int(gpu['used_mib']))
            history = request(args.server,'/history/'+record['prompt_id'])
            if record['prompt_id'] in history:
                result = history[record['prompt_id']]
                status = result.get('status',{})
                record.update(history=result,state='passed' if status.get('status_str')=='success' else 'failed',
                              wall_seconds_including_queue=time.monotonic()-started,
                              sampled_total_gpu_memory_peak_mib=peaks)
                atomic_json(args.record,record)
                print(f"{record['state']}: {args.record}")
                return 0 if record['state']=='passed' else 1
            time.sleep(1)
        record.update(state='timeout_reconcile_history',sampled_total_gpu_memory_peak_mib=peaks)
        atomic_json(args.record,record)
        return 1
    except Exception as error:
        record.update(state='observation_interrupted_reconcile_history',error=str(error))
        atomic_json(args.record,record)
        raise


if __name__=='__main__':
    raise SystemExit(main())
