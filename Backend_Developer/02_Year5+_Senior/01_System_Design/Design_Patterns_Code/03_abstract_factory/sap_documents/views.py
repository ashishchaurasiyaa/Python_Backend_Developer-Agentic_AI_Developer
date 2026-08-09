"""
API views for SAP document posting.

The whole point of the Abstract Factory shows up in PostDocumentView: it is
four lines long and contains no branch on doc_family. Compare that with the
version everyone writes first —

    if doc.doc_family == 'delivery':
        payload = build_delivery_header(doc)
        payload['DocumentLines'] = build_delivery_lines(doc)
        requests.post(f'{BASE}/DeliveryNotes', json=payload)
    elif doc.doc_family == 'return':
        ...

— which is the same conditional repeated in the view, in the retry job, in
the management command, and in the reconciliation script. Four copies, and
the fifth document family means editing all four.
"""
from decimal import Decimal

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .factories import (
    SAP_DOCUMENT_FACTORIES,
    get_factory,
    post_document,
    preview_payload,
)
from .models import SapDocument, SapDocumentLine
from .serializers import (
    CreateSapDocumentSerializer,
    SapDocumentLineSerializer,
    SapDocumentListSerializer,
    SapDocumentSerializer,
    SapPostingLogSerializer,
)


def _get_document_or_404(pk):
    try:
        return SapDocument.objects.get(pk=pk)
    except SapDocument.DoesNotExist:
        return Response({'error': 'SAP document not found'},
                        status=status.HTTP_404_NOT_FOUND)


class SapDocumentListView(APIView):
    """
    GET  /api/documents/   list documents
    POST /api/documents/   create a document with its lines
    """

    def get(self, request):
        documents = SapDocument.objects.all()

        doc_family = request.query_params.get('doc_family')
        if doc_family:
            documents = documents.filter(doc_family=doc_family)

        doc_status = request.query_params.get('status')
        if doc_status:
            documents = documents.filter(status=doc_status)

        return Response(SapDocumentListSerializer(documents, many=True).data)

    def post(self, request):
        payload = CreateSapDocumentSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = dict(payload.validated_data)
        lines = data.pop('lines', [])

        document = SapDocument.objects.create(**data)
        for index, line in enumerate(lines):
            SapDocumentLine.objects.create(
                document=document,
                line_num=line.get('line_num', index),
                item_code=line['item_code'],
                item_name=line.get('item_name', ''),
                quantity=Decimal(str(line['quantity'])),
                unit_price=Decimal(str(line.get('unit_price', '0'))),
                warehouse_code=line.get('warehouse_code', ''),
                base_entry=line.get('base_entry'),
                base_line=line.get('base_line'),
            )

        return Response(SapDocumentSerializer(document).data,
                        status=status.HTTP_201_CREATED)


class SapDocumentDetailView(APIView):
    """GET /api/documents/<pk>/ — document, lines and posting history."""

    def get(self, request, pk):
        document = _get_document_or_404(pk)
        if isinstance(document, Response):
            return document
        return Response(SapDocumentSerializer(document).data)


class SapDocumentLineView(APIView):
    """
    GET  /api/documents/<pk>/lines/   list lines
    POST /api/documents/<pk>/lines/   append a line
    """

    def get(self, request, pk):
        document = _get_document_or_404(pk)
        if isinstance(document, Response):
            return document
        return Response(
            SapDocumentLineSerializer(document.lines.all(), many=True).data)

    def post(self, request, pk):
        document = _get_document_or_404(pk)
        if isinstance(document, Response):
            return document

        serializer = SapDocumentLineSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        line = serializer.save(document=document)
        return Response(SapDocumentLineSerializer(line).data,
                        status=status.HTTP_201_CREATED)


class PreviewPayloadView(APIView):
    """
    GET /api/documents/<pk>/payload/ — the SAP payload, without posting.

    Same call for every family. The response shape differs per family
    because the products differ, not because this view knows anything.
    """

    def get(self, request, pk):
        document = _get_document_or_404(pk)
        if isinstance(document, Response):
            return document

        factory = get_factory(document.doc_family)
        return Response({
            'doc_family': document.doc_family,
            'factory': type(factory).__name__,
            'endpoint': factory.create_poster().endpoint,
            'header_builder': type(factory.create_header_builder()).__name__,
            'lines_builder': type(factory.create_lines_builder()).__name__,
            'payload': preview_payload(document),
        })


class PostDocumentView(APIView):
    """
    POST /api/documents/<pk>/post/ — build and send to SAP.

    No branch on doc_family anywhere in this method. That absence is the
    deliverable.
    """

    def post(self, request, pk):
        document = _get_document_or_404(pk)
        if isinstance(document, Response):
            return document

        if document.status == 'posted':
            return Response(
                {'error': f'{document.reference_no} is already posted as '
                          f'DocEntry {document.sap_doc_entry}.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        result = post_document(document)
        http_status = (status.HTTP_201_CREATED if result['success']
                       else status.HTTP_400_BAD_REQUEST)
        return Response(result, status=http_status)


class PostingLogView(APIView):
    """GET /api/documents/<pk>/posting-logs/ — every attempt, in order."""

    def get(self, request, pk):
        document = _get_document_or_404(pk)
        if isinstance(document, Response):
            return document
        return Response(
            SapPostingLogSerializer(document.posting_logs.all(), many=True).data)


class FamilyRegistryView(APIView):
    """
    GET /api/families/ — every family and the product trio it builds.

    This is the pattern rendered as JSON: four families, each with its own
    header builder, lines builder and endpoint.
    """

    def get(self, request):
        families = []
        for family, factory_class in SAP_DOCUMENT_FACTORIES.items():
            factory = factory_class()
            families.append({
                'doc_family': family,
                'factory': factory_class.__name__,
                'sap_object': factory.sap_object,
                'products': {
                    'header_builder': type(factory.create_header_builder()).__name__,
                    'lines_builder': type(factory.create_lines_builder()).__name__,
                    'poster': type(factory.create_poster()).__name__,
                },
            })
        return Response({'count': len(families), 'families': families})
