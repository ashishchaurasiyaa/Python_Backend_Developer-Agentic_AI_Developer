"""
API views for the Dependency Injection demo.

Every view resolves the gateway from the DI Container, then injects it into
PaymentService.  The views never import a specific gateway class.
"""

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .container import DIContainer
from .gateways import MockGateway, PayUGateway, RazorpayGateway
from .interfaces import PaymentGateway
from .models import Payment
from .serializers import PaymentDetailSerializer, PaymentSerializer
from .services import PaymentService


def _get_payment_service() -> PaymentService:
    """Resolve the gateway from the DI Container and inject into service."""
    gateway = DIContainer.resolve(PaymentGateway)
    return PaymentService(gateway=gateway)


# --------------------------------------------------------------------------
# 1. Initiate Payment
# --------------------------------------------------------------------------
class PaymentInitiateView(APIView):
    """
    POST /api/payments/initiate/
    Body: {"order_id": 1001, "amount": "25000.00", "phone": "9876543210"}
    """

    def post(self, request):
        order_id = request.data.get("order_id")
        amount = request.data.get("amount")
        phone = request.data.get("phone")

        if not all([order_id, amount, phone]):
            return Response(
                {"error": "order_id, amount, and phone are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = _get_payment_service()
        result = service.initiate_payment(
            order_id=int(order_id), amount=amount, phone=phone
        )
        return Response(result, status=status.HTTP_201_CREATED)


# --------------------------------------------------------------------------
# 2. Verify Payment
# --------------------------------------------------------------------------
class PaymentVerifyView(APIView):
    """
    POST /api/payments/verify/
    Body: {"reference_id": "rzp_link_1001"}
    """

    def post(self, request):
        reference_id = request.data.get("reference_id")
        if not reference_id:
            return Response(
                {"error": "reference_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = _get_payment_service()
        result = service.verify_payment(reference_id=reference_id)
        return Response(result, status=status.HTTP_200_OK)


# --------------------------------------------------------------------------
# 3. Refund Payment
# --------------------------------------------------------------------------
class PaymentRefundView(APIView):
    """
    POST /api/payments/refund/
    Body: {"reference_id": "rzp_link_1001", "amount": "25000.00"}
    """

    def post(self, request):
        reference_id = request.data.get("reference_id")
        amount = request.data.get("amount")

        if not all([reference_id, amount]):
            return Response(
                {"error": "reference_id and amount are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = _get_payment_service()
        result = service.refund_payment(reference_id=reference_id, amount=amount)
        return Response(result, status=status.HTTP_200_OK)


# --------------------------------------------------------------------------
# 4. Active Gateway
# --------------------------------------------------------------------------
class ActiveGatewayView(APIView):
    """
    GET /api/payments/gateway/
    Shows which payment gateway is currently wired in the DI Container.
    """

    def get(self, request):
        service = _get_payment_service()
        return Response(
            {
                "active_gateway": service.get_active_gateway_name(),
                "available_gateways": ["razorpay", "payu", "mock"],
                "note": "POST to /api/payments/gateway/switch/ to change at runtime.",
            }
        )


# --------------------------------------------------------------------------
# 5. Switch Gateway (runtime DI re-registration)
# --------------------------------------------------------------------------
class SwitchGatewayView(APIView):
    """
    POST /api/payments/gateway/switch/
    Body: {"gateway_name": "payu"}

    Demonstrates that DI lets us swap implementations at RUNTIME without
    changing a single line in PaymentService.
    """

    GATEWAY_MAP = {
        "razorpay": RazorpayGateway,
        "payu": PayUGateway,
        "mock": MockGateway,
    }

    def post(self, request):
        gateway_name = request.data.get("gateway_name", "").lower()

        if gateway_name not in self.GATEWAY_MAP:
            return Response(
                {
                    "error": f"Unknown gateway: '{gateway_name}'.",
                    "available": list(self.GATEWAY_MAP.keys()),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        DIContainer.register(PaymentGateway, self.GATEWAY_MAP[gateway_name])

        return Response(
            {
                "message": f"Gateway switched to '{gateway_name}' successfully.",
                "active_gateway": gateway_name,
            }
        )


# --------------------------------------------------------------------------
# 6. Payment List
# --------------------------------------------------------------------------
class PaymentListView(APIView):
    """
    GET /api/payments/list/
    Returns all payments with nested logs.
    """

    def get(self, request):
        payments = Payment.objects.prefetch_related("logs").all()[:50]
        serializer = PaymentDetailSerializer(payments, many=True)
        return Response(serializer.data)
