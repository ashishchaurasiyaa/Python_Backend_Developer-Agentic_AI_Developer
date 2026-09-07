import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model

from accounts.services import open_account
from ledger.services import TransferService

User = get_user_model()


def make_user_with_account(username: str, funded: Decimal | None = None):
    user = User.objects.create_user(username=username, password="hunter22")
    account = open_account(user=user, account_type="savings")
    if funded:
        TransferService().deposit(account_id=account.id, amount=funded, idempotency_key=uuid.uuid4().hex, initiated_by=user)
        account.balance.refresh_from_db()
    return user, account


def auth_headers_for(api_client, username: str, password: str = "hunter22") -> dict:
    resp = api_client.post("/auth/login", {"username": username, "password": password}, format="json")
    token = resp.json()["access"]
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}
