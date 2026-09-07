from django.urls import path

from ledger.views import (
    DepositView,
    ReverseView,
    TransactionDetailView,
    TransactionListView,
    TransferView,
    WithdrawView,
)

urlpatterns = [
    path("transactions", TransactionListView.as_view(), name="transaction-list"),
    path("transactions/transfer", TransferView.as_view(), name="transaction-transfer"),
    path("transactions/deposit", DepositView.as_view(), name="transaction-deposit"),
    path("transactions/withdraw", WithdrawView.as_view(), name="transaction-withdraw"),
    path("transactions/<uuid:pk>", TransactionDetailView.as_view(), name="transaction-detail"),
    path("transactions/<uuid:pk>/reverse", ReverseView.as_view(), name="transaction-reverse"),
]
