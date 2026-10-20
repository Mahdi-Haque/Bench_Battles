"""Root Views for Bench Battles API."""
from django.db import connection
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


class HealthCheckView(APIView):
    """
    GET /api/health/
    Health check endpoint returning system status and database connectivity.
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        db_status = 'disconnected'
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1;')
                row = cursor.fetchone()
                if row and row[0] == 1:
                    db_status = 'connected'
        except Exception:
            db_status = 'unreachable'

        return Response(
            {
                'status': 'ok',
                'service': 'Bench Battles Backend',
                'database': db_status,
                'timestamp': timezone.now().isoformat(),
            },
            status=status.HTTP_200_OK
        )
