"""WebSocket authentication middleware for Guest Players."""
import urllib.parse
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.utils import timezone
from .models import GuestPlayer


@database_sync_to_async
def get_guest_player_from_token(raw_token: str):
    """Asynchronously look up an active guest player from a raw token string."""
    if not raw_token:
        return None
    token_hash = GuestPlayer.hash_token(raw_token)
    player = GuestPlayer.objects.filter(token_hash=token_hash, is_active=True).first()
    if player:
        GuestPlayer.objects.filter(pk=player.pk).update(last_active_at=timezone.now())
    return player


class GuestTokenAuthMiddleware:
    """
    ASGI middleware that authenticates guest players via query parameter `?token=<secret_token>`.
    
    Populates:
    - scope['guest_player']: GuestPlayer instance or None
    - scope['user']: GuestPlayer instance or AnonymousUser
    """
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'').decode('utf-8')
        query_params = urllib.parse.parse_qs(query_string)
        token_list = query_params.get('token')

        raw_token = token_list[0].strip() if token_list else None
        player = await get_guest_player_from_token(raw_token) if raw_token else None

        scope['guest_player'] = player
        scope['user'] = player if player else AnonymousUser()

        return await self.inner(scope, receive, send)


def GuestTokenAuthMiddlewareStack(inner):
    """Helper wrapper for guest token ASGI middleware."""
    return GuestTokenAuthMiddleware(inner)
