"""
DRF serializers for SAP document posting.

These describe the Aandhi-side records only. The SAP-side payload shape is
NOT modelled here on purpose — it is produced by the factories, and it
differs per family, which is the whole reason the pattern exists.
"""
from rest_framework import serializers

from .models import SapDocument, SapDocumentLine, SapPostingLog


class SapDocumentLineSerializer(serializers.ModelSerializer):
    class Meta:
        model = SapDocumentLine
        fields = [
            'id',
            'document',
            'line_num',
            'item_code',
            'item_name',
            'quantity',
            'unit_price',
            'warehouse_code',
            'base_entry',
            'base_line',
        ]
        read_only_fields = ['id', 'document']


class SapPostingLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SapPostingLog
        fields = [
            'id',
            'document',
            'factory_used',
            'endpoint',
            'succeeded',
            'message',
            'attempted_at',
        ]
        read_only_fields = fields


class SapDocumentSerializer(serializers.ModelSerializer):
    """Full document with nested lines and posting history."""

    lines = SapDocumentLineSerializer(many=True, read_only=True)
    posting_logs = SapPostingLogSerializer(many=True, read_only=True)
    family_display = serializers.CharField(
        source='get_doc_family_display', read_only=True)

    class Meta:
        model = SapDocument
        fields = [
            'id',
            'doc_family',
            'family_display',
            'reference_no',
            'card_code',
            'card_name',
            'from_warehouse',
            'to_warehouse',
            'posting_date',
            'comments',
            'doc_total',
            'return_reason',
            'status',
            'sap_doc_entry',
            'sap_doc_num',
            'error_message',
            'created_at',
            'lines',
            'posting_logs',
        ]
        read_only_fields = [
            'id', 'status', 'sap_doc_entry', 'sap_doc_num',
            'error_message', 'created_at',
        ]


class SapDocumentListSerializer(serializers.ModelSerializer):
    """Lighter representation for list endpoints."""

    class Meta:
        model = SapDocument
        fields = [
            'id',
            'doc_family',
            'reference_no',
            'card_code',
            'from_warehouse',
            'to_warehouse',
            'posting_date',
            'doc_total',
            'status',
            'sap_doc_entry',
            'sap_doc_num',
            'created_at',
        ]
        read_only_fields = fields


class CreateSapDocumentSerializer(serializers.Serializer):
    """
    Input for POST /api/documents/.

    Accepts the document plus its lines in one call, because a SAP document
    with no lines is never valid in any family.
    """

    doc_family = serializers.ChoiceField(
        choices=[choice[0] for choice in SapDocument.DOC_FAMILY_CHOICES])
    reference_no = serializers.CharField(max_length=50)
    card_code = serializers.CharField(
        max_length=20, required=False, default='', allow_blank=True)
    card_name = serializers.CharField(
        max_length=255, required=False, default='', allow_blank=True)
    from_warehouse = serializers.CharField(
        max_length=20, required=False, default='', allow_blank=True)
    to_warehouse = serializers.CharField(
        max_length=20, required=False, default='', allow_blank=True)
    posting_date = serializers.DateField()
    comments = serializers.CharField(
        required=False, default='', allow_blank=True)
    doc_total = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, default=0)
    return_reason = serializers.CharField(
        max_length=255, required=False, default='', allow_blank=True)
    lines = serializers.ListField(
        child=serializers.DictField(), required=False, default=list)
