"""
DRF serializers for the payload Builder demo.

These cover the DRAFT side only. There is deliberately no serializer for
the built payload itself: its shape depends on which builder and which
recipe produced it, and pinning that down in a serializer would undo the
flexibility the Builder exists to provide.
"""
from rest_framework import serializers

from .models import BuiltPayload, DraftLine, SapDocumentDraft


class DraftLineSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True)

    class Meta:
        model = DraftLine
        fields = [
            'id',
            'draft',
            'line_num',
            'item_code',
            'item_name',
            'hsn_code',
            'quantity',
            'unit',
            'rate',
            'amount',
        ]
        read_only_fields = ['id', 'draft', 'amount']


class BuiltPayloadSerializer(serializers.ModelSerializer):
    class Meta:
        model = BuiltPayload
        fields = [
            'id',
            'draft',
            'builder_used',
            'recipe',
            'payload',
            'line_count',
            'taxable_value',
            'cgst_value',
            'sgst_value',
            'igst_value',
            'total_value',
            'built_at',
        ]
        read_only_fields = fields


class BuiltPayloadListSerializer(serializers.ModelSerializer):
    """List variant — omits the payload body."""

    class Meta:
        model = BuiltPayload
        fields = [
            'id',
            'draft',
            'builder_used',
            'recipe',
            'line_count',
            'taxable_value',
            'total_value',
            'built_at',
        ]
        read_only_fields = fields


class SapDocumentDraftSerializer(serializers.ModelSerializer):
    lines = DraftLineSerializer(many=True, read_only=True)
    is_intra_state = serializers.BooleanField(read_only=True)

    class Meta:
        model = SapDocumentDraft
        fields = [
            'id',
            'doc_type',
            'reference_no',
            'card_code',
            'card_name',
            'from_warehouse',
            'from_gstin',
            'from_state_code',
            'from_pincode',
            'from_address',
            'to_warehouse',
            'to_gstin',
            'to_state_code',
            'to_pincode',
            'to_address',
            'vehicle_number',
            'transport_mode',
            'transporter_id',
            'distance_km',
            'posting_date',
            'comments',
            'created_at',
            'is_intra_state',
            'lines',
        ]
        read_only_fields = ['id', 'created_at', 'is_intra_state']


class SapDocumentDraftListSerializer(serializers.ModelSerializer):
    class Meta:
        model = SapDocumentDraft
        fields = [
            'id',
            'doc_type',
            'reference_no',
            'card_name',
            'from_warehouse',
            'to_warehouse',
            'vehicle_number',
            'posting_date',
            'created_at',
        ]
        read_only_fields = fields


class BuildRequestSerializer(serializers.Serializer):
    """Input for the build endpoint."""

    recipe = serializers.ChoiceField(
        choices=['auto', 'delivery', 'pickup', 'minimal'],
        required=False, default='auto',
    )
    vehicle_number = serializers.CharField(
        required=False, allow_blank=True, default='')
    transport_mode = serializers.CharField(
        required=False, allow_blank=True, default='')
    transporter_id = serializers.CharField(
        required=False, allow_blank=True, default='')
    distance_km = serializers.IntegerField(required=False, allow_null=True)
    save = serializers.BooleanField(required=False, default=True)
