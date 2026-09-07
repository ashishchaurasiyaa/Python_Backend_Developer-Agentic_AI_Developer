"""TransferService / ReversalService — the correctness-critical core of this
project (spec section 7). Every money movement, including deposits and
withdrawals, goes through TransferService.transfer(): a deposit is a
transfer from the system cash account into the user's account, and a
withdrawal is the reverse — this is the standard double-entry trick from
spec section 4 and it means there is exactly one code path that can ever
move money.
"""

from decimal import Decimal

from django.conf import settings
from django.db import transaction as db_transaction
from django.utils import timezone

from accounts.models import Account, Balance
from ledger.exceptions import (
    AccountFrozenError,
    AlreadyReversedError,
    AmountExceedsLimitError,
    CannotReverseError,
    InsufficientFundsError,
    InvalidAmountError,
)
from ledger.models import AuditLog, LedgerEntry, Transaction

MAX_TRANSACTION_AMOUNT = Decimal(settings.MAX_TRANSACTION_AMOUNT)

SYSTEM_ACCOUNT_NUMBER = "00000000000001"


def get_or_create_system_account(currency: str = "INR") -> Account:
    """The cash/float account deposits credit from and withdrawals debit to.
    Spec section 4's second example: an external deposit is still a
    balanced two-sided entry, it just settles against this account instead
    of another user's account."""
    account, created = Account.objects.get_or_create(
        account_number=SYSTEM_ACCOUNT_NUMBER,
        defaults={"user": None, "account_type": "system", "currency": currency, "status": "active"},
    )
    if created:
        Balance.objects.create(account=account, current_balance=0, available_balance=0)
    return account


class TransferService:
    def transfer(
        self,
        source_account_id: int,
        dest_account_id: int,
        amount: Decimal,
        idempotency_key: str,
        txn_type: str = "transfer",
        description: str = "",
        initiated_by=None,
        metadata: dict | None = None,
    ) -> Transaction:
        # Idempotency: the DB unique constraint on idempotency_key is the
        # actual correctness guarantee (see ledger/views.py for the Redis
        # fast-path cache in front of this) — a retried request with the
        # same key always gets back the original transaction, never a
        # second debit (spec section 8, Stripe's pattern).
        existing = Transaction.objects.filter(idempotency_key=idempotency_key).first()
        if existing is not None:
            return existing

        if amount <= 0:
            raise InvalidAmountError()
        if amount > MAX_TRANSACTION_AMOUNT:
            raise AmountExceedsLimitError()

        with db_transaction.atomic():
            # Lock both accounts in a fixed order (ascending id) regardless
            # of which side is "source" vs "dest". Two concurrent transfers
            # moving money in opposite directions between the same pair of
            # accounts would otherwise lock source-then-dest on one thread
            # and dest-then-source on the other — a textbook deadlock. The
            # spec's own reference implementation (section 7) doesn't do
            # this; it's the one correction worth calling out.
            lo_id, hi_id = sorted([source_account_id, dest_account_id])
            locked = {a.id: a for a in Account.objects.select_for_update().filter(id__in=[lo_id, hi_id])}
            source = locked[source_account_id]
            dest = locked[dest_account_id]

            if source.status != "active":
                raise AccountFrozenError(f"Source account {source.account_number} is {source.status}")
            if dest.status != "active":
                raise AccountFrozenError(f"Destination account {dest.account_number} is {dest.status}")

            balances = {
                b.account_id: b
                for b in Balance.objects.select_for_update().filter(account_id__in=[lo_id, hi_id])
            }
            source_balance = balances[source.id]
            dest_balance = balances[dest.id]

            # The system cash account is the counterparty on every
            # deposit/withdrawal and is allowed to go negative (it's an
            # accounting fiction, not a real pool of money) — every other
            # account must have the funds.
            if source.account_type != "system" and source_balance.available_balance < amount:
                raise InsufficientFundsError()

            txn = Transaction.objects.create(
                idempotency_key=idempotency_key,
                txn_type=txn_type,
                status="pending",
                amount=amount,
                currency=source.currency,
                source_account=source,
                dest_account=dest,
                description=description,
                initiated_by=initiated_by,
                metadata=metadata or {},
            )

            new_source_balance = source_balance.current_balance - amount
            new_dest_balance = dest_balance.current_balance + amount

            LedgerEntry.objects.bulk_create([
                LedgerEntry(transaction=txn, account=source, entry_type="D", amount=amount, balance_after=new_source_balance),
                LedgerEntry(transaction=txn, account=dest, entry_type="C", amount=amount, balance_after=new_dest_balance),
            ])

            # Atomic at the DB level via F()-less direct assignment here is
            # fine because we already hold the row lock from
            # select_for_update() above — no other transaction can have
            # changed current_balance underneath us. (An F() expression
            # would also be correct and is what the spec uses when it
            # *isn't* already holding the lock.)
            # .update() bypasses auto_now, so updated_at is set explicitly here.
            now = timezone.now()
            Balance.objects.filter(account_id=source.id).update(
                current_balance=new_source_balance,
                available_balance=source_balance.available_balance - amount,
                version=source_balance.version + 1,
                updated_at=now,
            )
            Balance.objects.filter(account_id=dest.id).update(
                current_balance=new_dest_balance,
                available_balance=dest_balance.available_balance + amount,
                version=dest_balance.version + 1,
                updated_at=now,
            )

            txn.status = "success"
            txn.completed_at = timezone.now()
            txn.save(update_fields=["status", "completed_at"])

            AuditLog.objects.create(
                actor=initiated_by,
                action=f"{txn_type}.completed",
                resource_type="transaction",
                resource_id=str(txn.id),
                after={
                    "amount": str(amount),
                    "source_account": source.account_number,
                    "dest_account": dest.account_number,
                },
            )

        return txn

    def deposit(self, account_id: int, amount: Decimal, idempotency_key: str, initiated_by=None, description: str = "") -> Transaction:
        system = get_or_create_system_account()
        return self.transfer(
            source_account_id=system.id,
            dest_account_id=account_id,
            amount=amount,
            idempotency_key=idempotency_key,
            txn_type="deposit",
            description=description,
            initiated_by=initiated_by,
        )

    def withdraw(self, account_id: int, amount: Decimal, idempotency_key: str, initiated_by=None, description: str = "") -> Transaction:
        system = get_or_create_system_account()
        return self.transfer(
            source_account_id=account_id,
            dest_account_id=system.id,
            amount=amount,
            idempotency_key=idempotency_key,
            txn_type="withdrawal",
            description=description,
            initiated_by=initiated_by,
        )


class ReversalService:
    def __init__(self, transfer_service: TransferService | None = None):
        self.transfer_service = transfer_service or TransferService()

    def reverse(self, original_txn_id, reason: str, idempotency_key: str, initiated_by=None) -> Transaction:
        try:
            original = Transaction.objects.get(id=original_txn_id)
        except Transaction.DoesNotExist:
            raise CannotReverseError("Original transaction not found")

        if original.status != "success":
            raise CannotReverseError("Original transaction not successful")

        if Transaction.objects.filter(metadata__reversal_of=str(original.id), status="success").exists():
            raise AlreadyReversedError()

        reversal = self.transfer_service.transfer(
            source_account_id=original.dest_account_id,
            dest_account_id=original.source_account_id,
            amount=original.amount,
            idempotency_key=idempotency_key,
            txn_type=original.txn_type,
            description=f"Reversal of {original.id}: {reason}",
            initiated_by=initiated_by,
            metadata={"reversal_of": str(original.id), "reason": reason},
        )

        # Don't UPDATE the ledger entries or delete anything — mark the
        # original as reversed so it stops showing as an active balance
        # movement in queries, while every row from the original transfer
        # stays exactly as it was written (spec section 10).
        Transaction.objects.filter(id=original.id).update(status="reversed")

        return reversal
