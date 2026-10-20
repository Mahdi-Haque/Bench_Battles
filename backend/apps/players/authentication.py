"""Authentication scheme and permissions for Guest Players."""
from typing import Optional, Tuple
from django.utils import timezone
from rest_framework import authentication, exceptions, permissions
from .models import GuestPlayer


class GuestTokenAuthentication(authentication.BaseAuthentication):
    """
    Authenticates requests via Guest session tokens.
    
    Accepts tokens from either:
    1. Header `Authorization: Bearer <token>`
    2. Header `X-Guest-Token: <token>`
    
    Tokens are hashed using SHA-256 before database lookup.
    Raw tokens are never logged or persisted.
    """
    keyword = 'Bearer'

    def authenticate(self, request) -> Optional[Tuple[GuestPlayer, None]]:
        raw_token = self.extract_token(request)
        if not raw_token:
            return None

        token_hash = GuestPlayer.hash_token(raw_token)
        try:
            player = GuestPlayer.objects.filter(token_hash=token_hash, is_active=True).first()
        except Exception as exc:
            # Catch unexpected database errors safely without leaking internal details
            raise exceptions.AuthenticationFailed('Authentication service temporarily unavailable.') from exc

        if not player:
            raise exceptions.AuthenticationFailed('Invalid, expired, or inactive guest token.')

        # Update last active timestamp
        # (use update_fields to minimize write load and avoid updating created_at)
        GuestPlayer.objects.filter(pk=player.pk).update(last_active_at=timezone.now())

        return (player, None)

    def extract_token(self, request) -> Optional[str]:
        # 1. Check Authorization header
        auth_header = request.headers.get('Authorization')
        if auth_header:
            parts = auth_header.split()
            if len(parts) == 2 and parts[0].lower() == self.keyword.lower():
                return parts[1].strip()

        # 2. Fallback to X-Guest-Token header
        guest_token = request.headers.get('X-Guest-Token')
        if guest_token:
            return guest_token.strip()

        return None

    def authenticate_header(self, request) -> str:
        return self.keyword


class IsGuestAuthenticated(permissions.BasePermission):
    """
    Permission check requiring an active, authenticated GuestPlayer instance.
    """
    message = 'Authentication required. Please provide a valid guest token in Authorization or X-Guest-Token header.'

    def has_permission(self, request, view) -> bool:
        return bool(
            request.user and
            getattr(request.user, 'is_authenticated', False) and
            isinstance(request.user, GuestPlayer) and
            request.user.is_active
        )
