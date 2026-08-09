"""
API views for Challan Management.

EVERY view in this file follows the same four lines:

    1. validate the request SHAPE with a serializer
    2. call exactly one ChallanService method
    3. translate ChallanServiceError into HTTP 400
    4. serialize the result

There is no `if challan.is_authorized == '1'` anywhere below, no challan
number generation, no stage table. If you find yourself wanting to add one,
it belongs in services.py. That discipline is the whole pattern: the same
business rules hold whether a challan is created by this API, by a
management command, by a Celery task, or by a test.

Note also that the views never import the ORM or the repositories - they
only know ChallanService. Swapping the persistence layer would not touch
this file.
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Challan
from .serializers import (
    AddItemsSerializer,
    AdvanceStageSerializer,
    AuthorizeChallanSerializer,
    ChallanItemSerializer,
    ChallanListSerializer,
    ChallanSerializer,
    ChallanStageLogSerializer,
    CreateChallanSerializer,
)
from .services import ChallanService, ChallanServiceError


def _error(exc):
    """Uniform translation of a business-rule violation into HTTP 400."""
    return Response({'error': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


class ChallanListView(APIView):
    """
    GET  /api/challans/   list challans
    POST /api/challans/   create one through the service workflow
    """

    def get(self, request):
        service = ChallanService()
        challans = service.repository.all()

        order_id = request.query_params.get('order_id')
        if order_id:
            challans = service.repository.get_by_order(order_id)

        stage = request.query_params.get('stage')
        if stage:
            challans = service.repository.get_by_stage(stage)

        return Response(ChallanListSerializer(challans, many=True).data)

    def post(self, request):
        payload = CreateChallanSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        try:
            challan = ChallanService().create_challan(payload.validated_data)
        except ChallanServiceError as exc:
            return _error(exc)

        return Response(ChallanSerializer(challan).data,
                        status=status.HTTP_201_CREATED)


class ChallanDetailView(APIView):
    """GET /api/challans/<pk>/ — the service's summary view."""

    def get(self, request, pk):
        try:
            summary = ChallanService().get_challan_summary(pk)
        except ChallanServiceError as exc:
            return Response({'error': str(exc)},
                            status=status.HTTP_404_NOT_FOUND)

        return Response({
            'challan': ChallanSerializer(summary['challan']).data,
            'items': ChallanItemSerializer(summary['items'], many=True).data,
            'stage_logs': ChallanStageLogSerializer(
                summary['stage_logs'], many=True).data,
        })


class AuthorizeChallanView(APIView):
    """POST /api/challans/<pk>/authorize/ — approve or reject."""

    def post(self, request, pk):
        payload = AuthorizeChallanSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        try:
            challan = ChallanService().authorize_challan(
                pk,
                payload.validated_data['action'],
                payload.validated_data['remarks'],
            )
        except ChallanServiceError as exc:
            return _error(exc)

        return Response(ChallanSerializer(challan).data)


class AdvanceStageView(APIView):
    """POST /api/challans/<pk>/advance-stage/ — one step down the lifecycle."""

    def post(self, request, pk):
        payload = AdvanceStageSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        try:
            challan = ChallanService().advance_stage(
                pk,
                changed_by=payload.validated_data['changed_by'],
                remarks=payload.validated_data['remarks'],
            )
        except ChallanServiceError as exc:
            return _error(exc)

        return Response(ChallanSerializer(challan).data)


class ChallanItemsView(APIView):
    """
    GET  /api/challans/<pk>/items/   list line items
    POST /api/challans/<pk>/items/   attach line items
    """

    def get(self, request, pk):
        service = ChallanService()
        if not service.repository.find(pk):
            return Response({'error': f'Challan with id {pk} not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        items = service.item_repository.get_by_challan(pk)
        return Response(ChallanItemSerializer(items, many=True).data)

    def post(self, request, pk):
        payload = AddItemsSerializer(data=request.data)
        payload.is_valid(raise_exception=True)

        try:
            items = ChallanService().add_items(pk, payload.validated_data['items'])
        except ChallanServiceError as exc:
            return _error(exc)

        return Response(ChallanItemSerializer(items, many=True).data,
                        status=status.HTTP_201_CREATED)


class CloseChallanView(APIView):
    """POST /api/challans/<pk>/close/ — final transition to CLOSED."""

    def post(self, request, pk):
        try:
            challan = ChallanService().close_challan(pk)
        except ChallanServiceError as exc:
            return _error(exc)
        return Response(ChallanSerializer(challan).data)


class ChallanStageLogView(APIView):
    """GET /api/challans/<pk>/stage-logs/ — raw audit trail."""

    def get(self, request, pk):
        service = ChallanService()
        if not service.repository.find(pk):
            return Response({'error': f'Challan with id {pk} not found.'},
                            status=status.HTTP_404_NOT_FOUND)
        logs = service.stage_log_repository.get_by_challan(pk)
        return Response(ChallanStageLogSerializer(logs, many=True).data)


class PendingAuthorizationView(APIView):
    """GET /api/challans/pending-authorization/ — the approver's work queue."""

    def get(self, request):
        challans = ChallanService().repository.get_pending_authorization()
        return Response({
            'count': challans.count(),
            'results': ChallanListSerializer(challans, many=True).data,
        })


class StageFlowView(APIView):
    """
    GET /api/stage-flow/ — the stage machine the service enforces.

    Handy for the frontend, and it makes the point that the transition table
    lives in ONE place. The model only stores a string; the service owns
    which strings may follow which.
    """

    def get(self, request):
        return Response({
            'stage_flow': ChallanService.STAGE_FLOW,
            'terminal_stage': 'ARRIVAL_AT_BRANCH',
            'closed_stage': 'CLOSED',
            'all_stages': [choice[0] for choice in Challan.STAGE_CHOICES],
        })
