"""
Command Design Pattern — Credit Pipeline State Machine.

Each concrete Command encapsulates a state transition.
Every command can be:
  - executed   (move the invoice forward / to a specific state)
  - undone     (revert to the previous state)
  - logged     (an immutable TransitionLog row is created)

This mirrors Youngman Invoice.php's advanceInvoiceStep() method,
where the 12-state credit pipeline is driven by discrete commands.
"""
from abc import ABC, abstractmethod

from django.utils import timezone


# ── Abstract Base ────────────────────────────────────────────
class Command(ABC):
    """Interface every pipeline command must implement."""

    @abstractmethod
    def execute(self) -> dict:
        """Run the command. Return a result dict with 'success' key."""
        pass

    @abstractmethod
    def undo(self) -> dict:
        """Reverse the command. Return a result dict with 'success' key."""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Human-readable command name for logging."""
        pass


# ── AdvanceStatusCommand ─────────────────────────────────────
class AdvanceStatusCommand(Command):
    """
    Advances an invoice one step along the standard credit pipeline.
    This is the direct equivalent of advanceInvoiceStep() in Invoice.php.

    The valid linear path is:
        BILL_MADE -> BILL_SUBMITTED -> BILL_BOOKED -> BILL_OVERDUE ->
        FIRST_PTP -> SECOND_PTP -> THIRD_PTP -> FORCE_PICKUP ->
        SALES_ISSUE -> LEGAL -> BAD_DEBT
    """

    VALID_TRANSITIONS = {
        'BILL_MADE':      'BILL_SUBMITTED',
        'BILL_SUBMITTED': 'BILL_BOOKED',
        'BILL_BOOKED':    'BILL_OVERDUE',
        'BILL_OVERDUE':   'FIRST_PTP',
        'FIRST_PTP':      'SECOND_PTP',
        'SECOND_PTP':     'THIRD_PTP',
        'THIRD_PTP':      'FORCE_PICKUP',
        'FORCE_PICKUP':   'SALES_ISSUE',
        'SALES_ISSUE':    'LEGAL',
        'LEGAL':          'BAD_DEBT',
    }

    def __init__(self, entry, remarks='', executed_by='system'):
        self.entry = entry
        self.remarks = remarks
        self.executed_by = executed_by
        self._previous_status = None
        self._previous_remarks = None

    def execute(self) -> dict:
        self._previous_status = self.entry.current_status
        self._previous_remarks = self.entry.current_remarks

        next_status = self.VALID_TRANSITIONS.get(self.entry.current_status)
        if not next_status:
            return {
                'success': False,
                'error': f'No valid transition from {self.entry.current_status}',
            }

        self.entry.current_status = next_status
        self.entry.current_remarks = self.remarks
        self.entry.save()

        from .models import TransitionLog
        TransitionLog.objects.create(
            entry=self.entry,
            from_status=self._previous_status,
            to_status=next_status,
            command_name=self.get_name(),
            remarks=self.remarks,
            executed_by=self.executed_by,
        )

        return {
            'success': True,
            'from': self._previous_status,
            'to': next_status,
            'command': self.get_name(),
        }

    def undo(self) -> dict:
        if not self._previous_status:
            return {'success': False, 'error': 'No previous state to revert to'}

        current = self.entry.current_status
        self.entry.current_status = self._previous_status
        self.entry.current_remarks = self._previous_remarks or ''
        self.entry.save()

        from .models import TransitionLog

        # Mark the original transition as undone
        TransitionLog.objects.filter(
            entry=self.entry, to_status=current, is_undone=False,
        ).update(is_undone=True)

        # Create an undo log entry
        TransitionLog.objects.create(
            entry=self.entry,
            from_status=current,
            to_status=self._previous_status,
            command_name=f'UNDO_{self.get_name()}',
            remarks=f'Undone: {current} -> {self._previous_status}',
            executed_by=self.executed_by,
        )

        return {
            'success': True,
            'undone': True,
            'from': current,
            'reverted_to': self._previous_status,
        }

    def get_name(self) -> str:
        return 'AdvanceStatus'


# ── MarkPaidCommand ──────────────────────────────────────────
class MarkPaidCommand(Command):
    """
    Marks an invoice as BILL_PAID from any state.
    Clears the outstanding balance to zero.
    """

    def __init__(self, entry, payment_reference='', executed_by='system'):
        self.entry = entry
        self.payment_reference = payment_reference
        self.executed_by = executed_by
        self._previous_status = None
        self._previous_balance = None
        self._previous_remarks = None

    def execute(self) -> dict:
        self._previous_status = self.entry.current_status
        self._previous_balance = self.entry.balance
        self._previous_remarks = self.entry.current_remarks

        from_status = self.entry.current_status
        self.entry.current_status = 'BILL_PAID'
        self.entry.balance = 0
        self.entry.current_remarks = f'Payment received. Ref: {self.payment_reference}'
        self.entry.save()

        from .models import TransitionLog
        TransitionLog.objects.create(
            entry=self.entry,
            from_status=from_status,
            to_status='BILL_PAID',
            command_name=self.get_name(),
            remarks=f'Balance {self._previous_balance} cleared. Ref: {self.payment_reference}',
            executed_by=self.executed_by,
        )

        return {
            'success': True,
            'from': from_status,
            'to': 'BILL_PAID',
            'balance_cleared': str(self._previous_balance),
            'command': self.get_name(),
        }

    def undo(self) -> dict:
        if not self._previous_status:
            return {'success': False, 'error': 'Cannot undo — no previous state recorded'}

        self.entry.current_status = self._previous_status
        self.entry.balance = self._previous_balance
        self.entry.current_remarks = self._previous_remarks or ''
        self.entry.save()

        from .models import TransitionLog
        TransitionLog.objects.create(
            entry=self.entry,
            from_status='BILL_PAID',
            to_status=self._previous_status,
            command_name=f'UNDO_{self.get_name()}',
            remarks=f'Payment reversal. Balance restored: {self._previous_balance}',
            executed_by=self.executed_by,
        )

        return {
            'success': True,
            'undone': True,
            'reverted_to': self._previous_status,
            'balance_restored': str(self._previous_balance),
        }

    def get_name(self) -> str:
        return 'MarkPaid'


# ── EscalateToLegalCommand ───────────────────────────────────
class EscalateToLegalCommand(Command):
    """
    Immediately escalates an invoice to LEGAL status from any state.
    Used when the credit team decides to skip the normal pipeline.
    """

    def __init__(self, entry, legal_remarks='', executed_by='system'):
        self.entry = entry
        self.legal_remarks = legal_remarks
        self.executed_by = executed_by
        self._previous_status = None
        self._previous_remarks = None

    def execute(self) -> dict:
        self._previous_status = self.entry.current_status
        self._previous_remarks = self.entry.current_remarks

        self.entry.current_status = 'LEGAL'
        self.entry.current_remarks = f'Escalated to legal: {self.legal_remarks}'
        self.entry.save()

        from .models import TransitionLog
        TransitionLog.objects.create(
            entry=self.entry,
            from_status=self._previous_status,
            to_status='LEGAL',
            command_name=self.get_name(),
            remarks=self.legal_remarks,
            executed_by=self.executed_by,
        )

        return {
            'success': True,
            'from': self._previous_status,
            'to': 'LEGAL',
            'command': self.get_name(),
        }

    def undo(self) -> dict:
        if not self._previous_status:
            return {'success': False, 'error': 'Cannot undo — no previous state recorded'}

        current = self.entry.current_status
        self.entry.current_status = self._previous_status
        self.entry.current_remarks = self._previous_remarks or ''
        self.entry.save()

        from .models import TransitionLog
        TransitionLog.objects.create(
            entry=self.entry,
            from_status='LEGAL',
            to_status=self._previous_status,
            command_name=f'UNDO_{self.get_name()}',
            remarks='Legal escalation reversed',
            executed_by=self.executed_by,
        )

        return {
            'success': True,
            'undone': True,
            'reverted_to': self._previous_status,
        }

    def get_name(self) -> str:
        return 'EscalateToLegal'


# ── MarkSalesIssueCommand ───────────────────────────────────
class MarkSalesIssueCommand(Command):
    """
    Flags an invoice as a SALES_ISSUE from any state.
    Used when the issue is on the sales side (wrong delivery, disputes).
    """

    def __init__(self, entry, issue_remarks='', executed_by='system'):
        self.entry = entry
        self.issue_remarks = issue_remarks
        self.executed_by = executed_by
        self._previous_status = None
        self._previous_remarks = None

    def execute(self) -> dict:
        self._previous_status = self.entry.current_status
        self._previous_remarks = self.entry.current_remarks

        self.entry.current_status = 'SALES_ISSUE'
        self.entry.current_remarks = f'Sales issue flagged: {self.issue_remarks}'
        self.entry.save()

        from .models import TransitionLog
        TransitionLog.objects.create(
            entry=self.entry,
            from_status=self._previous_status,
            to_status='SALES_ISSUE',
            command_name=self.get_name(),
            remarks=self.issue_remarks,
            executed_by=self.executed_by,
        )

        return {
            'success': True,
            'from': self._previous_status,
            'to': 'SALES_ISSUE',
            'command': self.get_name(),
        }

    def undo(self) -> dict:
        if not self._previous_status:
            return {'success': False, 'error': 'Cannot undo — no previous state recorded'}

        self.entry.current_status = self._previous_status
        self.entry.current_remarks = self._previous_remarks or ''
        self.entry.save()

        from .models import TransitionLog
        TransitionLog.objects.create(
            entry=self.entry,
            from_status='SALES_ISSUE',
            to_status=self._previous_status,
            command_name=f'UNDO_{self.get_name()}',
            remarks='Sales issue flag reversed',
            executed_by=self.executed_by,
        )

        return {
            'success': True,
            'undone': True,
            'reverted_to': self._previous_status,
        }

    def get_name(self) -> str:
        return 'MarkSalesIssue'
