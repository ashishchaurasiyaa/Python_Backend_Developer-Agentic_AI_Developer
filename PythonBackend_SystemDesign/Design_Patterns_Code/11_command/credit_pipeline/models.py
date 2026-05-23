"""
Models for Credit Pipeline State Machine.

CreditPipelineEntry — an invoice moving through 12 credit states.
TransitionLog       — immutable audit log of every state change.
"""
from django.db import models


class CreditPipelineEntry(models.Model):
    """
    Represents an invoice in the credit pipeline.
    Tracks its current state across the 12-step collection process:
    BILL_MADE -> BILL_SUBMITTED -> BILL_BOOKED -> BILL_OVERDUE ->
    FIRST_PTP -> SECOND_PTP -> THIRD_PTP -> FORCE_PICKUP ->
    SALES_ISSUE -> LEGAL -> BAD_DEBT -> BILL_PAID
    """

    STATUS_CHOICES = [
        ('BILL_MADE', 'Bill Made'),
        ('BILL_SUBMITTED', 'Bill Submitted'),
        ('BILL_BOOKED', 'Bill Booked'),
        ('BILL_OVERDUE', 'Bill Overdue'),
        ('FIRST_PTP', 'First PTP'),
        ('SECOND_PTP', 'Second PTP'),
        ('THIRD_PTP', 'Third PTP'),
        ('FORCE_PICKUP', 'Force Pickup'),
        ('SALES_ISSUE', 'Sales Issue'),
        ('LEGAL', 'Legal'),
        ('BAD_DEBT', 'Bad Debt'),
        ('BILL_PAID', 'Bill Paid'),
    ]

    invoice_doc_number = models.CharField(
        max_length=50, primary_key=True,
        help_text='Unique invoice document number, e.g. INV-2025-0001',
    )
    order_id = models.IntegerField(
        help_text='Youngman Sales Order ID',
    )
    customer_name = models.CharField(
        max_length=255,
        help_text='Customer / debtor name',
    )
    invoice_date = models.DateField(
        auto_now_add=True,
        help_text='Date the invoice was created',
    )
    amount = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text='Original invoice amount',
    )
    balance = models.DecimalField(
        max_digits=12, decimal_places=2,
        help_text='Outstanding balance',
    )
    current_status = models.CharField(
        max_length=30, choices=STATUS_CHOICES, default='BILL_MADE',
        help_text='Current state in the credit pipeline',
    )
    current_remarks = models.TextField(
        blank=True, default='',
        help_text='Latest remarks / notes on the entry',
    )
    ptp_date = models.DateField(
        null=True, blank=True,
        help_text='Promise-to-pay date (if applicable)',
    )
    due_date = models.DateField(
        null=True, blank=True,
        help_text='Payment due date',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text='Record creation timestamp',
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Credit Pipeline Entry'
        verbose_name_plural = 'Credit Pipeline Entries'

    def __str__(self):
        return f'{self.invoice_doc_number} | {self.customer_name} | {self.current_status}'


class TransitionLog(models.Model):
    """
    Immutable audit log for every state transition (including undos).
    Each row records: who did what, when, from which state to which state.
    """

    entry = models.ForeignKey(
        CreditPipelineEntry,
        on_delete=models.CASCADE,
        related_name='transitions',
        help_text='The pipeline entry this transition belongs to',
    )
    from_status = models.CharField(
        max_length=30,
        help_text='State before the transition',
    )
    to_status = models.CharField(
        max_length=30,
        help_text='State after the transition',
    )
    command_name = models.CharField(
        max_length=50,
        help_text='Name of the Command that triggered this transition',
    )
    remarks = models.TextField(
        blank=True, default='',
        help_text='Remarks / reason for the transition',
    )
    executed_by = models.CharField(
        max_length=100, default='system',
        help_text='User or system that executed the command',
    )
    executed_at = models.DateTimeField(
        auto_now_add=True,
        help_text='Timestamp of execution',
    )
    is_undone = models.BooleanField(
        default=False,
        help_text='Whether this transition was later undone',
    )

    class Meta:
        ordering = ['-executed_at']
        verbose_name = 'Transition Log'
        verbose_name_plural = 'Transition Logs'

    def __str__(self):
        undo_tag = ' [UNDONE]' if self.is_undone else ''
        return (
            f'{self.entry_id}: {self.from_status} -> {self.to_status} '
            f'({self.command_name}){undo_tag}'
        )
