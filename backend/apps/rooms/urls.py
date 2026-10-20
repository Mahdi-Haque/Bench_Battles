"""URLs for Rooms app."""
from django.urls import path
from .views import (
    RoomDetailView,
    RoomJoinView,
    RoomLeaveView,
    RoomListCreateView,
)

app_name = 'rooms'

urlpatterns = [
    path('', RoomListCreateView.as_view(), name='room-list-create'),
    path('<str:room_code>/', RoomDetailView.as_view(), name='room-detail'),
    path('<str:room_code>/join/', RoomJoinView.as_view(), name='room-join'),
    path('<str:room_code>/leave/', RoomLeaveView.as_view(), name='room-leave'),
]
