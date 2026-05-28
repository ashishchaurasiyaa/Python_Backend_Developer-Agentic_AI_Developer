"""
Factory Design Pattern -- Challan Movement Type Factory.

The ChallanFactory creates the correct challan type handler based on
the movement_type string. Each concrete type (DeliveryChallan, PickupChallan,
InterBranchChallan, CapitalPurchaseChallan, SalesChallan) implements:
  - get_required_fields()   -- fields that MUST be present
  - get_initial_stage()     -- starting workflow stage
  - get_challan_type()      -- Delivery or Pickup
  - validate(data)          -- type-specific validation rules
  - get_defaults()          -- default field values

The registry pattern allows new types to be registered at runtime
without modifying the factory class (Open/Closed Principle).
"""

from abc import ABC, abstractmethod


# ---------------------------------------------------------------------------
# Abstract Base
# ---------------------------------------------------------------------------
class BaseChallanType(ABC):
    """Abstract base -- each challan movement type implements this."""

    @abstractmethod
    def get_required_fields(self) -> list:
        """Fields that MUST be present for this movement type."""
        pass

    @abstractmethod
    def get_initial_stage(self) -> str:
        """What stage does this challan start at?"""
        pass

    @abstractmethod
    def get_challan_type(self) -> str:
        """Delivery or Pickup."""
        pass

    @abstractmethod
    def validate(self, data: dict) -> dict:
        """Validate data specific to this movement type. Return {valid: bool, errors: []}."""
        pass

    def get_defaults(self) -> dict:
        """Default field values for this type."""
        return {}


# ---------------------------------------------------------------------------
# Concrete Implementations
# ---------------------------------------------------------------------------
class DeliveryChallan(BaseChallanType):
    """Godown -> Job Site delivery."""

    def get_required_fields(self):
        return ["order_id", "delivery_location", "pickup_location", "dispatch_date"]

    def get_initial_stage(self):
        return "PLANNING_DONE"

    def get_challan_type(self):
        return "Delivery"

    def validate(self, data):
        errors = []
        for field in self.get_required_fields():
            if not data.get(field):
                errors.append(f"{field} is required for Delivery challan")
        if data.get("pickup_location") == data.get("delivery_location"):
            errors.append("Pickup and delivery locations cannot be the same")
        return {"valid": len(errors) == 0, "errors": errors}

    def get_defaults(self):
        return {"is_authorized": "0", "vehicle_number": ""}


class PickupChallan(BaseChallanType):
    """Job Site -> Godown pickup."""

    def get_required_fields(self):
        return ["order_id", "pickup_location"]

    def get_initial_stage(self):
        return "PLANNING_DONE"

    def get_challan_type(self):
        return "Pickup"

    def validate(self, data):
        errors = []
        for field in self.get_required_fields():
            if not data.get(field):
                errors.append(f"{field} is required for Pickup challan")
        return {"valid": len(errors) == 0, "errors": errors}


class InterBranchChallan(BaseChallanType):
    """Godown -> Godown transfer."""

    def get_required_fields(self):
        return ["pickup_location", "delivery_location", "distance_km"]

    def get_initial_stage(self):
        return "GENERATED_CHALLAN"

    def get_challan_type(self):
        return "Delivery"

    def validate(self, data):
        errors = []
        for field in self.get_required_fields():
            if not data.get(field):
                errors.append(f"{field} is required for Inter-Branch challan")
        if data.get("pickup_location") == data.get("delivery_location"):
            errors.append("Source and destination godowns must be different")
        return {"valid": len(errors) == 0, "errors": errors}

    def get_defaults(self):
        return {"order_id": None, "customer_name": "INTERNAL TRANSFER"}


class CapitalPurchaseChallan(BaseChallanType):
    """Vendor -> Godown for new equipment."""

    def get_required_fields(self):
        return ["delivery_location", "vehicle_number"]

    def get_initial_stage(self):
        return "GENERATED_CHALLAN"

    def get_challan_type(self):
        return "Delivery"

    def validate(self, data):
        errors = []
        for field in self.get_required_fields():
            if not data.get(field):
                errors.append(f"{field} is required for Capital Purchase challan")
        return {"valid": len(errors) == 0, "errors": errors}

    def get_defaults(self):
        return {
            "order_id": None,
            "customer_name": "CAPITAL PURCHASE",
            "pickup_location": "VENDOR",
        }


class SalesChallan(BaseChallanType):
    """Godown -> Customer (sale, not rental)."""

    def get_required_fields(self):
        return ["order_id", "delivery_location", "customer_name"]

    def get_initial_stage(self):
        return "PLANNING_DONE"

    def get_challan_type(self):
        return "Delivery"

    def validate(self, data):
        errors = []
        for field in self.get_required_fields():
            if not data.get(field):
                errors.append(f"{field} is required for Sales challan")
        return {"valid": len(errors) == 0, "errors": errors}


# ---------------------------------------------------------------------------
# The Factory
# ---------------------------------------------------------------------------
class ChallanFactory:
    """
    Factory -- creates the correct challan type based on movement_type.
    Registry pattern for extensibility.
    """

    _registry = {
        "delivery": DeliveryChallan,
        "pickup": PickupChallan,
        "inter_branch": InterBranchChallan,
        "capital_purchase": CapitalPurchaseChallan,
        "sales": SalesChallan,
    }

    @classmethod
    def create(cls, movement_type: str) -> BaseChallanType:
        """Create and return the correct challan type handler."""
        challan_class = cls._registry.get(movement_type)
        if not challan_class:
            raise ValueError(
                f"Unknown movement type: "{movement_type}". "
                f"Available: {list(cls._registry.keys())}"
            )
        return challan_class()

    @classmethod
    def get_available_types(cls) -> list:
        """Return metadata for every registered movement type."""
        result = []
        for key, klass in cls._registry.items():
            instance = klass()
            result.append(
                {
                    "movement_type": key,
                    "challan_type": instance.get_challan_type(),
                    "required_fields": instance.get_required_fields(),
                    "initial_stage": instance.get_initial_stage(),
                }
            )
        return result

    @classmethod
    def register(cls, movement_type: str, challan_class):
        """Extensible -- register new types at runtime."""
        cls._registry[movement_type] = challan_class
