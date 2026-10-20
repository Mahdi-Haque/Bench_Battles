"""WebSocket URL routing for rooms app."""
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'^ws/rooms/(?P<room_code>[0-9A-Za-z]+)/$', consumers.RoomConsumer.as_asgi()),
]
