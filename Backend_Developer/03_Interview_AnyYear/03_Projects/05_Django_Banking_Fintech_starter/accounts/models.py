import random

from django.conf import settings
from django.db import models


ACCOUNT_TYPES = [
    ("savings", "Savings"),
    ("current", "Current"),
    ("escrow", "Escrow"),
    ("system", "System"),  # internal cash/float account — deposits & withdrawals settle against this
]

ACCOUNT_STATUSES = [
    ("active", "Active"),
    ("frozen", "Frozen"),
    ("closed", "Closed"),
]


def generate_account_number() -> str:
    """14-digit account number (spec section 6). Collision is handled by the
    caller retrying on IntegrityError — see AccountService.open_account."""
    return "".join(str(random.randint(0, 9)) for _ in range(14))


class Account(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="accounts",
        null=True, blank=True,  # null only for the system cash account
    )
    account_number = models.CharField(max_length=14, unique=True, default=generate_account_number)
    account_type = models.CharField(max_length=10, choices=ACCOUNT_TYPES)
    currency = models.CharField(max_length=3, default="INR")
    status = models.CharField(max_length=10, choices=ACCOUNT_STATUSES, default="active")
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user"])]

    def __str__(self) -> str:
        return f"{self.account_type}:{self.account_number}"


class Balance(models.Model):
    """One row per account. `current_balance` is always derivable from
    LedgerEntry — this table is a cache for fast reads (spec section 6)."""

    account = models.OneToOneField(Account, on_delete=models.CASCADE, primary_key=True, related_name="balance")
    current_balance = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    available_balance = models.DecimalField(max_digits=15, decimal_places=4, default=0)
    version = models.IntegerField(default=0)  # optimistic-lock counter for cached (non-transactional) reads
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.account.account_number}: {self.current_balance}"
