from django.contrib import admin
from .models import Room, RoomMembership


class RoomMembershipInline(admin.TabularInline):
    model = RoomMembership
    extra = 0
    readonly_fields = ('joined_at', 'left_at')


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'status', 'is_private', 'max_players', 'host', 'created_at')
    list_filter = ('status', 'is_private', 'created_at')
    search_fields = ('code', 'name', 'host__nickname')
    readonly_fields = ('id', 'code', 'created_at', 'updated_at')
    inlines = [RoomMembershipInline]


@admin.register(RoomMembership)
class RoomMembershipAdmin(admin.ModelAdmin):
    list_display = ('room', 'player', 'role', 'is_active', 'joined_at', 'left_at')
    list_filter = ('role', 'is_active', 'joined_at')
    search_fields = ('room__code', 'player__nickname')
    readonly_fields = ('joined_at', 'left_at')
