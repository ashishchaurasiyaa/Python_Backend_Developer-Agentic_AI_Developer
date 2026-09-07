from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import Account
from accounts.serializers import AccountSerializer, OpenAccountSerializer, SignupSerializer
from accounts.services import open_account


class SignupView(generics.CreateAPIView):
    serializer_class = SignupSerializer
    permission_classes = [permissions.AllowAny]


class AccountListCreateView(generics.ListCreateAPIView):
    serializer_class = AccountSerializer

    def get_queryset(self):
        return Account.objects.filter(user=self.request.user).select_related("balance")

    def create(self, request, *args, **kwargs):
        serializer = OpenAccountSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = open_account(user=request.user, **serializer.validated_data)
        return Response(AccountSerializer(account).data, status=status.HTTP_201_CREATED)


class AccountDetailView(generics.RetrieveAPIView):
    serializer_class = AccountSerializer

    def get_queryset(self):
        return Account.objects.filter(user=self.request.user).select_related("balance")


class AccountBalanceView(APIView):
    def get(self, request, pk):
        account = get_object_or_404(Account.objects.select_related("balance"), pk=pk, user=request.user)
        return Response({
            "current_balance": str(account.balance.current_balance),
            "available_balance": str(account.balance.available_balance),
            "version": account.balance.version,
            "updated_at": account.balance.updated_at,
        })
