"""WebSocket consumers for real-time multiplayer rooms and match lifecycle."""
import asyncio
import json
import logging
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.db import transaction
from django.utils import timezone
from .models import Match, MatchStatus, MembershipRole, Room, RoomMembership, RoomStatus

logger = logging.getLogger(__name__)


@database_sync_to_async
def get_room_and_membership(room_code: str, player_id):
    """Fetch room and active membership for a player."""
    try:
        room = Room.objects.get(code=room_code)
        membership = RoomMembership.objects.filter(
            room=room,
            player_id=player_id,
            is_active=True
        ).select_related('player').first()
        return room, membership
    except Room.DoesNotExist:
        return None, None


@database_sync_to_async
def get_room_state_snapshot(room_code: str):
    """Retrieve full authoritative snapshot of room state and active match."""
    try:
        room = Room.objects.get(code=room_code)
        members = list(
            room.memberships.filter(is_active=True)
            .select_related('player')
            .order_by('joined_at')
        )
        active_match = room.get_active_match()
        return {
            'room_code': room.code,
            'name': room.name,
            'host_id': str(room.host_id),
            'status': room.status,
            'max_players': room.max_players,
            'active_match': active_match.to_snapshot() if active_match else None,
            'players': [
                {
                    'id': str(m.player.id),
                    'nickname': m.player.nickname,
                    'role': m.role,
                    'joined_at': m.joined_at.isoformat(),
                }
                for m in members
            ]
        }
    except Room.DoesNotExist:
        return None


@database_sync_to_async
def start_match_in_db(room_code: str, player_id):
    """
    Atomically validate and start a match.
    Only the host can start, and the room must have at least 2 active players.
    Creates an authoritative Match instance in PostgreSQL.
    """
    try:
        with transaction.atomic():
            room = Room.objects.select_for_update().get(code=room_code)
            if str(room.host_id) != str(player_id):
                return False, "Only the host can start the match.", None

            if room.status != RoomStatus.WAITING:
                return False, f"Cannot start match: room is in '{room.status}' status.", None

            active_members = list(
                room.memberships.filter(is_active=True)
                .select_related('player')
                .order_by('joined_at')
            )
            if len(active_members) < 2:
                return False, "At least 2 players are required to start a match.", None

            room.status = RoomStatus.IN_PROGRESS
            room.save(update_fields=['status', 'updated_at'])

            player_order = [str(m.player.id) for m in active_members]
            first_player = active_members[0].player

            match = Match.objects.create(
                room=room,
                status=MatchStatus.IN_PROGRESS,
                turn_number=1,
                active_player=first_player,
                player_order=player_order,
                turn_duration_seconds=30,
                turn_in_progress=False,
                turn_started_at=timezone.now(),
            )

            return True, None, match.to_snapshot()
    except Room.DoesNotExist:
        return False, "Room not found.", None
    except Exception as exc:
        logger.error(f"Error starting match in room {room_code}: {exc}", exc_info=True)
        return False, "An internal error occurred while starting the match.", None


@database_sync_to_async
def flick_in_db(room_code: str, player_id, turn_number: int | None = None, power: float | None = None, angle: float | None = None):
    """
    Validates that a player is legally allowed to flick.
    Checks match status, active turn ownership, turn sequence, and animation state.
    """
    try:
        with transaction.atomic():
            match = Match.objects.select_for_update().filter(
                room__code=room_code,
                status=MatchStatus.IN_PROGRESS
            ).first()

            if not match:
                return False, "No active match in progress.", None

            if str(match.active_player_id) != str(player_id):
                return False, "It is not your turn to flick.", None

            if turn_number is not None and int(turn_number) != match.turn_number:
                return False, f"Stale action for turn {turn_number}. Current turn is {match.turn_number}.", None

            if match.turn_in_progress:
                return False, "A flick action is already executing for the current turn.", None

            match.turn_in_progress = True
            match.save(update_fields=['turn_in_progress', 'updated_at'])

            return True, None, {
                'match_id': str(match.id),
                'room_code': room_code,
                'turn_number': match.turn_number,
                'player_id': str(player_id),
                'power': power,
                'angle': angle,
            }
    except Exception as exc:
        logger.error(f"Error executing flick in room {room_code}: {exc}", exc_info=True)
        return False, "An internal error occurred during flick validation.", None


@database_sync_to_async
def advance_turn_in_db(room_code: str, player_id, turn_number: int | None = None):
    """
    Authoritatively advances the turn to the next player in round-robin order.
    Validates turn ownership, turn sequence number, and prevents duplicate/concurrent transitions.
    """
    try:
        with transaction.atomic():
            match = Match.objects.select_for_update().filter(
                room__code=room_code,
                status=MatchStatus.IN_PROGRESS
            ).first()

            if not match:
                return False, "No active match in progress.", None

            if str(match.active_player_id) != str(player_id):
                return False, "It is not your turn to end.", None

            if turn_number is not None and int(turn_number) != match.turn_number:
                return False, f"Stale turn action (expected turn {match.turn_number}, got {turn_number}).", None

            # Rotate to next player
            next_player_id = match.get_next_player_id()
            match.turn_number += 1
            match.active_player_id = next_player_id
            match.turn_in_progress = False
            match.turn_started_at = timezone.now()
            match.save(update_fields=['active_player', 'turn_number', 'turn_in_progress', 'turn_started_at', 'updated_at'])

            return True, None, match.to_snapshot()
    except Exception as exc:
        logger.error(f"Error advancing turn in room {room_code}: {exc}", exc_info=True)
        return False, "An internal error occurred while advancing turn.", None


@database_sync_to_async
def handle_turn_timeout_in_db(room_code: str, expected_turn_number: int):
    """
    Authoritatively advances turn when a turn timer expires.
    Guaranteed safe against duplicate or stale timer callbacks via PostgreSQL row locking.
    """
    try:
        with transaction.atomic():
            match = Match.objects.select_for_update().filter(
                room__code=room_code,
                status=MatchStatus.IN_PROGRESS
            ).first()

            if not match:
                return False, "No active match in progress.", None

            if match.turn_number != int(expected_turn_number):
                # Stale timer! The turn already advanced before the timeout fired.
                return False, f"Stale timeout callback for turn {expected_turn_number}. Current turn is {match.turn_number}.", None

            # Rotate to next player due to timeout
            next_player_id = match.get_next_player_id()
            match.turn_number += 1
            match.active_player_id = next_player_id
            match.turn_in_progress = False
            match.turn_started_at = timezone.now()
            match.save(update_fields=['active_player', 'turn_number', 'turn_in_progress', 'turn_started_at', 'updated_at'])

            return True, None, match.to_snapshot()
    except Exception as exc:
        logger.error(f"Error handling turn timeout in room {room_code}: {exc}", exc_info=True)
        return False, "An internal error occurred while handling turn timeout.", None


@database_sync_to_async
def concede_or_finish_match_in_db(room_code: str, player_id, reason: str = "concede"):
    """
    Concludes the active match and marks the room as finished.
    Determines the winner authoritatively.
    """
    try:
        with transaction.atomic():
            room = Room.objects.select_for_update().get(code=room_code)
            match = Match.objects.select_for_update().filter(
                room=room,
                status=MatchStatus.IN_PROGRESS
            ).first()

            if not match:
                return False, "No active match to conclude.", None

            if str(player_id) not in match.player_order:
                return False, "Player is not a participant in this match.", None

            # Winner is the remaining player (or opponent)
            remaining_players = [p for p in match.player_order if p != str(player_id)]
            winner_id = remaining_players[0] if remaining_players else str(player_id)

            match.status = MatchStatus.FINISHED
            match.winner_id = winner_id
            match.turn_in_progress = False
            match.save(update_fields=['status', 'winner', 'turn_in_progress', 'updated_at'])

            room.status = RoomStatus.FINISHED
            room.save(update_fields=['status', 'updated_at'])

            result = match.to_snapshot()
            result['reason'] = reason
            return True, None, result
    except Room.DoesNotExist:
        return False, "Room not found.", None
    except Exception as exc:
        logger.error(f"Error concluding match in room {room_code}: {exc}", exc_info=True)
        return False, "An internal error occurred while concluding the match.", None


class RoomConsumer(AsyncJsonWebsocketConsumer):
    """
    Manages WebSocket lifecycle and match turns for a real-time multiplayer room.
    
    Security & Validation:
    - Rejects unauthenticated connections (code 4001).
    - Rejects non-members (code 4003).
    - Rejects closed or non-existent rooms (codes 4004, 4005).
    - Enforces turn ownership: only active player can flick or end turn.
    - Prevents stale actions with sequence checks and PostgreSQL row locking.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.timeout_task = None

    async def connect(self):
        self.player = self.scope.get('guest_player')
        if not self.player or not getattr(self.player, 'is_active', False):
            await self.close(code=4001)
            return

        self.room_code = self.scope['url_route']['kwargs'].get('room_code', '').upper()
        self.room, self.membership = await get_room_and_membership(self.room_code, self.player.id)

        if not self.room:
            await self.close(code=4004)
            return

        if not self.membership:
            await self.close(code=4003)
            return

        if self.room.status == RoomStatus.CLOSED:
            await self.close(code=4005)
            return

        self.room_group_name = f"room_{self.room_code}"

        # Join room broadcast group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )

        await self.accept()

        # Send full authoritative room snapshot (including active match if ongoing)
        snapshot = await get_room_state_snapshot(self.room_code)
        await self.send_json({
            'type': 'room_state',
            'data': snapshot,
        })

        # Broadcast player connection to other players in the room
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'player_connected_event',
                'player_id': str(self.player.id),
                'nickname': self.player.nickname,
                'role': self.membership.role,
            }
        )

    async def disconnect(self, close_code):
        # Cancel any pending turn timeout task
        if self.timeout_task and not self.timeout_task.done():
            self.timeout_task.cancel()

        if hasattr(self, 'room_group_name') and hasattr(self, 'player') and self.player:
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'player_disconnected_event',
                    'player_id': str(self.player.id),
                    'nickname': self.player.nickname,
                }
            )
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )

    async def receive_json(self, content, **kwargs):
        action = content.get('action')

        if action == 'ping':
            await self.send_json({'type': 'pong'})
            return

        if action == 'start_match':
            success, error_msg, match_data = await start_match_in_db(
                self.room_code,
                self.player.id
            )
            if not success:
                await self.send_json({'type': 'error', 'message': error_msg})
                return

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'match_started_event',
                    'data': match_data
                }
            )
            return

        if action == 'flick':
            turn_number = content.get('turn_number')
            power = content.get('power', 0.5)
            angle = content.get('angle', 0.0)
            success, error_msg, flick_data = await flick_in_db(
                self.room_code,
                self.player.id,
                turn_number,
                power,
                angle
            )
            if not success:
                await self.send_json({'type': 'error', 'message': error_msg})
                return

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'player_flicked_event',
                    'data': flick_data
                }
            )
            return

        if action == 'end_turn':
            turn_number = content.get('turn_number')
            success, error_msg, match_snapshot = await advance_turn_in_db(
                self.room_code,
                self.player.id,
                turn_number
            )
            if not success:
                await self.send_json({'type': 'error', 'message': error_msg})
                return

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'turn_started_event',
                    'data': match_snapshot,
                    'reason': 'normal'
                }
            )
            return

        if action == 'turn_timeout':
            turn_number = content.get('turn_number')
            if turn_number is None:
                await self.send_json({'type': 'error', 'message': "turn_number is required for turn_timeout."})
                return

            success, error_msg, match_snapshot = await handle_turn_timeout_in_db(
                self.room_code,
                turn_number
            )
            if not success:
                await self.send_json({'type': 'error', 'message': error_msg})
                return

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'turn_started_event',
                    'data': match_snapshot,
                    'reason': 'timeout'
                }
            )
            return

        if action in ('concede', 'forfeit'):
            success, error_msg, match_snapshot = await concede_or_finish_match_in_db(
                self.room_code,
                self.player.id,
                reason=action
            )
            if not success:
                await self.send_json({'type': 'error', 'message': error_msg})
                return

            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'match_ended_event',
                    'data': match_snapshot
                }
            )
            return

        # Unknown action
        await self.send_json({
            'type': 'error',
            'message': f"Unknown or unsupported action: '{action}'."
        })

    def _schedule_turn_timeout(self, turn_number: int, duration_seconds: int):
        """Cancels any previous timeout and starts an async timer for the current turn."""
        if self.timeout_task and not self.timeout_task.done():
            self.timeout_task.cancel()
        self.timeout_task = asyncio.create_task(
            self._turn_timeout_worker(turn_number, duration_seconds)
        )

    async def _turn_timeout_worker(self, turn_number: int, duration_seconds: int):
        """Background worker that triggers turn timeout if turn has not advanced."""
        try:
            await asyncio.sleep(duration_seconds)
            success, _, match_snapshot = await handle_turn_timeout_in_db(
                self.room_code,
                turn_number
            )
            if success:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'turn_started_event',
                        'data': match_snapshot,
                        'reason': 'timeout'
                    }
                )
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.debug(f"Turn timeout worker completed: {exc}")

    # Group message handlers
    async def player_connected_event(self, event):
        await self.send_json({
            'type': 'player_connected',
            'player_id': event['player_id'],
            'nickname': event['nickname'],
            'role': event['role'],
        })

    async def player_disconnected_event(self, event):
        await self.send_json({
            'type': 'player_disconnected',
            'player_id': event['player_id'],
            'nickname': event['nickname'],
        })

    async def match_started_event(self, event):
        data = event['data']
        # Schedule timeout for turn 1
        duration = data.get('turn_duration_seconds', 30)
        self._schedule_turn_timeout(1, duration)

        await self.send_json({
            'type': 'match_started',
            'data': data,
        })

    async def turn_started_event(self, event):
        data = event['data']
        turn_num = data.get('turn_number', 1)
        duration = data.get('turn_duration_seconds', 30)
        self._schedule_turn_timeout(turn_num, duration)

        await self.send_json({
            'type': 'turn_started',
            'data': data,
            'reason': event.get('reason', 'normal'),
        })

    async def player_flicked_event(self, event):
        await self.send_json({
            'type': 'player_flicked',
            'data': event['data'],
        })

    async def match_ended_event(self, event):
        if self.timeout_task and not self.timeout_task.done():
            self.timeout_task.cancel()

        await self.send_json({
            'type': 'match_ended',
            'data': event['data'],
        })
