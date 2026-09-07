import uuid

from django.conf import settings
from django.db import models

from accounts.models import Account

TXN_TYPES = [
    ("transfer", "Transfer"),
    ("deposit", "Deposit"),
    ("withdrawal", "Withdrawal"),
]

TXN_STATUSES = [
    ("pending", "Pending"),
    ("success", "Success"),
    ("failed", "Failed"),
    ("reversed", "Reversed"),
]

ENTRY_TYPES = [
    ("D", "Debit"),
    ("C", "Credit"),
]


class Transaction(models.Model):
    """The logical operation (what the UI shows). The accounting reality
    lives in LedgerEntry — always 2+ rows per Transaction. See
    ledger/services.py for why both tables exist."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    idempotency_key = models.CharField(max_length=255, unique=True)
    txn_type = models.CharField(max_length=12, choices=TXN_TYPES)
    status = models.CharField(max_length=10, choices=TXN_STATUSES, default="pending")
    amount = models.DecimalField(max_digits=15, decimal_places=4)
    currency = models.CharField(max_length=3)
    source_account = models.ForeignKey(Account, null=True, blank=True, on_delete=models.PROTECT, related_name="outgoing_txns")
    dest_account = models.ForeignKey(Account, null=True, blank=True, on_delete=models.PROTECT, related_name="incoming_txns")
    description = models.TextField(blank=True, default="")
    external_ref = models.CharField(max_length=255, blank=True, default="")
    initiated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    initiated_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    failed_reason = models.TextField(blank=True, default="")
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["source_account", "-initiated_at"]),
            models.Index(fields=["dest_account", "-initiated_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.txn_type} {self.amount} ({self.status})"


class LedgerEntry(models.Model):
    """The double-entry side. Sum of all entries for a well-formed system is
    always 0 — see ledger/management/commands/reconcile_balances.py."""

    transaction = models.ForeignKey(Transaction, on_delete=models.PROTECT, related_name="entries")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="ledger_entries")
    entry_type = models.CharField(max_length=1, choices=ENTRY_TYPES)
    amount = models.DecimalField(max_digits=15, decimal_places=4)
    balance_after = models.DecimalField(max_digits=15, decimal_places=4)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["account", "id"]),
            models.Index(fields=["transaction"]),
        ]


class AuditLog(models.Model):
    """Append-only. A DB trigger (see migration 0002) blocks UPDATE/DELETE
    at the Postgres level — a Python-level guard is not enough for a
    compliance-grade audit trail (spec section 12)."""

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=100)
    resource_type = models.CharField(max_length=50, blank=True, default="")
    resource_id = models.CharField(max_length=100, blank=True, default="")
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)
    metadata = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["resource_type", "resource_id"])]

    def __str__(self) -> str:
        return f"{self.action} @ {self.created_at}"
