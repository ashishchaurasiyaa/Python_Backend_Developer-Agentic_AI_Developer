"""Daily reconciliation (spec section 9). The spec runs this via Celery
beat at 2am; Celery/RabbitMQ setup is deferred for this starter (see
README.md), so it runs as a plain management command instead — same logic,
meant to be invoked by cron or manually. Exits non-zero on any discrepancy
so it's usable as a CI/cron gate.
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Case, DecimalField, F, Sum, When

from accounts.models import Account, Balance
from ledger.models import LedgerEntry


class Command(BaseCommand):
    help = "Verify balances table matches the sum of ledger_entries for every active account."

    def handle(self, *args, **options):
        discrepancies = []

        for account in Account.objects.filter(status="active").select_related("balance"):
            ledger_balance = LedgerEntry.objects.filter(account=account).aggregate(
                total=Sum(
                    Case(
                        When(entry_type="C", then=F("amount")),
                        When(entry_type="D", then=-F("amount")),
                        output_field=DecimalField(max_digits=15, decimal_places=4),
                    )
                )
            )["total"] or Decimal("0")

            try:
                cache_balance = account.balance.current_balance
            except Balance.DoesNotExist:
                cache_balance = Decimal("0")

            if abs(ledger_balance - cache_balance) > Decimal("0.0001"):
                discrepancies.append({
                    "account_id": account.id,
                    "account_number": account.account_number,
                    "ledger": str(ledger_balance),
                    "cache": str(cache_balance),
                    "diff": str(cache_balance - ledger_balance),
                })

        if discrepancies:
            self.stderr.write(self.style.ERROR(f"CRITICAL: {len(discrepancies)} balance discrepancies found:"))
            for d in discrepancies:
                self.stderr.write(f"  account {d['account_number']}: ledger={d['ledger']} cache={d['cache']} diff={d['diff']}")
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS("Reconciliation OK — 0 discrepancies."))
