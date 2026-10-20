"""Views for Guest Player Identity."""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from .authentication import IsGuestAuthenticated
from .models import GuestPlayer
from .serializers import (
    GuestCreateRequestSerializer,
    GuestCreateResponseSerializer,
    GuestProfileSerializer,
)


class GuestCreateView(APIView):
    """
    POST /api/players/guest/
    
    Creates a new guest player identity.
    Returns the player's public UUID and a secret session token.
    The secret session token must be saved by the client and sent
    in the Authorization: Bearer <token> or X-Guest-Token header.
    """
    permission_classes = []
    authentication_classes = []

    def post(self, request):
        input_serializer = GuestCreateRequestSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)

        nickname = input_serializer.validated_data.get('nickname')
        guest, raw_token = GuestPlayer.create_guest(nickname=nickname)

        # Attach transient raw token for one-time response serialization
        guest.token = raw_token
        output_serializer = GuestCreateResponseSerializer(guest)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class GuestMeView(APIView):
    """
    GET /api/players/me/
    PATCH /api/players/me/
    
    Retrieves or updates the authenticated guest player's profile.
    Requires Authorization: Bearer <token> or X-Guest-Token: <token>.
    """
    permission_classes = [IsGuestAuthenticated]

    def get(self, request):
        serializer = GuestProfileSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def patch(self, request):
        serializer = GuestProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
