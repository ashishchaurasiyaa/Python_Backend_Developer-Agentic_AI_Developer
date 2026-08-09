"""
API views for the Template Method report pipeline.

The important line in this whole file is inside ReportGenerateView:

    result = get_generator(report.report_type).generate(report)

The view picks a generator by report_type and calls generate(). It does NOT
know — and must not know — which of the nine steps that particular subclass
overrode. Adding a fifth report type means adding one generator class and one
registry entry; this view never changes. That is the payoff of putting the
algorithm skeleton in the base class.
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .generators import REPORT_GENERATORS, get_generator
from .models import GeneratedReport, Report
from .serializers import (
    AddRecipientSerializer,
    GeneratedReportListSerializer,
    GeneratedReportSerializer,
    ReportListSerializer,
    ReportSerializer,
    ReportRecipientSerializer,
)


def _get_report_or_404(pk):
    try:
        return Report.objects.get(pk=pk)
    except Report.DoesNotExist:
        return Response({'error': 'Report not found'},
                        status=status.HTTP_404_NOT_FOUND)


class ReportListView(APIView):
    """
    GET  /api/reports/   list report configurations
    POST /api/reports/   create a report configuration
    """

    def get(self, request):
        reports = Report.objects.all()
        report_type = request.query_params.get('report_type')
        if report_type:
            reports = reports.filter(report_type=report_type)
        serializer = ReportListSerializer(reports, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = ReportListSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        report = serializer.save()
        return Response(ReportSerializer(report).data,
                        status=status.HTTP_201_CREATED)


class ReportDetailView(APIView):
    """GET /api/reports/<pk>/ — configuration plus nested recipients."""

    def get(self, request, pk):
        report = _get_report_or_404(pk)
        if isinstance(report, Response):
            return report
        return Response(ReportSerializer(report).data)


class ReportGenerateView(APIView):
    """
    POST /api/reports/<pk>/generate/ — run the template method.

    Returns the dict produced by ReportGenerator.generate(), which includes
    `steps_executed` so a caller can see the fixed nine-step skeleton that
    every report type shares.
    """

    def post(self, request, pk):
        report = _get_report_or_404(pk)
        if isinstance(report, Response):
            return report

        if not report.is_active:
            return Response(
                {'status': 'skipped', 'message': 'Report is not active'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            generator = get_generator(report.report_type)
        except ValueError as exc:
            return Response({'error': str(exc)},
                            status=status.HTTP_400_BAD_REQUEST)

        result = generator.generate(report)
        result['generator_class'] = type(generator).__name__

        if result['status'] == 'empty':
            return Response(result, status=status.HTTP_200_OK)
        return Response(result, status=status.HTTP_201_CREATED)


class GeneratedReportListView(APIView):
    """GET /api/reports/<pk>/generated/ — audit trail of past runs."""

    def get(self, request, pk):
        report = _get_report_or_404(pk)
        if isinstance(report, Response):
            return report
        rows = GeneratedReport.objects.filter(report=report)
        return Response(GeneratedReportListSerializer(rows, many=True).data)


class GeneratedReportDetailView(APIView):
    """GET /api/generated/<pk>/ — one run including the produced file body."""

    def get(self, request, pk):
        try:
            generated = GeneratedReport.objects.get(pk=pk)
        except GeneratedReport.DoesNotExist:
            return Response({'error': 'Generated report not found'},
                            status=status.HTTP_404_NOT_FOUND)
        return Response(GeneratedReportSerializer(generated).data)


class ReportRecipientView(APIView):
    """
    GET  /api/reports/<pk>/recipients/   list recipients
    POST /api/reports/<pk>/recipients/   attach a recipient
    """

    def get(self, request, pk):
        report = _get_report_or_404(pk)
        if isinstance(report, Response):
            return report
        return Response(
            ReportRecipientSerializer(report.recipients.all(), many=True).data
        )

    def post(self, request, pk):
        report = _get_report_or_404(pk)
        if isinstance(report, Response):
            return report

        payload = AddRecipientSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        recipient = report.recipients.create(
            name=payload.validated_data['name'],
            email=payload.validated_data['email'],
        )
        return Response(ReportRecipientSerializer(recipient).data,
                        status=status.HTTP_201_CREATED)


class GeneratorRegistryView(APIView):
    """
    GET /api/generators/ — which report types the registry can serve.

    Useful in interviews: it shows the Open/Closed seam. A new report type
    appears here the moment its class is registered, with no view changes.
    """

    def get(self, request):
        return Response({
            'count': len(REPORT_GENERATORS),
            'generators': [
                {'report_type': key, 'generator_class': cls.__name__}
                for key, cls in REPORT_GENERATORS.items()
            ],
        })
