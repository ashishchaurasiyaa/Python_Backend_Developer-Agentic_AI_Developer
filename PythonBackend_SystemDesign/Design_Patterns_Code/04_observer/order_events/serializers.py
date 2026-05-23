from rest_framework import serializers
from .models import Order, Notification, EventLog


class OrderSerializer(serializers.ModelSerializer):
    """Serializer for Order model."""

    class Meta:
        model = Order
        fields = [
            'id', 'job_order', 'customer_name', 'godown', 'po_no',
            'total_amount', 'status', 'account_manager_email',
            'customer_phone', 'created_by', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class OrderCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating orders (status defaults to under_review)."""

    class Meta:
        model = Order
        fields = [
            'job_order', 'customer_name', 'godown', 'po_no',
            'total_amount', 'account_manager_email', 'customer_phone',
            'created_by',
        ]


class NotificationSerializer(serializers.ModelSerializer):
    """Serializer for Notification model."""
    order_job_order = serializers.CharField(source='order.job_order', read_only=True)

    class Meta:
        model = Notification
        fields = [
            'id', 'order', 'order_job_order', 'recipient', 'channel',
            'subject', 'message', 'event_type', 'is_read', 'sent_at',
        ]
        read_only_fields = ['id', 'sent_at']


class EventLogSerializer(serializers.ModelSerializer):
    """Serializer for EventLog model."""
    order_job_order = serializers.CharField(source='order.job_order', read_only=True)

    class Meta:
        model = EventLog
        fields = [
            'id', 'event_type', 'order', 'order_job_order', 'payload',
            'observers_notified', 'observer_names', 'created_at',
        ]
        read_only_fields = ['id', 'created_at']


class RegisterObserverSerializer(serializers.Serializer):
    """Serializer for dynamically registering an observer."""
    event_type = serializers.CharField(max_length=50)
    observer_name = serializers.CharField(max_length=100)


class UnsubscribeObserverSerializer(serializers.Serializer):
    """Serializer for removing an observer."""
    event_type = serializers.CharField(max_length=50)
    observer_name = serializers.CharField(max_length=100)
