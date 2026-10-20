"""Tests for Guest Player Identity and Authentication."""
import hashlib
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from .models import GuestPlayer


class GuestPlayerTests(APITestCase):
    """Test suite for Guest Player identity creation, auth, and profile endpoints."""

    def test_create_guest_default_nickname(self):
        """Visitor can create a guest identity without providing credentials or email."""
        url = reverse('players:guest-create')
        response = self.client.post(url, {}, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('id', response.data)
        self.assertIn('nickname', response.data)
        self.assertIn('token', response.data)
        self.assertIn('created_at', response.data)

        raw_token = response.data['token']
        player_id = response.data['id']

        # Verify DB persistence
        player = GuestPlayer.objects.get(id=player_id)
        self.assertTrue(player.is_active)
        self.assertTrue(player.nickname.startswith('Guest-'))

        # Security check: DB must store ONLY the SHA-256 hash, never raw token
        expected_hash = hashlib.sha256(raw_token.encode('utf-8')).hexdigest()
        self.assertEqual(player.token_hash, expected_hash)
        self.assertNotIn(raw_token, player.token_hash)

    def test_create_guest_custom_nickname(self):
        """Visitor can supply a valid custom display name."""
        url = reverse('players:guest-create')
        payload = {'nickname': 'Striker_99'}
        response = self.client.post(url, payload, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['nickname'], 'Striker_99')

    def test_create_guest_invalid_nickname(self):
        """Rejects nicknames with invalid characters or inappropriate length."""
        url = reverse('players:guest-create')

        # Too short (< 2 chars)
        res_short = self.client.post(url, {'nickname': 'A'}, format='json')
        self.assertEqual(res_short.status_code, status.HTTP_400_BAD_REQUEST)

        # Illegal symbols
        res_symbols = self.client.post(url, {'nickname': 'bad<script>'}, format='json')
        self.assertEqual(res_symbols.status_code, status.HTTP_400_BAD_REQUEST)

    def test_guest_authentication_via_bearer_header(self):
        """Returning guest can authenticate using Authorization: Bearer <token>."""
        guest, raw_token = GuestPlayer.create_guest(nickname='FlickMaster')

        url = reverse('players:guest-me')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {raw_token}')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(guest.id))
        self.assertEqual(response.data['nickname'], 'FlickMaster')
        # Security: token and token_hash must NOT be present in profile response
        self.assertNotIn('token', response.data)
        self.assertNotIn('token_hash', response.data)

    def test_guest_authentication_via_custom_header(self):
        """Returning guest can authenticate using X-Guest-Token header."""
        guest, raw_token = GuestPlayer.create_guest(nickname='SpinDoctor')

        url = reverse('players:guest-me')
        response = self.client.get(url, HTTP_X_GUEST_TOKEN=raw_token)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], str(guest.id))

    def test_rejection_of_unauthenticated_request(self):
        """Protected endpoints reject requests missing authentication tokens."""
        url = reverse('players:guest-me')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rejection_of_invalid_token(self):
        """Protected endpoints reject invalid or tampered tokens."""
        url = reverse('players:guest-me')
        self.client.credentials(HTTP_AUTHORIZATION='Bearer completely-invalid-fake-token')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_rejection_of_inactive_player(self):
        """Inactive players cannot authenticate even with valid tokens."""
        guest, raw_token = GuestPlayer.create_guest(nickname='BannedPlayer')
        guest.is_active = False
        guest.save()

        url = reverse('players:guest-me')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {raw_token}')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_nickname(self):
        """Authenticated guest can update their display name."""
        guest, raw_token = GuestPlayer.create_guest(nickname='OldNick')

        url = reverse('players:guest-me')
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {raw_token}')
        response = self.client.patch(url, {'nickname': 'NewNick'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['nickname'], 'NewNick')
        guest.refresh_from_db()
        self.assertEqual(guest.nickname, 'NewNick')
