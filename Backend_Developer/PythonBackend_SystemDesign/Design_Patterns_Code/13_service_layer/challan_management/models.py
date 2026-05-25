from django.db import models
from decimal import Decimal


class Challan(models.Model):
    """
    Core Challan model representing a delivery/pickup document in the
    scaffolding rental business.

    In the Youngman ERP, a Challan tracks the movement of scaffolding
    materials between branches, warehouses, and customer sites.
    """

    CHALLAN_TYPE_CHOICES = [
        ('Delivery', 'Delivery'),
        ('Pickup', 'Pickup'),
    ]

    MOVEMENT_TYPE_CHOICES = [
        ('delivery', 'Delivery'),
        ('pickup', 'Pickup'),
        ('inter_branch', 'Inter Branch'),
        ('sales', 'Sales'),
    ]

    AUTHORIZATION_CHOICES = [
        ('0', 'Under Review'),
        ('1', 'Authorized'),
        ('-1', 'Rejected'),
    ]

    STAGE_CHOICES = [
        ('PLANNING_DONE', 'Planning Done'),
        ('GENERATED_CHALLAN', 'Generated Challan'),
        ('VEHICLE_EXIT', 'Vehicle Exit'),
        ('ARRIVAL_AT_SITE', 'Arrival At Site'),
        ('INSTALLATION_DONE', 'Installation Done'),
        ('SITE_EXIT', 'Site Exit'),
        ('ARRIVAL_AT_BRANCH', 'Arrival At Branch'),
        ('CLOSED', 'Closed'),
    ]

    challan_no = models.CharField(max_length=20, unique=True)
    challan_type = models.CharField(max_length=10, choices=CHALLAN_TYPE_CHOICES)
    challan_movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPE_CHOICES)
    order_id = models.IntegerField()
    pickup_location = models.CharField(max_length=255)
    delivery_location = models.CharField(max_length=255)
    dispatch_date = models.DateField(null=True, blank=True)
    is_authorized = models.CharField(
        max_length=2,
        choices=AUTHORIZATION_CHOICES,
        default='0',
    )
    current_stage = models.CharField(
        max_length=30,
        choices=STAGE_CHOICES,
        default='PLANNING_DONE',
    )
    freight_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Challans'

    def __str__(self):
        return f"{self.challan_no} ({self.challan_type}) - {self.current_stage}"


class ChallanItem(models.Model):
    """
    Line items on a Challan -- the actual scaffolding materials being moved.

    Tracks quantity dispatched, received OK, damaged, and missing to handle
    the real-world reality of material discrepancies at site.
    """

    challan = models.ForeignKey(
        Challan,
        on_delete=models.CASCADE,
        related_name='items',
    )
    item_code = models.CharField(max_length=50)
    item_name = models.CharField(max_length=255)
    quantity = models.IntegerField()
    ok_quantity = models.IntegerField(default=0)
    damaged_quantity = models.IntegerField(default=0)
    missing_quantity = models.IntegerField(default=0)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.item_code} - {self.item_name} (qty: {self.quantity})"


class ChallanStageLog(models.Model):
    """
    Audit trail for every stage transition a Challan goes through.

    This is critical for the Service Layer pattern -- the service decides
    WHEN and HOW stage transitions happen, and logs every one.
    """

    challan = models.ForeignKey(
        Challan,
        on_delete=models.CASCADE,
        related_name='stage_logs',
    )
    from_stage = models.CharField(max_length=30)
    to_stage = models.CharField(max_length=30)
    changed_by = models.CharField(max_length=100, null=True, blank=True)
    remarks = models.TextField(blank=True, default='')
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['changed_at']

    def __str__(self):
        return f"{self.challan.challan_no}: {self.from_stage} -> {self.to_stage}"
