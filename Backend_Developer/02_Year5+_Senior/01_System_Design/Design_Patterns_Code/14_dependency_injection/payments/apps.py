from django.apps import AppConfig


class PaymentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "payments"

    def ready(self):
        """
        Called once when Django starts.
        Reads the PAYMENT_GATEWAY setting and registers the corresponding
        concrete class in the DI Container.
        """
        from django.conf import settings

        from .container import DIContainer
        from .gateways import MockGateway, PayUGateway, RazorpayGateway
        from .interfaces import PaymentGateway

        gateway_map = {
            "razorpay": RazorpayGateway,
            "payu": PayUGateway,
            "mock": MockGateway,
        }

        gateway_name = getattr(settings, "PAYMENT_GATEWAY", "razorpay")
        gateway_class = gateway_map.get(gateway_name, RazorpayGateway)
        DIContainer.register(PaymentGateway, gateway_class)
