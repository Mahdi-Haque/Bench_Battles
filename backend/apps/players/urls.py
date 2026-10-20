"""URLs for Players app."""
from django.urls import path
from .views import GuestCreateView, GuestMeView

app_name = 'players'

urlpatterns = [
    path('guest/', GuestCreateView.as_view(), name='guest-create'),
    path('me/', GuestMeView.as_view(), name='guest-me'),
]
