from django.core.cache import cache
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Account
from ledger.exceptions import LedgerError
from ledger.models import Transaction
from ledger.serializers import (
    DepositWithdrawRequestSerializer,
    ReversalRequestSerializer,
    TransactionSerializer,
    TransferRequestSerializer,
)
from ledger.services import ReversalService, TransferService

IDEMPOTENCY_CACHE_TTL = 60 * 60 * 24  # 24h, per spec section 8


class MoneyMovementView(APIView):
    """Shared Idempotency-Key handling for transfer/deposit/withdraw/reverse.

    The DB-level unique constraint on Transaction.idempotency_key (checked
    inside TransferService itself) is what actually guarantees a retried
    request can never double-move money. This Redis-backed cache is a
    fast-path in front of that: a retry within the TTL skips re-hitting the
    DB and the service layer entirely, and returns byte-identical response
    the client already saw for that key.
    """

    request_serializer_class = None

    def post(self, request, *args, **kwargs):
        key = request.headers.get("Idempotency-Key")
        if not key:
            return Response({"error": "Idempotency-Key header is required"}, status=status.HTTP_400_BAD_REQUEST)

        cache_key = f"idem:{key}"
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached["body"], status=cached["status"])

        serializer = self.request_serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            txn = self.execute(request, key, serializer.validated_data, *args, **kwargs)
        except LedgerError as exc:
            body = {"error": str(exc)}
            resp = Response(body, status=status.HTTP_400_BAD_REQUEST)
            # Deliberately NOT cached: a failed validation (e.g. insufficient
            # funds right now) should not permanently pin that outcome to
            # the idempotency key — only a successful, money-moving result is
            # cached, matching Stripe's behavior of only fixing outcomes for
            # requests that actually took an action.
            return resp

        body = TransactionSerializer(txn).data
        # DRF Decimal/UUID fields aren't directly JSON-cacheable via the
        # default pickle-free cache backends in every configuration, but
        # django-redis pickles by default, so this round-trips fine.
        cache.set(cache_key, {"body": body, "status": status.HTTP_201_CREATED}, timeout=IDEMPOTENCY_CACHE_TTL)
        return Response(body, status=status.HTTP_201_CREATED)

    def execute(self, request, idempotency_key, data, *args, **kwargs):
        raise NotImplementedError


class TransferView(MoneyMovementView):
    request_serializer_class = TransferRequestSerializer

    def execute(self, request, idempotency_key, data, *args, **kwargs):
        source = get_object_or_404(Account, pk=data["source_account"], user=request.user)
        return TransferService().transfer(
            source_account_id=source.id,
            dest_account_id=data["dest_account"],
            amount=data["amount"],
            idempotency_key=idempotency_key,
            description=data.get("description", ""),
            initiated_by=request.user,
        )


class DepositView(MoneyMovementView):
    request_serializer_class = DepositWithdrawRequestSerializer

    def execute(self, request, idempotency_key, data, *args, **kwargs):
        account = get_object_or_404(Account, pk=data["account"], user=request.user)
        return TransferService().deposit(
            account_id=account.id,
            amount=data["amount"],
            idempotency_key=idempotency_key,
            initiated_by=request.user,
            description=data.get("description", ""),
        )


class WithdrawView(MoneyMovementView):
    request_serializer_class = DepositWithdrawRequestSerializer

    def execute(self, request, idempotency_key, data, *args, **kwargs):
        account = get_object_or_404(Account, pk=data["account"], user=request.user)
        return TransferService().withdraw(
            account_id=account.id,
            amount=data["amount"],
            idempotency_key=idempotency_key,
            initiated_by=request.user,
            description=data.get("description", ""),
        )


class ReverseView(MoneyMovementView):
    request_serializer_class = ReversalRequestSerializer

    def execute(self, request, idempotency_key, data, *args, **kwargs):
        original = get_object_or_404(Transaction, pk=kwargs["pk"])
        is_party = original.source_account.user_id == request.user.id or original.dest_account.user_id == request.user.id
        if not (request.user.is_staff or is_party):
            raise Http404
        return ReversalService().reverse(
            original_txn_id=original.id,
            reason=data["reason"],
            idempotency_key=idempotency_key,
            initiated_by=request.user,
        )


class TransactionListView(generics.ListAPIView):
    serializer_class = TransactionSerializer

    def get_queryset(self):
        account_ids = Account.objects.filter(user=self.request.user).values_list("id", flat=True)
        qs = Transaction.objects.filter(Q(source_account_id__in=account_ids) | Q(dest_account_id__in=account_ids))
        txn_type = self.request.query_params.get("type")
        if txn_type:
            qs = qs.filter(txn_type=txn_type)
        return qs.order_by("-initiated_at")


class TransactionDetailView(generics.RetrieveAPIView):
    serializer_class = TransactionSerializer

    def get_queryset(self):
        account_ids = Account.objects.filter(user=self.request.user).values_list("id", flat=True)
        return Transaction.objects.filter(Q(source_account_id__in=account_ids) | Q(dest_account_id__in=account_ids))
