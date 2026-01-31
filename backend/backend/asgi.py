"""
ASGI config for backend project.
"""

import os

# -----------------------------
# MUST set DJANGO_SETTINGS_MODULE before any Django imports
# -----------------------------
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from channels.auth import AuthMiddlewareStack
from chat.routing import websocket_urlpatterns

# Initialize Django ASGI app for HTTP handling
django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        # Keep AllowedHostsOriginValidator/AuthMiddlewareStack for safety in dev,
        # your consumer does JWT auth from querystring so this is optional.
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
