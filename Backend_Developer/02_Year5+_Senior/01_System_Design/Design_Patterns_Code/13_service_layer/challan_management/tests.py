"""
Tests for the Service Layer pattern (ChallanService over ChallanRepository).

Behavioural guarantee under test: ALL challan business logic lives in
ChallanService. The models stay dumb (structure only), the repositories stay
dumb (data access only), and the views stay thin (HTTP only). Every rule is
asserted twice on purpose:

  * once directly against the service   -> proves the rule lives there
  * once through the HTTP endpoint      -> proves the view only delegates

If a rule ever gets duplicated into a view or a serializer, the direct
service test keeps passing while the intent of the architecture quietly
rots — so the paired tests are the point, not redundancy.

The InjectedRepositoryTests class covers the other half of the pattern's
value: because the service takes its repositories via __init__, it can be
driven with zero database.
"""
from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from .models import Challan, ChallanItem, ChallanStageLog
from .repositories import (
    ChallanItemRepository,
    ChallanRepository,
    ChallanStageLogRepository,
)
from .services import ChallanService, ChallanServiceError


def valid_payload(**overrides):
    """A minimal payload that passes every service validation."""
    data = {
        'challan_type': 'Delivery',
        'challan_movement_type': 'delivery',
        'order_id': 4021,
        'pickup_location': 'Bhiwandi Warehouse',
        'delivery_location': 'Worli Site, Mumbai',
    }
    data.update(overrides)
    return data


def make_challan(service=None, **overrides):
    return (service or ChallanService()).create_challan(valid_payload(**overrides))


def authorized_challan(service=None, **overrides):
    """Create and approve a challan so it is eligible to advance stages."""
    service = service or ChallanService()
    challan = service.create_challan(valid_payload(**overrides))
    return service.authorize_challan(challan.pk, 'approve')


def advance_to(challan_pk, target_stage, service=None):
    """Walk a challan forward until it reaches target_stage."""
    service = service or ChallanService()
    challan = service.repository.find(challan_pk)
    while challan.current_stage != target_stage:
        challan = service.advance_stage(challan_pk)
    return challan


# ----------------------------------------------------------------------
# Test doubles for the dependency-injection tests.
# ----------------------------------------------------------------------

class FakeChallan:
    """A stand-in for a Challan row — no database involved."""

    def __init__(self, pk=1, challan_no='DC-000001',
                 is_authorized='0', current_stage='PLANNING_DONE'):
        self.pk = pk
        self.challan_no = challan_no
        self.is_authorized = is_authorized
        self.current_stage = current_stage


class FakeChallanRepository:
    """Records every call so tests can assert on the service's data access."""

    def __init__(self, stored=None):
        self.stored = stored
        self.created = []
        self.updates = []

    def find(self, pk):
        return self.stored

    def create(self, data):
        self.created.append(data)
        return FakeChallan(
            challan_no=data['challan_no'],
            is_authorized=data['is_authorized'],
            current_stage=data['current_stage'],
        )

    def update(self, pk, data):
        self.updates.append((pk, data))
        for field, value in data.items():
            setattr(self.stored, field, value)
        return self.stored


class FakeStageLogRepository:
    def __init__(self):
        self.rows = []

    def create(self, data):
        self.rows.append(data)
        return data

    def get_by_challan(self, challan_id):
        return [r for r in self.rows if r.get('challan_id') == challan_id]


class FakeItemRepository:
    def __init__(self):
        self.bulk = []

    def bulk_create(self, items_list):
        self.bulk.extend(items_list)
        return items_list

    def get_by_challan(self, challan_id):
        return [i for i in self.bulk if i.get('challan_id') == challan_id]


# ----------------------------------------------------------------------


class CreateChallanServiceTests(TestCase):
    """The multi-step create workflow — the heart of the service."""

    def test_create_returns_a_persisted_challan(self):
        challan = make_challan()
        self.assertIsNotNone(challan.pk)
        self.assertEqual(Challan.objects.count(), 1)

    def test_service_generates_the_challan_number_not_the_caller(self):
        challan = make_challan()
        self.assertEqual(challan.challan_no, 'DC-000001')

    def test_delivery_and_pickup_numbers_run_on_separate_sequences(self):
        first_delivery = make_challan()
        first_pickup = make_challan(challan_type='Pickup',
                                    challan_movement_type='pickup')
        second_delivery = make_challan()

        self.assertEqual(first_delivery.challan_no, 'DC-000001')
        self.assertEqual(first_pickup.challan_no, 'PC-000001')
        self.assertEqual(second_delivery.challan_no, 'DC-000002')

    def test_a_client_cannot_smuggle_in_its_own_starting_state(self):
        # Even though the caller asks for an authorized, half-finished
        # challan, the service overwrites both fields.
        challan = ChallanService().create_challan(valid_payload(
            challan_no='HACK-0001',
            is_authorized='1',
            current_stage='SITE_EXIT',
        ))
        self.assertEqual(challan.challan_no, 'DC-000001')
        self.assertEqual(challan.is_authorized, '0')
        self.assertEqual(challan.current_stage, 'PLANNING_DONE')

    def test_create_writes_the_opening_stage_log(self):
        challan = make_challan()
        log = ChallanStageLog.objects.get(challan=challan)
        self.assertEqual(log.from_stage, 'NEW')
        self.assertEqual(log.to_stage, 'PLANNING_DONE')
        self.assertEqual(log.remarks, 'Challan created')

    def test_created_by_is_recorded_on_the_opening_log(self):
        challan = make_challan(created_by='ashish')
        log = ChallanStageLog.objects.get(challan=challan)
        self.assertEqual(log.changed_by, 'ashish')

    def test_created_by_defaults_to_system(self):
        challan = make_challan()
        self.assertEqual(
            ChallanStageLog.objects.get(challan=challan).changed_by, 'system')

    def test_freight_amount_is_coerced_to_decimal(self):
        challan = make_challan(freight_amount='4500.50')
        challan.refresh_from_db()
        self.assertEqual(challan.freight_amount, Decimal('4500.50'))

    def test_freight_amount_defaults_to_zero(self):
        challan = make_challan()
        challan.refresh_from_db()
        self.assertEqual(challan.freight_amount, Decimal('0.00'))

    def test_missing_required_fields_are_reported_together(self):
        with self.assertRaises(ChallanServiceError) as ctx:
            ChallanService().create_challan({'challan_type': 'Delivery'})

        message = str(ctx.exception)
        self.assertIn('challan_movement_type', message)
        self.assertIn('order_id', message)
        self.assertIn('pickup_location', message)
        self.assertIn('delivery_location', message)

    def test_validation_failure_creates_nothing(self):
        with self.assertRaises(ChallanServiceError):
            ChallanService().create_challan({})
        self.assertEqual(Challan.objects.count(), 0)
        self.assertEqual(ChallanStageLog.objects.count(), 0)

    def test_invalid_challan_type_is_rejected(self):
        with self.assertRaises(ChallanServiceError) as ctx:
            ChallanService().create_challan(valid_payload(challan_type='Transfer'))
        self.assertIn('Invalid challan_type', str(ctx.exception))

    def test_invalid_movement_type_is_rejected(self):
        with self.assertRaises(ChallanServiceError) as ctx:
            ChallanService().create_challan(
                valid_payload(challan_movement_type='teleport'))
        self.assertIn('Invalid movement type', str(ctx.exception))

    def test_all_four_documented_movement_types_are_accepted(self):
        for movement in ('delivery', 'pickup', 'inter_branch', 'sales'):
            challan = make_challan(challan_movement_type=movement)
            self.assertEqual(challan.challan_movement_type, movement)


class AuthorizeChallanServiceTests(TestCase):
    def test_approve_marks_the_challan_authorized(self):
        challan = make_challan()
        approved = ChallanService().authorize_challan(challan.pk, 'approve')
        self.assertEqual(approved.is_authorized, '1')

    def test_reject_marks_the_challan_rejected(self):
        challan = make_challan()
        rejected = ChallanService().authorize_challan(challan.pk, 'reject')
        self.assertEqual(rejected.is_authorized, '-1')

    def test_authorization_is_logged_without_moving_the_stage(self):
        challan = make_challan()
        ChallanService().authorize_challan(challan.pk, 'approve', 'looks fine')

        log = ChallanStageLog.objects.filter(challan=challan).last()
        self.assertEqual(log.from_stage, log.to_stage)
        self.assertEqual(log.from_stage, 'PLANNING_DONE')
        self.assertIn('approve', log.remarks)
        self.assertIn('looks fine', log.remarks)

    def test_an_already_authorized_challan_cannot_be_authorized_again(self):
        challan = make_challan()
        service = ChallanService()
        service.authorize_challan(challan.pk, 'approve')

        with self.assertRaises(ChallanServiceError) as ctx:
            service.authorize_challan(challan.pk, 'approve')
        self.assertIn('already', str(ctx.exception))

    def test_a_rejected_challan_cannot_be_revived_by_approving_it(self):
        challan = make_challan()
        service = ChallanService()
        service.authorize_challan(challan.pk, 'reject')

        with self.assertRaises(ChallanServiceError):
            service.authorize_challan(challan.pk, 'approve')

    def test_an_unknown_action_is_rejected(self):
        challan = make_challan()
        with self.assertRaises(ChallanServiceError) as ctx:
            ChallanService().authorize_challan(challan.pk, 'maybe')
        self.assertIn('Invalid action', str(ctx.exception))

    def test_authorizing_a_missing_challan_raises(self):
        with self.assertRaises(ChallanServiceError) as ctx:
            ChallanService().authorize_challan(9999, 'approve')
        self.assertIn('not found', str(ctx.exception))


class AdvanceStageServiceTests(TestCase):
    def test_an_unauthorized_challan_cannot_advance(self):
        challan = make_challan()
        with self.assertRaises(ChallanServiceError) as ctx:
            ChallanService().advance_stage(challan.pk)

        self.assertIn('not authorized', str(ctx.exception))
        challan.refresh_from_db()
        self.assertEqual(challan.current_stage, 'PLANNING_DONE')

    def test_a_rejected_challan_cannot_advance(self):
        challan = make_challan()
        service = ChallanService()
        service.authorize_challan(challan.pk, 'reject')
        with self.assertRaises(ChallanServiceError):
            service.advance_stage(challan.pk)

    def test_advance_follows_the_declared_stage_flow_exactly(self):
        challan = authorized_challan()
        service = ChallanService()

        expected = [
            'GENERATED_CHALLAN', 'VEHICLE_EXIT', 'ARRIVAL_AT_SITE',
            'INSTALLATION_DONE', 'SITE_EXIT', 'ARRIVAL_AT_BRANCH',
        ]
        observed = [service.advance_stage(challan.pk).current_stage
                    for _ in expected]
        self.assertEqual(observed, expected)

    def test_the_terminal_stage_cannot_advance_further(self):
        challan = authorized_challan()
        advance_to(challan.pk, 'ARRIVAL_AT_BRANCH')

        with self.assertRaises(ChallanServiceError) as ctx:
            ChallanService().advance_stage(challan.pk)
        self.assertIn('terminal stage', str(ctx.exception))

    def test_every_advance_is_logged_with_who_and_why(self):
        challan = authorized_challan()
        ChallanService().advance_stage(
            challan.pk, changed_by='dispatcher', remarks='vehicle loaded')

        log = ChallanStageLog.objects.filter(challan=challan).last()
        self.assertEqual(log.from_stage, 'PLANNING_DONE')
        self.assertEqual(log.to_stage, 'GENERATED_CHALLAN')
        self.assertEqual(log.changed_by, 'dispatcher')
        self.assertEqual(log.remarks, 'vehicle loaded')

    def test_changed_by_falls_back_to_system(self):
        challan = authorized_challan()
        ChallanService().advance_stage(challan.pk)
        self.assertEqual(
            ChallanStageLog.objects.filter(challan=challan).last().changed_by,
            'system')

    def test_advancing_a_missing_challan_raises(self):
        with self.assertRaises(ChallanServiceError):
            ChallanService().advance_stage(9999)

    def test_stage_flow_table_has_no_dead_ends_before_the_terminal_stage(self):
        # Every value in the flow must itself be a key, except the terminal.
        flow = ChallanService.STAGE_FLOW
        for source, destination in flow.items():
            if destination != 'ARRIVAL_AT_BRANCH':
                self.assertIn(destination, flow,
                              f'{source} -> {destination} is a dead end')


class CloseChallanServiceTests(TestCase):
    def test_a_challan_at_the_terminal_stage_can_be_closed(self):
        challan = authorized_challan()
        advance_to(challan.pk, 'ARRIVAL_AT_BRANCH')

        closed = ChallanService().close_challan(challan.pk)
        self.assertEqual(closed.current_stage, 'CLOSED')

    def test_closing_mid_lifecycle_is_refused(self):
        challan = authorized_challan()
        ChallanService().advance_stage(challan.pk)  # GENERATED_CHALLAN

        with self.assertRaises(ChallanServiceError) as ctx:
            ChallanService().close_challan(challan.pk)
        self.assertIn('ARRIVAL_AT_BRANCH', str(ctx.exception))

    def test_an_unauthorized_challan_cannot_be_closed(self):
        challan = make_challan()
        with self.assertRaises(ChallanServiceError) as ctx:
            ChallanService().close_challan(challan.pk)
        self.assertIn('not authorized', str(ctx.exception))

    def test_closing_is_logged(self):
        challan = authorized_challan()
        advance_to(challan.pk, 'ARRIVAL_AT_BRANCH')
        ChallanService().close_challan(challan.pk)

        log = ChallanStageLog.objects.filter(challan=challan).last()
        self.assertEqual(log.from_stage, 'ARRIVAL_AT_BRANCH')
        self.assertEqual(log.to_stage, 'CLOSED')

    def test_the_full_lifecycle_leaves_a_complete_audit_trail(self):
        challan = authorized_challan()
        advance_to(challan.pk, 'ARRIVAL_AT_BRANCH')
        ChallanService().close_challan(challan.pk)

        logs = ChallanStageLog.objects.filter(challan=challan).order_by('changed_at')
        # 1 create + 1 authorize + 6 advances + 1 close
        self.assertEqual(logs.count(), 9)
        self.assertEqual(logs.first().from_stage, 'NEW')
        self.assertEqual(logs.last().to_stage, 'CLOSED')


class AddItemsServiceTests(TestCase):
    def test_items_are_attached_to_the_challan(self):
        challan = make_challan()
        ChallanService().add_items(challan.pk, [
            {'item_code': 'SCAF-01', 'item_name': 'Standard Frame', 'quantity': 250},
            {'item_code': 'SCAF-02', 'item_name': 'Walk Board', 'quantity': 400},
        ])

        self.assertEqual(ChallanItem.objects.filter(challan=challan).count(), 2)

    def test_quantity_is_coerced_from_string_input(self):
        challan = make_challan()
        ChallanService().add_items(challan.pk, [
            {'item_code': 'SCAF-01', 'item_name': 'Standard Frame', 'quantity': '250'},
        ])
        self.assertEqual(ChallanItem.objects.get(challan=challan).quantity, 250)

    def test_discrepancy_quantities_default_to_zero(self):
        challan = make_challan()
        ChallanService().add_items(challan.pk, [
            {'item_code': 'SCAF-01', 'item_name': 'Standard Frame', 'quantity': 10},
        ])
        item = ChallanItem.objects.get(challan=challan)
        self.assertEqual(item.ok_quantity, 0)
        self.assertEqual(item.damaged_quantity, 0)
        self.assertEqual(item.missing_quantity, 0)

    def test_discrepancy_quantities_are_stored_when_supplied(self):
        challan = make_challan()
        ChallanService().add_items(challan.pk, [
            {'item_code': 'SCAF-01', 'item_name': 'Standard Frame',
             'quantity': 100, 'ok_quantity': 92,
             'damaged_quantity': 5, 'missing_quantity': 3},
        ])
        item = ChallanItem.objects.get(challan=challan)
        self.assertEqual((item.ok_quantity, item.damaged_quantity,
                          item.missing_quantity), (92, 5, 3))

    def test_a_missing_item_code_is_rejected_by_index(self):
        challan = make_challan()
        with self.assertRaises(ChallanServiceError) as ctx:
            ChallanService().add_items(challan.pk, [
                {'item_code': 'SCAF-01', 'item_name': 'Frame', 'quantity': 5},
                {'item_name': 'Board', 'quantity': 5},
            ])
        self.assertIn('index 1', str(ctx.exception))

    def test_a_missing_item_name_is_rejected(self):
        challan = make_challan()
        with self.assertRaises(ChallanServiceError) as ctx:
            ChallanService().add_items(
                challan.pk, [{'item_code': 'SCAF-01', 'quantity': 5}])
        self.assertIn('item_name', str(ctx.exception))

    def test_a_non_positive_quantity_is_rejected(self):
        challan = make_challan()
        with self.assertRaises(ChallanServiceError):
            ChallanService().add_items(challan.pk, [
                {'item_code': 'SCAF-01', 'item_name': 'Frame', 'quantity': 0}])

    def test_validation_is_all_or_nothing_across_the_batch(self):
        # The second item is invalid, so the FIRST must not be written either.
        challan = make_challan()
        with self.assertRaises(ChallanServiceError):
            ChallanService().add_items(challan.pk, [
                {'item_code': 'SCAF-01', 'item_name': 'Frame', 'quantity': 5},
                {'item_code': 'SCAF-02', 'item_name': 'Board', 'quantity': -1},
            ])
        self.assertEqual(ChallanItem.objects.count(), 0)

    def test_an_empty_list_is_rejected(self):
        challan = make_challan()
        with self.assertRaises(ChallanServiceError):
            ChallanService().add_items(challan.pk, [])

    def test_adding_items_to_a_missing_challan_raises(self):
        with self.assertRaises(ChallanServiceError):
            ChallanService().add_items(9999, [
                {'item_code': 'X', 'item_name': 'Y', 'quantity': 1}])


class ChallanSummaryServiceTests(TestCase):
    def test_summary_bundles_challan_items_and_stage_logs(self):
        challan = authorized_challan()
        ChallanService().add_items(challan.pk, [
            {'item_code': 'SCAF-01', 'item_name': 'Frame', 'quantity': 10}])

        summary = ChallanService().get_challan_summary(challan.pk)

        self.assertEqual(summary['challan'].pk, challan.pk)
        self.assertEqual(len(summary['items']), 1)
        self.assertEqual(len(summary['stage_logs']), 2)  # create + authorize

    def test_summary_of_a_missing_challan_raises(self):
        with self.assertRaises(ChallanServiceError):
            ChallanService().get_challan_summary(9999)


class InjectedRepositoryTests(TestCase):
    """
    The payoff of constructor injection: the service runs against fakes.

    These tests touch no Challan rows at all — which is exactly the claim
    the Service Layer + Repository combination is supposed to buy you.
    """

    def test_service_defaults_to_the_real_repositories(self):
        service = ChallanService()
        self.assertIsInstance(service.repository, ChallanRepository)
        self.assertIsInstance(service.item_repository, ChallanItemRepository)
        self.assertIsInstance(service.stage_log_repository,
                              ChallanStageLogRepository)

    def test_authorize_runs_entirely_against_an_injected_fake(self):
        stored = FakeChallan()
        repo = FakeChallanRepository(stored=stored)
        logs = FakeStageLogRepository()
        service = ChallanService(repository=repo, stage_log_repository=logs)

        result = service.authorize_challan(1, 'approve', 'ok')

        self.assertEqual(result.is_authorized, '1')
        self.assertEqual(repo.updates, [(1, {'is_authorized': '1'})])
        self.assertEqual(len(logs.rows), 1)
        self.assertEqual(Challan.objects.count(), 0)  # nothing hit the DB

    def test_advance_stage_runs_entirely_against_an_injected_fake(self):
        stored = FakeChallan(is_authorized='1', current_stage='VEHICLE_EXIT')
        repo = FakeChallanRepository(stored=stored)
        logs = FakeStageLogRepository()
        service = ChallanService(repository=repo, stage_log_repository=logs)

        service.advance_stage(1, changed_by='qa', remarks='reached site')

        self.assertEqual(repo.updates,
                         [(1, {'current_stage': 'ARRIVAL_AT_SITE'})])
        self.assertEqual(logs.rows[0]['from_stage'], 'VEHICLE_EXIT')
        self.assertEqual(logs.rows[0]['to_stage'], 'ARRIVAL_AT_SITE')
        self.assertEqual(logs.rows[0]['changed_by'], 'qa')

    def test_business_rules_still_fire_against_a_fake(self):
        # The rule lives in the service, so it does not care what the
        # repository is backed by.
        repo = FakeChallanRepository(stored=FakeChallan(is_authorized='0'))
        service = ChallanService(repository=repo,
                                 stage_log_repository=FakeStageLogRepository())
        with self.assertRaises(ChallanServiceError):
            service.advance_stage(1)
        self.assertEqual(repo.updates, [])

    def test_add_items_uses_the_injected_item_repository(self):
        items = FakeItemRepository()
        service = ChallanService(
            repository=FakeChallanRepository(stored=FakeChallan()),
            item_repository=items,
        )
        service.add_items(1, [
            {'item_code': 'SCAF-01', 'item_name': 'Frame', 'quantity': 7}])

        self.assertEqual(len(items.bulk), 1)
        self.assertEqual(items.bulk[0]['quantity'], 7)
        self.assertEqual(ChallanItem.objects.count(), 0)

    def test_challan_numbering_still_reaches_the_orm_directly(self):
        """
        Documents a real leak in the seam, so nobody is surprised by it.

        _generate_challan_number() queries Challan.objects directly instead
        of going through self.repository. So even with a fake repository the
        numbering is driven by real rows — meaning create_challan() is the
        one method you cannot unit-test without a database.
        """
        Challan.objects.create(
            challan_no='DC-000001', challan_type='Delivery',
            challan_movement_type='delivery', order_id=1,
            pickup_location='A', delivery_location='B')

        repo = FakeChallanRepository(stored=FakeChallan())
        service = ChallanService(repository=repo,
                                 stage_log_repository=FakeStageLogRepository())
        service.create_challan(valid_payload())

        # Numbered from the ORM row, not from the (empty) fake repository.
        self.assertEqual(repo.created[0]['challan_no'], 'DC-000002')


class RepositoryTests(TestCase):
    """The data-access layer the service leans on."""

    def test_get_pending_authorization_returns_only_under_review(self):
        service = ChallanService()
        pending = make_challan(service)
        approved = make_challan(service)
        service.authorize_challan(approved.pk, 'approve')

        results = ChallanRepository().get_pending_authorization()
        self.assertEqual([c.pk for c in results], [pending.pk])

    def test_get_by_stage_filters_on_the_current_stage(self):
        moved = authorized_challan()
        ChallanService().advance_stage(moved.pk)
        make_challan()  # stays at PLANNING_DONE

        results = ChallanRepository().get_by_stage('GENERATED_CHALLAN')
        self.assertEqual([c.pk for c in results], [moved.pk])

    def test_get_by_order_filters_on_the_order_id(self):
        make_challan(order_id=111)
        make_challan(order_id=222)
        self.assertEqual(ChallanRepository().get_by_order(222).count(), 1)

    def test_find_returns_none_instead_of_raising(self):
        self.assertIsNone(ChallanRepository().find(9999))

    def test_update_returns_none_for_a_missing_row(self):
        self.assertIsNone(ChallanRepository().update(9999, {'order_id': 1}))

    def test_delete_reports_whether_anything_was_removed(self):
        challan = make_challan()
        self.assertTrue(ChallanRepository().delete(challan.pk))
        self.assertFalse(ChallanRepository().delete(challan.pk))

    def test_count_reflects_created_rows(self):
        make_challan()
        make_challan()
        self.assertEqual(ChallanRepository().count(), 2)


class ModelTests(TestCase):
    def test_challan_str_shows_number_type_and_stage(self):
        challan = make_challan()
        self.assertEqual(str(challan), 'DC-000001 (Delivery) - PLANNING_DONE')

    def test_challan_item_str_shows_code_name_and_quantity(self):
        challan = make_challan()
        ChallanService().add_items(challan.pk, [
            {'item_code': 'SCAF-01', 'item_name': 'Frame', 'quantity': 12}])
        item = ChallanItem.objects.get(challan=challan)
        self.assertEqual(str(item), 'SCAF-01 - Frame (qty: 12)')

    def test_stage_log_str_shows_the_transition(self):
        challan = make_challan()
        log = ChallanStageLog.objects.get(challan=challan)
        self.assertEqual(str(log), 'DC-000001: NEW -> PLANNING_DONE')

    def test_challan_numbers_are_unique(self):
        make_challan()
        with self.assertRaises(IntegrityError):
            Challan.objects.create(
                challan_no='DC-000001', challan_type='Delivery',
                challan_movement_type='delivery', order_id=9,
                pickup_location='A', delivery_location='B')

    def test_count_based_numbering_collides_after_a_delete(self):
        """
        Known limitation, documented rather than hidden.

        _generate_challan_number() uses COUNT(*) + 1, so deleting an earlier
        challan makes the next create collide with an existing number. The
        production fix is a dedicated sequence table or a DB sequence; the
        demo keeps the naive version because it reads clearly.
        """
        service = ChallanService()
        first = make_challan(service)
        make_challan(service)          # DC-000002
        first.delete()                 # count is back to 1

        with self.assertRaises(IntegrityError):
            service.create_challan(valid_payload())  # tries DC-000002 again

    def test_deleting_a_challan_cascades_to_items_and_logs(self):
        challan = make_challan()
        ChallanService().add_items(challan.pk, [
            {'item_code': 'SCAF-01', 'item_name': 'Frame', 'quantity': 1}])

        challan.delete()
        self.assertEqual(ChallanItem.objects.count(), 0)
        self.assertEqual(ChallanStageLog.objects.count(), 0)

    def test_stage_logs_are_ordered_oldest_first(self):
        challan = authorized_challan()
        ChallanService().advance_stage(challan.pk)
        stages = [log.to_stage for log in ChallanStageLog.objects.all()]
        self.assertEqual(
            stages, ['PLANNING_DONE', 'PLANNING_DONE', 'GENERATED_CHALLAN'])


class ChallanHttpEndpointTests(APITestCase):
    """
    The view layer must add NOTHING. Each test below has a sibling above
    that asserts the same rule directly against the service.
    """

    def test_create_endpoint_delegates_number_generation_to_the_service(self):
        response = self.client.post(reverse('challan_management:challan-list'),
                                    valid_payload(), format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['challan_no'], 'DC-000001')
        self.assertEqual(response.data['current_stage'], 'PLANNING_DONE')
        self.assertEqual(response.data['is_authorized'], '0')

    def test_create_endpoint_surfaces_a_service_error_as_400(self):
        response = self.client.post(
            reverse('challan_management:challan-list'),
            valid_payload(challan_movement_type='teleport'), format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('Invalid movement type', response.data['error'])
        self.assertEqual(Challan.objects.count(), 0)

    def test_create_endpoint_rejects_a_malformed_body_at_the_serializer(self):
        response = self.client.post(reverse('challan_management:challan-list'),
                                    {'challan_type': 'Delivery'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_detail_endpoint_returns_challan_items_and_logs(self):
        challan = authorized_challan()
        ChallanService().add_items(challan.pk, [
            {'item_code': 'SCAF-01', 'item_name': 'Frame', 'quantity': 3}])

        response = self.client.get(
            reverse('challan_management:challan-detail', args=[challan.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['challan']['challan_no'], 'DC-000001')
        self.assertEqual(len(response.data['items']), 1)
        self.assertEqual(len(response.data['stage_logs']), 2)

    def test_detail_endpoint_returns_404_for_a_missing_challan(self):
        response = self.client.get(
            reverse('challan_management:challan-detail', args=[9999]))
        self.assertEqual(response.status_code, 404)

    def test_authorize_endpoint_approves(self):
        challan = make_challan()
        response = self.client.post(
            reverse('challan_management:challan-authorize', args=[challan.pk]),
            {'action': 'approve', 'remarks': 'verified'}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['is_authorized'], '1')
        self.assertEqual(response.data['authorization_status'], 'Authorized')

    def test_authorize_endpoint_refuses_a_second_authorization(self):
        challan = make_challan()
        url = reverse('challan_management:challan-authorize', args=[challan.pk])
        self.client.post(url, {'action': 'approve'}, format='json')
        response = self.client.post(url, {'action': 'reject'}, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('already', response.data['error'])

    def test_advance_endpoint_refuses_an_unauthorized_challan(self):
        challan = make_challan()
        response = self.client.post(
            reverse('challan_management:challan-advance-stage', args=[challan.pk]),
            {}, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('not authorized', response.data['error'])

    def test_advance_endpoint_walks_the_lifecycle(self):
        challan = authorized_challan()
        url = reverse('challan_management:challan-advance-stage', args=[challan.pk])

        first = self.client.post(url, {'changed_by': 'ops'}, format='json')
        second = self.client.post(url, {}, format='json')

        self.assertEqual(first.data['current_stage'], 'GENERATED_CHALLAN')
        self.assertEqual(second.data['current_stage'], 'VEHICLE_EXIT')

    def test_items_endpoint_creates_and_lists_line_items(self):
        challan = make_challan()
        url = reverse('challan_management:challan-items', args=[challan.pk])

        created = self.client.post(url, {'items': [
            {'item_code': 'SCAF-01', 'item_name': 'Frame', 'quantity': 250},
            {'item_code': 'SCAF-02', 'item_name': 'Board', 'quantity': 400},
        ]}, format='json')
        self.assertEqual(created.status_code, 201)

        listed = self.client.get(url)
        self.assertEqual(len(listed.data), 2)

    def test_items_endpoint_surfaces_item_validation_as_400(self):
        challan = make_challan()
        response = self.client.post(
            reverse('challan_management:challan-items', args=[challan.pk]),
            {'items': [{'item_code': 'SCAF-01', 'quantity': 5}]}, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('item_name', response.data['error'])

    def test_close_endpoint_requires_the_terminal_stage(self):
        challan = authorized_challan()
        response = self.client.post(
            reverse('challan_management:challan-close', args=[challan.pk]), format='json')
        self.assertEqual(response.status_code, 400)

    def test_close_endpoint_closes_a_challan_at_the_terminal_stage(self):
        challan = authorized_challan()
        advance_to(challan.pk, 'ARRIVAL_AT_BRANCH')

        response = self.client.post(
            reverse('challan_management:challan-close', args=[challan.pk]), format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['current_stage'], 'CLOSED')

    def test_stage_logs_endpoint_returns_the_audit_trail_in_order(self):
        challan = authorized_challan()
        ChallanService().advance_stage(challan.pk)

        response = self.client.get(
            reverse('challan_management:challan-stage-logs', args=[challan.pk]))
        self.assertEqual([row['to_stage'] for row in response.data],
                         ['PLANNING_DONE', 'PLANNING_DONE', 'GENERATED_CHALLAN'])

    def test_pending_authorization_endpoint_is_the_approver_queue(self):
        service = ChallanService()
        make_challan(service)
        approved = make_challan(service)
        service.authorize_challan(approved.pk, 'approve')

        response = self.client.get(reverse('challan_management:challan-pending'))
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['challan_no'], 'DC-000001')

    def test_list_endpoint_filters_by_order_id(self):
        make_challan(order_id=111)
        make_challan(order_id=222)

        response = self.client.get(
            reverse('challan_management:challan-list'), {'order_id': 222})
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['order_id'], 222)

    def test_stage_flow_endpoint_exposes_the_service_owned_transition_table(self):
        response = self.client.get(reverse('challan_management:stage-flow'))
        self.assertEqual(response.data['stage_flow'], ChallanService.STAGE_FLOW)
        self.assertIn('CLOSED', response.data['all_stages'])
