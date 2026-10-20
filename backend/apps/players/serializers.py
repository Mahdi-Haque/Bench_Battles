"""Serializers for Guest Players."""
from rest_framework import serializers
from .models import GuestPlayer, nickname_validator


class GuestCreateRequestSerializer(serializers.Serializer):
    """Input serializer for guest creation."""
    nickname = serializers.CharField(
        max_length=32,
        min_length=2,
        required=False,
        allow_blank=False,
        validators=[nickname_validator],
        help_text='Optional display name. If omitted, an auto-generated nickname is assigned.'
    )


class GuestCreateResponseSerializer(serializers.ModelSerializer):
    """
    Response serializer returned ONLY upon guest creation.
    Delivers the raw session token to the client.
    """
    token = serializers.CharField(
        read_only=True,
        help_text='Secret session token. Store locally in client. Never shown again.'
    )

    class Meta:
        model = GuestPlayer
        fields = ['id', 'nickname', 'token', 'created_at']
        read_only_fields = ['id', 'nickname', 'token', 'created_at']


class GuestProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for the authenticated player's own profile.
    Allows updating nickname while strictly excluding credentials.
    """
    nickname = serializers.CharField(
        max_length=32,
        min_length=2,
        validators=[nickname_validator]
    )

    class Meta:
        model = GuestPlayer
        fields = ['id', 'nickname', 'created_at', 'last_active_at']
        read_only_fields = ['id', 'created_at', 'last_active_at']


class PublicPlayerSerializer(serializers.ModelSerializer):
    """
    Safe public representation of a player shown to opponents or room members.
    Never exposes internal timestamps, credentials, or token hashes.
    """
    class Meta:
        model = GuestPlayer
        fields = ['id', 'nickname']
        read_only_fields = ['id', 'nickname']
