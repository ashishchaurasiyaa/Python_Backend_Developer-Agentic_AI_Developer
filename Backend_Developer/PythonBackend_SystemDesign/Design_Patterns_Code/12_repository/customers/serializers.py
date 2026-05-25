"""
DRF Serializers for the Customer domain.
Serializers handle validation and data transformation — NOT data access.
"""

from rest_framework import serializers
from customers.models import Customer, CustomerContact, CustomerOutstanding


class CustomerContactSerializer(serializers.ModelSerializer):
    """Serializer for customer contacts (purchaser / site contact / decision maker)."""

    class Meta:
        model = CustomerContact
        fields = [
            "id",
            "customer",
            "contact_type",
            "name",
            "phone",
            "email",
        ]
        read_only_fields = ["id"]


class CustomerOutstandingSerializer(serializers.ModelSerializer):
    """Serializer for outstanding invoices."""

    class Meta:
        model = CustomerOutstanding
        fields = [
            "id",
            "customer",
            "invoice_number",
            "amount",
            "balance",
            "status",
            "due_date",
        ]
        read_only_fields = ["id"]


class CustomerSerializer(serializers.ModelSerializer):
    """Flat serializer for customer list / create / update."""

    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Customer
        fields = [
            "id",
            "sap_ref",
            "company",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone_number",
            "gstn",
            "credit_limit",
            "credit_rating",
            "due_days",
            "business_type",
            "is_verified",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "full_name"]


class CustomerWithOutstandingSerializer(serializers.ModelSerializer):
    """Serializer that includes the annotated total_outstanding field."""

    full_name = serializers.CharField(read_only=True)
    total_outstanding = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True,
    )

    class Meta:
        model = Customer
        fields = [
            "id",
            "sap_ref",
            "company",
            "full_name",
            "phone_number",
            "credit_limit",
            "credit_rating",
            "is_verified",
            "total_outstanding",
        ]


class CustomerDetailSerializer(serializers.ModelSerializer):
    """
    Nested serializer for the customer detail view.
    Includes contacts and outstanding invoices inline.
    """

    full_name = serializers.CharField(read_only=True)
    contacts = CustomerContactSerializer(many=True, read_only=True)
    outstandings = CustomerOutstandingSerializer(many=True, read_only=True)

    class Meta:
        model = Customer
        fields = [
            "id",
            "sap_ref",
            "company",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone_number",
            "gstn",
            "credit_limit",
            "credit_rating",
            "due_days",
            "business_type",
            "is_verified",
            "created_at",
            "contacts",
            "outstandings",
        ]
        read_only_fields = ["id", "created_at", "full_name"]
