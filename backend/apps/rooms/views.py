"""Views for Game Room Management."""
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.players.authentication import IsGuestAuthenticated
from .models import (
    MembershipRole,
    Room,
    RoomMembership,
    RoomStatus,
    generate_unique_room_code,
)
from .serializers import (
    RoomCreateSerializer,
    RoomDetailSerializer,
    RoomJoinSerializer,
    RoomListSerializer,
)


class RoomListCreateView(APIView):
    """
    GET /api/rooms/
        List public, joinable rooms waiting for players.
    POST /api/rooms/
        Create a new room. Requires guest authentication.
        Creator is automatically assigned as the initial HOST.
    """
    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsGuestAuthenticated()]
        return []

    def get(self, request):
        # Query public rooms that are currently in WAITING status
        rooms = (
            Room.objects.filter(is_private=False, status=RoomStatus.WAITING)
            .select_related('host')
            .prefetch_related('memberships')
            .order_by('-created_at')
        )
        # Filter out rooms that are already full
        eligible_rooms = [r for r in rooms if not r.is_full()]
        serializer = RoomListSerializer(eligible_rooms, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = RoomCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        data = serializer.validated_data
        name = data['name'].strip()
        is_private = data.get('is_private', False)
        passcode = data.get('passcode')
        max_players = data.get('max_players', 2)

        with transaction.atomic():
            code = generate_unique_room_code()
            room = Room(
                code=code,
                name=name,
                host=request.user,
                is_private=is_private,
                max_players=max_players,
                status=RoomStatus.WAITING,
            )
            if is_private and passcode:
                room.set_passcode(passcode)
            room.save()

            # Assign host membership
            RoomMembership.objects.create(
                room=room,
                player=request.user,
                role=MembershipRole.HOST,
                is_active=True
            )

        output_serializer = RoomDetailSerializer(room)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)


class RoomDetailView(APIView):
    """
    GET /api/rooms/{room_code}/
        Retrieve permitted room details and active player rosters.
        Public rooms are accessible to all.
        For private rooms: accessible to active members, or visitors providing
        the passcode via 'X-Room-Passcode' header (query parameters avoided for security).
    POST /api/rooms/{room_code}/
        Retrieve permitted private room details by supplying {"passcode": "..."} in request body.
    """
    def _check_and_serialize_room(self, request, room_code: str, raw_passcode: str | None = None):
        room = get_object_or_404(
            Room.objects.select_related('host').prefetch_related('memberships__player'),
            code=room_code.upper()
        )

        if room.is_private:
            is_member = False
            if request.user and request.user.is_authenticated:
                is_member = room.memberships.filter(player=request.user, is_active=True).exists()

            if not is_member:
                passcode = raw_passcode or request.headers.get('X-Room-Passcode')
                if not room.check_passcode(passcode):
                    raise PermissionDenied('This room is private. Valid passcode required to view details.')

        serializer = RoomDetailSerializer(room)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def get(self, request, room_code: str):
        return self._check_and_serialize_room(request, room_code)

    def post(self, request, room_code: str):
        passcode = (request.data.get('passcode') or '').strip() if isinstance(request.data, dict) else None
        return self._check_and_serialize_room(request, room_code, raw_passcode=passcode)


class RoomJoinView(APIView):
    """
    POST /api/rooms/{room_code}/join/
        Join an eligible room. Requires guest authentication.
        Enforces atomic locking, capacity limits, state checks,
        and duplicate membership prevention.
    """
    permission_classes = [IsGuestAuthenticated]

    def post(self, request, room_code: str):
        serializer = RoomJoinSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        passcode = serializer.validated_data.get('passcode')

        with transaction.atomic():
            # Row-level lock exclusively on the target Room record (PostgreSQL-optimized)
            try:
                room = Room.objects.select_for_update().get(code=room_code.upper())
            except Room.DoesNotExist:
                return Response(
                    {'detail': 'Room not found.'},
                    status=status.HTTP_404_NOT_FOUND
                )

            # 1. State check: only WAITING rooms may be joined
            if room.status != RoomStatus.WAITING:
                return Response(
                    {'detail': f"Cannot join room with status '{room.get_status_display()}'."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 2. Private room passcode check
            if room.is_private:
                if not room.check_passcode(passcode):
                    return Response(
                        {'detail': 'Invalid room passcode.'},
                        status=status.HTTP_403_FORBIDDEN
                    )

            # 3. Duplicate active membership check
            already_active = RoomMembership.objects.select_for_update().filter(
                room=room,
                player=request.user,
                is_active=True
            ).exists()
            if already_active:
                return Response(
                    {'detail': 'You are already an active member of this room.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 4. Capacity check
            active_count = RoomMembership.objects.filter(room=room, is_active=True).count()
            if active_count >= room.max_players:
                return Response(
                    {'detail': 'Room has reached maximum player capacity.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # 5. Join / Re-join
            past_membership = RoomMembership.objects.filter(
                room=room,
                player=request.user,
                is_active=False
            ).first()

            if past_membership:
                past_membership.is_active = True
                past_membership.left_at = None
                past_membership.role = MembershipRole.PLAYER
                past_membership.save(update_fields=['is_active', 'left_at', 'role'])
            else:
                RoomMembership.objects.create(
                    room=room,
                    player=request.user,
                    role=MembershipRole.PLAYER,
                    is_active=True
                )

        output_serializer = RoomDetailSerializer(room)
        return Response(output_serializer.data, status=status.HTTP_200_OK)


class RoomLeaveView(APIView):
    """
    POST /api/rooms/{room_code}/leave/
        Leave a room. Requires guest authentication.
        
        Host Leaving Policy:
        - If the leaving player is the HOST and other active players remain,
          ownership is automatically transferred to the next oldest active member.
        - If the leaving player is the HOST and NO other players remain,
          the room is transitioned to CLOSED.
        - Non-host leaving simply updates their active membership to False.
    """
    permission_classes = [IsGuestAuthenticated]

    def post(self, request, room_code: str):
        with transaction.atomic():
            try:
                room = Room.objects.select_for_update().get(code=room_code.upper())
            except Room.DoesNotExist:
                return Response(
                    {'detail': 'Room not found.'},
                    status=status.HTTP_404_NOT_FOUND
                )

            membership = RoomMembership.objects.select_for_update().filter(
                room=room,
                player=request.user,
                is_active=True
            ).first()

            if not membership:
                return Response(
                    {'detail': 'You are not an active member of this room.'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Mark player as left
            membership.leave()

            # Handle Host-leaving lifecycle
            if request.user == room.host:
                next_active_member = (
                    room.memberships.filter(is_active=True)
                    .order_by('joined_at')
                    .first()
                )
                if next_active_member:
                    # Transfer ownership to oldest remaining member
                    room.host = next_active_member.player
                    room.save(update_fields=['host', 'updated_at'])
                    next_active_member.role = MembershipRole.HOST
                    next_active_member.save(update_fields=['role'])
                else:
                    # No active players left; close the room
                    room.status = RoomStatus.CLOSED
                    room.save(update_fields=['status', 'updated_at'])

        return Response(
            {
                'detail': 'Successfully left the room.',
                'room_code': room.code,
                'room_status': room.status,
            },
            status=status.HTTP_200_OK
        )
