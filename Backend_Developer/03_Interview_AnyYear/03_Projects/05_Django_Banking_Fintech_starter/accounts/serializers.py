from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from accounts.models import Account, Balance

User = get_user_model()


class SignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, validators=[validate_password])

    class Meta:
        model = User
        fields = ["id", "username", "email", "password"]

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class BalanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Balance
        fields = ["current_balance", "available_balance", "version", "updated_at"]


class AccountSerializer(serializers.ModelSerializer):
    balance = BalanceSerializer(read_only=True)

    class Meta:
        model = Account
        fields = ["id", "account_number", "account_type", "currency", "status", "opened_at", "closed_at", "balance"]
        read_only_fields = ["id", "account_number", "status", "opened_at", "closed_at"]


class OpenAccountSerializer(serializers.Serializer):
    account_type = serializers.ChoiceField(choices=["savings", "current", "escrow"])
    currency = serializers.CharField(max_length=3, default="INR")
