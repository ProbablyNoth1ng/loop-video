import json
import time
import uuid
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

from .project import atomic_json, sha


def request(base, route, body=None):
    data = json.dumps(body).encode() if body is not None else None
    with urlopen(Request(base.rstrip('/') + route, data=data,
                         headers={'Content-Type': 'application/json'}), timeout=30) as response:
        return json.load(response)


def submit(graph_path, receipt, base):
    graph_path, receipt = Path(graph_path), Path(receipt)
    if receipt.exists():
        old = json.loads(receipt.read_text())
        if old['graph_hash'] != sha(graph_path) or old['server'] != base:
            raise ValueError('Queue receipt belongs to different graph/server')
        return old
    graph = json.loads(graph_path.read_text())
    client = str(uuid.uuid4())
    # Persist intent before submitting; uncertain responses must never be retried blindly.
    record = {'server': base, 'graph_hash': sha(graph_path), 'client_id': client,
              'state': 'submission_pending'}
    atomic_json(receipt, record)
    response = request(base, '/prompt', {'prompt': graph, 'client_id': client})
    if response.get('node_errors') or not response.get('prompt_id'):
        record.update(state='rejected', response=response)
    else:
        record.update(state='queued', prompt_id=response['prompt_id'])
    atomic_json(receipt, record)
    return record


def status(receipt):
    receipt = Path(receipt)
    record = json.loads(receipt.read_text())
    if 'prompt_id' not in record:
        raise ValueError('Submission response uncertain/rejected; inspect server queue before taking further action')
    response = request(record['server'], '/history/' + record['prompt_id'])
    entry = response.get(record['prompt_id'])
    if entry:
        record.update(history=entry, state='completed' if entry.get('status', {}).get('status_str') == 'success' else 'failed')
        atomic_json(receipt, record)
    return record
