from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command

from tests.helpers import make_user_with_account

pytestmark = pytest.mark.django_db


def test_reconcile_reports_no_discrepancies_after_clean_transfers():
    from ledger.services import TransferService

    alice, alice_acc = make_user_with_account("alice_rec", funded=Decimal("500"))
    bob, bob_acc = make_user_with_account("bob_rec")
    TransferService().transfer(source_account_id=alice_acc.id, dest_account_id=bob_acc.id, amount=Decimal("150"), idempotency_key="rec1", initiated_by=alice)

    out = StringIO()
    call_command("reconcile_balances", stdout=out)
    assert "0 discrepancies" in out.getvalue() or "OK" in out.getvalue()


def test_reconcile_detects_a_manually_introduced_discrepancy():
    alice, alice_acc = make_user_with_account("alice_bad", funded=Decimal("500"))

    # Tamper with the cache directly — simulates a bug that desynced
    # `balances` from the ledger's own accounting.
    alice_acc.balance.current_balance = Decimal("999")
    alice_acc.balance.save(update_fields=["current_balance"])

    with pytest.raises(SystemExit) as exc_info:
        call_command("reconcile_balances")
    assert exc_info.value.code == 1
