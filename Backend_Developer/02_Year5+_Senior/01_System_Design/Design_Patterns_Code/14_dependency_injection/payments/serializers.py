from rest_framework import serializers

from .models import Payment, PaymentLog


class PaymentLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentLog
        fields = [
            "id",
            "action",
            "request_payload",
            "response_payload",
            "status",
            "created_at",
        ]


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "id",
            "order_id",
            "amount",
            "currency",
            "gateway",
            "gateway_reference_id",
            "status",
            "customer_phone",
            "created_at",
        ]


class PaymentDetailSerializer(serializers.ModelSerializer):
    """Includes nested logs for a detailed view."""

    logs = PaymentLogSerializer(many=True, read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "order_id",
            "amount",
            "currency",
            "gateway",
            "gateway_reference_id",
            "status",
            "customer_phone",
            "created_at",
            "logs",
        ]
