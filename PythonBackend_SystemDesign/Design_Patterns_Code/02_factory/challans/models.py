from django.db import models


class Challan(models.Model):
    """
    Core Challan model.
    The challan_movement_type determines which factory class handles
    validation, defaults, and initial stage assignment.
    """

    CHALLAN_TYPE_CHOICES = [
        ("Delivery", "Delivery"),
        ("Pickup", "Pickup"),
    ]

    MOVEMENT_TYPE_CHOICES = [
        ("delivery", "Delivery"),
        ("pickup", "Pickup"),
        ("inter_branch", "Inter Branch"),
        ("capital_purchase", "Capital Purchase"),
        ("sales", "Sales"),
    ]

    AUTHORIZATION_CHOICES = [
        ("0", "Pending"),
        ("1", "Authorized"),
        ("-1", "Rejected"),
    ]

    challan_no = models.CharField(max_length=50, unique=True)
    challan_type = models.CharField(max_length=20, choices=CHALLAN_TYPE_CHOICES)
    challan_movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPE_CHOICES)
    order_id = models.IntegerField(null=True, blank=True)
    customer_name = models.CharField(max_length=255, blank=True, default="")
    pickup_location = models.CharField(max_length=255, default="")
    delivery_location = models.CharField(max_length=255, default="")
    dispatch_date = models.DateField(null=True, blank=True)
    distance_km = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    vehicle_number = models.CharField(max_length=50, blank=True, default="")
    is_authorized = models.CharField(
        max_length=2, default="0", choices=AUTHORIZATION_CHOICES
    )
    current_stage = models.CharField(max_length=50, default="PLANNING_DONE")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.challan_no} ({self.challan_movement_type})"


class ChallanItem(models.Model):
    """Line items on a challan."""

    challan = models.ForeignKey(Challan, on_delete=models.CASCADE, related_name="items")
    item_code = models.CharField(max_length=50)
    item_name = models.CharField(max_length=255)
    quantity = models.IntegerField()
    ok_quantity = models.IntegerField(default=0)
    damaged_quantity = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.item_code} x {self.quantity}"


class ChallanCreationLog(models.Model):
    """
    Audit log capturing which factory class was used, what movement type
    was requested, and which fields were validated during creation.
    """

    challan = models.ForeignKey(
        Challan, on_delete=models.CASCADE, related_name="creation_logs"
    )
    movement_type = models.CharField(max_length=20)
    required_fields_validated = models.JSONField()
    factory_used = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Log: {self.challan.challan_no} via {self.factory_used}"
