"""Automated tests for RoomConsumer WebSockets, match lifecycle, and real-time turn synchronization."""
import asyncio
import json
from channels.testing import WebsocketCommunicator
from django.db import connections
from django.test import TransactionTestCase
from apps.players.models import GuestPlayer
from apps.rooms.consumers import advance_turn_in_db
from apps.rooms.models import Match, MatchStatus, MembershipRole, Room, RoomMembership, RoomStatus
from config.asgi import application


class RoomConsumerTests(TransactionTestCase):
    """Integration tests for Room WebSocket consumer using PostgreSQL."""

    def tearDown(self):
        super().tearDown()
        connections.close_all()

    async def test_connect_with_valid_token_and_membership(self):
        host, host_token = await GuestPlayer.acreate_guest(nickname="HostPlayer")
        room = await Room.objects.acreate(
            name="Test Battle Room",
            code="WSROOM",
            host=host,
            max_players=2
        )
        await RoomMembership.objects.acreate(
            room=room,
            player=host,
            role=MembershipRole.HOST,
            is_active=True
        )

        communicator = WebsocketCommunicator(
            application,
            f"/ws/rooms/{room.code}/?token={host_token}"
        )
        connected, _ = await communicator.connect()
        self.assertTrue(connected)

        # First message should be full room_state snapshot
        response = await communicator.receive_json_from()
        self.assertEqual(response['type'], 'room_state')
        self.assertEqual(response['data']['room_code'], 'WSROOM')
        self.assertEqual(response['data']['host_id'], str(host.id))
        self.assertEqual(len(response['data']['players']), 1)
        self.assertEqual(response['data']['players'][0]['nickname'], 'HostPlayer')
        self.assertIsNone(response['data']['active_match'])

        await communicator.disconnect()

    async def test_connect_without_token_rejected(self):
        host, _ = await GuestPlayer.acreate_guest(nickname="HostPlayer")
        room = await Room.objects.acreate(
            name="Test Battle Room",
            code="NOTOKN",
            host=host,
            max_players=2
        )
        await RoomMembership.objects.acreate(
            room=room,
            player=host,
            role=MembershipRole.HOST,
            is_active=True
        )

        communicator = WebsocketCommunicator(
            application,
            f"/ws/rooms/{room.code}/"
        )
        connected, close_code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(close_code, 4001)

    async def test_connect_with_invalid_token_rejected(self):
        communicator = WebsocketCommunicator(
            application,
            "/ws/rooms/ANYCOD/?token=completely_fake_token_12345"
        )
        connected, close_code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(close_code, 4001)

    async def test_connect_non_member_rejected(self):
        host, _ = await GuestPlayer.acreate_guest(nickname="HostPlayer")
        outsider, outsider_token = await GuestPlayer.acreate_guest(nickname="Outsider")
        room = await Room.objects.acreate(
            name="Exclusive Room",
            code="EXCLUS",
            host=host,
            max_players=2
        )
        await RoomMembership.objects.acreate(
            room=room,
            player=host,
            role=MembershipRole.HOST,
            is_active=True
        )

        communicator = WebsocketCommunicator(
            application,
            f"/ws/rooms/{room.code}/?token={outsider_token}"
        )
        connected, close_code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(close_code, 4003)

    async def test_connect_nonexistent_room_rejected(self):
        player, token = await GuestPlayer.acreate_guest(nickname="PlayerOne")
        communicator = WebsocketCommunicator(
            application,
            f"/ws/rooms/NONEX9/?token={token}"
        )
        connected, close_code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(close_code, 4004)

    async def test_dual_client_presence_synchronization(self):
        # 1. Setup room and 2 members
        host, host_token = await GuestPlayer.acreate_guest(nickname="HostPlayer")
        guest2, guest2_token = await GuestPlayer.acreate_guest(nickname="Challenger")
        room = await Room.objects.acreate(
            name="Battle Arena",
            code="DUALWS",
            host=host,
            max_players=2
        )
        await RoomMembership.objects.acreate(
            room=room,
            player=host,
            role=MembershipRole.HOST,
            is_active=True
        )
        await RoomMembership.objects.acreate(
            room=room,
            player=guest2,
            role=MembershipRole.PLAYER,
            is_active=True
        )

        # 2. Host connects
        comm1 = WebsocketCommunicator(
            application,
            f"/ws/rooms/{room.code}/?token={host_token}"
        )
        connected1, _ = await comm1.connect()
        self.assertTrue(connected1)

        msg1 = await comm1.receive_json_from()
        self.assertEqual(msg1['type'], 'room_state')
        conn_event = await comm1.receive_json_from()
        self.assertEqual(conn_event['type'], 'player_connected')
        self.assertEqual(conn_event['player_id'], str(host.id))

        # 3. Challenger connects
        comm2 = WebsocketCommunicator(
            application,
            f"/ws/rooms/{room.code}/?token={guest2_token}"
        )
        connected2, _ = await comm2.connect()
        self.assertTrue(connected2)

        msg2 = await comm2.receive_json_from()
        self.assertEqual(msg2['type'], 'room_state')
        self.assertEqual(len(msg2['data']['players']), 2)

        host_notif = await comm1.receive_json_from()
        self.assertEqual(host_notif['type'], 'player_connected')
        self.assertEqual(host_notif['player_id'], str(guest2.id))

        challenger_notif = await comm2.receive_json_from()
        self.assertEqual(challenger_notif['type'], 'player_connected')
        self.assertEqual(challenger_notif['player_id'], str(guest2.id))

        # 4. Challenger disconnects
        await comm2.disconnect()

        disc_notif = await comm1.receive_json_from()
        self.assertEqual(disc_notif['type'], 'player_disconnected')
        self.assertEqual(disc_notif['player_id'], str(guest2.id))

        await comm1.disconnect()

    async def test_start_match_validation_and_broadcast(self):
        host, host_token = await GuestPlayer.acreate_guest(nickname="HostPlayer")
        guest2, guest2_token = await GuestPlayer.acreate_guest(nickname="Challenger")
        room = await Room.objects.acreate(
            name="Match Start Room",
            code="STRTWS",
            host=host,
            max_players=2
        )
        await RoomMembership.objects.acreate(
            room=room,
            player=host,
            role=MembershipRole.HOST,
            is_active=True
        )
        await RoomMembership.objects.acreate(
            room=room,
            player=guest2,
            role=MembershipRole.PLAYER,
            is_active=True
        )

        comm1 = WebsocketCommunicator(
            application,
            f"/ws/rooms/{room.code}/?token={host_token}"
        )
        connected1, _ = await comm1.connect()
        self.assertTrue(connected1)
        await comm1.receive_json_from()  # room_state
        await comm1.receive_json_from()  # player_connected (host)

        comm2 = WebsocketCommunicator(
            application,
            f"/ws/rooms/{room.code}/?token={guest2_token}"
        )
        connected2, _ = await comm2.connect()
        self.assertTrue(connected2)
        await comm2.receive_json_from()  # room_state
        await comm1.receive_json_from()  # player_connected (guest2) to host
        await comm2.receive_json_from()  # player_connected (guest2) to guest2

        # 1. Non-host attempts to start match -> Rejected
        await comm2.send_json_to({'action': 'start_match'})
        err_response = await comm2.receive_json_from()
        self.assertEqual(err_response['type'], 'error')
        self.assertIn('Only the host', err_response['message'])

        # 2. Host starts match -> Successful broadcast to both players
        await comm1.send_json_to({'action': 'start_match'})
        event_host = await comm1.receive_json_from()
        event_guest = await comm2.receive_json_from()

        self.assertEqual(event_host['type'], 'match_started')
        self.assertEqual(event_guest['type'], 'match_started')
        self.assertEqual(event_host['data']['status'], MatchStatus.IN_PROGRESS)
        self.assertEqual(event_host['data']['turn_number'], 1)
        self.assertEqual(event_host['data']['active_turn_player_id'], str(host.id))

        # 3. Host tries to start match again while IN_PROGRESS -> Rejected
        await comm1.send_json_to({'action': 'start_match'})
        err_again = await comm1.receive_json_from()
        self.assertEqual(err_again['type'], 'error')
        self.assertIn('Cannot start match', err_again['message'])

        await comm1.disconnect()
        await comm2.disconnect()

    async def test_valid_turn_flick_and_advance(self):
        """Host and challenger alternate turns with valid flicks and turn settlements."""
        host, host_token = await GuestPlayer.acreate_guest(nickname="HostPlayer")
        guest2, guest2_token = await GuestPlayer.acreate_guest(nickname="Challenger")
        room = await Room.objects.acreate(
            name="Turn Test Room",
            code="TURNA1",
            host=host,
            max_players=2
        )
        await RoomMembership.objects.acreate(room=room, player=host, role=MembershipRole.HOST, is_active=True)
        await RoomMembership.objects.acreate(room=room, player=guest2, role=MembershipRole.PLAYER, is_active=True)

        comm1 = WebsocketCommunicator(application, f"/ws/rooms/{room.code}/?token={host_token}")
        await comm1.connect()
        await comm1.receive_json_from()  # room_state
        await comm1.receive_json_from()  # player_connected

        comm2 = WebsocketCommunicator(application, f"/ws/rooms/{room.code}/?token={guest2_token}")
        await comm2.connect()
        await comm2.receive_json_from()  # room_state
        await comm1.receive_json_from()  # player_connected (guest2)
        await comm2.receive_json_from()  # player_connected (guest2)

        # Host starts match (Turn 1: Host is active)
        await comm1.send_json_to({'action': 'start_match'})
        await comm1.receive_json_from()  # match_started
        await comm2.receive_json_from()  # match_started

        # Turn 1: Host flicks
        await comm1.send_json_to({
            'action': 'flick',
            'turn_number': 1,
            'power': 0.85,
            'angle': 1.57
        })
        flick1_host = await comm1.receive_json_from()
        flick1_guest = await comm2.receive_json_from()
        self.assertEqual(flick1_host['type'], 'player_flicked')
        self.assertEqual(flick1_guest['type'], 'player_flicked')
        self.assertEqual(flick1_host['data']['player_id'], str(host.id))
        self.assertEqual(flick1_host['data']['turn_number'], 1)

        # Turn 1: Host ends turn -> Turn rotates to Challenger (Turn 2)
        await comm1.send_json_to({'action': 'end_turn', 'turn_number': 1})
        turn2_host = await comm1.receive_json_from()
        turn2_guest = await comm2.receive_json_from()
        self.assertEqual(turn2_host['type'], 'turn_started')
        self.assertEqual(turn2_guest['type'], 'turn_started')
        self.assertEqual(turn2_host['data']['turn_number'], 2)
        self.assertEqual(turn2_host['data']['active_turn_player_id'], str(guest2.id))

        # Turn 2: Challenger flicks
        await comm2.send_json_to({
            'action': 'flick',
            'turn_number': 2,
            'power': 0.65,
            'angle': -0.78
        })
        flick2_host = await comm1.receive_json_from()
        flick2_guest = await comm2.receive_json_from()
        self.assertEqual(flick2_host['type'], 'player_flicked')
        self.assertEqual(flick2_guest['type'], 'player_flicked')
        self.assertEqual(flick2_host['data']['player_id'], str(guest2.id))
        self.assertEqual(flick2_host['data']['turn_number'], 2)

        # Turn 2: Challenger ends turn -> Turn rotates back to Host (Turn 3)
        await comm2.send_json_to({'action': 'end_turn', 'turn_number': 2})
        turn3_host = await comm1.receive_json_from()
        turn3_guest = await comm2.receive_json_from()
        self.assertEqual(turn3_host['type'], 'turn_started')
        self.assertEqual(turn3_guest['type'], 'turn_started')
        self.assertEqual(turn3_host['data']['turn_number'], 3)
        self.assertEqual(turn3_host['data']['active_turn_player_id'], str(host.id))

        await comm1.disconnect()
        await comm2.disconnect()

    async def test_out_of_turn_actions_rejected(self):
        """Clients attempting to flick or end turn out-of-turn are strictly rejected."""
        host, host_token = await GuestPlayer.acreate_guest(nickname="HostPlayer")
        guest2, guest2_token = await GuestPlayer.acreate_guest(nickname="Challenger")
        room = await Room.objects.acreate(
            name="Turn Guard Room",
            code="TURNG1",
            host=host,
            max_players=2
        )
        await RoomMembership.objects.acreate(room=room, player=host, role=MembershipRole.HOST, is_active=True)
        await RoomMembership.objects.acreate(room=room, player=guest2, role=MembershipRole.PLAYER, is_active=True)

        comm1 = WebsocketCommunicator(application, f"/ws/rooms/{room.code}/?token={host_token}")
        await comm1.connect()
        await comm1.receive_json_from()
        await comm1.receive_json_from()

        comm2 = WebsocketCommunicator(application, f"/ws/rooms/{room.code}/?token={guest2_token}")
        await comm2.connect()
        await comm2.receive_json_from()
        await comm1.receive_json_from()
        await comm2.receive_json_from()

        await comm1.send_json_to({'action': 'start_match'})
        await comm1.receive_json_from()
        await comm2.receive_json_from()

        # Turn 1 is active for Host. Challenger tries to flick -> Rejected
        await comm2.send_json_to({'action': 'flick', 'turn_number': 1, 'power': 0.5})
        err1 = await comm2.receive_json_from()
        self.assertEqual(err1['type'], 'error')
        self.assertIn('not your turn to flick', err1['message'])

        # Challenger tries to end turn -> Rejected
        await comm2.send_json_to({'action': 'end_turn', 'turn_number': 1})
        err2 = await comm2.receive_json_from()
        self.assertEqual(err2['type'], 'error')
        self.assertIn('not your turn to end', err2['message'])

        await comm1.disconnect()
        await comm2.disconnect()

    async def test_duplicate_and_stale_turn_actions_rejected(self):
        """Duplicate turn endings or actions with stale turn numbers are rejected."""
        host, host_token = await GuestPlayer.acreate_guest(nickname="HostPlayer")
        guest2, guest2_token = await GuestPlayer.acreate_guest(nickname="Challenger")
        room = await Room.objects.acreate(
            name="Stale Guard Room",
            code="STALE1",
            host=host,
            max_players=2
        )
        await RoomMembership.objects.acreate(room=room, player=host, role=MembershipRole.HOST, is_active=True)
        await RoomMembership.objects.acreate(room=room, player=guest2, role=MembershipRole.PLAYER, is_active=True)

        comm1 = WebsocketCommunicator(application, f"/ws/rooms/{room.code}/?token={host_token}")
        await comm1.connect()
        await comm1.receive_json_from()
        await comm1.receive_json_from()

        comm2 = WebsocketCommunicator(application, f"/ws/rooms/{room.code}/?token={guest2_token}")
        await comm2.connect()
        await comm2.receive_json_from()
        await comm1.receive_json_from()
        await comm2.receive_json_from()

        await comm1.send_json_to({'action': 'start_match'})
        await comm1.receive_json_from()
        await comm2.receive_json_from()

        # Host ends turn 1 -> Turn becomes 2
        await comm1.send_json_to({'action': 'end_turn', 'turn_number': 1})
        await comm1.receive_json_from()  # turn_started (turn 2)
        await comm2.receive_json_from()  # turn_started (turn 2)

        # Host attempts to end turn 1 again -> Rejected
        await comm1.send_json_to({'action': 'end_turn', 'turn_number': 1})
        dup_err = await comm1.receive_json_from()
        self.assertEqual(dup_err['type'], 'error')
        self.assertIn('not your turn to end', dup_err['message'])

        # Challenger is now active (turn 2), but sends stale turn_number 1 -> Rejected
        await comm2.send_json_to({'action': 'end_turn', 'turn_number': 1})
        stale_err = await comm2.receive_json_from()
        self.assertEqual(stale_err['type'], 'error')
        self.assertIn('Stale turn action', stale_err['message'])

        await comm1.disconnect()
        await comm2.disconnect()

    async def test_concurrent_turn_actions_protection(self):
        """Two concurrent advance_turn_in_db calls on the same turn: exactly one succeeds."""
        host, _ = await GuestPlayer.acreate_guest(nickname="HostPlayer")
        guest2, _ = await GuestPlayer.acreate_guest(nickname="Challenger")
        room = await Room.objects.acreate(
            name="Concurrency Room",
            code="CONCUR",
            host=host,
            max_players=2
        )
        await RoomMembership.objects.acreate(room=room, player=host, role=MembershipRole.HOST, is_active=True)
        await RoomMembership.objects.acreate(room=room, player=guest2, role=MembershipRole.PLAYER, is_active=True)

        match = await Match.objects.acreate(
            room=room,
            status=MatchStatus.IN_PROGRESS,
            turn_number=1,
            active_player=host,
            player_order=[str(host.id), str(guest2.id)],
            turn_duration_seconds=30
        )

        # Concurrently fire advance_turn_in_db for turn 1
        res1, res2 = await asyncio.gather(
            advance_turn_in_db(room.code, host.id, 1),
            advance_turn_in_db(room.code, host.id, 1)
        )

        # Exactly one must succeed and the other must fail due to PostgreSQL row lock & sequence check
        successes = [r for r in [res1, res2] if r[0] is True]
        failures = [r for r in [res1, res2] if r[0] is False]

        self.assertEqual(len(successes), 1)
        self.assertEqual(len(failures), 1)

        # Verify DB match state advanced to turn 2 exactly once
        refreshed_match = await Match.objects.aget(id=match.id)
        self.assertEqual(refreshed_match.turn_number, 2)
        self.assertEqual(str(refreshed_match.active_player_id), str(guest2.id))

    async def test_turn_timeout_handling_and_stale_timer_immunity(self):
        """Turn timeout advances turn authoritatively; duplicate or late timeout is safely ignored."""
        host, host_token = await GuestPlayer.acreate_guest(nickname="HostPlayer")
        guest2, guest2_token = await GuestPlayer.acreate_guest(nickname="Challenger")
        room = await Room.objects.acreate(
            name="Timeout Room",
            code="TIME01",
            host=host,
            max_players=2
        )
        await RoomMembership.objects.acreate(room=room, player=host, role=MembershipRole.HOST, is_active=True)
        await RoomMembership.objects.acreate(room=room, player=guest2, role=MembershipRole.PLAYER, is_active=True)

        comm1 = WebsocketCommunicator(application, f"/ws/rooms/{room.code}/?token={host_token}")
        await comm1.connect()
        await comm1.receive_json_from()
        await comm1.receive_json_from()

        comm2 = WebsocketCommunicator(application, f"/ws/rooms/{room.code}/?token={guest2_token}")
        await comm2.connect()
        await comm2.receive_json_from()
        await comm1.receive_json_from()
        await comm2.receive_json_from()

        await comm1.send_json_to({'action': 'start_match'})
        await comm1.receive_json_from()
        await comm2.receive_json_from()

        # Turn 1 expires via timeout action
        await comm1.send_json_to({'action': 'turn_timeout', 'turn_number': 1})
        t1_host = await comm1.receive_json_from()
        t1_guest = await comm2.receive_json_from()

        self.assertEqual(t1_host['type'], 'turn_started')
        self.assertEqual(t1_host['reason'], 'timeout')
        self.assertEqual(t1_host['data']['turn_number'], 2)
        self.assertEqual(t1_host['data']['active_turn_player_id'], str(guest2.id))

        # A stale timeout callback for turn 1 arrives when match is on turn 2 -> Safely rejected
        await comm1.send_json_to({'action': 'turn_timeout', 'turn_number': 1})
        stale_err = await comm1.receive_json_from()
        self.assertEqual(stale_err['type'], 'error')
        self.assertIn('Stale timeout callback', stale_err['message'])

        # Verify DB match is intact on turn 2
        active_match = await Match.objects.filter(room=room, status=MatchStatus.IN_PROGRESS).afirst()
        self.assertEqual(active_match.turn_number, 2)
        self.assertEqual(str(active_match.active_player_id), str(guest2.id))

        await comm1.disconnect()
        await comm2.disconnect()

    async def test_concede_and_match_completion(self):
        """Conceding or finishing a match transitions room and match to FINISHED and sets winner."""
        host, host_token = await GuestPlayer.acreate_guest(nickname="HostPlayer")
        guest2, guest2_token = await GuestPlayer.acreate_guest(nickname="Challenger")
        room = await Room.objects.acreate(
            name="Concede Room",
            code="CONCD1",
            host=host,
            max_players=2
        )
        await RoomMembership.objects.acreate(room=room, player=host, role=MembershipRole.HOST, is_active=True)
        await RoomMembership.objects.acreate(room=room, player=guest2, role=MembershipRole.PLAYER, is_active=True)

        comm1 = WebsocketCommunicator(application, f"/ws/rooms/{room.code}/?token={host_token}")
        await comm1.connect()
        await comm1.receive_json_from()
        await comm1.receive_json_from()

        comm2 = WebsocketCommunicator(application, f"/ws/rooms/{room.code}/?token={guest2_token}")
        await comm2.connect()
        await comm2.receive_json_from()
        await comm1.receive_json_from()
        await comm2.receive_json_from()

        await comm1.send_json_to({'action': 'start_match'})
        await comm1.receive_json_from()
        await comm2.receive_json_from()

        # Challenger concedes
        await comm2.send_json_to({'action': 'concede'})
        ended_host = await comm1.receive_json_from()
        ended_guest = await comm2.receive_json_from()

        self.assertEqual(ended_host['type'], 'match_ended')
        self.assertEqual(ended_guest['type'], 'match_ended')
        self.assertEqual(ended_host['data']['status'], MatchStatus.FINISHED)
        self.assertEqual(ended_host['data']['winner_id'], str(host.id))
        self.assertEqual(ended_host['data']['reason'], 'concede')

        # Verify database updates
        refreshed_room = await Room.objects.aget(id=room.id)
        refreshed_match = await Match.objects.aget(room=room)
        self.assertEqual(refreshed_room.status, RoomStatus.FINISHED)
        self.assertEqual(refreshed_match.status, MatchStatus.FINISHED)
        self.assertEqual(str(refreshed_match.winner_id), str(host.id))

        # Subsequent turn actions are rejected
        await comm1.send_json_to({'action': 'flick', 'turn_number': 1})
        err_action = await comm1.receive_json_from()
        self.assertEqual(err_action['type'], 'error')
        self.assertIn('No active match in progress', err_action['message'])

        await comm1.disconnect()
        await comm2.disconnect()

    async def test_reconnect_receives_active_match_state(self):
        """A player reconnecting mid-match immediately receives the authoritative match state."""
        host, host_token = await GuestPlayer.acreate_guest(nickname="HostPlayer")
        guest2, guest2_token = await GuestPlayer.acreate_guest(nickname="Challenger")
        room = await Room.objects.acreate(
            name="Reconnect Room",
            code="RECWS1",
            host=host,
            max_players=2
        )
        await RoomMembership.objects.acreate(room=room, player=host, role=MembershipRole.HOST, is_active=True)
        await RoomMembership.objects.acreate(room=room, player=guest2, role=MembershipRole.PLAYER, is_active=True)

        comm1 = WebsocketCommunicator(application, f"/ws/rooms/{room.code}/?token={host_token}")
        await comm1.connect()
        await comm1.receive_json_from()
        await comm1.receive_json_from()

        comm2 = WebsocketCommunicator(application, f"/ws/rooms/{room.code}/?token={guest2_token}")
        await comm2.connect()
        await comm2.receive_json_from()
        await comm1.receive_json_from()
        await comm2.receive_json_from()

        # Host starts match
        await comm1.send_json_to({'action': 'start_match'})
        await comm1.receive_json_from()
        await comm2.receive_json_from()

        # Challenger disconnects mid-match
        await comm2.disconnect()
        await comm1.receive_json_from()  # player_disconnected notification

        # Challenger reconnects
        comm2_reconnect = WebsocketCommunicator(application, f"/ws/rooms/{room.code}/?token={guest2_token}")
        connected, _ = await comm2_reconnect.connect()
        self.assertTrue(connected)

        reconnect_state = await comm2_reconnect.receive_json_from()
        self.assertEqual(reconnect_state['type'], 'room_state')
        self.assertEqual(reconnect_state['data']['status'], RoomStatus.IN_PROGRESS)

        active_match = reconnect_state['data']['active_match']
        self.assertIsNotNone(active_match)
        self.assertEqual(active_match['turn_number'], 1)
        self.assertEqual(active_match['active_turn_player_id'], str(host.id))
        self.assertGreater(active_match['time_remaining_seconds'], 0)

        await comm1.disconnect()
        await comm2_reconnect.disconnect()

    async def test_ping_pong_and_unknown_action(self):
        host, host_token = await GuestPlayer.acreate_guest(nickname="HostPlayer")
        room = await Room.objects.acreate(
            name="Ping Room",
            code="PINGWS",
            host=host,
            max_players=2
        )
        await RoomMembership.objects.acreate(
            room=room,
            player=host,
            role=MembershipRole.HOST,
            is_active=True
        )

        comm = WebsocketCommunicator(
            application,
            f"/ws/rooms/{room.code}/?token={host_token}"
        )
        connected, _ = await comm.connect()
        self.assertTrue(connected)
        await comm.receive_json_from()  # room_state
        await comm.receive_json_from()  # player_connected

        # Send ping
        await comm.send_json_to({'action': 'ping'})
        pong = await comm.receive_json_from()
        self.assertEqual(pong['type'], 'pong')

        # Send invalid action
        await comm.send_json_to({'action': 'fly_to_moon'})
        err = await comm.receive_json_from()
        self.assertEqual(err['type'], 'error')
        self.assertIn('Unknown or unsupported action', err['message'])

        await comm.disconnect()
