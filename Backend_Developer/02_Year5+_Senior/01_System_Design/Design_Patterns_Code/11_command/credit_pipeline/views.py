"""
API views for the Credit Pipeline Command pattern demo.

Every state-changing endpoint builds a Command object and hands it to the
module-level PipelineInvoker, which is what actually calls execute()/undo()
and maintains the undo history. Views never mutate CreditPipelineEntry
directly - that discipline is the whole point of the pattern.
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .commands import (
    AdvanceStatusCommand,
    EscalateToLegalCommand,
    MarkPaidCommand,
    MarkSalesIssueCommand,
)
from .invoker import get_invoker
from .models import CreditPipelineEntry, TransitionLog
from .serializers import (
    AdvanceStatusSerializer,
    CreditPipelineEntryListSerializer,
    CreditPipelineEntrySerializer,
    EscalateSerializer,
    MarkPaidSerializer,
)


class EntryListView(APIView):
    """
    GET  /api/entries/          list all pipeline entries
    POST /api/entries/          create a new entry (starts at BILL_MADE)
    """

    def get(self, request):
        entries = CreditPipelineEntry.objects.all()
        serializer = CreditPipelineEntryListSerializer(entries, many=True)
        return Response(serializer.data)

    def post(self, request):
        data = request.data
        entry = CreditPipelineEntry.objects.create(
            invoice_doc_number=data['invoice_doc_number'],
            order_id=data['order_id'],
            customer_name=data['customer_name'],
            amount=data['amount'],
            balance=data.get('balance', data['amount']),
        )
        serializer = CreditPipelineEntrySerializer(entry)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class EntryDetailView(APIView):
    """GET /api/entries/<invoice_doc_number>/ — entry + full transition history."""

    def get(self, request, invoice_doc_number):
        try:
            entry = CreditPipelineEntry.objects.get(invoice_doc_number=invoice_doc_number)
        except CreditPipelineEntry.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        serializer = CreditPipelineEntrySerializer(entry)
        return Response(serializer.data)


class AdvanceStatusView(APIView):
    """POST /api/entries/<invoice_doc_number>/advance/ — move one step forward."""

    def post(self, request, invoice_doc_number):
        entry = _get_entry_or_404(invoice_doc_number)
        if isinstance(entry, Response):
            return entry

        payload = AdvanceStatusSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        command = AdvanceStatusCommand(
            entry, remarks=payload.validated_data['remarks'],
            executed_by=payload.validated_data['executed_by'],
        )
        result = get_invoker().execute(command)
        http_status = status.HTTP_200_OK if result.get('success') else status.HTTP_400_BAD_REQUEST
        return Response(result, status=http_status)


class MarkPaidView(APIView):
    """POST /api/entries/<invoice_doc_number>/mark-paid/ — clear balance, close entry."""

    def post(self, request, invoice_doc_number):
        entry = _get_entry_or_404(invoice_doc_number)
        if isinstance(entry, Response):
            return entry

        payload = MarkPaidSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        command = MarkPaidCommand(
            entry, payment_reference=payload.validated_data['payment_reference'],
            executed_by=payload.validated_data['executed_by'],
        )
        result = get_invoker().execute(command)
        return Response(result, status=status.HTTP_200_OK)


class EscalateToLegalView(APIView):
    """POST /api/entries/<invoice_doc_number>/escalate/ — jump straight to LEGAL."""

    def post(self, request, invoice_doc_number):
        entry = _get_entry_or_404(invoice_doc_number)
        if isinstance(entry, Response):
            return entry

        payload = EscalateSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        command = EscalateToLegalCommand(
            entry, legal_remarks=payload.validated_data['legal_remarks'],
            executed_by=payload.validated_data['executed_by'],
        )
        result = get_invoker().execute(command)
        return Response(result, status=status.HTTP_200_OK)


class MarkSalesIssueView(APIView):
    """POST /api/entries/<invoice_doc_number>/sales-issue/ — flag a sales-side dispute."""

    def post(self, request, invoice_doc_number):
        entry = _get_entry_or_404(invoice_doc_number)
        if isinstance(entry, Response):
            return entry

        issue_remarks = request.data.get('issue_remarks', '')
        executed_by = request.data.get('executed_by', 'system')

        command = MarkSalesIssueCommand(entry, issue_remarks=issue_remarks, executed_by=executed_by)
        result = get_invoker().execute(command)
        return Response(result, status=status.HTTP_200_OK)


class UndoLastCommandView(APIView):
    """POST /api/undo-last/ — pop the invoker's history stack and undo it."""

    def post(self, request):
        result = get_invoker().undo_last()
        http_status = status.HTTP_200_OK if result.get('success') else status.HTTP_400_BAD_REQUEST
        return Response(result, status=http_status)


class InvokerHistoryView(APIView):
    """GET /api/invoker-history/ — names of commands currently undoable, in order."""

    def get(self, request):
        invoker = get_invoker()
        return Response({
            'history_count': invoker.get_history_count(),
            'history': invoker.get_history(),
        })


class TransitionLogListView(APIView):
    """GET /api/entries/<invoice_doc_number>/transitions/ — raw audit trail."""

    def get(self, request, invoice_doc_number):
        entry = _get_entry_or_404(invoice_doc_number)
        if isinstance(entry, Response):
            return entry
        logs = TransitionLog.objects.filter(entry=entry)
        from .serializers import TransitionLogSerializer
        serializer = TransitionLogSerializer(logs, many=True)
        return Response(serializer.data)


def _get_entry_or_404(invoice_doc_number):
    try:
        return CreditPipelineEntry.objects.get(invoice_doc_number=invoice_doc_number)
    except CreditPipelineEntry.DoesNotExist:
        return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
