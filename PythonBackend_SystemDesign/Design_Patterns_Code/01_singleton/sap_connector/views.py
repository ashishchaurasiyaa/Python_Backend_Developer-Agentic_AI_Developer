from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .singleton import SapConnectionManager
from .models import SapConnection, ConnectionLog
from .serializers import SapConnectionSerializer, ConnectionLogSerializer


class ConnectionStatusView(APIView):
    """
    GET /api/connection/status/
    Returns current singleton status. Calling this multiple times proves the
    same Python object (same instance_id) is returned every time.
    """

    def get(self, request):
        manager = SapConnectionManager()
        return Response({
            "pattern": "Singleton",
            "description": "SapConnectionManager is a singleton - one SAP B1 session shared across all requests",
            "status": manager.get_status(),
        })


class ConnectionConnectView(APIView):
    """
    POST /api/connection/connect/
    Establish a new SAP B1 session through the singleton.
    """

    def post(self, request):
        manager = SapConnectionManager()
        if manager.session_id:
            return Response({
                "message": "Already connected - singleton reuses existing session",
                "session_id": manager.session_id,
                "instance_id": id(manager),
            }, status=status.HTTP_200_OK)

        session_id = manager.connect()
        return Response({
            "message": "SAP B1 session established via singleton",
            "session_id": session_id,
            "instance_id": id(manager),
        }, status=status.HTTP_201_CREATED)


class SapInvoiceView(APIView):
    """
    POST /api/sap/invoices/
    Create an A/R Invoice in SAP B1 through the singleton connection.
    """

    def post(self, request):
        manager = SapConnectionManager()
        invoice_data = request.data or {
            "CardCode": "C001",
            "DocDate": "2026-02-15",
            "DocumentLines": [
                {"ItemCode": "SCAFFOLD-001", "Quantity": 10, "UnitPrice": 1500.00}
            ],
        }
        result = manager.post_invoice(invoice_data)
        return Response({
            "message": "Invoice created via singleton SAP connection",
            "instance_id": id(manager),
            "result": result,
        }, status=status.HTTP_201_CREATED)


class SapCreditNoteView(APIView):
    """
    POST /api/sap/credit-notes/
    Create an A/R Credit Note in SAP B1 through the singleton connection.
    """

    def post(self, request):
        manager = SapConnectionManager()
        cn_data = request.data or {
            "CardCode": "C001",
            "DocDate": "2026-02-15",
            "DocumentLines": [
                {"ItemCode": "SCAFFOLD-001", "Quantity": 2, "UnitPrice": 1500.00}
            ],
        }
        result = manager.post_credit_note(cn_data)
        return Response({
            "message": "Credit Note created via singleton SAP connection",
            "instance_id": id(manager),
            "result": result,
        }, status=status.HTTP_201_CREATED)


class SapJournalEntryView(APIView):
    """
    POST /api/sap/journal-entries/
    Create a Journal Entry in SAP B1 through the singleton connection.
    """

    def post(self, request):
        manager = SapConnectionManager()
        je_data = request.data or {
            "ReferenceDate": "2026-02-15",
            "Memo": "Scaffold rental revenue",
            "JournalEntryLines": [
                {"AccountCode": "410000", "Debit": 15000.00},
                {"AccountCode": "110000", "Credit": 15000.00},
            ],
        }
        result = manager.add_journal_entry(je_data)
        return Response({
            "message": "Journal Entry created via singleton SAP connection",
            "instance_id": id(manager),
            "result": result,
        }, status=status.HTTP_201_CREATED)


class SapBusinessPartnerView(APIView):
    """
    GET /api/sap/business-partners/?card_code=C001
    Fetch a Business Partner from SAP B1 through the singleton connection.
    """

    def get(self, request):
        card_code = request.query_params.get('card_code', 'C001')
        manager = SapConnectionManager()
        result = manager.get_business_partner(card_code)
        return Response({
            "message": "Business Partner fetched via singleton SAP connection",
            "instance_id": id(manager),
            "result": result,
        })


class ConnectionLogsView(APIView):
    """
    GET /api/connection/logs/
    List all connection logs - audit trail of SAP API calls.
    """

    def get(self, request):
        logs = ConnectionLog.objects.select_related('connection').all()[:50]
        serializer = ConnectionLogSerializer(logs, many=True)
        connections = SapConnection.objects.all()[:10]
        conn_serializer = SapConnectionSerializer(connections, many=True)
        return Response({
            "connections": conn_serializer.data,
            "recent_logs": serializer.data,
        })


class ConnectionDisconnectView(APIView):
    """
    POST /api/connection/disconnect/
    Disconnect from SAP B1 and reset the singleton instance.
    Next call to any SAP method will create a new session.
    """

    def post(self, request):
        manager = SapConnectionManager()
        old_session = manager.session_id
        if not old_session:
            return Response({
                "message": "No active SAP connection to disconnect",
            }, status=status.HTTP_400_BAD_REQUEST)

        manager.disconnect()
        return Response({
            "message": "SAP B1 session disconnected and singleton reset",
            "disconnected_session": old_session,
        })


class SingletonProofView(APIView):
    """
    GET /api/singleton-proof/
    Creates TWO SapConnectionManager instances and proves they are the
    exact same Python object (same memory address / id).
    This is the definitive proof of the Singleton pattern.
    """

    def get(self, request):
        instance_a = SapConnectionManager()
        instance_b = SapConnectionManager()

        return Response({
            "pattern": "Singleton",
            "proof": {
                "instance_a_id": id(instance_a),
                "instance_b_id": id(instance_b),
                "are_same_object": instance_a is instance_b,
                "id_match": id(instance_a) == id(instance_b),
            },
            "explanation": (
                "Both variables point to the SAME Python object in memory. "
                "SapConnectionManager() always returns the same instance, "
                "so SAP B1 session is never duplicated. "
                "This is exactly how Youngman's SapService works - "
                "SapRepository.__construct() creates ONE expensive HTTP session "
                "and the singleton ensures it is reused everywhere."
            ),
            "instance_a_status": instance_a.get_status(),
            "instance_b_status": instance_b.get_status(),
        })
