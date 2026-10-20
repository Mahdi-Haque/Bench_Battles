from django.contrib import admin
from .models import GuestPlayer


@admin.register(GuestPlayer)
class GuestPlayerAdmin(admin.ModelAdmin):
    list_display = ('id', 'nickname', 'is_active', 'created_at', 'last_active_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('id', 'nickname')
    readonly_fields = ('id', 'token_hash', 'created_at', 'last_active_at')
