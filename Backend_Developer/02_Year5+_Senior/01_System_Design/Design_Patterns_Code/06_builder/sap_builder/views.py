"""
API views for the payload Builder demo.

BuildPayloadView is the interesting one. It never assembles a payload
field by field — it names a recipe and lets PayloadDirector drive the
builder. The endpoint therefore cannot produce a payload that skips
validation, which is exactly the guarantee you want on a compliance
filing.

Note also that BuilderValidationError is caught and returned as a list of
problems rather than a single string, so a client fixing a draft sees
everything wrong with it in one response.
"""
from decimal import Decimal

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .builders import (
    EWAY_BILL_BUILDERS,
    BuilderValidationError,
    PayloadBuilder,
    PayloadDirector,
    get_eway_bill_builder,
    save_payload,
)
from .models import BuiltPayload, DraftLine, SapDocumentDraft
from .serializers import (
    BuildRequestSerializer,
    BuiltPayloadListSerializer,
    BuiltPayloadSerializer,
    DraftLineSerializer,
    SapDocumentDraftListSerializer,
    SapDocumentDraftSerializer,
)


def _get_draft_or_404(pk):
    try:
        return SapDocumentDraft.objects.get(pk=pk)
    except SapDocumentDraft.DoesNotExist:
        return Response({'error': 'Draft not found'},
                        status=status.HTTP_404_NOT_FOUND)


class DraftListView(APIView):
    """
    GET  /api/drafts/   list drafts
    POST /api/drafts/   create a draft, optionally with its lines
    """

    def get(self, request):
        drafts = SapDocumentDraft.objects.all()
        doc_type = request.query_params.get('doc_type')
        if doc_type:
            drafts = drafts.filter(doc_type=doc_type)
        return Response(SapDocumentDraftListSerializer(drafts, many=True).data)

    def post(self, request):
        # `lines` is read-only on the draft serializer, so it is ignored
        # there and handled explicitly below. No mutation of request.data.
        lines = request.data.get('lines', [])

        serializer = SapDocumentDraftSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        draft = serializer.save()

        for index, line in enumerate(lines):
            DraftLine.objects.create(
                draft=draft,
                line_num=line.get('line_num', index),
                item_code=line['item_code'],
                item_name=line.get('item_name', ''),
                hsn_code=line.get('hsn_code', ''),
                quantity=Decimal(str(line['quantity'])),
                unit=line.get('unit', 'NOS'),
                rate=Decimal(str(line.get('rate', '0'))),
            )

        return Response(SapDocumentDraftSerializer(draft).data,
                        status=status.HTTP_201_CREATED)


class DraftDetailView(APIView):
    """GET /api/drafts/<pk>/ — draft with its lines."""

    def get(self, request, pk):
        draft = _get_draft_or_404(pk)
        if isinstance(draft, Response):
            return draft
        return Response(SapDocumentDraftSerializer(draft).data)


class DraftLineView(APIView):
    """
    GET  /api/drafts/<pk>/lines/   list lines
    POST /api/drafts/<pk>/lines/   append a line
    """

    def get(self, request, pk):
        draft = _get_draft_or_404(pk)
        if isinstance(draft, Response):
            return draft
        return Response(DraftLineSerializer(draft.lines.all(), many=True).data)

    def post(self, request, pk):
        draft = _get_draft_or_404(pk)
        if isinstance(draft, Response):
            return draft

        serializer = DraftLineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        line = serializer.save(draft=draft)
        return Response(DraftLineSerializer(line).data,
                        status=status.HTTP_201_CREATED)


class BuildPayloadView(APIView):
    """
    POST /api/drafts/<pk>/build/ — assemble a payload via a director recipe.

    Body: {"recipe": "auto|delivery|pickup|minimal", "vehicle_number": ...,
           "save": true}
    """

    def post(self, request, pk):
        draft = _get_draft_or_404(pk)
        if isinstance(draft, Response):
            return draft

        payload_in = BuildRequestSerializer(data=request.data)
        payload_in.is_valid(raise_exception=True)
        options = payload_in.validated_data

        transport = {
            key: options[key]
            for key in ('vehicle_number', 'transport_mode', 'transporter_id')
            if options.get(key)
        }
        if options.get('distance_km') is not None:
            transport['distance_km'] = options['distance_km']

        director = PayloadDirector()
        recipe = options['recipe']

        try:
            if recipe == 'minimal':
                payload = director.build_minimal(draft)
            elif recipe == 'delivery':
                payload = director.build_delivery(draft, **transport)
            elif recipe == 'pickup':
                payload = director.build_pickup(draft, **transport)
            else:
                payload = director.build_for_draft(draft, **transport)
        except BuilderValidationError as exc:
            return Response(
                {'error': 'Payload is incomplete', 'problems': exc.errors},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response = {
            'recipe': recipe,
            'builder': type(director.builder).__name__,
            'payload': payload,
        }

        if options['save']:
            record = save_payload(
                draft, payload,
                builder_used=type(director.builder).__name__,
                recipe=recipe,
            )
            response['built_payload_id'] = record.pk

        return Response(response, status=status.HTTP_201_CREATED)


class BuildEwayBillView(APIView):
    """
    POST /api/drafts/<pk>/eway-bill/ — the abstract-builder flavour.

    The direction-specific subclass is chosen from the draft's doc_type,
    so this view has no conditional of its own.
    """

    def post(self, request, pk):
        draft = _get_draft_or_404(pk)
        if isinstance(draft, Response):
            return draft

        try:
            builder = get_eway_bill_builder(draft, request.data or {})
        except ValueError as exc:
            return Response({'error': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)

        payload = builder.build()
        record = save_payload(
            draft, payload,
            builder_used=type(builder).__name__,
            recipe='eway_bill',
        )
        return Response({
            'builder': type(builder).__name__,
            'built_payload_id': record.pk,
            'payload': payload,
        }, status=status.HTTP_201_CREATED)


class BuiltPayloadListView(APIView):
    """GET /api/drafts/<pk>/payloads/ — everything built from this draft."""

    def get(self, request, pk):
        draft = _get_draft_or_404(pk)
        if isinstance(draft, Response):
            return draft
        rows = BuiltPayload.objects.filter(draft=draft)
        return Response(BuiltPayloadListSerializer(rows, many=True).data)


class BuiltPayloadDetailView(APIView):
    """GET /api/payloads/<pk>/ — one built payload, body included."""

    def get(self, request, pk):
        try:
            record = BuiltPayload.objects.get(pk=pk)
        except BuiltPayload.DoesNotExist:
            return Response({'error': 'Built payload not found'},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(BuiltPayloadSerializer(record).data)


class BuilderCatalogueView(APIView):
    """
    GET /api/builders/ — what this app can build and with which steps.

    Exposing the fluent builder's step list is genuinely useful: it is the
    quickest way for a new developer to see which parts of a payload are
    optional.
    """

    def get(self, request):
        fluent_steps = [
            name for name in dir(PayloadBuilder)
            if name.startswith('with_') or name == 'for_draft'
        ]
        return Response({
            'fluent_builder': {
                'class': 'PayloadBuilder',
                'steps': sorted(fluent_steps),
                'required_keys': PayloadBuilder.REQUIRED_KEYS,
            },
            'director_recipes': [
                'build_delivery', 'build_pickup', 'build_minimal',
                'build_for_draft',
            ],
            'eway_bill_builders': {
                doc_type: builder_class.__name__
                for doc_type, builder_class in EWAY_BILL_BUILDERS.items()
            },
        })
