"""ASGI config for Bench Battles backend with Django Channels and WebSockets."""
import os
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Initialize Django ASGI application early to ensure the AppRegistry is populated
# before importing code that may import ORM models.
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter
from apps.players.ws_auth import GuestTokenAuthMiddlewareStack
import apps.rooms.routing

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': GuestTokenAuthMiddlewareStack(
        URLRouter(
            apps.rooms.routing.websocket_urlpatterns
        )
    ),
})
