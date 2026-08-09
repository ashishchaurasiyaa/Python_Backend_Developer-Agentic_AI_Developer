"""
Models for SAP Document posting (Abstract Factory demo).

SapDocument     — a document Youngman intends to push into SAP Business One.
SapDocumentLine — its line items.
SapPostingLog   — immutable audit of every posting attempt.

Keep these dumb on purpose. The interesting behaviour — how a Delivery Note
payload differs from a Return payload, and which SAP endpoint each one must
go to — lives in factories.py, not here.
"""
from django.db import models


class SapDocument(models.Model):
    """
    One document destined for SAP Business One.

    `doc_family` is the only field the client code needs in order to pick a
    factory. Everything downstream (header shape, line shape, endpoint) is
    decided by the concrete factory that family maps to.
    """

    DOC_FAMILY_CHOICES = [
        ('delivery', 'Delivery Note'),
        ('return', 'Return'),
        ('transfer', 'Inventory Transfer'),
        ('invoice', 'A/R Invoice'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('posted', 'Posted'),
        ('failed', 'Failed'),
    ]

    doc_family = models.CharField(
        max_length=20, choices=DOC_FAMILY_CHOICES,
        help_text='Which SAP document family this record becomes',
    )
    reference_no = models.CharField(
        max_length=50, unique=True,
        help_text='Source document number in Aandhi, e.g. DC-000101',
    )
    card_code = models.CharField(
        max_length=20, blank=True, default='',
        help_text='SAP Business Partner code. Blank for internal transfers.',
    )
    card_name = models.CharField(
        max_length=255, blank=True, default='',
        help_text='Business partner name, for readability only',
    )
    from_warehouse = models.CharField(
        max_length=20, blank=True, default='',
        help_text='Issuing warehouse code',
    )
    to_warehouse = models.CharField(
        max_length=20, blank=True, default='',
        help_text='Receiving warehouse code (inventory transfers)',
    )
    posting_date = models.DateField(
        help_text='SAP DocDate',
    )
    comments = models.TextField(
        blank=True, default='',
        help_text='Free-text comments carried into SAP',
    )
    doc_total = models.DecimalField(
        max_digits=14, decimal_places=2, default=0,
        help_text='Document total, used by the invoice family',
    )
    return_reason = models.CharField(
        max_length=255, blank=True, default='',
        help_text='Why material came back (return family only)',
    )
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default='draft',
        help_text='Posting status',
    )
    sap_doc_entry = models.IntegerField(
        null=True, blank=True,
        help_text='DocEntry assigned by SAP once posted',
    )
    sap_doc_num = models.IntegerField(
        null=True, blank=True,
        help_text='Human-facing DocNum assigned by SAP',
    )
    error_message = models.TextField(
        blank=True, default='',
        help_text='Last posting failure reason',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'SAP Document'
        verbose_name_plural = 'SAP Documents'

    def __str__(self):
        return f'{self.reference_no} | {self.get_doc_family_display()} | {self.status}'


class SapDocumentLine(models.Model):
    """
    A line on a SapDocument.

    base_entry / base_line exist because a Return in SAP must reference the
    Delivery Note it reverses. Nothing else in the system needs them, which
    is precisely why the Return family gets its own lines builder.
    """

    document = models.ForeignKey(
        SapDocument, on_delete=models.CASCADE, related_name='lines',
    )
    line_num = models.IntegerField(
        default=0, help_text='Zero-based line number, as SAP expects',
    )
    item_code = models.CharField(max_length=50)
    item_name = models.CharField(max_length=255, blank=True, default='')
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit_price = models.DecimalField(
        max_digits=12, decimal_places=2, default=0,
        help_text='Required by the invoice family, ignored by transfers',
    )
    warehouse_code = models.CharField(max_length=20, blank=True, default='')
    base_entry = models.IntegerField(
        null=True, blank=True,
        help_text='DocEntry of the document being reversed (returns)',
    )
    base_line = models.IntegerField(
        null=True, blank=True,
        help_text='LineNum on the base document (returns)',
    )

    class Meta:
        ordering = ['line_num', 'id']
        verbose_name = 'SAP Document Line'
        verbose_name_plural = 'SAP Document Lines'

    def __str__(self):
        return f'{self.item_code} x {self.quantity}'


class SapPostingLog(models.Model):
    """Immutable record of every attempt to push a document to SAP."""

    document = models.ForeignKey(
        SapDocument, on_delete=models.CASCADE, related_name='posting_logs',
    )
    factory_used = models.CharField(
        max_length=100, help_text='Concrete factory class that built the payload',
    )
    endpoint = models.CharField(
        max_length=100, help_text='SAP Service Layer object posted to',
    )
    succeeded = models.BooleanField(default=False)
    message = models.TextField(blank=True, default='')
    attempted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-attempted_at']
        verbose_name = 'SAP Posting Log'
        verbose_name_plural = 'SAP Posting Logs'

    def __str__(self):
        outcome = 'OK' if self.succeeded else 'FAIL'
        return f'{self.document_id} -> {self.endpoint} [{outcome}]'
