from rest_framework import serializers

from ledger.models import Transaction


class TransactionSerializer(serializers.ModelSerializer):
    source_account = serializers.CharField(source="source_account.account_number", read_only=True)
    dest_account = serializers.CharField(source="dest_account.account_number", read_only=True)

    class Meta:
        model = Transaction
        fields = [
            "id", "idempotency_key", "txn_type", "status", "amount", "currency",
            "source_account", "dest_account", "description", "initiated_at",
            "completed_at", "failed_reason", "metadata",
        ]
        read_only_fields = fields


class TransferRequestSerializer(serializers.Serializer):
    source_account = serializers.IntegerField()
    dest_account = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=4)
    description = serializers.CharField(required=False, allow_blank=True, default="")


class DepositWithdrawRequestSerializer(serializers.Serializer):
    account = serializers.IntegerField()
    amount = serializers.DecimalField(max_digits=15, decimal_places=4)
    description = serializers.CharField(required=False, allow_blank=True, default="")


class ReversalRequestSerializer(serializers.Serializer):
    reason = serializers.CharField()
