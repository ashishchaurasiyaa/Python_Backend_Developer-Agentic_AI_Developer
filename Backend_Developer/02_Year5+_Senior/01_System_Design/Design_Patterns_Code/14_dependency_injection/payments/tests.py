"""
Tests for the Dependency Injection pattern (DIContainer + PaymentService).

Behavioural guarantee under test: PaymentService never hardcodes a gateway.
Whatever PaymentGateway implementation is injected - Razorpay, PayU, Mock,
or a test double we define here - PaymentService's business logic and
persisted records must behave consistently, and swapping implementations
must require touching NOTHING inside PaymentService itself.
"""

from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from .container import DIContainer
from .gateways import MockGateway, PayUGateway, RazorpayGateway
from .interfaces import PaymentGateway
from .models import Payment
from .services import PaymentService


class RecordingFakeGateway(PaymentGateway):
    """
    A minimal test double that satisfies the PaymentGateway contract.
    Its existence proves PaymentService depends on the ABSTRACTION, not
    on any concrete gateway class - a completely unknown implementation
    plugs in without PaymentService changing a single line.
    """

    def __init__(self):
        self.calls = []

    def create_payment_link(self, order_id, amount, phone):
        self.calls.append(("create_payment_link", order_id, amount, phone))
        return {
            "gateway": "fake",
            "reference_id": f"FAKE-{order_id}",
            "currency": "INR",
            "status": "created",
        }

    def verify_payment(self, reference_id):
        self.calls.append(("verify_payment", reference_id))
        return {"gateway": "fake", "status": "captured"}

    def refund_payment(self, reference_id, amount):
        self.calls.append(("refund_payment", reference_id, amount))
        return {"gateway": "fake", "status": "processed"}

    def get_gateway_name(self):
        return "fake"


class DIContainerTests(TestCase):
    """The container itself: register/resolve/clear semantics."""

    def setUp(self):
        self._saved_registry = dict(DIContainer._registry)

    def tearDown(self):
        DIContainer._registry = self._saved_registry

    def test_resolve_without_registration_raises(self):
        DIContainer.clear()
        with self.assertRaises(ValueError):
            DIContainer.resolve(PaymentGateway)

    def test_register_class_and_resolve_instantiates_it(self):
        DIContainer.clear()
        DIContainer.register(PaymentGateway, MockGateway)
        resolved = DIContainer.resolve(PaymentGateway)
        self.assertIsInstance(resolved, MockGateway)

    def test_resolve_with_class_registration_gives_new_instance_each_time(self):
        DIContainer.clear()
        DIContainer.register(PaymentGateway, MockGateway)
        a = DIContainer.resolve(PaymentGateway)
        b = DIContainer.resolve(PaymentGateway)
        self.assertIsNot(a, b)

    def test_resolve_with_instance_registration_returns_same_object(self):
        DIContainer.clear()
        shared = MockGateway()
        DIContainer.register(PaymentGateway, shared)
        a = DIContainer.resolve(PaymentGateway)
        b = DIContainer.resolve(PaymentGateway)
        self.assertIs(a, shared)
        self.assertIs(a, b)

    def test_re_registering_swaps_the_bound_implementation(self):
        DIContainer.clear()
        DIContainer.register(PaymentGateway, RazorpayGateway)
        self.assertIsInstance(DIContainer.resolve(PaymentGateway), RazorpayGateway)

        DIContainer.register(PaymentGateway, PayUGateway)
        self.assertIsInstance(DIContainer.resolve(PaymentGateway), PayUGateway)


class PaymentServiceInjectionTests(TestCase):
    """
    PaymentService must produce consistent, correct results regardless of
    WHICH gateway implementation was constructor-injected, and it must
    delegate every gateway-specific call through the injected object only.
    """

    def test_service_records_whichever_gateway_name_was_injected(self):
        for gateway_cls, expected_name in [
            (RazorpayGateway, "razorpay"),
            (PayUGateway, "payu"),
            (MockGateway, "mock"),
        ]:
            service = PaymentService(gateway=gateway_cls())
            self.assertEqual(service.get_active_gateway_name(), expected_name)

    def test_initiate_payment_persists_gateway_specific_reference_id(self):
        razorpay_service = PaymentService(gateway=RazorpayGateway())
        result = razorpay_service.initiate_payment(order_id=1, amount="100.00", phone="9000000001")
        self.assertTrue(result["gateway_reference_id"].startswith("rzp_link_"))
        self.assertEqual(result["gateway"], "razorpay")

        payu_service = PaymentService(gateway=PayUGateway())
        result2 = payu_service.initiate_payment(order_id=2, amount="100.00", phone="9000000002")
        self.assertTrue(result2["gateway_reference_id"].startswith("payu_txn_"))
        self.assertEqual(result2["gateway"], "payu")

    def test_arbitrary_unknown_gateway_implementation_works_unmodified(self):
        # The core DI promise: PaymentService was never written with
        # RecordingFakeGateway in mind, yet it works out of the box.
        fake = RecordingFakeGateway()
        service = PaymentService(gateway=fake)
        result = service.initiate_payment(order_id=99, amount="50.00", phone="9999999999")

        self.assertEqual(result["gateway"], "fake")
        self.assertEqual(result["gateway_reference_id"], "FAKE-99")
        self.assertEqual(fake.calls[0][0], "create_payment_link")

        payment = Payment.objects.get(id=result["payment_id"])
        self.assertEqual(payment.gateway, "fake")

    def test_verify_payment_delegates_to_injected_gateway_only(self):
        fake = RecordingFakeGateway()
        service = PaymentService(gateway=fake)
        create_result = service.initiate_payment(order_id=5, amount="20.00", phone="9111111111")

        verify_result = service.verify_payment(create_result["gateway_reference_id"])

        self.assertEqual(verify_result["our_status"], "success")
        self.assertEqual(fake.calls[-1], ("verify_payment", create_result["gateway_reference_id"]))

    def test_refund_payment_delegates_to_injected_gateway_only(self):
        fake = RecordingFakeGateway()
        service = PaymentService(gateway=fake)
        create_result = service.initiate_payment(order_id=6, amount="30.00", phone="9222222222")

        service.refund_payment(create_result["gateway_reference_id"], "30.00")

        payment = Payment.objects.get(id=create_result["payment_id"])
        self.assertEqual(payment.status, "refunded")
        self.assertEqual(fake.calls[-1][0], "refund_payment")


class DIHttpEndpointTests(APITestCase):
    """
    Exercises the actual HTTP surface: the SwitchGatewayView must change
    what DIContainer hands out, and subsequent requests must reflect the
    newly-injected implementation - proving runtime swap works end to end.
    """

    def setUp(self):
        # AppConfig.ready() already registered PAYMENT_GATEWAY="razorpay"
        # (the default in settings.py) when Django started; make sure
        # each test starts from that known baseline.
        DIContainer.register(PaymentGateway, RazorpayGateway)

    def test_active_gateway_endpoint_reflects_container_state(self):
        url = reverse("payments:active-gateway")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["active_gateway"], "razorpay")

    def test_switch_gateway_endpoint_changes_active_gateway(self):
        switch_url = reverse("payments:switch-gateway")
        response = self.client.post(switch_url, {"gateway_name": "mock"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["active_gateway"], "mock")

        active_url = reverse("payments:active-gateway")
        follow_up = self.client.get(active_url)
        self.assertEqual(follow_up.data["active_gateway"], "mock")

    def test_switch_gateway_rejects_unknown_gateway_name(self):
        switch_url = reverse("payments:switch-gateway")
        response = self.client.post(switch_url, {"gateway_name": "stripe"}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_initiate_payment_after_switch_uses_new_gateway(self):
        switch_url = reverse("payments:switch-gateway")
        self.client.post(switch_url, {"gateway_name": "mock"}, format="json")

        initiate_url = reverse("payments:payment-initiate")
        response = self.client.post(
            initiate_url,
            {"order_id": 42, "amount": "150.00", "phone": "9333333333"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["gateway"], "mock")
        self.assertTrue(response.data["gateway_reference_id"].startswith("MOCK-"))
