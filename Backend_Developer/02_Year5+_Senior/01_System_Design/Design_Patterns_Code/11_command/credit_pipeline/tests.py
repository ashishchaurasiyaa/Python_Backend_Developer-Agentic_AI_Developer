"""
Tests for the Command pattern (AdvanceStatusCommand / MarkPaidCommand /
EscalateToLegalCommand / MarkSalesIssueCommand + PipelineInvoker).

Behavioural guarantee under test: every state change is encapsulated as a
Command object that can be executed AND undone, the PipelineInvoker keeps
a LIFO undo stack independent of which concrete command was run, and every
transition (including undos) leaves an immutable TransitionLog row.
"""
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from .commands import (
    AdvanceStatusCommand,
    EscalateToLegalCommand,
    MarkPaidCommand,
    MarkSalesIssueCommand,
)
from .invoker import PipelineInvoker, get_invoker
from .models import CreditPipelineEntry, TransitionLog


def make_entry(**overrides):
    defaults = dict(
        invoice_doc_number='INV-TEST-0001',
        order_id=1001,
        customer_name='Metro Constructions',
        amount=Decimal('50000.00'),
        balance=Decimal('50000.00'),
    )
    defaults.update(overrides)
    return CreditPipelineEntry.objects.create(**defaults)


class AdvanceStatusCommandTests(TestCase):
    def test_execute_moves_entry_to_next_status_in_the_pipeline(self):
        entry = make_entry()
        result = AdvanceStatusCommand(entry, remarks='submitted to accounts').execute()

        self.assertTrue(result['success'])
        self.assertEqual(result['from'], 'BILL_MADE')
        self.assertEqual(result['to'], 'BILL_SUBMITTED')
        entry.refresh_from_db()
        self.assertEqual(entry.current_status, 'BILL_SUBMITTED')

    def test_execute_writes_an_immutable_transition_log_row(self):
        entry = make_entry()
        AdvanceStatusCommand(entry, remarks='x', executed_by='ashish').execute()

        log = TransitionLog.objects.get(entry=entry)
        self.assertEqual(log.from_status, 'BILL_MADE')
        self.assertEqual(log.to_status, 'BILL_SUBMITTED')
        self.assertEqual(log.command_name, 'AdvanceStatus')
        self.assertEqual(log.executed_by, 'ashish')
        self.assertFalse(log.is_undone)

    def test_execute_from_terminal_state_fails_cleanly(self):
        entry = make_entry(current_status='BAD_DEBT')
        result = AdvanceStatusCommand(entry).execute()
        self.assertFalse(result['success'])
        entry.refresh_from_db()
        self.assertEqual(entry.current_status, 'BAD_DEBT')  # unchanged

    def test_undo_reverts_status_to_the_pre_execute_value(self):
        entry = make_entry()
        command = AdvanceStatusCommand(entry)
        command.execute()
        self.assertEqual(entry.current_status, 'BILL_SUBMITTED')

        undo_result = command.undo()
        self.assertTrue(undo_result['success'])
        entry.refresh_from_db()
        self.assertEqual(entry.current_status, 'BILL_MADE')

    def test_undo_without_prior_execute_fails_cleanly(self):
        entry = make_entry()
        result = AdvanceStatusCommand(entry).undo()
        self.assertFalse(result['success'])

    def test_undo_marks_original_log_row_as_undone_and_adds_undo_row(self):
        entry = make_entry()
        command = AdvanceStatusCommand(entry)
        command.execute()
        command.undo()

        original = TransitionLog.objects.get(command_name='AdvanceStatus')
        self.assertTrue(original.is_undone)
        undo_row = TransitionLog.objects.get(command_name='UNDO_AdvanceStatus')
        self.assertEqual(undo_row.from_status, 'BILL_SUBMITTED')
        self.assertEqual(undo_row.to_status, 'BILL_MADE')


class MarkPaidCommandTests(TestCase):
    def test_execute_clears_balance_and_sets_bill_paid(self):
        entry = make_entry(current_status='BILL_OVERDUE', balance=Decimal('12000.00'))
        result = MarkPaidCommand(entry, payment_reference='UTR123').execute()

        self.assertTrue(result['success'])
        entry.refresh_from_db()
        self.assertEqual(entry.current_status, 'BILL_PAID')
        self.assertEqual(entry.balance, 0)

    def test_undo_restores_previous_status_and_balance(self):
        entry = make_entry(current_status='THIRD_PTP', balance=Decimal('8000.00'))
        command = MarkPaidCommand(entry, payment_reference='UTR999')
        command.execute()

        command.undo()
        entry.refresh_from_db()
        self.assertEqual(entry.current_status, 'THIRD_PTP')
        self.assertEqual(entry.balance, Decimal('8000.00'))


class EscalateAndSalesIssueCommandTests(TestCase):
    def test_escalate_moves_entry_to_legal_from_any_state(self):
        entry = make_entry(current_status='FIRST_PTP')
        result = EscalateToLegalCommand(entry, legal_remarks='no response').execute()

        self.assertTrue(result['success'])
        entry.refresh_from_db()
        self.assertEqual(entry.current_status, 'LEGAL')

    def test_escalate_undo_restores_prior_state(self):
        entry = make_entry(current_status='SECOND_PTP')
        command = EscalateToLegalCommand(entry, legal_remarks='y')
        command.execute()
        command.undo()
        entry.refresh_from_db()
        self.assertEqual(entry.current_status, 'SECOND_PTP')

    def test_mark_sales_issue_flags_entry_regardless_of_prior_state(self):
        entry = make_entry(current_status='BILL_OVERDUE')
        result = MarkSalesIssueCommand(entry, issue_remarks='wrong item delivered').execute()

        self.assertTrue(result['success'])
        entry.refresh_from_db()
        self.assertEqual(entry.current_status, 'SALES_ISSUE')


class PipelineInvokerTests(TestCase):
    """
    The invoker doesn't know or care WHICH command it's running - that's
    the polymorphism the pattern buys. It only needs execute()/undo()/
    get_name() to exist, and it maintains a strict LIFO undo stack.
    """

    def test_execute_pushes_successful_command_onto_history(self):
        entry = make_entry()
        invoker = PipelineInvoker()
        invoker.execute(AdvanceStatusCommand(entry))
        self.assertEqual(invoker.get_history_count(), 1)
        self.assertEqual(invoker.get_history(), ['AdvanceStatus'])

    def test_execute_does_not_push_failed_command_onto_history(self):
        entry = make_entry(current_status='BAD_DEBT')  # terminal - will fail
        invoker = PipelineInvoker()
        invoker.execute(AdvanceStatusCommand(entry))
        self.assertEqual(invoker.get_history_count(), 0)

    def test_undo_last_pops_history_in_lifo_order_across_different_command_types(self):
        entry = make_entry()
        invoker = PipelineInvoker()

        invoker.execute(AdvanceStatusCommand(entry))  # BILL_MADE -> BILL_SUBMITTED
        invoker.execute(MarkPaidCommand(entry, payment_reference='UTR1'))  # -> BILL_PAID
        self.assertEqual(invoker.get_history(), ['AdvanceStatus', 'MarkPaid'])

        # Undo must reverse MarkPaid FIRST (LIFO), not AdvanceStatus.
        first_undo = invoker.undo_last()
        self.assertTrue(first_undo['success'])
        entry.refresh_from_db()
        self.assertEqual(entry.current_status, 'BILL_SUBMITTED')
        self.assertEqual(invoker.get_history_count(), 1)

        second_undo = invoker.undo_last()
        self.assertTrue(second_undo['success'])
        entry.refresh_from_db()
        self.assertEqual(entry.current_status, 'BILL_MADE')
        self.assertEqual(invoker.get_history_count(), 0)

    def test_undo_last_on_empty_history_fails_cleanly(self):
        invoker = PipelineInvoker()
        result = invoker.undo_last()
        self.assertFalse(result['success'])

    def test_clear_history_empties_the_undo_stack(self):
        entry = make_entry()
        invoker = PipelineInvoker()
        invoker.execute(AdvanceStatusCommand(entry))
        invoker.clear_history()
        self.assertEqual(invoker.get_history_count(), 0)

    def test_get_invoker_returns_same_module_level_instance_every_call(self):
        # get_invoker() is a Singleton-flavoured accessor so undo history
        # survives across separate Django request/response cycles.
        a = get_invoker()
        b = get_invoker()
        self.assertIs(a, b)


class CreditPipelineHttpEndpointTests(APITestCase):
    """Exercise the actual API surface end to end through Django's test client."""

    def setUp(self):
        get_invoker().clear_history()

    def test_create_and_advance_entry_via_api(self):
        create_url = reverse('credit_pipeline:entry-list')
        create_resp = self.client.post(create_url, {
            'invoice_doc_number': 'INV-API-0001',
            'order_id': 55,
            'customer_name': 'Site Builders Pvt Ltd',
            'amount': '75000.00',
        }, format='json')
        self.assertEqual(create_resp.status_code, 201)
        self.assertEqual(create_resp.data['current_status'], 'BILL_MADE')

        advance_url = reverse('credit_pipeline:entry-advance', args=['INV-API-0001'])
        advance_resp = self.client.post(advance_url, {'remarks': 'sent'}, format='json')
        self.assertEqual(advance_resp.status_code, 200)
        self.assertEqual(advance_resp.data['to'], 'BILL_SUBMITTED')

    def test_undo_last_endpoint_reverses_most_recent_api_driven_change(self):
        make_entry(invoice_doc_number='INV-API-0002')
        advance_url = reverse('credit_pipeline:entry-advance', args=['INV-API-0002'])
        self.client.post(advance_url, {}, format='json')

        undo_url = reverse('credit_pipeline:undo-last')
        undo_resp = self.client.post(undo_url)
        self.assertEqual(undo_resp.status_code, 200)
        self.assertTrue(undo_resp.data['success'])

        entry = CreditPipelineEntry.objects.get(invoice_doc_number='INV-API-0002')
        self.assertEqual(entry.current_status, 'BILL_MADE')

    def test_invoker_history_endpoint_reflects_executed_commands(self):
        make_entry(invoice_doc_number='INV-API-0003')
        advance_url = reverse('credit_pipeline:entry-advance', args=['INV-API-0003'])
        mark_paid_url = reverse('credit_pipeline:entry-mark-paid', args=['INV-API-0003'])

        self.client.post(advance_url, {}, format='json')
        self.client.post(mark_paid_url, {}, format='json')

        history_url = reverse('credit_pipeline:invoker-history')
        response = self.client.get(history_url)
        self.assertEqual(response.data['history'], ['AdvanceStatus', 'MarkPaid'])

    def test_transitions_endpoint_lists_full_audit_trail(self):
        make_entry(invoice_doc_number='INV-API-0004')
        advance_url = reverse('credit_pipeline:entry-advance', args=['INV-API-0004'])
        self.client.post(advance_url, {}, format='json')
        self.client.post(advance_url, {}, format='json')

        transitions_url = reverse('credit_pipeline:entry-transitions', args=['INV-API-0004'])
        response = self.client.get(transitions_url)
        self.assertEqual(len(response.data), 2)
