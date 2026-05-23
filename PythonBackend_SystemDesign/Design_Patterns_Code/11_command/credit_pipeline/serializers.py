"""
DRF serializers for the Credit Pipeline State Machine.
"""
from rest_framework import serializers
from .models import CreditPipelineEntry, TransitionLog


class TransitionLogSerializer(serializers.ModelSerializer):
    """Read-only serializer for transition audit logs."""

    class Meta:
        model = TransitionLog
        fields = [
            'id',
            'entry',
            'from_status',
            'to_status',
            'command_name',
            'remarks',
            'executed_by',
            'executed_at',
            'is_undone',
        ]
        read_only_fields = fields


class CreditPipelineEntrySerializer(serializers.ModelSerializer):
    """Full serializer for pipeline entries, with nested transition history."""

    transitions = TransitionLogSerializer(many=True, read_only=True)
    transition_count = serializers.SerializerMethodField()

    class Meta:
        model = CreditPipelineEntry
        fields = [
            'invoice_doc_number',
            'order_id',
            'customer_name',
            'invoice_date',
            'amount',
            'balance',
            'current_status',
            'current_remarks',
            'ptp_date',
            'due_date',
            'created_at',
            'transition_count',
            'transitions',
        ]
        read_only_fields = [
            'invoice_date',
            'current_status',
            'current_remarks',
            'created_at',
        ]

    def get_transition_count(self, obj):
        return obj.transitions.count()


class CreditPipelineEntryListSerializer(serializers.ModelSerializer):
    """Lighter serializer for list views (no nested transitions)."""

    class Meta:
        model = CreditPipelineEntry
        fields = [
            'invoice_doc_number',
            'order_id',
            'customer_name',
            'invoice_date',
            'amount',
            'balance',
            'current_status',
            'current_remarks',
            'ptp_date',
            'due_date',
            'created_at',
        ]
        read_only_fields = [
            'invoice_date',
            'current_status',
            'current_remarks',
            'created_at',
        ]


class AdvanceStatusSerializer(serializers.Serializer):
    """Input for the advance-status endpoint."""
    remarks = serializers.CharField(required=False, default='', allow_blank=True)
    executed_by = serializers.CharField(required=False, default='system')


class MarkPaidSerializer(serializers.Serializer):
    """Input for the mark-paid endpoint."""
    payment_reference = serializers.CharField(required=False, default='', allow_blank=True)
    executed_by = serializers.CharField(required=False, default='system')


class EscalateSerializer(serializers.Serializer):
    """Input for the escalate-to-legal endpoint."""
    legal_remarks = serializers.CharField(required=False, default='', allow_blank=True)
    executed_by = serializers.CharField(required=False, default='system')
