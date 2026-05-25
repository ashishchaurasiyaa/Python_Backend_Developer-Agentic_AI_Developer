"""
Three concrete PaymentGateway implementations.

Each one fulfils the same abstract interface but returns data in the format
of its real-world counterpart.  The beauty of DI is that PaymentService
never knows (or cares) which one it is talking to.
"""

import uuid
from decimal import Decimal

from .interfaces import PaymentGateway


# ---------------------------------------------------------------------------
# 1. Razorpay Gateway
# ---------------------------------------------------------------------------
class RazorpayGateway(PaymentGateway):
    """
    Simulates the Razorpay payment flow used in Youngman production.
    - Amounts are sent in PAISE (amount x 100).
    - Reference IDs look like rzp_link_<ORDER_ID>.
    - Callback URL points to Youngman's domain.
    """

    CALLBACK_URL = "https://www.youngmanindia.com/api/razorpay/callback"

    def create_payment_link(self, order_id: int, amount, phone: str) -> dict:
        amount_paise = int(Decimal(str(amount)) * 100)
        reference_id = f"rzp_link_{order_id}"
        return {
            "gateway": "razorpay",
            "reference_id": reference_id,
            "amount_paise": amount_paise,
            "amount_display": str(amount),
            "currency": "INR",
            "short_url": f"https://rzp.io/i/{reference_id}",
            "callback_url": self.CALLBACK_URL,
            "customer_phone": phone,
            "status": "created",
        }

    def verify_payment(self, reference_id: str) -> dict:
        return {
            "gateway": "razorpay",
            "reference_id": reference_id,
            "status": "captured",
            "method": "upi",
            "captured": True,
            "description": "Payment verified via Razorpay API",
        }

    def refund_payment(self, reference_id: str, amount) -> dict:
        amount_paise = int(Decimal(str(amount)) * 100)
        refund_id = f"rfnd_{uuid.uuid4().hex[:12]}"
        return {
            "gateway": "razorpay",
            "reference_id": reference_id,
            "refund_id": refund_id,
            "amount_paise": amount_paise,
            "status": "processed",
            "speed": "normal",
        }

    def get_gateway_name(self) -> str:
        return "razorpay"


# ---------------------------------------------------------------------------
# 2. PayU Gateway
# ---------------------------------------------------------------------------
class PayUGateway(PaymentGateway):
    """
    Simulates the PayU payment flow.
    - Amounts stay in RUPEES (no conversion).
    - Uses txnid instead of reference_id internally.
    - Different field names than Razorpay to prove the interface abstracts
      away these differences.
    """

    def create_payment_link(self, order_id: int, amount, phone: str) -> dict:
        txnid = f"payu_txn_{order_id}_{uuid.uuid4().hex[:6]}"
        return {
            "gateway": "payu",
            "reference_id": txnid,
            "txnid": txnid,
            "amount": str(amount),
            "currency": "INR",
            "payment_url": f"https://secure.payu.in/_payment/{txnid}",
            "customer_phone": phone,
            "status": "created",
            "merchant_key": "youngman_merchant",
        }

    def verify_payment(self, reference_id: str) -> dict:
        return {
            "gateway": "payu",
            "reference_id": reference_id,
            "txnid": reference_id,
            "status": "success",
            "mode": "NB",
            "unmappedstatus": "captured",
            "description": "Payment verified via PayU API",
        }

    def refund_payment(self, reference_id: str, amount) -> dict:
        refund_id = f"payu_rfnd_{uuid.uuid4().hex[:8]}"
        return {
            "gateway": "payu",
            "reference_id": reference_id,
            "refund_id": refund_id,
            "amount": str(amount),
            "status": "refund_initiated",
        }

    def get_gateway_name(self) -> str:
        return "payu"


# ---------------------------------------------------------------------------
# 3. Mock Gateway (for tests)
# ---------------------------------------------------------------------------
class MockGateway(PaymentGateway):
    """
    Returns instant success responses without any network calls.
    Perfect for unit tests — no API keys, no latency, deterministic output.
    """

    def create_payment_link(self, order_id: int, amount, phone: str) -> dict:
        return {
            "gateway": "mock",
            "reference_id": f"MOCK-{order_id}",
            "amount": str(amount),
            "currency": "INR",
            "customer_phone": phone,
            "status": "created",
            "note": "Mock gateway - no real transaction",
        }

    def verify_payment(self, reference_id: str) -> dict:
        return {
            "gateway": "mock",
            "reference_id": reference_id,
            "status": "success",
            "note": "Mock verification - always succeeds",
        }

    def refund_payment(self, reference_id: str, amount) -> dict:
        return {
            "gateway": "mock",
            "reference_id": reference_id,
            "refund_id": f"MOCK-RFND-{uuid.uuid4().hex[:8]}",
            "amount": str(amount),
            "status": "refunded",
            "note": "Mock refund - instant success",
        }

    def get_gateway_name(self) -> str:
        return "mock"
