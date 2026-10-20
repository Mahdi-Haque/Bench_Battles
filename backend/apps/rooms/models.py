"""Models for Game Rooms and Memberships."""
import secrets
import string
import uuid
from django.contrib.auth.hashers import check_password, make_password
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models
from django.utils import timezone


# 6-character room codes excluding ambiguous characters: 0, O, 1, I
ROOM_CODE_ALPHABET = '23456789ABCDEFGHJKLMNPQRSTUVWXYZ'
ROOM_CODE_LENGTH = 6

room_code_validator = RegexValidator(
    regex=rf'^[{ROOM_CODE_ALPHABET}]{{{ROOM_CODE_LENGTH}}}$',
    message=f'Room code must be exactly {ROOM_CODE_LENGTH} uppercase alphanumeric characters.'
)


def generate_unique_room_code() -> str:
    """Generates an unguessable 6-character human-readable room code."""
    for _ in range(10):
        code = ''.join(secrets.choice(ROOM_CODE_ALPHABET) for _ in range(ROOM_CODE_LENGTH))
        if not Room.objects.filter(code=code).exists():
            return code
    # Fallback to UUID-derived snippet if collision rate is high
    return uuid.uuid4().hex[:ROOM_CODE_LENGTH].upper()


class RoomStatus(models.TextChoices):
    WAITING = 'WAITING', 'Waiting for Players'
    IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
    FINISHED = 'FINISHED', 'Finished'
    CLOSED = 'CLOSED', 'Closed'


class MembershipRole(models.TextChoices):
    HOST = 'HOST', 'Host'
    PLAYER = 'PLAYER', 'Player'
    SPECTATOR = 'SPECTATOR', 'Spectator'


class Room(models.Model):
    """
    Represents a game room for a tabletop match.
    
    Security & Lifecycle:
    - Passcodes for private rooms are hashed using Django's password hashers (PBKDF2/argon2)
      and never returned in API responses or serialized.
    - Capacity is strictly validated between 2 and 10 players.
    - Atomic concurrency checks prevent room over-subscription.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    code = models.CharField(
        max_length=ROOM_CODE_LENGTH,
        unique=True,
        db_index=True,
        validators=[room_code_validator],
        help_text='Shareable 6-character room code.'
    )
    name = models.CharField(
        max_length=64,
        help_text='Room title / name.'
    )
    host = models.ForeignKey(
        'players.GuestPlayer',
        on_delete=models.PROTECT,
        related_name='hosted_rooms',
        help_text='Current host player.'
    )
    is_private = models.BooleanField(
        default=False,
        help_text='If true, requires passcode to join.'
    )
    passcode_hash = models.CharField(
        max_length=128,
        blank=True,
        null=True,
        help_text='Hashed passcode for private rooms. Never exposed in API.'
    )
    status = models.CharField(
        max_length=16,
        choices=RoomStatus.choices,
        default=RoomStatus.WAITING,
        db_index=True
    )
    max_players = models.PositiveSmallIntegerField(
        default=2,
        validators=[MinValueValidator(2), MaxValueValidator(10)],
        help_text='Maximum allowed players in this room (2 to 10).'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Game Room'
        verbose_name_plural = 'Game Rooms'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(max_players__gte=2) & models.Q(max_players__lte=10),
                name='check_room_capacity_range'
            )
        ]

    def __str__(self) -> str:
        return f"[{self.code}] {self.name} ({self.status})"

    def set_passcode(self, raw_passcode: str) -> None:
        """Hash and save passcode using Django's secure password hasher."""
        if raw_passcode:
            self.passcode_hash = make_password(raw_passcode.strip())
        else:
            self.passcode_hash = None

    def check_passcode(self, raw_passcode: str) -> bool:
        """Verify given raw passcode against the hashed passcode."""
        if not self.is_private or not self.passcode_hash:
            return True
        if not raw_passcode:
            return False
        return check_password(raw_passcode.strip(), self.passcode_hash)

    def active_memberships(self):
        """Query active memberships."""
        return self.memberships.filter(is_active=True).select_related('player')

    def active_players_count(self) -> int:
        """Count currently active players."""
        return self.memberships.filter(is_active=True).count()

    def is_full(self) -> bool:
        """Check if room has reached its maximum player limit."""
        return self.active_players_count() >= self.max_players

    def is_joinable(self) -> bool:
        """Check if room can accept new players."""
        return self.status == RoomStatus.WAITING and not self.is_full()

    def get_active_match(self):
        """Returns currently active match if any."""
        return self.matches.filter(status=MatchStatus.IN_PROGRESS).select_related('active_player', 'winner').first()


class RoomMembership(models.Model):
    """
    Tracks a player's membership in a room.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name='memberships'
    )
    player = models.ForeignKey(
        'players.GuestPlayer',
        on_delete=models.CASCADE,
        related_name='room_memberships'
    )
    role = models.CharField(
        max_length=16,
        choices=MembershipRole.choices,
        default=MembershipRole.PLAYER
    )
    joined_at = models.DateTimeField(auto_now_add=True)
    left_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text='Indicates if the player is currently in the room.'
    )

    class Meta:
        ordering = ['joined_at']
        verbose_name = 'Room Membership'
        verbose_name_plural = 'Room Memberships'
        constraints = [
            # Ensure a player cannot have multiple concurrent active memberships in the same room
            models.UniqueConstraint(
                fields=['room', 'player'],
                condition=models.Q(is_active=True),
                name='unique_active_room_player'
            )
        ]

    def __str__(self) -> str:
        status_str = "Active" if self.is_active else "Left"
        return f"{self.player.nickname} in [{self.room.code}] as {self.role} ({status_str})"

    def leave(self) -> None:
        """Marks this membership as left and records timestamp."""
        self.is_active = False
        self.left_at = timezone.now()
        self.save(update_fields=['is_active', 'left_at'])


class MatchStatus(models.TextChoices):
    IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
    FINISHED = 'FINISHED', 'Finished'
    ABORTED = 'ABORTED', 'Aborted'


class Match(models.Model):
    """
    Represents an authoritative multiplayer match within a game room.
    
    Authority & State Machine:
    - Server dictates turn_number, active_player, player_order, and status.
    - PostgreSQL select_for_update() row locking ensures turn transitions and timeouts
      are strictly atomic and race-condition free.
    """
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name='matches'
    )
    status = models.CharField(
        max_length=16,
        choices=MatchStatus.choices,
        default=MatchStatus.IN_PROGRESS,
        db_index=True
    )
    turn_number = models.PositiveIntegerField(
        default=1,
        help_text='Current turn number (1-based, strictly increasing).'
    )
    active_player = models.ForeignKey(
        'players.GuestPlayer',
        on_delete=models.PROTECT,
        related_name='active_turns',
        help_text='Player whose turn is currently active.'
    )
    player_order = models.JSONField(
        default=list,
        help_text='Array of player UUID strings defining turn rotation order.'
    )
    turn_started_at = models.DateTimeField(
        default=timezone.now,
        help_text='Timestamp when the current turn started.'
    )
    turn_duration_seconds = models.PositiveSmallIntegerField(
        default=30,
        help_text='Time allocated per turn before timeout.'
    )
    turn_in_progress = models.BooleanField(
        default=False,
        help_text='True when a turn flick action is executing before settlement.'
    )
    winner = models.ForeignKey(
        'players.GuestPlayer',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='won_matches',
        help_text='Winner of the match if finished.'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Game Match'
        verbose_name_plural = 'Game Matches'

    def __str__(self) -> str:
        return f"Match {str(self.id)[:8]} in [{self.room.code}] (Turn {self.turn_number})"

    def get_time_remaining_seconds(self) -> int:
        """Calculate seconds remaining in the current turn."""
        elapsed = (timezone.now() - self.turn_started_at).total_seconds()
        return max(0, int(self.turn_duration_seconds - elapsed))

    def get_next_player_id(self) -> str:
        """Determines the next player ID in the round-robin turn order."""
        current_id_str = str(self.active_player_id)
        if self.player_order and current_id_str in self.player_order:
            idx = self.player_order.index(current_id_str)
            next_idx = (idx + 1) % len(self.player_order)
            return self.player_order[next_idx]
        return self.player_order[0] if self.player_order else current_id_str

    def to_snapshot(self) -> dict:
        """Authoritative state snapshot serialized for clients."""
        return {
            'match_id': str(self.id),
            'room_code': self.room.code,
            'status': self.status,
            'turn_number': self.turn_number,
            'active_turn_player_id': str(self.active_player_id),
            'player_order': self.player_order,
            'turn_duration_seconds': self.turn_duration_seconds,
            'turn_started_at': self.turn_started_at.isoformat(),
            'turn_in_progress': self.turn_in_progress,
            'time_remaining_seconds': self.get_time_remaining_seconds(),
            'winner_id': str(self.winner_id) if self.winner_id else None,
        }
