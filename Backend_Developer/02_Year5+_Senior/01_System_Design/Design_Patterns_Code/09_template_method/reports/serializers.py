"""
DRF serializers for the Report Generation pipeline.

Nothing pattern-specific lives here on purpose — the Template Method lives
in generators.py. These serializers only shape the HTTP payloads so the
views can stay thin and the tests can assert on real JSON.
"""
from rest_framework import serializers

from .models import GeneratedReport, Report, ReportRecipient


class ReportRecipientSerializer(serializers.ModelSerializer):
    """Email recipients attached to a report configuration."""

    class Meta:
        model = ReportRecipient
        fields = ['id', 'report', 'name', 'email']
        read_only_fields = ['id']


class GeneratedReportSerializer(serializers.ModelSerializer):
    """Audit row written by step 8 of the template method."""

    class Meta:
        model = GeneratedReport
        fields = [
            'id',
            'report',
            'file_name',
            'file_content',
            'row_count',
            'column_count',
            'generated_at',
            'sent_to',
            'status',
        ]
        read_only_fields = fields


class GeneratedReportListSerializer(serializers.ModelSerializer):
    """Lighter variant — omits file_content, which can be large."""

    class Meta:
        model = GeneratedReport
        fields = [
            'id',
            'report',
            'file_name',
            'row_count',
            'column_count',
            'generated_at',
            'sent_to',
            'status',
        ]
        read_only_fields = fields


class ReportSerializer(serializers.ModelSerializer):
    """Full report configuration with nested recipients."""

    recipients = ReportRecipientSerializer(many=True, read_only=True)
    recipient_count = serializers.SerializerMethodField()
    generated_count = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = [
            'id',
            'name',
            'report_type',
            'description',
            'output_format',
            'interval',
            'is_active',
            'last_generated',
            'created_at',
            'recipient_count',
            'generated_count',
            'recipients',
        ]
        read_only_fields = ['id', 'last_generated', 'created_at']

    def get_recipient_count(self, obj):
        return obj.recipients.count()

    def get_generated_count(self, obj):
        return obj.generated_reports.count()


class ReportListSerializer(serializers.ModelSerializer):
    """List view — no nested recipients."""

    class Meta:
        model = Report
        fields = [
            'id',
            'name',
            'report_type',
            'description',
            'output_format',
            'interval',
            'is_active',
            'last_generated',
            'created_at',
        ]
        read_only_fields = ['id', 'last_generated', 'created_at']


class AddRecipientSerializer(serializers.Serializer):
    """Input for the add-recipient endpoint."""

    name = serializers.CharField(max_length=100)
    email = serializers.EmailField()
