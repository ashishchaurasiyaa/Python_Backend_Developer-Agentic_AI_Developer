"""
Simple Dependency Injection Container.

Provides a class-level registry to map abstract interfaces to concrete
implementations.  At startup, PaymentsConfig.ready() registers the default
gateway.  At runtime, the SwitchGateway API can re-register a different one.

This is a SERVICE LOCATOR variant of DI.  In production Django apps you
might use django-injector or punq, but this 30-line container is enough
to demonstrate the concept clearly.
"""


class DIContainer:
    """Thread-safe-enough for a demo; production would use threading.Lock."""

    _registry: dict = {}

    @classmethod
    def register(cls, interface, implementation):
        """
        Bind an abstract interface to a concrete class (or instance).

        Usage:
            DIContainer.register(PaymentGateway, RazorpayGateway)
        """
        cls._registry[interface.__name__] = implementation

    @classmethod
    def resolve(cls, interface):
        """
        Retrieve the concrete implementation for the given interface.

        If a class was registered, a NEW instance is created each time.
        If an instance was registered, the same instance is returned.

        Usage:
            gateway = DIContainer.resolve(PaymentGateway)
        """
        impl = cls._registry.get(interface.__name__)
        if impl is None:
            raise ValueError(
                f"No implementation registered for {interface.__name__}. "
                f"Registered keys: {list(cls._registry.keys())}"
            )
        # If it is a class, instantiate it; if already an instance, return as-is
        return impl() if isinstance(impl, type) else impl

    @classmethod
    def clear(cls):
        """Remove all registrations (useful in tests)."""
        cls._registry.clear()
