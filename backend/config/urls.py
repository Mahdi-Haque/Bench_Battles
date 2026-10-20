"""Root URL Configuration for Bench Battles."""
from django.contrib import admin
from django.urls import include, path
from .views import HealthCheckView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/health/', HealthCheckView.as_view(), name='health-check'),
    path('api/players/', include('apps.players.urls', namespace='players')),
    path('api/rooms/', include('apps.rooms.urls', namespace='rooms')),
]
