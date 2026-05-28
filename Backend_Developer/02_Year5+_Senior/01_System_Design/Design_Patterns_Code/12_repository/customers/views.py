"""
Views — thin HTTP layer.
All data access is delegated to the repository; views only handle
request parsing, serialization, and response formatting.

Pattern in action:
    view  -->  repository  -->  ORM  -->  database
"""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from customers.repositories import CustomerRepository
from customers.serializers import (
    CustomerSerializer,
    CustomerDetailSerializer,
    CustomerWithOutstandingSerializer,
)


# ---------------------------------------------------------------------------
# Customer List + Create
# ---------------------------------------------------------------------------
class CustomerListView(APIView):
    """
    GET  /api/customers/          — list all customers
    POST /api/customers/          — create a new customer
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.repo = CustomerRepository()

    def get(self, request):
        customers = self.repo.all()
        serializer = CustomerSerializer(customers, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = CustomerSerializer(data=request.data)
        if serializer.is_valid():
            customer = self.repo.create(serializer.validated_data)
            output = CustomerSerializer(customer)
            return Response(output.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------------------------------------------------------
# Customer Detail / Update / Delete
# ---------------------------------------------------------------------------
class CustomerDetailView(APIView):
    """
    GET    /api/customers/<pk>/   — retrieve single customer with contacts
    PUT    /api/customers/<pk>/   — update customer
    DELETE /api/customers/<pk>/   — delete customer
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.repo = CustomerRepository()

    def get(self, request, pk):
        customer = self.repo.get_customer_with_contacts(pk)
        if customer is None:
            return Response(
                {"error": "Customer not found"}, status=status.HTTP_404_NOT_FOUND,
            )
        serializer = CustomerDetailSerializer(customer)
        return Response(serializer.data)

    def put(self, request, pk):
        serializer = CustomerSerializer(data=request.data, partial=True)
        if serializer.is_valid():
            customer = self.repo.update(pk, serializer.validated_data)
            if customer is None:
                return Response(
                    {"error": "Customer not found"}, status=status.HTTP_404_NOT_FOUND,
                )
            output = CustomerSerializer(customer)
            return Response(output.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        deleted = self.repo.delete(pk)
        if not deleted:
            return Response(
                {"error": "Customer not found"}, status=status.HTTP_404_NOT_FOUND,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------
# Customer Search
# ---------------------------------------------------------------------------
class CustomerSearchView(APIView):
    """
    GET /api/customers/search/?q=<query>
    Searches across company, first_name, phone_number, gstn.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.repo = CustomerRepository()

    def get(self, request):
        query = request.query_params.get("q", "")
        customers = self.repo.search(query)
        serializer = CustomerSerializer(customers, many=True)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# Customers with Outstanding
# ---------------------------------------------------------------------------
class CustomerOutstandingView(APIView):
    """
    GET /api/customers/outstanding/
    Returns customers annotated with their total outstanding balance.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.repo = CustomerRepository()

    def get(self, request):
        customers = self.repo.get_customers_with_outstanding()
        serializer = CustomerWithOutstandingSerializer(customers, many=True)
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# Customers by Business Type
# ---------------------------------------------------------------------------
class CustomerByBusinessTypeView(APIView):
    """
    GET /api/customers/business-type/?type=construction
    Filters customers by business_type field.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.repo = CustomerRepository()

    def get(self, request):
        business_type = request.query_params.get("type", "")
        if not business_type:
            return Response(
                {"error": "Query parameter 'type' is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        valid_types = ["construction", "infrastructure", "industrial", "events"]
        if business_type not in valid_types:
            return Response(
                {"error": f"Invalid type. Choose from: {', '.join(valid_types)}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        customers = self.repo.get_by_business_type(business_type)
        serializer = CustomerSerializer(customers, many=True)
        return Response(serializer.data)
