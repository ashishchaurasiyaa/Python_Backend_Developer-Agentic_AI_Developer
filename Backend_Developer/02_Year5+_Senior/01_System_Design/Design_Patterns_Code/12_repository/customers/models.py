from django.db import models
from decimal import Decimal


class Customer(models.Model):
    """
    Core customer model for Youngman India B2B scaffolding rental business.
    Maps to SAP customer master data synced nightly.
    """

    BUSINESS_TYPE_CHOICES = [
        ("construction", "Construction"),
        ("infrastructure", "Infrastructure"),
        ("industrial", "Industrial"),
        ("events", "Events"),
    ]

    CREDIT_RATING_CHOICES = [
        ("A", "Excellent"),
        ("B", "Good"),
        ("C", "Average"),
        ("D", "Poor"),
        ("E", "Blocked"),
    ]

    sap_ref = models.CharField(
        max_length=20, unique=True, null=True, blank=True,
        help_text="SAP Customer Reference Number (synced from SAP B1)",
    )
    company = models.CharField(max_length=255, help_text="Registered company name")
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20)
    gstn = models.CharField(
        max_length=20, blank=True, default="",
        help_text="GST Identification Number",
    )
    credit_limit = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
        help_text="Credit limit in INR",
    )
    credit_rating = models.CharField(
        max_length=1, choices=CREDIT_RATING_CHOICES, default="C",
    )
    due_days = models.PositiveIntegerField(
        default=30, help_text="Payment due days",
    )
    business_type = models.CharField(
        max_length=20, choices=BUSINESS_TYPE_CHOICES, default="construction",
    )
    is_verified = models.BooleanField(
        default=False, help_text="KYC verification status",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.company} ({self.sap_ref or 'No SAP Ref'})"

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"


class CustomerContact(models.Model):
    """
    Additional contacts for a customer — purchasers, site contacts,
    decision makers — used by sales reps on the field.
    """

    CONTACT_TYPE_CHOICES = [
        ("purchaser", "Purchaser"),
        ("site_contact", "Site Contact"),
        ("decision_maker", "Decision Maker"),
    ]

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="contacts",
    )
    contact_type = models.CharField(
        max_length=20, choices=CONTACT_TYPE_CHOICES, default="purchaser",
    )
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True, default="")

    class Meta:
        ordering = ["contact_type", "name"]

    def __str__(self):
        return f"{self.name} ({self.get_contact_type_display()}) - {self.customer.company}"


class CustomerOutstanding(models.Model):
    """
    Outstanding invoices for a customer — synced from SAP.
    Used by credit control team and sales reps.
    """

    STATUS_CHOICES = [
        ("open", "Open"),
        ("partial", "Partially Paid"),
        ("overdue", "Overdue"),
        ("paid", "Paid"),
    ]

    customer = models.ForeignKey(
        Customer, on_delete=models.CASCADE, related_name="outstandings",
    )
    invoice_number = models.CharField(max_length=50)
    amount = models.DecimalField(
        max_digits=12, decimal_places=2, help_text="Original invoice amount in INR",
    )
    balance = models.DecimalField(
        max_digits=12, decimal_places=2, help_text="Remaining balance in INR",
    )
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default="open",
    )
    due_date = models.DateField()

    class Meta:
        ordering = ["due_date"]

    def __str__(self):
        return f"INV-{self.invoice_number} | {self.customer.company} | Balance: {self.balance}"
