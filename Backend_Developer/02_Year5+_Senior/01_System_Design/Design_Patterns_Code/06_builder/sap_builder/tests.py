"""
Tests for the Builder pattern (PayloadBuilder + BaseEwayBillBuilder +
PayloadDirector).

Behavioural guarantee under test: a complex payload is assembled one named
step at a time; optional steps really are optional; the half-built product
is inspectable; validation happens once at build() and reports every
problem together; and a builder instance resets itself so it can be reused
without leaking state between payloads.

That last one gets its own test class. State leaking between builds is the
single most common Builder bug in production code — the second payload
quietly inherits the first payload's line items, the totals are wrong, and
nothing raises.
"""
from datetime import date
from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from .builders import (
    EWAY_BILL_BUILDERS,
    BaseEwayBillBuilder,
    BuilderValidationError,
    DeliveryEwayBillBuilder,
    PayloadBuilder,
    PayloadDirector,
    PickupEwayBillBuilder,
    get_eway_bill_builder,
    save_payload,
)
from .models import BuiltPayload, DraftLine, SapDocumentDraft

# Maharashtra = 27, Karnataka = 29. Used to flip intra/inter state.
MAHARASHTRA = 27
KARNATAKA = 29


def make_draft(**overrides):
    defaults = dict(
        doc_type='delivery',
        reference_no='DC-000101',
        card_code='C00421',
        card_name='Metro Constructions Pvt Ltd',
        from_warehouse='MUM-01',
        from_gstin='27AAACY1234A1Z5',
        from_state_code=MAHARASHTRA,
        from_pincode=421302,
        from_address='Bhiwandi Godown, Thane',
        to_warehouse='SITE-09',
        to_gstin='27AABCM5678B1Z3',
        to_state_code=MAHARASHTRA,
        to_pincode=400018,
        to_address='Worli Tower Site, Mumbai',
        vehicle_number='MH-04-AB-1234',
        transport_mode='Road',
        transporter_id='TR-9001',
        distance_km=45,
        posting_date=date(2026, 8, 8),
        comments='Handle with care',
    )
    defaults.update(overrides)
    return SapDocumentDraft.objects.create(**defaults)


def add_line(draft, **overrides):
    defaults = dict(
        line_num=draft.lines.count(),
        item_code='SCAF-01',
        item_name='Standard Frame',
        hsn_code='73084000',
        quantity=Decimal('100.000'),
        unit='NOS',
        rate=Decimal('120.00'),
    )
    defaults.update(overrides)
    return DraftLine.objects.create(draft=draft, **defaults)


def draft_with_lines(**overrides):
    draft = make_draft(**overrides)
    add_line(draft)
    return draft


class FluentInterfaceTests(TestCase):
    """Every configuration step must return the builder itself."""

    def test_every_with_step_returns_self_so_calls_chain(self):
        draft = draft_with_lines()
        builder = PayloadBuilder()

        self.assertIs(builder.for_draft(draft), builder)
        self.assertIs(builder.with_supply_direction(), builder)
        self.assertIs(builder.with_consignor_from_company(), builder)
        self.assertIs(builder.with_consignee_from_customer(), builder)
        self.assertIs(builder.with_transport(), builder)
        self.assertIs(builder.with_comments(), builder)
        self.assertIs(builder.with_warehouses(), builder)
        self.assertIs(builder.with_lines_from_draft(), builder)
        self.assertIs(builder.with_taxes(), builder)
        self.assertIs(builder.reset(), builder)

    def test_a_full_chain_reads_as_one_expression(self):
        draft = draft_with_lines()
        payload = (PayloadBuilder()
                   .for_draft(draft)
                   .with_supply_direction('Outward')
                   .with_consignor_from_company()
                   .with_consignee_from_customer()
                   .with_transport(vehicle_number='MH-12-XY-0099')
                   .with_lines_from_draft()
                   .with_taxes()
                   .build())

        self.assertEqual(payload['supply_type'], 'Outward')
        self.assertEqual(payload['vehicle_number'], 'MH-12-XY-0099')
        self.assertEqual(len(payload['item_list']), 1)

    def test_steps_applied_records_the_construction_history(self):
        draft = draft_with_lines()
        builder = (PayloadBuilder()
                   .for_draft(draft)
                   .with_supply_direction()
                   .with_consignor_from_company())

        self.assertEqual(builder.steps_applied,
                         ['for_draft', 'with_supply_direction',
                          'with_consignor_from_company'])

    def test_steps_may_be_applied_in_any_order(self):
        draft = draft_with_lines()
        forwards = (PayloadBuilder().for_draft(draft)
                    .with_supply_direction('Outward')
                    .with_consignor_from_company()
                    .with_consignee_from_customer()
                    .with_transport()
                    .with_lines_from_draft().with_taxes().build())
        backwards = (PayloadBuilder().for_draft(draft)
                     .with_transport()
                     .with_consignee_from_customer()
                     .with_lines_from_draft()
                     .with_consignor_from_company()
                     .with_supply_direction('Outward')
                     .with_taxes().build())

        self.assertEqual(forwards, backwards)


class OptionalStepTests(TestCase):
    """Optional steps must genuinely be skippable."""

    def test_a_payload_builds_with_no_transport_step_at_all(self):
        draft = draft_with_lines()
        payload = (PayloadBuilder().for_draft(draft)
                   .with_supply_direction()
                   .with_consignor_from_company()
                   .with_consignee_from_customer()
                   .with_lines_from_draft()
                   .with_taxes()
                   .build())

        self.assertNotIn('vehicle_number', payload)
        self.assertEqual(payload['supply_type'], 'Outward')

    def test_transport_falls_back_to_the_draft_when_given_no_arguments(self):
        draft = draft_with_lines()
        builder = PayloadBuilder().for_draft(draft).with_transport()
        snapshot = builder.peek()

        self.assertEqual(snapshot['vehicle_number'], 'MH-04-AB-1234')
        self.assertEqual(snapshot['transporter_id'], 'TR-9001')
        self.assertEqual(snapshot['distance'], 45)

    def test_explicit_transport_arguments_override_the_draft(self):
        draft = draft_with_lines()
        snapshot = (PayloadBuilder().for_draft(draft)
                    .with_transport(vehicle_number='MH-99-ZZ-0001',
                                    transport_mode='Rail',
                                    distance_km=900)
                    .peek())

        self.assertEqual(snapshot['vehicle_number'], 'MH-99-ZZ-0001')
        self.assertEqual(snapshot['transport_mode'], 'Rail')
        self.assertEqual(snapshot['distance'], 900)

    def test_comments_default_to_the_draft_and_can_be_overridden(self):
        draft = draft_with_lines()
        self.assertEqual(
            PayloadBuilder().for_draft(draft).with_comments().peek()['comments'],
            'Handle with care')
        self.assertEqual(
            PayloadBuilder().for_draft(draft)
            .with_comments('Urgent').peek()['comments'],
            'Urgent')

    def test_supply_direction_defaults_from_the_draft_doc_type(self):
        delivery = PayloadBuilder().for_draft(
            draft_with_lines()).with_supply_direction().peek()
        pickup = PayloadBuilder().for_draft(
            draft_with_lines(doc_type='pickup', reference_no='PC-000055')
        ).with_supply_direction().peek()

        self.assertEqual((delivery['supply_type'], delivery['transaction_type']),
                         ('Outward', 2))
        self.assertEqual((pickup['supply_type'], pickup['transaction_type']),
                         ('Inward', 3))

    def test_a_step_needing_a_draft_fails_clearly_without_one(self):
        with self.assertRaises(BuilderValidationError) as ctx:
            PayloadBuilder().with_consignor_from_company()
        self.assertIn('for_draft', str(ctx.exception))


class PartialConstructionTests(TestCase):
    """
    peek() exposes the half-built product.

    This is what separates a Builder from a factory function: construction
    can be paused, inspected, and resumed.
    """

    def test_peek_returns_the_payload_so_far(self):
        draft = draft_with_lines()
        builder = (PayloadBuilder().for_draft(draft)
                   .with_supply_direction('Outward'))

        snapshot = builder.peek()
        self.assertEqual(snapshot['supply_type'], 'Outward')
        self.assertNotIn('gstin_of_consignor', snapshot)

    def test_peek_does_not_finish_or_reset_the_builder(self):
        draft = draft_with_lines()
        builder = PayloadBuilder().for_draft(draft).with_supply_direction()

        builder.peek()
        builder.peek()

        # State survives both peeks and the build still works.
        payload = (builder.with_consignor_from_company()
                   .with_consignee_from_customer()
                   .with_lines_from_draft().with_taxes().build())
        self.assertEqual(payload['supply_type'], 'Outward')

    def test_mutating_a_peeked_snapshot_does_not_corrupt_the_builder(self):
        draft = draft_with_lines()
        builder = PayloadBuilder().for_draft(draft).with_supply_direction()

        snapshot = builder.peek()
        snapshot['supply_type'] = 'TAMPERED'
        snapshot['item_list'].append({'bogus': True})

        self.assertEqual(builder.peek()['supply_type'], 'Outward')
        self.assertEqual(builder.peek()['item_list'], [])


class BuilderResetTests(TestCase):
    """State must never leak from one build into the next."""

    def test_build_resets_the_builder(self):
        draft = draft_with_lines()
        builder = PayloadBuilder()
        (builder.for_draft(draft).with_supply_direction()
         .with_consignor_from_company().with_consignee_from_customer()
         .with_lines_from_draft().with_taxes().build())

        self.assertEqual(builder.peek(), {'item_list': []})
        self.assertEqual(builder.steps_applied, [])

    def test_reusing_one_builder_does_not_accumulate_line_items(self):
        first = draft_with_lines()
        second = draft_with_lines(reference_no='DC-000102')
        add_line(second, item_code='SCAF-02')

        builder = PayloadBuilder()
        payloads = []
        for draft in (first, second):
            payloads.append(
                builder.for_draft(draft).with_supply_direction()
                .with_consignor_from_company().with_consignee_from_customer()
                .with_lines_from_draft().with_taxes().build())

        self.assertEqual(len(payloads[0]['item_list']), 1)
        self.assertEqual(len(payloads[1]['item_list']), 2)  # not 3

    def test_a_failed_build_leaves_state_intact_for_correction(self):
        # build() only resets on SUCCESS, so a caller can fix the problem
        # and retry without re-running every step.
        draft = draft_with_lines()
        builder = (PayloadBuilder().for_draft(draft)
                   .with_supply_direction()
                   .with_consignor_from_company()
                   .with_lines_from_draft()
                   .with_taxes())

        with self.assertRaises(BuilderValidationError):
            builder.build()          # no consignee yet

        payload = builder.with_consignee_from_customer().build()
        self.assertEqual(len(payload['item_list']), 1)

    def test_the_returned_payload_is_detached_from_the_builder(self):
        draft = draft_with_lines()
        builder = PayloadBuilder()
        payload = (builder.for_draft(draft).with_supply_direction()
                   .with_consignor_from_company().with_consignee_from_customer()
                   .with_lines_from_draft().with_taxes().build())

        payload['item_list'].append({'bogus': True})
        self.assertEqual(builder.peek()['item_list'], [])


class ValidationTests(TestCase):
    """build() validates once, and reports everything at once."""

    def test_an_empty_builder_reports_every_missing_field_together(self):
        with self.assertRaises(BuilderValidationError) as ctx:
            PayloadBuilder().build()

        errors = ctx.exception.errors
        for key in PayloadBuilder.REQUIRED_KEYS:
            self.assertTrue(any(key in error for error in errors), key)

    def test_the_error_carries_a_structured_list_not_just_a_string(self):
        with self.assertRaises(BuilderValidationError) as ctx:
            PayloadBuilder().build()
        self.assertIsInstance(ctx.exception.errors, list)
        self.assertGreater(len(ctx.exception.errors), 1)

    def test_a_payload_with_no_lines_is_rejected(self):
        draft = make_draft()  # no lines
        with self.assertRaises(BuilderValidationError) as ctx:
            (PayloadBuilder().for_draft(draft).with_supply_direction()
             .with_consignor_from_company().with_consignee_from_customer()
             .with_lines_from_draft().with_taxes().build())
        self.assertTrue(any('item_list' in e for e in ctx.exception.errors))

    def test_computing_taxes_before_adding_lines_is_caught(self):
        # The classic ordering mistake: totals would silently be zero.
        draft = draft_with_lines()
        with self.assertRaises(BuilderValidationError) as ctx:
            (PayloadBuilder().for_draft(draft).with_supply_direction()
             .with_consignor_from_company().with_consignee_from_customer()
             .with_taxes()                    # too early
             .with_lines_from_draft()
             .build())
        self.assertTrue(
            any('with_taxes()' in e for e in ctx.exception.errors))

    def test_road_transport_without_a_vehicle_number_is_caught(self):
        draft = draft_with_lines(vehicle_number='')
        with self.assertRaises(BuilderValidationError) as ctx:
            (PayloadBuilder().for_draft(draft).with_supply_direction()
             .with_consignor_from_company().with_consignee_from_customer()
             .with_transport()
             .with_lines_from_draft().with_taxes().build())
        self.assertTrue(
            any('vehicle_number' in e for e in ctx.exception.errors))

    def test_skipping_the_transport_step_avoids_the_vehicle_rule(self):
        # Not filing transport at all is legal; filing it incomplete is not.
        draft = draft_with_lines(vehicle_number='')
        payload = (PayloadBuilder().for_draft(draft).with_supply_direction()
                   .with_consignor_from_company().with_consignee_from_customer()
                   .with_lines_from_draft().with_taxes().build())
        self.assertNotIn('vehicle_number', payload)


class TaxCalculationTests(TestCase):
    def test_intra_state_movement_splits_into_cgst_and_sgst(self):
        draft = draft_with_lines()  # both ends in Maharashtra
        payload = PayloadDirector().build_minimal(draft)

        self.assertEqual(payload['tax_mode'], 'intra')
        self.assertEqual(payload['total_value'], 12000.0)     # 100 * 120
        self.assertEqual(payload['cgst_value'], 1080.0)       # 9%
        self.assertEqual(payload['sgst_value'], 1080.0)       # 9%
        self.assertEqual(payload['igst_value'], 0.0)
        self.assertEqual(payload['grand_total'], 14160.0)

    def test_inter_state_movement_uses_igst_only(self):
        draft = draft_with_lines(to_state_code=KARNATAKA)
        payload = PayloadDirector().build_minimal(draft)

        self.assertEqual(payload['tax_mode'], 'inter')
        self.assertEqual(payload['igst_value'], 2160.0)       # 18%
        self.assertEqual(payload['cgst_value'], 0.0)
        self.assertEqual(payload['sgst_value'], 0.0)
        self.assertEqual(payload['grand_total'], 14160.0)

    def test_the_tax_mode_can_be_forced_regardless_of_the_draft(self):
        draft = draft_with_lines()  # intra by data
        snapshot = (PayloadBuilder().for_draft(draft)
                    .with_lines_from_draft()
                    .with_taxes(intra_state=False)
                    .peek())
        self.assertEqual(snapshot['tax_mode'], 'inter')

    def test_taxes_cover_every_line_added_so_far(self):
        draft = draft_with_lines()
        add_line(draft, item_code='SCAF-02', quantity=Decimal('50.000'),
                 rate=Decimal('80.00'))

        payload = PayloadDirector().build_minimal(draft)
        self.assertEqual(payload['total_value'], 16000.0)  # 12000 + 4000

    def test_hand_added_lines_and_draft_lines_both_count(self):
        draft = draft_with_lines()
        snapshot = (PayloadBuilder().for_draft(draft)
                    .with_lines_from_draft()
                    .with_line('SCAF-99', quantity=10, rate=100)
                    .with_taxes()
                    .peek())
        self.assertEqual(len(snapshot['item_list']), 2)
        self.assertEqual(snapshot['total_value'], 13000.0)

    def test_is_intra_state_is_false_when_a_state_code_is_missing(self):
        draft = draft_with_lines(to_state_code=None)
        self.assertFalse(draft.is_intra_state)


class LineBuildingTests(TestCase):
    def test_a_hand_added_line_computes_its_taxable_amount(self):
        snapshot = PayloadBuilder().with_line(
            'SCAF-07', quantity=12, rate='75.50',
            item_name='Base Jack', hsn_code='73084000').peek()

        line = snapshot['item_list'][0]
        self.assertEqual(line['item_code'], 'SCAF-07')
        self.assertEqual(line['product_name'], 'Base Jack')
        self.assertEqual(line['taxable_amount'], 906.0)  # 12 * 75.50

    def test_product_name_falls_back_to_the_item_code(self):
        snapshot = PayloadBuilder().with_line('SCAF-07', 1, 10).peek()
        self.assertEqual(snapshot['item_list'][0]['product_name'], 'SCAF-07')

    def test_draft_lines_carry_hsn_and_unit_into_the_payload(self):
        draft = draft_with_lines()
        snapshot = (PayloadBuilder().for_draft(draft)
                    .with_lines_from_draft().peek())

        line = snapshot['item_list'][0]
        self.assertEqual(line['hsn_code'], '73084000')
        self.assertEqual(line['unit'], 'NOS')
        self.assertEqual(line['quantity'], 100.0)

    def test_lines_accumulate_across_repeated_calls(self):
        builder = PayloadBuilder()
        builder.with_line('A', 1, 10).with_line('B', 2, 20).with_line('C', 3, 30)
        self.assertEqual(len(builder.peek()['item_list']), 3)


class PayloadDirectorTests(TestCase):
    """The director encodes the recipes so callers stop improvising."""

    def test_build_delivery_produces_a_complete_outward_payload(self):
        draft = draft_with_lines()
        payload = PayloadDirector().build_delivery(draft)

        self.assertEqual(payload['supply_type'], 'Outward')
        self.assertEqual(payload['gstin_of_consignor'], '27AAACY1234A1Z5')
        self.assertEqual(payload['name_of_consignee'],
                         'Metro Constructions Pvt Ltd')
        self.assertEqual(payload['vehicle_number'], 'MH-04-AB-1234')
        self.assertEqual(payload['from_warehouse'], 'MUM-01')

    def test_build_pickup_swaps_the_two_parties(self):
        draft = draft_with_lines(doc_type='pickup', reference_no='PC-000055')
        payload = PayloadDirector().build_pickup(draft)

        self.assertEqual(payload['supply_type'], 'Inward')
        self.assertEqual(payload['name_of_consignor'],
                         'Metro Constructions Pvt Ltd')
        self.assertEqual(payload['gstin_of_consignee'], '27AAACY1234A1Z5')

    def test_delivery_and_pickup_are_exact_mirrors(self):
        draft = draft_with_lines()
        director = PayloadDirector()
        delivery = director.build_delivery(draft)
        pickup = director.build_pickup(draft)

        self.assertEqual(delivery['gstin_of_consignor'],
                         pickup['gstin_of_consignee'])
        self.assertEqual(delivery['gstin_of_consignee'],
                         pickup['gstin_of_consignor'])

    def test_build_minimal_omits_transport_and_comments(self):
        draft = draft_with_lines()
        payload = PayloadDirector().build_minimal(draft)

        self.assertNotIn('vehicle_number', payload)
        self.assertNotIn('comments', payload)
        self.assertIn('item_list', payload)  # still a valid payload

    def test_build_minimal_succeeds_where_the_full_recipe_would_fail(self):
        # No vehicle assigned yet: the full recipe is refused, the minimal
        # one still files.
        draft = draft_with_lines(vehicle_number='')

        with self.assertRaises(BuilderValidationError):
            PayloadDirector().build_delivery(draft)

        payload = PayloadDirector().build_minimal(draft)
        self.assertEqual(payload['supply_type'], 'Outward')

    def test_build_for_draft_picks_the_recipe_from_the_doc_type(self):
        delivery = draft_with_lines()
        pickup = draft_with_lines(doc_type='pickup', reference_no='PC-000056')
        director = PayloadDirector()

        self.assertEqual(director.build_for_draft(delivery)['supply_type'],
                         'Outward')
        self.assertEqual(director.build_for_draft(pickup)['supply_type'],
                         'Inward')

    def test_one_director_builds_many_drafts_without_cross_contamination(self):
        director = PayloadDirector()
        first = draft_with_lines()
        second = draft_with_lines(reference_no='DC-000103')
        add_line(second, item_code='SCAF-02')

        first_payload = director.build_delivery(first)
        second_payload = director.build_delivery(second)

        self.assertEqual(len(first_payload['item_list']), 1)
        self.assertEqual(len(second_payload['item_list']), 2)

    def test_a_director_accepts_an_injected_builder(self):
        builder = PayloadBuilder()
        director = PayloadDirector(builder=builder)
        self.assertIs(director.builder, builder)

    def test_the_same_draft_yields_different_representations(self):
        # One source object, three products - the Builder's headline claim.
        draft = draft_with_lines()
        director = PayloadDirector()

        full = director.build_delivery(draft)
        minimal = director.build_minimal(draft)
        eway = DeliveryEwayBillBuilder(draft).build()

        self.assertIn('vehicle_number', full)
        self.assertNotIn('vehicle_number', minimal)
        self.assertIn('U_ReferenceNo', eway)
        self.assertEqual(full['total_value'], minimal['total_value'])


class AbstractEwayBillBuilderTests(TestCase):
    """The second flavour: fixed step order, subclass-varying steps."""

    def test_the_base_builder_cannot_be_instantiated(self):
        draft = draft_with_lines()
        with self.assertRaises(TypeError):
            BaseEwayBillBuilder(draft)

    def test_a_subclass_missing_a_party_step_cannot_be_instantiated(self):
        class HalfFinishedBuilder(BaseEwayBillBuilder):
            def _get_supply_type(self):
                return {'supply_type': 'Outward', 'transaction_type': 2}

            # _get_consignor_details / _get_consignee_details are missing.

        with self.assertRaises(TypeError):
            HalfFinishedBuilder(draft_with_lines())

    def test_delivery_builder_sends_from_company_to_customer(self):
        payload = DeliveryEwayBillBuilder(draft_with_lines()).build()

        self.assertEqual(payload['supply_type'], 'Outward')
        self.assertEqual(payload['transaction_type'], 2)
        self.assertEqual(payload['name_of_consignor'],
                         'Y Equipment Services PVT. LTD.')
        self.assertEqual(payload['name_of_consignee'],
                         'Metro Constructions Pvt Ltd')

    def test_pickup_builder_sends_from_customer_to_company(self):
        draft = draft_with_lines(doc_type='pickup', reference_no='PC-000057')
        payload = PickupEwayBillBuilder(draft).build()

        self.assertEqual(payload['supply_type'], 'Inward')
        self.assertEqual(payload['transaction_type'], 3)
        self.assertEqual(payload['name_of_consignor'],
                         'Metro Constructions Pvt Ltd')
        self.assertEqual(payload['name_of_consignee'],
                         'Y Equipment Services PVT. LTD.')

    def test_only_the_three_party_steps_differ_between_subclasses(self):
        draft = draft_with_lines()
        delivery = DeliveryEwayBillBuilder(draft).build()
        pickup = PickupEwayBillBuilder(draft).build()

        # Shared steps produce identical output.
        for shared_key in ('transporter_id', 'transport_mode',
                           'vehicle_number', 'distance', 'item_list',
                           'total_value', 'cgst_value', 'sgst_value',
                           'igst_value', 'U_ReferenceNo'):
            self.assertEqual(delivery[shared_key], pickup[shared_key],
                             f'{shared_key} should not vary by direction')

    def test_params_override_the_draft_transport_details(self):
        draft = draft_with_lines()
        payload = DeliveryEwayBillBuilder(
            draft, {'vehicle_no': 'MH-01-QQ-7777', 'distance': 250}).build()

        self.assertEqual(payload['vehicle_number'], 'MH-01-QQ-7777')
        self.assertEqual(payload['distance'], 250)

    def test_amounts_use_the_same_gst_rules_as_the_fluent_builder(self):
        draft = draft_with_lines()
        eway = DeliveryEwayBillBuilder(draft).build()
        fluent = PayloadDirector().build_minimal(draft)

        self.assertEqual(eway['total_value'], fluent['total_value'])
        self.assertEqual(eway['cgst_value'], fluent['cgst_value'])
        self.assertEqual(eway['igst_value'], fluent['igst_value'])

    def test_rebuilding_the_same_builder_gives_a_stable_result(self):
        builder = DeliveryEwayBillBuilder(draft_with_lines())
        self.assertEqual(builder.build(), builder.build())

    def test_the_registry_selects_the_builder_by_doc_type(self):
        self.assertIsInstance(get_eway_bill_builder(draft_with_lines()),
                              DeliveryEwayBillBuilder)
        self.assertIsInstance(
            get_eway_bill_builder(
                draft_with_lines(doc_type='pickup', reference_no='PC-000058')),
            PickupEwayBillBuilder)

    def test_every_registered_builder_extends_the_base(self):
        for doc_type, builder_class in EWAY_BILL_BUILDERS.items():
            self.assertTrue(issubclass(builder_class, BaseEwayBillBuilder),
                            doc_type)


class SavePayloadTests(TestCase):
    def test_saving_records_the_computed_tax_split(self):
        draft = draft_with_lines()
        payload = PayloadDirector().build_minimal(draft)
        record = save_payload(draft, payload, 'PayloadBuilder', 'minimal')

        self.assertEqual(record.line_count, 1)
        self.assertEqual(record.taxable_value, Decimal('12000.00'))
        self.assertEqual(record.cgst_value, Decimal('1080.00'))
        self.assertEqual(record.total_value, Decimal('14160.00'))
        self.assertEqual(record.recipe, 'minimal')

    def test_saving_an_eway_payload_falls_back_to_total_value(self):
        # The abstract builder emits no grand_total key.
        draft = draft_with_lines()
        payload = DeliveryEwayBillBuilder(draft).build()
        record = save_payload(draft, payload, 'DeliveryEwayBillBuilder')

        self.assertEqual(record.total_value, Decimal('12000.00'))


class ModelTests(TestCase):
    def test_draft_str_is_readable(self):
        self.assertEqual(str(make_draft()), 'DC-000101 (delivery)')

    def test_line_str_is_readable(self):
        self.assertEqual(str(add_line(make_draft())),
                         'SCAF-01 x 100.000 NOS')

    def test_line_amount_multiplies_quantity_by_rate(self):
        line = add_line(make_draft(), quantity=Decimal('7.000'),
                        rate=Decimal('12.50'))
        self.assertEqual(line.amount, Decimal('87.500'))

    def test_built_payload_str_is_readable(self):
        draft = draft_with_lines()
        record = save_payload(draft, PayloadDirector().build_minimal(draft),
                              'PayloadBuilder')
        self.assertIn('PayloadBuilder', str(record))
        self.assertIn('1 lines', str(record))

    def test_reference_no_is_unique(self):
        make_draft()
        with self.assertRaises(IntegrityError):
            make_draft()

    def test_lines_are_ordered_by_line_num(self):
        draft = make_draft()
        add_line(draft, line_num=2, item_code='C')
        add_line(draft, line_num=0, item_code='A')
        add_line(draft, line_num=1, item_code='B')
        self.assertEqual([line.item_code for line in draft.lines.all()],
                         ['A', 'B', 'C'])

    def test_deleting_a_draft_cascades(self):
        draft = draft_with_lines()
        save_payload(draft, PayloadDirector().build_minimal(draft), 'X')
        draft.delete()

        self.assertEqual(DraftLine.objects.count(), 0)
        self.assertEqual(BuiltPayload.objects.count(), 0)


class BuilderHttpEndpointTests(APITestCase):
    """End to end through the real API surface."""

    def test_create_a_draft_with_lines_in_one_call(self):
        response = self.client.post(reverse('sap_builder:draft-list'), {
            'doc_type': 'delivery',
            'reference_no': 'DC-000300',
            'card_name': 'Metro Constructions',
            'from_gstin': '27AAACY1234A1Z5',
            'from_state_code': MAHARASHTRA,
            'to_gstin': '27AABCM5678B1Z3',
            'to_state_code': MAHARASHTRA,
            'posting_date': '2026-08-08',
            'vehicle_number': 'MH-04-AB-1234',
            'lines': [
                {'item_code': 'SCAF-01', 'quantity': '100', 'rate': '120.00'},
                {'item_code': 'SCAF-02', 'quantity': '50', 'rate': '80.00'},
            ],
        }, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.data['lines']), 2)
        self.assertTrue(response.data['is_intra_state'])

    def test_build_endpoint_returns_a_complete_payload(self):
        draft = draft_with_lines()
        response = self.client.post(
            reverse('sap_builder:draft-build', args=[draft.pk]),
            {'recipe': 'delivery'}, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['payload']['supply_type'], 'Outward')
        self.assertEqual(response.data['payload']['total_value'], 12000.0)
        self.assertIn('built_payload_id', response.data)

    def test_build_endpoint_reports_every_problem_at_once(self):
        draft = make_draft()  # no lines at all
        response = self.client.post(
            reverse('sap_builder:draft-build', args=[draft.pk]),
            {'recipe': 'minimal'}, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIsInstance(response.data['problems'], list)
        self.assertTrue(any('item_list' in problem
                            for problem in response.data['problems']))

    def test_build_endpoint_honours_the_minimal_recipe(self):
        draft = draft_with_lines(vehicle_number='')
        response = self.client.post(
            reverse('sap_builder:draft-build', args=[draft.pk]),
            {'recipe': 'minimal'}, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertNotIn('vehicle_number', response.data['payload'])

    def test_build_endpoint_accepts_transport_overrides(self):
        draft = draft_with_lines()
        response = self.client.post(
            reverse('sap_builder:draft-build', args=[draft.pk]),
            {'recipe': 'delivery', 'vehicle_number': 'MH-77-PP-4321',
             'distance_km': 310}, format='json')

        self.assertEqual(response.data['payload']['vehicle_number'],
                         'MH-77-PP-4321')
        self.assertEqual(response.data['payload']['distance'], 310)

    def test_build_endpoint_can_skip_saving(self):
        draft = draft_with_lines()
        response = self.client.post(
            reverse('sap_builder:draft-build', args=[draft.pk]),
            {'recipe': 'delivery', 'save': False}, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertNotIn('built_payload_id', response.data)
        self.assertEqual(BuiltPayload.objects.count(), 0)

    def test_auto_recipe_follows_the_draft_direction(self):
        pickup = draft_with_lines(doc_type='pickup', reference_no='PC-000059')
        response = self.client.post(
            reverse('sap_builder:draft-build', args=[pickup.pk]),
            {}, format='json')
        self.assertEqual(response.data['payload']['supply_type'], 'Inward')

    def test_eway_bill_endpoint_uses_the_abstract_builder(self):
        draft = draft_with_lines()
        response = self.client.post(
            reverse('sap_builder:draft-eway-bill', args=[draft.pk]),
            {}, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['builder'], 'DeliveryEwayBillBuilder')
        self.assertEqual(response.data['payload']['transaction_type'], 2)

    def test_eway_bill_endpoint_picks_the_pickup_subclass(self):
        draft = draft_with_lines(doc_type='pickup', reference_no='PC-000060')
        response = self.client.post(
            reverse('sap_builder:draft-eway-bill', args=[draft.pk]),
            {}, format='json')
        self.assertEqual(response.data['builder'], 'PickupEwayBillBuilder')

    def test_payload_history_records_every_build(self):
        draft = draft_with_lines()
        build_url = reverse('sap_builder:draft-build', args=[draft.pk])
        self.client.post(build_url, {'recipe': 'delivery'}, format='json')
        self.client.post(build_url, {'recipe': 'minimal'}, format='json')
        self.client.post(reverse('sap_builder:draft-eway-bill', args=[draft.pk]),
                         {}, format='json')

        response = self.client.get(
            reverse('sap_builder:draft-payloads', args=[draft.pk]))
        self.assertEqual(len(response.data), 3)
        self.assertEqual({row['recipe'] for row in response.data},
                         {'delivery', 'minimal', 'eway_bill'})

    def test_payload_detail_returns_the_body(self):
        draft = draft_with_lines()
        created = self.client.post(
            reverse('sap_builder:draft-build', args=[draft.pk]),
            {'recipe': 'delivery'}, format='json')

        response = self.client.get(
            reverse('sap_builder:payload-detail',
                    args=[created.data['built_payload_id']]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['payload']['supply_type'], 'Outward')

    def test_build_endpoint_returns_404_for_a_missing_draft(self):
        response = self.client.post(
            reverse('sap_builder:draft-build', args=[9999]), {}, format='json')
        self.assertEqual(response.status_code, 404)

    def test_catalogue_endpoint_lists_the_optional_steps(self):
        response = self.client.get(reverse('sap_builder:builder-catalogue'))

        self.assertIn('with_transport', response.data['fluent_builder']['steps'])
        self.assertIn('with_taxes', response.data['fluent_builder']['steps'])
        self.assertEqual(response.data['eway_bill_builders']['pickup'],
                         'PickupEwayBillBuilder')

    def test_adding_a_line_to_an_existing_draft(self):
        draft = make_draft()
        response = self.client.post(
            reverse('sap_builder:draft-lines', args=[draft.pk]),
            {'line_num': 0, 'item_code': 'SCAF-05', 'quantity': '25.000',
             'rate': '60.00', 'unit': 'NOS'}, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(draft.lines.count(), 1)

    def test_list_endpoint_filters_by_doc_type(self):
        draft_with_lines()
        draft_with_lines(doc_type='pickup', reference_no='PC-000061')

        response = self.client.get(reverse('sap_builder:draft-list'),
                                   {'doc_type': 'pickup'})
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['doc_type'], 'pickup')
