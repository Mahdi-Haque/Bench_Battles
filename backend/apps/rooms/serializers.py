"""Serializers for Game Rooms."""
from rest_framework import serializers
from apps.players.serializers import PublicPlayerSerializer
from .models import MembershipRole, Room, RoomMembership, RoomStatus


class RoomMemberSerializer(serializers.ModelSerializer):
    """Represents a member inside a room using safe public player profiles."""
    player = PublicPlayerSerializer(read_only=True)

    class Meta:
        model = RoomMembership
        fields = ['id', 'player', 'role', 'joined_at', 'is_active']
        read_only_fields = ['id', 'player', 'role', 'joined_at', 'is_active']


class RoomListSerializer(serializers.ModelSerializer):
    """
    Representation of rooms for public directory listings.
    Excludes private credentials and internal details.
    """
    current_players = serializers.SerializerMethodField()
    host = PublicPlayerSerializer(read_only=True)

    class Meta:
        model = Room
        fields = [
            'code',
            'name',
            'host',
            'status',
            'is_private',
            'max_players',
            'current_players',
            'created_at',
        ]
        read_only_fields = fields

    def get_current_players(self, obj: Room) -> int:
        return obj.active_players_count()


class RoomDetailSerializer(serializers.ModelSerializer):
    """
    Detailed room information including active member list and host info.
    Strictly excludes passcode hashes.
    """
    current_players = serializers.SerializerMethodField()
    host = PublicPlayerSerializer(read_only=True)
    members = serializers.SerializerMethodField()

    class Meta:
        model = Room
        fields = [
            'code',
            'name',
            'host',
            'status',
            'is_private',
            'max_players',
            'current_players',
            'members',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_current_players(self, obj: Room) -> int:
        return obj.active_players_count()

    def get_members(self, obj: Room):
        active_members = obj.memberships.filter(is_active=True).select_related('player')
        return RoomMemberSerializer(active_members, many=True).data


class RoomCreateSerializer(serializers.Serializer):
    """Input serializer for room creation."""
    name = serializers.CharField(
        max_length=64,
        min_length=2,
        help_text='Name / title of the room.'
    )
    is_private = serializers.BooleanField(
        default=False,
        help_text='Whether room requires a passcode to join.'
    )
    passcode = serializers.CharField(
        max_length=32,
        min_length=4,
        required=False,
        write_only=True,
        help_text='Required if is_private is true. Minimum 4 characters.'
    )
    max_players = serializers.IntegerField(
        min_value=2,
        max_value=10,
        default=2,
        help_text='Maximum allowed players (2 to 10).'
    )

    def validate(self, attrs):
        is_private = attrs.get('is_private', False)
        passcode = attrs.get('passcode')

        if is_private and not passcode:
            raise serializers.ValidationError({
                'passcode': 'A passcode of at least 4 characters is required for private rooms.'
            })
        return attrs


class RoomJoinSerializer(serializers.Serializer):
    """Input serializer for joining a room."""
    passcode = serializers.CharField(
        max_length=32,
        required=False,
        allow_blank=True,
        write_only=True,
        help_text='Passcode if joining a private room.'
    )
