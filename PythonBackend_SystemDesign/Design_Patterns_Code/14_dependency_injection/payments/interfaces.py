from abc import ABC, abstractmethod


class PaymentGateway(ABC):
    """
    Abstract interface that every payment gateway must implement.

    This is the CONTRACT that makes Dependency Injection possible.
    PaymentService depends on this abstraction, not on Razorpay/PayU directly.

    Youngman context:
        The original RazorpayController.php does:
            $this->repo = new RazorpayRepository();   // HARDCODED
        With DI we instead receive the dependency through the constructor:
            def __init__(self, gateway: PaymentGateway):  // INJECTED
    """

    @abstractmethod
    def create_payment_link(self, order_id: int, amount, phone: str) -> dict:
        """Create a payment link / order on the gateway and return its details."""
        pass

    @abstractmethod
    def verify_payment(self, reference_id: str) -> dict:
        """Verify whether a payment was captured / successful."""
        pass

    @abstractmethod
    def refund_payment(self, reference_id: str, amount) -> dict:
        """Initiate a refund and return the refund details."""
        pass

    @abstractmethod
    def get_gateway_name(self) -> str:
        """Return a human-readable name for this gateway."""
        pass
