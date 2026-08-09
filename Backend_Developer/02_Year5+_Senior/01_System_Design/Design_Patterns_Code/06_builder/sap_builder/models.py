"""
Models for the SAP / E-Way Bill payload Builder demo.

SapDocumentDraft — the raw Aandhi-side data a payload gets built FROM.
                   Note how many fields are optional: that is exactly the
                   condition that makes a Builder worth having, because a
                   constructor taking all of them would be unreadable.
DraftLine       — the item lines.
BuiltPayload    — an audit record of a payload that was actually built.

All the assembly logic lives in builders.py. These models only store data.
"""
from django.db import models


class SapDocumentDraft(models.Model):
    """
    Everything known about a movement before a payload is assembled.

    A single draft can produce several different payloads — a full E-Way
    Bill, a minimal SAP lines payload, a delivery-direction bill or a
    pickup-direction one — which is why building is kept separate from the
    data. One source, many representations.
    """

    DOC_TYPE_CHOICES = [
        ('delivery', 'Delivery'),
        ('pickup', 'Pickup'),
    ]

    TRANSPORT_MODE_CHOICES = [
        ('Road', 'Road'),
        ('Rail', 'Rail'),
        ('Air', 'Air'),
        ('Ship', 'Ship'),
    ]

    doc_type = models.CharField(max_length=10, choices=DOC_TYPE_CHOICES)
    reference_no = models.CharField(
        max_length=50, unique=True,
        help_text='Source challan number, e.g. DC-000101',
    )

    # --- Business partner ------------------------------------------------
    card_code = models.CharField(max_length=20, blank=True, default='')
    card_name = models.CharField(max_length=255, blank=True, default='')

    # --- Company side (godown) -------------------------------------------
    from_warehouse = models.CharField(max_length=20, blank=True, default='')
    from_gstin = models.CharField(max_length=15, blank=True, default='')
    from_state_code = models.IntegerField(null=True, blank=True)
    from_pincode = models.IntegerField(null=True, blank=True)
    from_address = models.TextField(blank=True, default='')

    # --- Customer side (site) --------------------------------------------
    to_warehouse = models.CharField(max_length=20, blank=True, default='')
    to_gstin = models.CharField(max_length=15, blank=True, default='')
    to_state_code = models.IntegerField(null=True, blank=True)
    to_pincode = models.IntegerField(null=True, blank=True)
    to_address = models.TextField(blank=True, default='')

    # --- Transport (all optional) ----------------------------------------
    vehicle_number = models.CharField(max_length=20, blank=True, default='')
    transport_mode = models.CharField(
        max_length=10, choices=TRANSPORT_MODE_CHOICES,
        blank=True, default='Road',
    )
    transporter_id = models.CharField(max_length=20, blank=True, default='')
    distance_km = models.IntegerField(null=True, blank=True)

    posting_date = models.DateField()
    comments = models.TextField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'SAP Document Draft'
        verbose_name_plural = 'SAP Document Drafts'

    def __str__(self):
        return f'{self.reference_no} ({self.doc_type})'

    @property
    def is_intra_state(self):
        """
        True when both ends sit in the same GST state.

        Drives CGST+SGST vs IGST. Kept on the model because it is a fact
        about the data, not a decision about how to assemble a payload.
        """
        if self.from_state_code is None or self.to_state_code is None:
            return False
        return self.from_state_code == self.to_state_code


class DraftLine(models.Model):
    """One item line on a draft."""

    draft = models.ForeignKey(
        SapDocumentDraft, on_delete=models.CASCADE, related_name='lines',
    )
    line_num = models.IntegerField(default=0)
    item_code = models.CharField(max_length=50)
    item_name = models.CharField(max_length=255, blank=True, default='')
    hsn_code = models.CharField(max_length=10, blank=True, default='')
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    unit = models.CharField(max_length=10, default='NOS')
    rate = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        ordering = ['line_num', 'id']
        verbose_name = 'Draft Line'
        verbose_name_plural = 'Draft Lines'

    def __str__(self):
        return f'{self.item_code} x {self.quantity} {self.unit}'

    @property
    def amount(self):
        """Taxable value for this line."""
        return self.quantity * self.rate


class BuiltPayload(models.Model):
    """
    Audit record of a payload that was assembled and kept.

    Storing the computed tax split alongside the payload means a later
    dispute can be answered without re-running the builder against data
    that may since have changed.
    """

    draft = models.ForeignKey(
        SapDocumentDraft, on_delete=models.CASCADE, related_name='built_payloads',
    )
    builder_used = models.CharField(
        max_length=100, help_text='Builder class that produced this payload',
    )
    recipe = models.CharField(
        max_length=50, blank=True, default='',
        help_text='Director recipe name, if a director built it',
    )
    payload = models.JSONField(default=dict)
    line_count = models.IntegerField(default=0)
    taxable_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    cgst_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    sgst_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    igst_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    built_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-built_at']
        verbose_name = 'Built Payload'
        verbose_name_plural = 'Built Payloads'

    def __str__(self):
        return f'{self.draft_id} via {self.builder_used} ({self.line_count} lines)'
