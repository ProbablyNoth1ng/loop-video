"""Same-origin ComfyUI review and persistent-candidate browsing."""
from pathlib import Path

from .motion import review_plan
from .staged_comfy import output_root


def register_routes():
    from aiohttp import web
    from server import PromptServer

    @PromptServer.instance.routes.post('/ambient-loop/review')
    async def review(request):
        try:
            return web.json_response(review_plan(await request.json()))
        except (ValueError, KeyError, TypeError, IndexError) as error:
            return web.json_response({'error':str(error)},status=400)

    @PromptServer.instance.routes.get('/ambient-loop/candidates')
    async def candidates(request):
        root = output_root()
        records = sorted(p.relative_to(root).as_posix() for p in root.glob('candidate-*/record.json'))
        return web.json_response(records)

    @PromptServer.instance.routes.get('/ambient-loop/record')
    async def record(request):
        import json
        path = (output_root()/request.query.get('candidate','')).resolve()
        if not path.is_relative_to(output_root().resolve()) or path.name != 'record.json':
            raise web.HTTPBadRequest(text='Choose a saved candidate')
        try:
            return web.json_response(json.loads(path.read_text(encoding='utf-8')))
        except (OSError,ValueError):
            raise web.HTTPNotFound(text='Candidate record not found')
