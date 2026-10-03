import argparse
import json
import sys
from pathlib import Path

from .project import Project, approve, atomic_json
from .jobs import render, accept


def main():
    parser = argparse.ArgumentParser(prog='ambient-loop')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('examples')
    p.add_argument('destination')
    p = sub.add_parser('validate')
    p.add_argument('project')
    p = sub.add_parser('approve')
    p.add_argument('project')
    p.add_argument('stage', choices=['masks', 'motion'])
    p.add_argument('--reviewer', required=True)
    p.add_argument('--reviewed', action='store_true', required=True)
    for cmd in ('render', 'preview'):
        p = sub.add_parser(cmd)
        p.add_argument('project')
        p.add_argument('output')
        p.add_argument('--chunk-size', type=int, default=4)
    p = sub.add_parser('accept')
    p.add_argument('output')
    p.add_argument('--reviewer', required=True)
    p.add_argument('--visually-reviewed', action='store_true', required=True)
    p = sub.add_parser('batch')
    p.add_argument('batch_file', help='JSON list of {project, output}')
    p = sub.add_parser('graphs')
    p.add_argument('project')
    p.add_argument('destination')
    p.add_argument('--output', default='/workspace/ambient-loop/outputs/loop')
    p.add_argument('--project-path', help='Override project path for the target ComfyUI host')
    p = sub.add_parser('benchmark')
    p.add_argument('project')
    p.add_argument('destination')
    p.add_argument('--transfer-to', required=True)
    p = sub.add_parser('environment')
    p.add_argument('action', choices=['record', 'check'])
    p.add_argument('--comfy', required=True)
    p.add_argument('--lock', required=True)
    p.add_argument('--image-digest')
    p = sub.add_parser('regional')
    p.add_argument('action', choices=['prepare', 'candidate', 'finish'])
    p.add_argument('project')
    p.add_argument('accepted_a')
    p.add_argument('destination')
    p.add_argument('--reviewer')
    p.add_argument('--seed', type=int, choices=[42, 43, 44])
    p.add_argument('--raw-frames')
    p = sub.add_parser('submit')
    p.add_argument('graph')
    p.add_argument('receipt')
    p.add_argument('--server', default='http://127.0.0.1:8188')
    p = sub.add_parser('status')
    p.add_argument('receipt')
    p = sub.add_parser('cache-weight')
    p.add_argument('url')
    p.add_argument('destination')
    p.add_argument('--sha256', required=True)
    args = parser.parse_args()
    try:
        if args.command == 'examples':
            from .examples import create_examples
            create_examples(args.destination)
            result = {'examples': args.destination, 'approved': False}
        elif args.command == 'validate':
            p = Project.load(args.project)
            result = {'hash': p.fingerprint, 'working_size': p.working_size,
                      'output_size': p.output_size, 'frames': p.frames, 'upscale': p.upscale}
        elif args.command == 'approve':
            approve(args.project, args.stage, args.reviewer)
            result = {'approved': args.stage}
        elif args.command in ('render', 'preview'):
            p = Project.load(args.project)
            preview = args.command == 'preview'
            sizes = None
            if preview:
                from .project import dimensions
                sizes = (dimensions(p.source_size, 360), dimensions(p.source_size, 360))
            result = render(p, args.output, chunk_size=args.chunk_size, sizes=sizes, preview=preview)
        elif args.command == 'accept':
            accept(args.output, args.reviewer)
            result = {'state': 'accepted'}
        elif args.command == 'batch':
            entries = json.loads(Path(args.batch_file).read_text())
            projects = [(Project.load(e['project']), e['output']) for e in entries]
            for p, _ in projects:
                p.require_approvals()
            result = []
            for p, out in projects:
                try:
                    result.append(render(p, out))
                except Exception as error:
                    result.append({'project': str(p.path), 'error': str(error), 'state': 'failed'})
        elif args.command == 'graphs':
            from .comfy import export_graphs
            export_graphs(args.project, args.destination, args.output, args.project_path)
            result = {'graphs': args.destination}
        elif args.command == 'benchmark':
            from .benchmark import benchmark
            result = benchmark(args.project, args.destination, args.transfer_to)
        elif args.command == 'environment':
            from .environment import environment
            result = environment(args.action, args.comfy, args.lock, args.image_digest)
        elif args.command == 'submit':
            from .queue import submit
            result = submit(args.graph, args.receipt, args.server)
        elif args.command == 'status':
            from .queue import status
            result = status(args.receipt)
        elif args.command == 'cache-weight':
            from .assets import cache_weight
            result = cache_weight(args.url, args.destination, args.sha256)
        else:
            from .regional import prepare, candidate, finish
            if args.action == 'prepare':
                result = prepare(args.project, args.accepted_a, args.destination)
            elif args.action == 'candidate':
                result = candidate(args.project, args.accepted_a, args.destination, args.reviewer)
            else:
                if args.seed is None or not args.raw_frames:
                    raise ValueError('Regional finish requires --seed and --raw-frames')
                result = finish(args.project, args.accepted_a, args.destination, args.seed, args.raw_frames)
        if isinstance(result, dict) and 'frame_hashes' in result:
            result = {k: v for k, v in result.items() if k not in ('frame_hashes', 'assets', 'artifacts')}
        print(json.dumps(result, indent=2))
    except (ValueError, OSError, RuntimeError) as error:
        parser.exit(1, f'ambient-loop: {error}\n')


if __name__ == '__main__':
    main()
