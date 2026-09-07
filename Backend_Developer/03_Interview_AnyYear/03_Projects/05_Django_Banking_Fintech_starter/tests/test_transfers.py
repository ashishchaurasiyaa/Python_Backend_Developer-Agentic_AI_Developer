from decimal import Decimal

import pytest

from ledger.exceptions import (
    AccountFrozenError,
    AmountExceedsLimitError,
    InsufficientFundsError,
    InvalidAmountError,
)
from ledger.models import LedgerEntry, Transaction
from ledger.services import ReversalService, TransferService
from tests.helpers import auth_headers_for, make_user_with_account

pytestmark = pytest.mark.django_db


def test_deposit_credits_account():
    user, account = make_user_with_account("depositor")
    txn = TransferService().deposit(account_id=account.id, amount=Decimal("500"), idempotency_key="k1", initiated_by=user)
    account.balance.refresh_from_db()
    assert txn.status == "success"
    assert account.balance.current_balance == Decimal("500")


def test_double_entry_sums_to_zero():
    user, account = make_user_with_account("de_user", funded=Decimal("100"))
    txn = Transaction.objects.filter(dest_account=account, txn_type="deposit").latest("initiated_at")
    entries = LedgerEntry.objects.filter(transaction=txn)
    total = sum(
        (e.amount if e.entry_type == "C" else -e.amount) for e in entries
    )
    assert total == Decimal("0")
    assert entries.count() == 2


def test_transfer_moves_money_between_accounts():
    alice, alice_acc = make_user_with_account("alice_t", funded=Decimal("1000"))
    bob, bob_acc = make_user_with_account("bob_t")

    TransferService().transfer(
        source_account_id=alice_acc.id, dest_account_id=bob_acc.id,
        amount=Decimal("300"), idempotency_key="xfer1", initiated_by=alice,
    )
    alice_acc.balance.refresh_from_db()
    bob_acc.balance.refresh_from_db()
    assert alice_acc.balance.current_balance == Decimal("700")
    assert bob_acc.balance.current_balance == Decimal("300")


def test_retry_with_same_idempotency_key_does_not_double_move_money():
    alice, alice_acc = make_user_with_account("alice_idem", funded=Decimal("1000"))
    bob, bob_acc = make_user_with_account("bob_idem")

    svc = TransferService()
    first = svc.transfer(source_account_id=alice_acc.id, dest_account_id=bob_acc.id, amount=Decimal("300"), idempotency_key="dup-key", initiated_by=alice)
    second = svc.transfer(source_account_id=alice_acc.id, dest_account_id=bob_acc.id, amount=Decimal("300"), idempotency_key="dup-key", initiated_by=alice)

    assert first.id == second.id
    alice_acc.balance.refresh_from_db()
    assert alice_acc.balance.current_balance == Decimal("700")  # not 400 — only debited once


def test_insufficient_funds_rejected():
    alice, alice_acc = make_user_with_account("alice_poor", funded=Decimal("10"))
    bob, bob_acc = make_user_with_account("bob_poor")

    with pytest.raises(InsufficientFundsError):
        TransferService().transfer(source_account_id=alice_acc.id, dest_account_id=bob_acc.id, amount=Decimal("100"), idempotency_key="k2", initiated_by=alice)


def test_frozen_account_rejected():
    alice, alice_acc = make_user_with_account("alice_frz", funded=Decimal("100"))
    bob, bob_acc = make_user_with_account("bob_frz")
    bob_acc.status = "frozen"
    bob_acc.save(update_fields=["status"])

    with pytest.raises(AccountFrozenError):
        TransferService().transfer(source_account_id=alice_acc.id, dest_account_id=bob_acc.id, amount=Decimal("10"), idempotency_key="k3", initiated_by=alice)


def test_zero_amount_rejected():
    alice, alice_acc = make_user_with_account("alice_zero", funded=Decimal("100"))
    bob, bob_acc = make_user_with_account("bob_zero")
    with pytest.raises(InvalidAmountError):
        TransferService().transfer(source_account_id=alice_acc.id, dest_account_id=bob_acc.id, amount=Decimal("0"), idempotency_key="k4", initiated_by=alice)


def test_over_limit_amount_rejected():
    # The limit check runs before the balance check (see TransferService.transfer),
    # so an unfunded account is enough to prove this specific rejection.
    alice, alice_acc = make_user_with_account("alice_big")
    bob, bob_acc = make_user_with_account("bob_big")
    with pytest.raises(AmountExceedsLimitError):
        TransferService().transfer(source_account_id=alice_acc.id, dest_account_id=bob_acc.id, amount=Decimal("200000"), idempotency_key="k5", initiated_by=alice)


def test_reversal_creates_new_transaction_and_preserves_original():
    alice, alice_acc = make_user_with_account("alice_rev", funded=Decimal("1000"))
    bob, bob_acc = make_user_with_account("bob_rev")

    original = TransferService().transfer(source_account_id=alice_acc.id, dest_account_id=bob_acc.id, amount=Decimal("300"), idempotency_key="orig1", initiated_by=alice)
    original_entries_before = list(LedgerEntry.objects.filter(transaction=original).values("id", "amount", "balance_after"))

    reversal = ReversalService().reverse(original_txn_id=original.id, reason="test", idempotency_key="rev1", initiated_by=alice)

    original.refresh_from_db()
    assert original.status == "reversed"
    # the original's ledger rows are untouched — reversal never mutates history
    original_entries_after = list(LedgerEntry.objects.filter(transaction=original).values("id", "amount", "balance_after"))
    assert original_entries_before == original_entries_after
    assert reversal.id != original.id
    assert reversal.metadata["reversal_of"] == str(original.id)

    alice_acc.balance.refresh_from_db()
    assert alice_acc.balance.current_balance == Decimal("1000")


def test_transfer_api_end_to_end_with_idempotency_header(api_client):
    api_client.post("/auth/signup", {"username": "api_alice", "password": "CorrectHorse9!"}, format="json")
    api_client.post("/auth/signup", {"username": "api_bob", "password": "CorrectHorse9!"}, format="json")
    alice_headers = auth_headers_for(api_client, "api_alice", "CorrectHorse9!")
    bob_headers = auth_headers_for(api_client, "api_bob", "CorrectHorse9!")

    alice_acc = api_client.post("/accounts", {"account_type": "savings"}, format="json", **alice_headers).json()
    bob_acc = api_client.post("/accounts", {"account_type": "savings"}, format="json", **bob_headers).json()

    dep = api_client.post(
        "/transactions/deposit", {"account": alice_acc["id"], "amount": "500.00"}, format="json",
        HTTP_IDEMPOTENCY_KEY="dep-e2e-1", **alice_headers,
    )
    assert dep.status_code == 201

    missing_header = api_client.post(
        "/transactions/transfer", {"source_account": alice_acc["id"], "dest_account": bob_acc["id"], "amount": "100.00"},
        format="json", **alice_headers,
    )
    assert missing_header.status_code == 400

    xfer = api_client.post(
        "/transactions/transfer", {"source_account": alice_acc["id"], "dest_account": bob_acc["id"], "amount": "100.00"},
        format="json", HTTP_IDEMPOTENCY_KEY="xfer-e2e-1", **alice_headers,
    )
    assert xfer.status_code == 201

    retry = api_client.post(
        "/transactions/transfer", {"source_account": alice_acc["id"], "dest_account": bob_acc["id"], "amount": "100.00"},
        format="json", HTTP_IDEMPOTENCY_KEY="xfer-e2e-1", **alice_headers,
    )
    assert retry.status_code == 201
    assert retry.json()["id"] == xfer.json()["id"]

    balance = api_client.get(f"/accounts/{alice_acc['id']}/balance", **alice_headers).json()
    assert balance["current_balance"] == "400.0000"  # 500 deposit - 100 transfer, not 300
