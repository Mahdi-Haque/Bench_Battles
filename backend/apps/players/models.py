"""Models for Guest Player Identity."""
import hashlib
import secrets
import uuid
from django.core.validators import RegexValidator
from django.db import models


nickname_validator = RegexValidator(
    regex=r'^[a-zA-Z0-9_\- ]{2,32}$',
    message='Nickname must be 2-32 characters and contain only letters, numbers, spaces, underscores, or hyphens.'
)


class GuestPlayer(models.Model):
    """
    Represents a guest player session.
    
    Security & Identity Architecture:
    - Public Identifier: `id` (UUIDv4) is safe to expose in public room listings and gameplay.
    - Authentication Credential: `token_hash` stores a SHA-256 hash of a cryptographically
      secure token (`secrets.token_urlsafe(32)`). The raw token is delivered ONLY ONCE
      upon creation to the client and never stored in plaintext or logged.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        help_text='Public unguessable unique identifier.'
    )
    nickname = models.CharField(
        max_length=32,
        validators=[nickname_validator],
        help_text='Display name for the player.'
    )
    token_hash = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text='SHA-256 hash of the secret session token.'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Designates whether this guest identity is active.'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    last_active_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Guest Player'
        verbose_name_plural = 'Guest Players'

    def __str__(self) -> str:
        return f"{self.nickname} ({str(self.id)[:8]})"

    @property
    def is_authenticated(self) -> bool:
        """Compatibility property for Django / DRF permission checks."""
        return True

    @property
    def is_anonymous(self) -> bool:
        return False

    @staticmethod
    def hash_token(raw_token: str) -> str:
        """Compute SHA-256 hash of a raw authentication token."""
        return hashlib.sha256(raw_token.strip().encode('utf-8')).hexdigest()

    @classmethod
    def create_guest(cls, nickname: str | None = None) -> tuple['GuestPlayer', str]:
        """
        Creates a new guest player with a cryptographically strong session token.
        
        Returns:
            tuple: (GuestPlayer instance, raw_secret_token_string)
        """
        raw_token = secrets.token_urlsafe(32)
        token_hash = cls.hash_token(raw_token)

        chosen_nickname = (nickname or '').strip()
        if not chosen_nickname:
            chosen_nickname = f"Guest-{secrets.token_hex(2).upper()}"

        guest = cls.objects.create(
            nickname=chosen_nickname,
            token_hash=token_hash,
            is_active=True,
        )
        return guest, raw_token

    @classmethod
    async def acreate_guest(cls, nickname: str | None = None) -> tuple['GuestPlayer', str]:
        """Asynchronous version of create_guest."""
        from asgiref.sync import sync_to_async
        return await sync_to_async(cls.create_guest)(nickname=nickname)
