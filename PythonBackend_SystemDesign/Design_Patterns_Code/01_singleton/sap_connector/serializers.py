from rest_framework import serializers
from .models import SapConnection, ConnectionLog


class ConnectionLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConnectionLog
        fields = [
            'id',
            'connection',
            'entity_type',
            'action',
            'endpoint',
            'success',
            'response_time_ms',
            'error_message',
            'timestamp',
        ]


class SapConnectionSerializer(serializers.ModelSerializer):
    logs = ConnectionLogSerializer(many=True, read_only=True)

    class Meta:
        model = SapConnection
        fields = [
            'id',
            'service_url',
            'session_id',
            'company_db',
            'connected_at',
            'last_used_at',
            'is_active',
            'request_count',
            'logs',
        ]
