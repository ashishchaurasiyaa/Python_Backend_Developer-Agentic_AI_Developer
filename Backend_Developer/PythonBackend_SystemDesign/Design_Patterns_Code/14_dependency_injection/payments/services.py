"""
PaymentService - the core business logic layer.

KEY DI PRINCIPLE:
    The gateway is INJECTED via the constructor, never created here.
    This class has NO idea whether it is talking to Razorpay, PayU, or a Mock.

Compare with the Youngman production anti-pattern:
    class RazorpayController:
        def __init__(self):
            self.repo = RazorpayRepository()   # HARDCODED dependency

DI version:
    class PaymentService:
        def __init__(self, gateway: PaymentGateway):  # INJECTED dependency
            self.gateway = gateway
"""

from decimal import Decimal

from .interfaces import PaymentGateway
from .models import Payment, PaymentLog


class PaymentService:
    """
    Orchestrates payment operations against any PaymentGateway implementation.
    """

    def __init__(self, gateway: PaymentGateway):
        """
        Constructor Injection - the gateway dependency is provided from outside.
        The caller decides which concrete gateway to pass in.
        """
        self.gateway = gateway

    # ------------------------------------------------------------------
    # Initiate
    # ------------------------------------------------------------------
    def initiate_payment(self, order_id: int, amount, phone: str) -> dict:
        """
        Create a payment link via the injected gateway, persist a Payment
        record and an audit PaymentLog entry.
        """
        amount = Decimal(str(amount))

        # Call the gateway (could be Razorpay, PayU, or Mock - we do not care)
        gateway_response = self.gateway.create_payment_link(order_id, amount, phone)

        # Persist
        payment = Payment.objects.create(
            order_id=order_id,
            amount=amount,
            currency=gateway_response.get("currency", "INR"),
            gateway=self.gateway.get_gateway_name(),
            gateway_reference_id=gateway_response.get("reference_id"),
            status="pending",
            customer_phone=phone,
        )

        PaymentLog.objects.create(
            payment=payment,
            action="create_link",
            request_payload={
                "order_id": order_id,
                "amount": str(amount),
                "phone": phone,
            },
            response_payload=gateway_response,
            status="created",
        )

        return {
            "payment_id": payment.id,
            "order_id": payment.order_id,
            "gateway": payment.gateway,
            "gateway_reference_id": payment.gateway_reference_id,
            "amount": str(payment.amount),
            "status": payment.status,
            "gateway_response": gateway_response,
        }

    # ------------------------------------------------------------------
    # Verify
    # ------------------------------------------------------------------
    def verify_payment(self, reference_id: str) -> dict:
        """
        Verify a payment's status on the gateway and update our records.
        """
        gateway_response = self.gateway.verify_payment(reference_id)

        gw_status = gateway_response.get("status", "")
        our_status = "success" if gw_status in ("captured", "success") else "failed"

        payment = Payment.objects.filter(gateway_reference_id=reference_id).first()
        if payment:
            payment.status = our_status
            payment.save(update_fields=["status"])

            PaymentLog.objects.create(
                payment=payment,
                action="verify",
                request_payload={"reference_id": reference_id},
                response_payload=gateway_response,
                status=our_status,
            )

        return {
            "reference_id": reference_id,
            "gateway": self.gateway.get_gateway_name(),
            "gateway_status": gw_status,
            "our_status": our_status,
            "payment_id": payment.id if payment else None,
            "gateway_response": gateway_response,
        }

    # ------------------------------------------------------------------
    # Refund
    # ------------------------------------------------------------------
    def refund_payment(self, reference_id: str, amount) -> dict:
        """
        Request a refund through the injected gateway.
        """
        amount = Decimal(str(amount))
        gateway_response = self.gateway.refund_payment(reference_id, amount)

        payment = Payment.objects.filter(gateway_reference_id=reference_id).first()
        if payment:
            payment.status = "refunded"
            payment.save(update_fields=["status"])

            PaymentLog.objects.create(
                payment=payment,
                action="refund",
                request_payload={
                    "reference_id": reference_id,
                    "amount": str(amount),
                },
                response_payload=gateway_response,
                status="refunded",
            )

        return {
            "reference_id": reference_id,
            "gateway": self.gateway.get_gateway_name(),
            "refund_amount": str(amount),
            "status": "refunded",
            "payment_id": payment.id if payment else None,
            "gateway_response": gateway_response,
        }

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------
    def get_active_gateway_name(self) -> str:
        """Return the name of the currently injected gateway."""
        return self.gateway.get_gateway_name()
