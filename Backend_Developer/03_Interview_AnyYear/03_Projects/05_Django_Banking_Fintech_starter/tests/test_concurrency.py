"""The one test that actually proves SELECT FOR UPDATE does its job: fire
concurrent transfers at the same source account, each on its own DB
connection (real threads, real Postgres, not Django's single-connection
TestCase transaction wrapper — hence `transaction=True`) and confirm the
balance never goes negative and the total moved matches exactly what should
have succeeded. Without the row lock in TransferService.transfer(), this
test is flaky/fails under load — with it, it's deterministic.
"""

import threading
from decimal import Decimal

import pytest
from django import db as django_db

from ledger.exceptions import InsufficientFundsError, LedgerError
from ledger.services import TransferService
from tests.helpers import make_user_with_account

pytestmark = pytest.mark.django_db(transaction=True)


def test_concurrent_transfers_never_overdraw_the_source_account():
    alice, alice_acc = make_user_with_account("alice_conc", funded=Decimal("1000"))
    bob, bob_acc = make_user_with_account("bob_conc")

    n_attempts = 10
    amount = Decimal("200")  # 1000 / 200 = exactly 5 can succeed
    results = [None] * n_attempts

    def attempt(i):
        try:
            TransferService().transfer(
                source_account_id=alice_acc.id, dest_account_id=bob_acc.id,
                amount=amount, idempotency_key=f"conc-{i}", initiated_by=alice,
            )
            results[i] = "success"
        except InsufficientFundsError:
            results[i] = "insufficient_funds"
        except LedgerError as exc:
            results[i] = f"error:{exc}"
        finally:
            django_db.connections.close_all()

    threads = [threading.Thread(target=attempt, args=(i,)) for i in range(n_attempts)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    successes = results.count("success")
    assert successes == 5, f"expected exactly 5 successful transfers, got {successes}: {results}"
    assert results.count("insufficient_funds") == 5

    alice_acc.balance.refresh_from_db()
    bob_acc.balance.refresh_from_db()
    assert alice_acc.balance.current_balance == Decimal("0")      # never negative
    assert bob_acc.balance.current_balance == Decimal("1000")     # exactly what alice sent, nothing lost or duplicated
