"""Tests for Game Room Models, Concurrency, and REST API."""
from django.contrib.auth.hashers import check_password
from django.test import TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from apps.players.models import GuestPlayer
from .models import MembershipRole, Room, RoomMembership, RoomStatus


class GameRoomTests(APITestCase):
    """Test suite covering Room lifecycle, membership, capacity, and security."""

    def setUp(self):
        # Create test players
        self.player1, self.token1 = GuestPlayer.create_guest(nickname='PlayerOne')
        self.player2, self.token2 = GuestPlayer.create_guest(nickname='PlayerTwo')
        self.player3, self.token3 = GuestPlayer.create_guest(nickname='PlayerThree')

    def test_health_check(self):
        """GET /api/health/ returns system status."""
        url = reverse('health-check')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'ok')
        self.assertIn('database', response.data)

    def test_create_public_room(self):
        """Authenticated guest can create a public room and is set as HOST."""
        url = reverse('rooms:room-list-create')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token1}')
        payload = {
            'name': 'Classroom Desk 1',
            'is_private': False,
            'max_players': 2,
        }
        response = self.client.post(url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('code', response.data)
        self.assertEqual(len(response.data['code']), 6)
        self.assertEqual(response.data['name'], 'Classroom Desk 1')
        self.assertEqual(response.data['status'], RoomStatus.WAITING)
        self.assertEqual(response.data['current_players'], 1)
        self.assertEqual(response.data['host']['id'], str(self.player1.id))

        # Verify DB membership
        room = Room.objects.get(code=response.data['code'])
        self.assertEqual(room.host, self.player1)
        host_membership = room.memberships.get(player=self.player1)
        self.assertEqual(host_membership.role, MembershipRole.HOST)
        self.assertTrue(host_membership.is_active)

    def test_create_private_room_hashes_passcode(self):
        """Private room stores hashed passcode and never exposes hash in API."""
        url = reverse('rooms:room-list-create')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token1}')
        raw_passcode = 'SecretPass123'
        payload = {
            'name': 'Private Arena',
            'is_private': True,
            'passcode': raw_passcode,
            'max_players': 4,
        }
        response = self.client.post(url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['is_private'])
        self.assertNotIn('passcode', response.data)
        self.assertNotIn('passcode_hash', response.data)

        room = Room.objects.get(code=response.data['code'])
        self.assertTrue(room.is_private)
        self.assertIsNotNone(room.passcode_hash)
        # Verify passcode was hashed securely using Django's check_password
        self.assertTrue(check_password(raw_passcode, room.passcode_hash))
        self.assertNotIn(raw_passcode, room.passcode_hash)

    def test_create_private_room_requires_passcode(self):
        """Creating a private room without a passcode is rejected with 400."""
        url = reverse('rooms:room-list-create')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token1}')
        payload = {
            'name': 'No Passcode Room',
            'is_private': True,
        }
        response = self.client.post(url, payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('passcode', response.data)

    def test_list_eligible_public_rooms(self):
        """GET /api/rooms/ lists only waiting, public, non-full rooms."""
        # 1. Eligible public room
        r1 = Room.objects.create(code='PUB001', name='Public One', host=self.player1, is_private=False, max_players=2)
        RoomMembership.objects.create(room=r1, player=self.player1, role=MembershipRole.HOST, is_active=True)

        # 2. Private room (must NOT appear in public list)
        r2 = Room.objects.create(code='PRIV01', name='Private One', host=self.player1, is_private=True, max_players=2)
        RoomMembership.objects.create(room=r2, player=self.player1, role=MembershipRole.HOST, is_active=True)

        # 3. Full public room (must NOT appear)
        r3 = Room.objects.create(code='FULL01', name='Full One', host=self.player1, is_private=False, max_players=2)
        RoomMembership.objects.create(room=r3, player=self.player1, role=MembershipRole.HOST, is_active=True)
        RoomMembership.objects.create(room=r3, player=self.player2, role=MembershipRole.PLAYER, is_active=True)

        # 4. In-progress room (must NOT appear)
        r4 = Room.objects.create(code='PROG01', name='In Progress', host=self.player1, status=RoomStatus.IN_PROGRESS, max_players=4)
        RoomMembership.objects.create(room=r4, player=self.player1, role=MembershipRole.HOST, is_active=True)

        url = reverse('rooms:room-list-create')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        codes = [item['code'] for item in response.data]
        self.assertIn('PUB001', codes)
        self.assertNotIn('PRIV01', codes)
        self.assertNotIn('FULL01', codes)
        self.assertNotIn('PROG01', codes)

    def test_join_public_room(self):
        """Eligible player can join a public room."""
        room = Room.objects.create(code='JOIN01', name='Join Test', host=self.player1, is_private=False, max_players=2)
        RoomMembership.objects.create(room=room, player=self.player1, role=MembershipRole.HOST, is_active=True)

        url = reverse('rooms:room-join', kwargs={'room_code': 'JOIN01'})
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token2}')
        response = self.client.post(url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['current_players'], 2)

        membership = RoomMembership.objects.get(room=room, player=self.player2)
        self.assertEqual(membership.role, MembershipRole.PLAYER)
        self.assertTrue(membership.is_active)

    def test_join_private_room_with_correct_passcode(self):
        """Player can join a private room when supplying the correct passcode."""
        room = Room.objects.create(code='PRIV99', name='Pass Test', host=self.player1, is_private=True, max_players=3)
        room.set_passcode('Secret123')
        room.save()
        RoomMembership.objects.create(room=room, player=self.player1, role=MembershipRole.HOST, is_active=True)

        url = reverse('rooms:room-join', kwargs={'room_code': 'PRIV99'})
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token2}')
        response = self.client.post(url, {'passcode': 'Secret123'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['current_players'], 2)

    def test_join_private_room_with_wrong_passcode(self):
        """Rejects joining a private room with incorrect passcode (403 Forbidden)."""
        room = Room.objects.create(code='PRIV88', name='Pass Test', host=self.player1, is_private=True, max_players=3)
        room.set_passcode('Secret123')
        room.save()
        RoomMembership.objects.create(room=room, player=self.player1, role=MembershipRole.HOST, is_active=True)

        url = reverse('rooms:room-join', kwargs={'room_code': 'PRIV88'})
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token2}')
        response = self.client.post(url, {'passcode': 'WrongPass'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(room.active_players_count(), 1)

    def test_private_room_detail_access_via_post_body(self):
        """Non-members can retrieve private room details by sending passcode in POST body."""
        room = Room.objects.create(code='PRVD01', name='Private Detail', host=self.player1, is_private=True, max_players=2)
        room.set_passcode('Secret123')
        room.save()
        RoomMembership.objects.create(room=room, player=self.player1, role=MembershipRole.HOST, is_active=True)

        url = reverse('rooms:room-detail', kwargs={'room_code': 'PRVD01'})
        # POST body with passcode avoids query string logging risks
        response = self.client.post(url, {'passcode': 'Secret123'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['code'], 'PRVD01')
        self.assertNotIn('passcode_hash', response.data)

    def test_private_room_detail_access_via_header(self):
        """Non-members can retrieve private room details via X-Room-Passcode header."""
        room = Room.objects.create(code='PRVD02', name='Header Detail', host=self.player1, is_private=True, max_players=2)
        room.set_passcode('Secret123')
        room.save()
        RoomMembership.objects.create(room=room, player=self.player1, role=MembershipRole.HOST, is_active=True)

        url = reverse('rooms:room-detail', kwargs={'room_code': 'PRVD02'})
        response = self.client.get(url, HTTP_X_ROOM_PASSCODE='Secret123')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['code'], 'PRVD02')

    def test_private_room_detail_without_passcode_rejected(self):
        """Non-members cannot view private room details without a valid passcode."""
        room = Room.objects.create(code='PRVD03', name='Reject Detail', host=self.player1, is_private=True, max_players=2)
        room.set_passcode('Secret123')
        room.save()
        RoomMembership.objects.create(room=room, player=self.player1, role=MembershipRole.HOST, is_active=True)

        url = reverse('rooms:room-detail', kwargs={'room_code': 'PRVD03'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_reject_duplicate_membership(self):
        """Active member cannot join the same room twice."""
        room = Room.objects.create(code='DUP001', name='Duplicate Test', host=self.player1, is_private=False, max_players=4)
        RoomMembership.objects.create(room=room, player=self.player1, role=MembershipRole.HOST, is_active=True)

        url = reverse('rooms:room-join', kwargs={'room_code': 'DUP001'})
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token1}')
        response = self.client.post(url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('already an active member', response.data['detail'])

    def test_reject_joining_full_room(self):
        """Rejects joining a room that has reached capacity (400 Bad Request)."""
        room = Room.objects.create(code='CAP001', name='Capacity Test', host=self.player1, is_private=False, max_players=2)
        RoomMembership.objects.create(room=room, player=self.player1, role=MembershipRole.HOST, is_active=True)
        RoomMembership.objects.create(room=room, player=self.player2, role=MembershipRole.PLAYER, is_active=True)

        url = reverse('rooms:room-join', kwargs={'room_code': 'CAP001'})
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token3}')
        response = self.client.post(url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('maximum player capacity', response.data['detail'])

    def test_reject_joining_non_waiting_room(self):
        """Cannot join a room that is IN_PROGRESS, FINISHED, or CLOSED."""
        room = Room.objects.create(code='STAT01', name='State Test', host=self.player1, is_private=False, status=RoomStatus.IN_PROGRESS, max_players=4)
        RoomMembership.objects.create(room=room, player=self.player1, role=MembershipRole.HOST, is_active=True)

        url = reverse('rooms:room-join', kwargs={'room_code': 'STAT01'})
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token2}')
        response = self.client.post(url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Cannot join room with status', response.data['detail'])

    def test_non_host_leaves_room(self):
        """Non-host member leaves room: membership is deactivated and left_at recorded."""
        room = Room.objects.create(code='LEAV01', name='Leave Test', host=self.player1, is_private=False, max_players=3)
        RoomMembership.objects.create(room=room, player=self.player1, role=MembershipRole.HOST, is_active=True)
        mem2 = RoomMembership.objects.create(room=room, player=self.player2, role=MembershipRole.PLAYER, is_active=True)

        url = reverse('rooms:room-leave', kwargs={'room_code': 'LEAV01'})
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token2}')
        response = self.client.post(url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        mem2.refresh_from_db()
        self.assertFalse(mem2.is_active)
        self.assertIsNotNone(mem2.left_at)
        self.assertEqual(room.active_players_count(), 1)
        self.assertEqual(room.status, RoomStatus.WAITING)

    def test_host_leaves_transfers_ownership_to_next_member(self):
        """When host leaves and other active members remain, host role is transferred."""
        room = Room.objects.create(code='HTRF01', name='Host Transfer', host=self.player1, is_private=False, max_players=3)
        RoomMembership.objects.create(room=room, player=self.player1, role=MembershipRole.HOST, is_active=True)
        mem2 = RoomMembership.objects.create(room=room, player=self.player2, role=MembershipRole.PLAYER, is_active=True)

        url = reverse('rooms:room-leave', kwargs={'room_code': 'HTRF01'})
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token1}')
        response = self.client.post(url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        room.refresh_from_db()
        # Player 2 is now host
        self.assertEqual(room.host, self.player2)
        mem2.refresh_from_db()
        self.assertEqual(mem2.role, MembershipRole.HOST)
        self.assertEqual(room.status, RoomStatus.WAITING)

    def test_host_leaves_closes_room_when_no_members_remain(self):
        """When host leaves and no other active members remain, room transitions to CLOSED."""
        room = Room.objects.create(code='HCLS01', name='Host Close', host=self.player1, is_private=False, max_players=2)
        RoomMembership.objects.create(room=room, player=self.player1, role=MembershipRole.HOST, is_active=True)

        url = reverse('rooms:room-leave', kwargs={'room_code': 'HCLS01'})
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token1}')
        response = self.client.post(url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        room.refresh_from_db()
        self.assertEqual(room.status, RoomStatus.CLOSED)
        self.assertEqual(room.active_players_count(), 0)

    def test_database_unique_active_membership_constraint(self):
        """Direct database insertion of duplicate active membership raises IntegrityError."""
        from django.db import IntegrityError
        room = Room.objects.create(code='UNQ001', name='Unique Check', host=self.player1, is_private=False, max_players=4)
        RoomMembership.objects.create(room=room, player=self.player1, role=MembershipRole.HOST, is_active=True)

        with self.assertRaises(IntegrityError):
            RoomMembership.objects.create(room=room, player=self.player1, role=MembershipRole.PLAYER, is_active=True)

    def test_create_room_validation_failures(self):
        """Invalid room parameters are rejected with 400 Bad Request."""
        url = reverse('rooms:room-list-create')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {self.token1}')

        # Name too short
        res1 = self.client.post(url, {'name': 'A', 'max_players': 2}, format='json')
        self.assertEqual(res1.status_code, status.HTTP_400_BAD_REQUEST)

        # Capacity too high (> 10)
        res2 = self.client.post(url, {'name': 'Valid Name', 'max_players': 11}, format='json')
        self.assertEqual(res2.status_code, status.HTTP_400_BAD_REQUEST)

        # Capacity too low (< 2)
        res3 = self.client.post(url, {'name': 'Valid Name', 'max_players': 1}, format='json')
        self.assertEqual(res3.status_code, status.HTTP_400_BAD_REQUEST)


class PostgreSQLConcurrencyTests(TransactionTestCase):
    """
    Tests concurrent room joins specifically against PostgreSQL row-level locks.
    Uses TransactionTestCase so real database transactions and row locks execute.
    """

    def test_simultaneous_join_for_last_seat(self):
        """
        When only 1 seat remains in a room, two simultaneous join attempts must result
        in exactly one successful join (200) and one rejected join (400), with the room
        never exceeding max_players.
        """
        import concurrent.futures
        from rest_framework.test import APIClient

        # 1. Create host and room with max_players = 2
        host, host_token = GuestPlayer.create_guest(nickname='HostPlayer')
        room = Room.objects.create(
            code='RACE01',
            name='Race Room',
            host=host,
            is_private=False,
            max_players=2
        )
        RoomMembership.objects.create(
            room=room,
            player=host,
            role=MembershipRole.HOST,
            is_active=True
        )

        # 2. Create 2 competing players
        p1, token1 = GuestPlayer.create_guest(nickname='RacerOne')
        p2, token2 = GuestPlayer.create_guest(nickname='RacerTwo')

        url = reverse('rooms:room-join', kwargs={'room_code': 'RACE01'})

        def attempt_join(token):
            try:
                client = APIClient()
                client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
                return client.post(url, {}, format='json')
            finally:
                from django.db import connections
                connections.close_all()

        # 3. Fire both join requests concurrently using ThreadPoolExecutor
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(attempt_join, token1)
            future2 = executor.submit(attempt_join, token2)
            res1 = future1.result()
            res2 = future2.result()

        status_codes = sorted([res1.status_code, res2.status_code])
        # Exactly one must succeed (200), and exactly one must be rejected (400)
        self.assertEqual(
            status_codes,
            [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST],
            f"Expected [200, 400], got [{res1.status_code}: {res1.data}, {res2.status_code}: {res2.data}]"
        )

        # Verify PostgreSQL database state: exactly 2 active players (Host + 1 winner)
        room.refresh_from_db()
        self.assertEqual(room.active_players_count(), 2)
        self.assertTrue(room.is_full())

    def tearDown(self):
        from django.db import connections
        connections.close_all()
        super().tearDown()



