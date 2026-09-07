from django.db import IntegrityError, transaction

from accounts.models import Account, Balance, generate_account_number

MAX_ACCOUNT_NUMBER_ATTEMPTS = 5


def open_account(user, account_type: str, currency: str = "INR") -> Account:
    """14-digit account_number is randomly generated — collide-and-retry on
    the unique constraint rather than trusting randomness alone, same
    pattern used for short-code generation in the URL shortener starter."""
    last_error = None
    for _ in range(MAX_ACCOUNT_NUMBER_ATTEMPTS):
        try:
            with transaction.atomic():
                account = Account.objects.create(
                    user=user,
                    account_number=generate_account_number(),
                    account_type=account_type,
                    currency=currency,
                )
                Balance.objects.create(account=account, current_balance=0, available_balance=0)
                return account
        except IntegrityError as exc:
            last_error = exc
            continue
    raise last_error
