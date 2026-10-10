from comfy_ltx_loop.comfy import NODE_CLASS_MAPPINGS, NODE_DISPLAY_NAME_MAPPINGS
from comfy_ltx_loop.comfy_routes import register_routes

WEB_DIRECTORY = './web'
register_routes()

__all__ = ['NODE_CLASS_MAPPINGS', 'NODE_DISPLAY_NAME_MAPPINGS', 'WEB_DIRECTORY']
