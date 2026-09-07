class LedgerError(Exception):
    """Base class for all ledger/transfer domain errors."""

    default_message = "Ledger error"

    def __init__(self, message: str | None = None):
        super().__init__(message or self.default_message)


class InvalidAmountError(LedgerError):
    default_message = "Amount must be greater than zero"


class AmountExceedsLimitError(LedgerError):
    default_message = "Amount exceeds the per-transaction limit"


class AccountFrozenError(LedgerError):
    default_message = "Account is not active"


class InsufficientFundsError(LedgerError):
    default_message = "Insufficient available balance"


class CannotReverseError(LedgerError):
    default_message = "Transaction cannot be reversed"


class AlreadyReversedError(LedgerError):
    default_message = "Transaction has already been reversed"
