"""
Tests for the Repository Pattern demo.

Covers:
    1. BaseRepository CRUD (via CustomerRepository which extends it)
    2. CustomerRepository domain-specific methods
    3. API endpoint integration tests
"""

from decimal import Decimal
from datetime import date

from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status

from customers.models import Customer, CustomerContact, CustomerOutstanding
from customers.repositories import CustomerRepository


# ===========================================================================
# Helper mixin to create test data
# ===========================================================================
class CustomerDataMixin:
    """Shared test fixtures for customer tests."""

    def create_customer(self, **overrides):
        defaults = {
            "sap_ref": "SAP-10001",
            "company": "Metro Constructions Pvt Ltd",
            "first_name": "Rajesh",
            "last_name": "Sharma",
            "email": "rajesh@metroconstructions.in",
            "phone_number": "9876543210",
            "gstn": "27AABCM1234F1Z5",
            "credit_limit": Decimal("500000.00"),
            "credit_rating": "A",
            "due_days": 30,
            "business_type": "construction",
            "is_verified": True,
        }
        defaults.update(overrides)
        return Customer.objects.create(**defaults)

    def create_contact(self, customer, **overrides):
        defaults = {
            "customer": customer,
            "contact_type": "purchaser",
            "name": "Amit Kumar",
            "phone": "9876500001",
            "email": "amit@metroconstructions.in",
        }
        defaults.update(overrides)
        return CustomerContact.objects.create(**defaults)

    def create_outstanding(self, customer, **overrides):
        defaults = {
            "customer": customer,
            "invoice_number": "INV-2024-001",
            "amount": Decimal("150000.00"),
            "balance": Decimal("75000.00"),
            "status": "partial",
            "due_date": date(2025, 3, 15),
        }
        defaults.update(overrides)
        return CustomerOutstanding.objects.create(**defaults)


# ===========================================================================
# 1. BaseRepository CRUD Tests (through CustomerRepository)
# ===========================================================================
class BaseRepositoryTests(CustomerDataMixin, TestCase):
    """Test the generic CRUD methods inherited from BaseRepository."""

    def setUp(self):
        self.repo = CustomerRepository()

    def test_create(self):
        """Repository.create() should persist and return a Customer instance."""
        data = {
            "company": "BuildRight Infrastructure",
            "first_name": "Priya",
            "last_name": "Patel",
            "email": "priya@buildright.in",
            "phone_number": "9812345678",
            "business_type": "infrastructure",
        }
        customer = self.repo.create(data)
        self.assertIsNotNone(customer.pk)
        self.assertEqual(customer.company, "BuildRight Infrastructure")
        self.assertEqual(Customer.objects.count(), 1)

    def test_find(self):
        """Repository.find() should return the correct instance by PK."""
        customer = self.create_customer()
        found = self.repo.find(customer.pk)
        self.assertEqual(found.pk, customer.pk)
        self.assertEqual(found.company, customer.company)

    def test_find_not_found(self):
        """Repository.find() should return None for non-existent PK."""
        result = self.repo.find(99999)
        self.assertIsNone(result)

    def test_all(self):
        """Repository.all() should return all records."""
        self.create_customer(sap_ref="SAP-001")
        self.create_customer(sap_ref="SAP-002", company="Second Company")
        customers = self.repo.all()
        self.assertEqual(customers.count(), 2)

    def test_update(self):
        """Repository.update() should modify and return the updated instance."""
        customer = self.create_customer()
        updated = self.repo.update(customer.pk, {"company": "Metro Infra Pvt Ltd"})
        self.assertEqual(updated.company, "Metro Infra Pvt Ltd")
        # Verify it persisted
        customer.refresh_from_db()
        self.assertEqual(customer.company, "Metro Infra Pvt Ltd")

    def test_update_not_found(self):
        """Repository.update() should return None for non-existent PK."""
        result = self.repo.update(99999, {"company": "Ghost"})
        self.assertIsNone(result)

    def test_delete(self):
        """Repository.delete() should remove the record and return True."""
        customer = self.create_customer()
        result = self.repo.delete(customer.pk)
        self.assertTrue(result)
        self.assertEqual(Customer.objects.count(), 0)

    def test_delete_not_found(self):
        """Repository.delete() should return False for non-existent PK."""
        result = self.repo.delete(99999)
        self.assertFalse(result)

    def test_filter_by(self):
        """Repository.filter_by() should filter using keyword arguments."""
        self.create_customer(sap_ref="SAP-001", business_type="construction")
        self.create_customer(sap_ref="SAP-002", business_type="events", company="EventPro")
        results = self.repo.filter_by(business_type="events")
        self.assertEqual(results.count(), 1)
        self.assertEqual(results.first().company, "EventPro")

    def test_count(self):
        """Repository.count() should return total record count."""
        self.assertEqual(self.repo.count(), 0)
        self.create_customer(sap_ref="SAP-001")
        self.create_customer(sap_ref="SAP-002", company="Second")
        self.assertEqual(self.repo.count(), 2)


# ===========================================================================
# 2. CustomerRepository Domain-Specific Tests
# ===========================================================================
class CustomerRepositoryTests(CustomerDataMixin, TestCase):
    """Test the domain-specific methods on CustomerRepository."""

    def setUp(self):
        self.repo = CustomerRepository()

    def test_find_by_sap_ref(self):
        customer = self.create_customer(sap_ref="SAP-FIND-001")
        found = self.repo.find_by_sap_ref("SAP-FIND-001")
        self.assertEqual(found.pk, customer.pk)

    def test_find_by_sap_ref_not_found(self):
        result = self.repo.find_by_sap_ref("SAP-NONEXISTENT")
        self.assertIsNone(result)

    def test_find_by_gstn(self):
        customer = self.create_customer(gstn="27AABCM9999F1Z5")
        found = self.repo.find_by_gstn("27AABCM9999F1Z5")
        self.assertEqual(found.pk, customer.pk)

    def test_find_by_gstn_not_found(self):
        result = self.repo.find_by_gstn("INVALID_GSTN")
        self.assertIsNone(result)

    def test_get_verified_customers(self):
        self.create_customer(sap_ref="SAP-V1", is_verified=True)
        self.create_customer(sap_ref="SAP-V2", is_verified=False, company="Unverified Co")
        verified = self.repo.get_verified_customers()
        self.assertEqual(verified.count(), 1)
        self.assertTrue(verified.first().is_verified)

    def test_get_unverified_customers(self):
        self.create_customer(sap_ref="SAP-U1", is_verified=True)
        self.create_customer(sap_ref="SAP-U2", is_verified=False, company="Pending KYC")
        unverified = self.repo.get_unverified_customers()
        self.assertEqual(unverified.count(), 1)
        self.assertEqual(unverified.first().company, "Pending KYC")

    def test_get_customers_with_outstanding(self):
        c1 = self.create_customer(sap_ref="SAP-OUT1")
        c2 = self.create_customer(sap_ref="SAP-OUT2", company="No Outstanding Co")
        # c1 has outstanding, c2 does not
        self.create_outstanding(c1, balance=Decimal("50000.00"))
        self.create_outstanding(c1, invoice_number="INV-002", balance=Decimal("25000.00"))
        results = self.repo.get_customers_with_outstanding()
        self.assertEqual(results.count(), 1)
        self.assertEqual(results.first().pk, c1.pk)
        self.assertEqual(results.first().total_outstanding, Decimal("75000.00"))

    def test_get_by_business_type(self):
        self.create_customer(sap_ref="SAP-BT1", business_type="construction")
        self.create_customer(sap_ref="SAP-BT2", business_type="events", company="EventPro")
        self.create_customer(sap_ref="SAP-BT3", business_type="construction", company="Builder2")
        results = self.repo.get_by_business_type("construction")
        self.assertEqual(results.count(), 2)

    def test_search_by_company(self):
        self.create_customer(sap_ref="SAP-S1", company="Metro Constructions Pvt Ltd")
        self.create_customer(sap_ref="SAP-S2", company="Reliance Infra")
        results = self.repo.search("Metro")
        self.assertEqual(results.count(), 1)

    def test_search_by_phone(self):
        self.create_customer(sap_ref="SAP-S3", phone_number="9876543210")
        results = self.repo.search("98765")
        self.assertEqual(results.count(), 1)

    def test_search_by_gstn(self):
        self.create_customer(sap_ref="SAP-S4", gstn="27AABCM1234F1Z5")
        results = self.repo.search("27AABCM")
        self.assertEqual(results.count(), 1)

    def test_search_empty_query(self):
        self.create_customer(sap_ref="SAP-S5")
        results = self.repo.search("")
        self.assertEqual(results.count(), 0)

    def test_get_customer_with_contacts(self):
        customer = self.create_customer()
        self.create_contact(customer, name="Contact 1")
        self.create_contact(customer, name="Contact 2", contact_type="site_contact")
        result = self.repo.get_customer_with_contacts(customer.pk)
        self.assertIsNotNone(result)
        self.assertEqual(result.contacts.count(), 2)

    def test_get_customer_with_contacts_not_found(self):
        result = self.repo.get_customer_with_contacts(99999)
        self.assertIsNone(result)


# ===========================================================================
# 3. API Endpoint Integration Tests
# ===========================================================================
class CustomerAPITests(CustomerDataMixin, APITestCase):
    """Integration tests for the REST API endpoints."""

    def setUp(self):
        self.customer = self.create_customer()

    # -- List ---------------------------------------------------------------

    def test_list_customers(self):
        response = self.client.get("/api/customers/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["company"], "Metro Constructions Pvt Ltd")

    # -- Create -------------------------------------------------------------

    def test_create_customer(self):
        data = {
            "company": "New Builder Co",
            "first_name": "Suresh",
            "last_name": "Mehta",
            "email": "suresh@newbuilder.in",
            "phone_number": "9988776655",
            "business_type": "infrastructure",
        }
        response = self.client.post("/api/customers/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["company"], "New Builder Co")
        self.assertEqual(Customer.objects.count(), 2)

    def test_create_customer_invalid(self):
        data = {"company": ""}  # missing required fields
        response = self.client.post("/api/customers/", data, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    # -- Detail -------------------------------------------------------------

    def test_get_customer_detail(self):
        self.create_contact(self.customer)
        response = self.client.get(f"/api/customers/{self.customer.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["company"], "Metro Constructions Pvt Ltd")
        self.assertEqual(len(response.data["contacts"]), 1)

    def test_get_customer_not_found(self):
        response = self.client.get("/api/customers/99999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # -- Update -------------------------------------------------------------

    def test_update_customer(self):
        data = {"company": "Metro Infra Updated"}
        response = self.client.put(
            f"/api/customers/{self.customer.pk}/", data, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["company"], "Metro Infra Updated")

    def test_update_customer_not_found(self):
        response = self.client.put(
            "/api/customers/99999/", {"company": "Ghost"}, format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # -- Delete -------------------------------------------------------------

    def test_delete_customer(self):
        response = self.client.delete(f"/api/customers/{self.customer.pk}/")
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(Customer.objects.count(), 0)

    def test_delete_customer_not_found(self):
        response = self.client.delete("/api/customers/99999/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    # -- Search -------------------------------------------------------------

    def test_search_customers(self):
        response = self.client.get("/api/customers/search/?q=Metro")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_search_no_results(self):
        response = self.client.get("/api/customers/search/?q=NonExistent")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    # -- Outstanding --------------------------------------------------------

    def test_outstanding_customers(self):
        self.create_outstanding(self.customer)
        response = self.client.get("/api/customers/outstanding/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            Decimal(response.data[0]["total_outstanding"]), Decimal("75000.00"),
        )

    def test_outstanding_empty(self):
        response = self.client.get("/api/customers/outstanding/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    # -- Business Type ------------------------------------------------------

    def test_filter_by_business_type(self):
        response = self.client.get("/api/customers/business-type/?type=construction")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_filter_by_business_type_empty(self):
        response = self.client.get("/api/customers/business-type/?type=events")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 0)

    def test_filter_by_business_type_missing_param(self):
        response = self.client.get("/api/customers/business-type/")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_filter_by_business_type_invalid(self):
        response = self.client.get("/api/customers/business-type/?type=invalid")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
