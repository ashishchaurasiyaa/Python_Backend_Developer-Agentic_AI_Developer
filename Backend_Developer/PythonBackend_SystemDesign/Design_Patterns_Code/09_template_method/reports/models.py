from django.db import models


class Report(models.Model):
    """Report configuration — defines what report to generate and how."""

    REPORT_TYPE_CHOICES = [
        ('credit_pipeline', 'Credit Pipeline'),
        ('challan_tat', 'Challan TAT'),
        ('revenue', 'Revenue'),
        ('utilization', 'Utilization'),
    ]

    OUTPUT_FORMAT_CHOICES = [
        ('csv', 'CSV'),
        ('excel', 'Excel'),
        ('json', 'JSON'),
    ]

    INTERVAL_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]

    name = models.CharField(max_length=100)
    report_type = models.CharField(max_length=50, choices=REPORT_TYPE_CHOICES)
    description = models.TextField(blank=True)
    output_format = models.CharField(
        max_length=10, choices=OUTPUT_FORMAT_CHOICES, default='csv'
    )
    interval = models.CharField(
        max_length=10, choices=INTERVAL_CHOICES, default='daily'
    )
    is_active = models.BooleanField(default=True)
    last_generated = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_report_type_display()})"


class ReportRecipient(models.Model):
    """Email recipients for a report."""

    report = models.ForeignKey(
        Report, on_delete=models.CASCADE, related_name='recipients'
    )
    name = models.CharField(max_length=100)
    email = models.EmailField()

    class Meta:
        unique_together = ['report', 'email']

    def __str__(self):
        return f"{self.name} <{self.email}>"


class GeneratedReport(models.Model):
    """Record of a generated report — audit trail."""

    STATUS_CHOICES = [
        ('generated', 'Generated'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
    ]

    report = models.ForeignKey(
        Report, on_delete=models.CASCADE, related_name='generated_reports'
    )
    file_name = models.CharField(max_length=255)
    file_content = models.TextField()
    row_count = models.IntegerField(default=0)
    column_count = models.IntegerField(default=0)
    generated_at = models.DateTimeField(auto_now_add=True)
    sent_to = models.JSONField(default=list)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='generated'
    )

    class Meta:
        ordering = ['-generated_at']

    def __str__(self):
        return f"{self.file_name} ({self.status})"
