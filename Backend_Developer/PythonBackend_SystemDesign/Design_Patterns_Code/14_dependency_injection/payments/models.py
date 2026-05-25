from django.db import models


class Payment(models.Model):
    """
    Tracks every payment initiated through any gateway.
    The 'gateway' field records WHICH implementation was used — proof that DI
    lets us swap without touching this model.
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("success", "Success"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    ]

    order_id = models.IntegerField(db_index=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=5, default="INR")
    gateway = models.CharField(max_length=30)
    gateway_reference_id = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    customer_phone = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Payment #{self.id} | Order {self.order_id} | {self.gateway} | {self.status}"


class PaymentLog(models.Model):
    """
    Immutable audit trail for every gateway interaction.
    Stores raw request/response payloads for debugging.
    """

    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="logs")
    action = models.CharField(max_length=50)  # create_link / verify / refund
    request_payload = models.JSONField()
    response_payload = models.JSONField(null=True, blank=True)
    status = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Log #{self.id} | Payment {self.payment_id} | {self.action} | {self.status}"
