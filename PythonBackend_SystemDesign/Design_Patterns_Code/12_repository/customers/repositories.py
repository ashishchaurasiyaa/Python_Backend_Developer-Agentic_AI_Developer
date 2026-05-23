"""
Repository Pattern Implementation
==================================
The repository sits between the domain/service layer and the data mapping layer
(Django ORM). It provides a collection-like interface for accessing domain objects,
hiding the details of data access behind a clean API.

At Youngman India we have ~19 repositories in our Laravel codebase:
    CustomerRepository, QuotationRepository, OrderRepository, InvoiceRepository,
    ItemRepository, DepotRepository, LogisticsRepository, UserRepository ...

This module demonstrates the pattern in Django with a CustomerRepository.
"""

from abc import ABC, abstractmethod
from django.db.models import Sum, Q
from customers.models import Customer, CustomerContact, CustomerOutstanding


# ---------------------------------------------------------------------------
# Base Repository — generic CRUD for any Django model
# ---------------------------------------------------------------------------
class BaseRepository(ABC):
    """
    Abstract base repository that provides generic CRUD operations.
    Concrete repositories must implement get_model() to bind to a Django model.
    """

    @abstractmethod
    def get_model(self):
        """Return the Django model class this repository manages."""
        pass

    # -- Read operations ----------------------------------------------------

    def all(self):
        """Return all records."""
        return self.get_model().objects.all()

    def find(self, pk):
        """Find a single record by primary key. Returns None if not found."""
        try:
            return self.get_model().objects.get(pk=pk)
        except self.get_model().DoesNotExist:
            return None

    def filter_by(self, **kwargs):
        """Filter records by keyword arguments (Django field lookups)."""
        return self.get_model().objects.filter(**kwargs)

    def count(self):
        """Return total count of records."""
        return self.get_model().objects.count()

    # -- Write operations ---------------------------------------------------

    def create(self, data: dict):
        """Create and return a new record from a dictionary of field values."""
        return self.get_model().objects.create(**data)

    def update(self, pk, data: dict):
        """Update a record by primary key. Returns updated instance or None."""
        instance = self.find(pk)
        if instance is None:
            return None
        for field, value in data.items():
            setattr(instance, field, value)
        instance.save()
        return instance

    def delete(self, pk):
        """Delete a record by primary key. Returns True if deleted, False otherwise."""
        instance = self.find(pk)
        if instance is None:
            return False
        instance.delete()
        return True


# ---------------------------------------------------------------------------
# Customer Repository — domain-specific data access for Customer
# ---------------------------------------------------------------------------
class CustomerRepository(BaseRepository):
    """
    Encapsulates all data access logic for the Customer model.

    In the Youngman codebase the CustomerRepository handles:
        - SAP reference lookups (for nightly sync)
        - GSTN-based search (for GST compliance)
        - Credit-control queries (outstanding aggregation)
        - Role-based filtered views (sales rep sees own customers,
          branch manager sees branch customers, admin sees all)

    This demo covers the core query methods.
    """

    def get_model(self):
        return Customer

    # -- Lookup by unique identifiers ---------------------------------------

    def find_by_sap_ref(self, sap_ref):
        """Find a customer by SAP reference number."""
        try:
            return Customer.objects.get(sap_ref=sap_ref)
        except Customer.DoesNotExist:
            return None

    def find_by_gstn(self, gstn):
        """Find a customer by GST Identification Number."""
        try:
            return Customer.objects.get(gstn=gstn)
        except Customer.DoesNotExist:
            return None

    # -- Verification status ------------------------------------------------

    def get_verified_customers(self):
        """Return all KYC-verified customers."""
        return Customer.objects.filter(is_verified=True)

    def get_unverified_customers(self):
        """Return all customers pending KYC verification."""
        return Customer.objects.filter(is_verified=False)

    # -- Outstanding / Credit queries ---------------------------------------

    def get_customers_with_outstanding(self):
        """
        Return customers annotated with their total outstanding balance.
        Only includes customers who have at least some outstanding balance.
        Used by credit control team for daily review.
        """
        return (
            Customer.objects
            .annotate(total_outstanding=Sum("outstandings__balance"))
            .filter(total_outstanding__gt=0)
            .order_by("-total_outstanding")
        )

    # -- Business type filter -----------------------------------------------

    def get_by_business_type(self, business_type):
        """Filter customers by business type (construction, infrastructure, etc.)."""
        return Customer.objects.filter(business_type=business_type)

    # -- Full-text search ---------------------------------------------------

    def search(self, query):
        """
        Search customers across multiple fields using Q objects.
        Used by the search bar in the CRM frontend.
        """
        if not query:
            return Customer.objects.none()
        return Customer.objects.filter(
            Q(company__icontains=query)
            | Q(first_name__icontains=query)
            | Q(phone_number__icontains=query)
            | Q(gstn__icontains=query)
        )

    # -- Prefetch related ---------------------------------------------------

    def get_customer_with_contacts(self, pk):
        """
        Get a single customer with all contacts prefetched.
        Avoids N+1 queries when rendering the customer detail page.
        """
        try:
            return (
                Customer.objects
                .prefetch_related("contacts", "outstandings")
                .get(pk=pk)
            )
        except Customer.DoesNotExist:
            return None


# ---------------------------------------------------------------------------
# Contact Repository
# ---------------------------------------------------------------------------
class CustomerContactRepository(BaseRepository):
    """Repository for CustomerContact model."""

    def get_model(self):
        return CustomerContact

    def get_contacts_for_customer(self, customer_id):
        """Return all contacts for a given customer."""
        return CustomerContact.objects.filter(customer_id=customer_id)


# ---------------------------------------------------------------------------
# Outstanding Repository
# ---------------------------------------------------------------------------
class CustomerOutstandingRepository(BaseRepository):
    """Repository for CustomerOutstanding model."""

    def get_model(self):
        return CustomerOutstanding

    def get_outstandings_for_customer(self, customer_id):
        """Return all outstanding invoices for a given customer."""
        return CustomerOutstanding.objects.filter(customer_id=customer_id)

    def get_overdue(self):
        """Return all overdue invoices across all customers."""
        return CustomerOutstanding.objects.filter(status="overdue")
