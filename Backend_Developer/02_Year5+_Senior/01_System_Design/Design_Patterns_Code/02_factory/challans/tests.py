"""
Tests for the Factory Method pattern (ChallanFactory).

Behavioural guarantee under test: ChallanFactory.create(movement_type)
must return an instance of the RIGHT concrete BaseChallanType subclass
for each input, and each subclass must carry its own required fields /
validation / defaults - that divergence is the entire point of the
pattern (callers never branch on movement_type themselves).
"""

from django.test import TestCase

from .factory import (
    ChallanFactory,
    DeliveryChallan,
    PickupChallan,
    InterBranchChallan,
    CapitalPurchaseChallan,
    SalesChallan,
)
from .models import Challan


class ChallanFactoryCreateTests(TestCase):
    """create() must dispatch to the correct concrete subclass."""

    def test_delivery_movement_type_returns_delivery_challan(self):
        instance = ChallanFactory.create("delivery")
        self.assertIsInstance(instance, DeliveryChallan)

    def test_pickup_movement_type_returns_pickup_challan(self):
        instance = ChallanFactory.create("pickup")
        self.assertIsInstance(instance, PickupChallan)

    def test_inter_branch_movement_type_returns_inter_branch_challan(self):
        instance = ChallanFactory.create("inter_branch")
        self.assertIsInstance(instance, InterBranchChallan)

    def test_capital_purchase_movement_type_returns_capital_purchase_challan(self):
        instance = ChallanFactory.create("capital_purchase")
        self.assertIsInstance(instance, CapitalPurchaseChallan)

    def test_sales_movement_type_returns_sales_challan(self):
        instance = ChallanFactory.create("sales")
        self.assertIsInstance(instance, SalesChallan)

    def test_unknown_movement_type_raises_value_error(self):
        with self.assertRaises(ValueError) as ctx:
            ChallanFactory.create("teleportation")
        self.assertIn("teleportation", str(ctx.exception))

    def test_each_call_returns_a_fresh_instance_not_a_shared_one(self):
        # Unlike Singleton, Factory Method must hand back independent
        # objects each time - proves this isn't accidentally memoized.
        a = ChallanFactory.create("delivery")
        b = ChallanFactory.create("delivery")
        self.assertIsInstance(a, DeliveryChallan)
        self.assertIsInstance(b, DeliveryChallan)
        self.assertIsNot(a, b)


class ChallanFactoryPolymorphicBehaviourTests(TestCase):
    """
    The whole reason to use Factory here: each concrete type has
    genuinely different required_fields / initial_stage / validation,
    and callers get that behaviour without an if/elif ladder.
    """

    def test_required_fields_differ_by_movement_type(self):
        delivery_fields = set(ChallanFactory.create("delivery").get_required_fields())
        pickup_fields = set(ChallanFactory.create("pickup").get_required_fields())
        capital_fields = set(ChallanFactory.create("capital_purchase").get_required_fields())

        self.assertNotEqual(delivery_fields, pickup_fields)
        self.assertNotEqual(delivery_fields, capital_fields)
        self.assertIn("dispatch_date", delivery_fields)
        self.assertNotIn("dispatch_date", pickup_fields)

    def test_initial_stage_differs_by_movement_type(self):
        # delivery/pickup/sales start at PLANNING_DONE, inter_branch and
        # capital_purchase skip planning and start at GENERATED_CHALLAN.
        self.assertEqual(ChallanFactory.create("delivery").get_initial_stage(), "PLANNING_DONE")
        self.assertEqual(
            ChallanFactory.create("inter_branch").get_initial_stage(), "GENERATED_CHALLAN"
        )
        self.assertEqual(
            ChallanFactory.create("capital_purchase").get_initial_stage(), "GENERATED_CHALLAN"
        )

    def test_delivery_validate_rejects_identical_pickup_and_delivery_location(self):
        result = ChallanFactory.create("delivery").validate({
            "order_id": 1,
            "delivery_location": "Site-A",
            "pickup_location": "Site-A",
            "dispatch_date": "2026-01-01",
        })
        self.assertFalse(result["valid"])
        self.assertTrue(any("same" in e.lower() for e in result["errors"]))

    def test_delivery_validate_passes_with_all_required_fields(self):
        result = ChallanFactory.create("delivery").validate({
            "order_id": 1,
            "delivery_location": "Site-A",
            "pickup_location": "Godown-1",
            "dispatch_date": "2026-01-01",
        })
        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])

    def test_pickup_validate_flags_each_missing_required_field(self):
        result = ChallanFactory.create("pickup").validate({})
        self.assertFalse(result["valid"])
        self.assertEqual(len(result["errors"]), 2)  # order_id + pickup_location

    def test_inter_branch_rejects_same_source_and_destination(self):
        result = ChallanFactory.create("inter_branch").validate({
            "pickup_location": "Godown-1",
            "delivery_location": "Godown-1",
            "distance_km": 5,
        })
        self.assertFalse(result["valid"])

    def test_get_defaults_is_type_specific(self):
        delivery_defaults = ChallanFactory.create("delivery").get_defaults()
        capital_defaults = ChallanFactory.create("capital_purchase").get_defaults()
        sales_defaults = ChallanFactory.create("sales").get_defaults()

        self.assertIn("vehicle_number", delivery_defaults)
        self.assertEqual(capital_defaults["customer_name"], "CAPITAL PURCHASE")
        self.assertEqual(sales_defaults, {})  # SalesChallan doesn't override get_defaults


class ChallanFactoryRegistryTests(TestCase):
    """The registry is the extensibility seam - Open/Closed in practice."""

    def test_get_available_types_lists_every_registered_movement_type(self):
        types = ChallanFactory.get_available_types()
        movement_types = {t["movement_type"] for t in types}
        self.assertEqual(
            movement_types,
            {"delivery", "pickup", "inter_branch", "capital_purchase", "sales"},
        )

    def test_register_adds_a_new_type_without_modifying_factory_class(self):
        class ReturnToVendorChallan(DeliveryChallan):
            def get_challan_type(self):
                return "Pickup"

        ChallanFactory.register("return_to_vendor", ReturnToVendorChallan)
        try:
            instance = ChallanFactory.create("return_to_vendor")
            self.assertIsInstance(instance, ReturnToVendorChallan)
            self.assertEqual(instance.get_challan_type(), "Pickup")
        finally:
            # keep the registry clean for other tests in the suite
            del ChallanFactory._registry["return_to_vendor"]


class ChallanFactoryModelIntegrationTests(TestCase):
    """
    Proves factory output is actually usable to build a persisted Challan -
    the initial_stage/defaults the factory computes must round-trip
    through the ORM unchanged.
    """

    def test_challan_created_with_factory_computed_stage_and_type(self):
        handler = ChallanFactory.create("inter_branch")
        challan = Challan.objects.create(
            challan_no="CH-1001",
            challan_type=handler.get_challan_type(),
            challan_movement_type="inter_branch",
            current_stage=handler.get_initial_stage(),
            pickup_location="Godown-1",
            delivery_location="Godown-2",
            distance_km=12,
        )
        challan.refresh_from_db()
        self.assertEqual(challan.current_stage, "GENERATED_CHALLAN")
        self.assertEqual(challan.challan_type, "Delivery")
