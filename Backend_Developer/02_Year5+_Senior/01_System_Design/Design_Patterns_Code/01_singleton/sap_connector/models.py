from django.db import models


class SapConnection(models.Model):
    """
    Tracks SAP B1 Service Layer sessions.
    In production, SapRepository.__construct() creates an expensive HTTP session
    to SAP B1 Service Layer. The Singleton pattern ensures only ONE session exists.
    """
    service_url = models.URLField()
    session_id = models.CharField(max_length=255)
    company_db = models.CharField(max_length=100, default='YOUNGMAN_LIVE')
    connected_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    request_count = models.IntegerField(default=0)

    class Meta:
        ordering = ['-connected_at']

    def __str__(self):
        status = 'ACTIVE' if self.is_active else 'CLOSED'
        return f'[{status}] {self.session_id} -> {self.company_db}'


class ConnectionLog(models.Model):
    """
    Audit trail of every SAP B1 API call made through the singleton connection.
    Maps to real SAP entities: Invoices, CreditNotes, JournalEntries, BusinessPartners, Orders.
    """
    ENTITY_CHOICES = [
        ('Invoices', 'Invoices'),
        ('CreditNotes', 'Credit Notes'),
        ('JournalEntries', 'Journal Entries'),
        ('BusinessPartners', 'Business Partners'),
        ('Orders', 'Orders'),
        ('Session', 'Session'),
    ]
    ACTION_CHOICES = [
        ('POST', 'POST'),
        ('GET', 'GET'),
        ('PATCH', 'PATCH'),
    ]

    connection = models.ForeignKey(
        SapConnection,
        on_delete=models.CASCADE,
        related_name='logs',
    )
    entity_type = models.CharField(max_length=50, choices=ENTITY_CHOICES)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    endpoint = models.CharField(max_length=200)
    success = models.BooleanField(default=True)
    response_time_ms = models.IntegerField(null=True, blank=True)
    error_message = models.TextField(blank=True, default='')
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        status = 'OK' if self.success else 'FAIL'
        return f'[{status}] {self.action} {self.entity_type} @ {self.timestamp:%H:%M:%S}'
