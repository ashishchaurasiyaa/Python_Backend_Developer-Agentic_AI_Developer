from django.db import models


class Order(models.Model):
    """
    Represents a Youngman job order.
    When status changes, the Observer pattern fires notifications.
    """

    STATUS_CHOICES = [
        ('under_review', 'Under Review'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('amended', 'Amended'),
    ]

    job_order = models.CharField(max_length=100, unique=True)
    customer_name = models.CharField(max_length=255)
    godown = models.CharField(max_length=100)
    po_no = models.CharField(max_length=50, blank=True, default='')
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='under_review')
    account_manager_email = models.EmailField(blank=True, default='')
    customer_phone = models.CharField(max_length=20, blank=True, default='')
    created_by = models.CharField(max_length=100, default='system')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.job_order} - {self.customer_name} ({self.status})"


class Notification(models.Model):
    """
    Stores every notification dispatched by an observer.
    Mirrors Laravel's DatabaseNotification model.
    """

    CHANNEL_CHOICES = [
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('database', 'Database'),
        ('whatsapp', 'WhatsApp'),
    ]

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='notifications')
    recipient = models.CharField(max_length=255)
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    subject = models.CharField(max_length=255, blank=True, default='')
    message = models.TextField()
    event_type = models.CharField(max_length=50)
    is_read = models.BooleanField(default=False)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sent_at']

    def __str__(self):
        return f"[{self.channel}] {self.event_type} -> {self.recipient}"


class EventLog(models.Model):
    """
    Audit log for every event that was fired.
    Tracks how many observers were notified and their names.
    """

    event_type = models.CharField(max_length=50)
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, related_name='event_logs', null=True)
    payload = models.JSONField(default=dict)
    observers_notified = models.IntegerField(default=0)
    observer_names = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Event: {self.event_type} | Observers: {self.observers_notified}"
