import threading
import time
import uuid


class SapConnectionManager:
    """
    Thread-safe Singleton for SAP B1 Service Layer connection.

    Production context:
        SapRepository.__construct() creates an expensive HTTP session to
        SAP B1 Service Layer (https://sap-b1.youngman.co.in:50000/b1s/v1).
        The login call alone takes 2-5 seconds and returns a session cookie
        (B1SESSION) that must be reused for all subsequent API calls.

    Why Singleton:
        Without it, every Django request would create a new SAP login session,
        overwhelming the SAP server and adding seconds of latency per request.
        The Singleton ensures ONE session is created and shared across all
        requests within the same process.

    Thread safety:
        Uses double-checked locking with threading.Lock to ensure that even
        under concurrent Django requests (via threads), only one instance
        is ever created.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:  # Double-checked locking
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, service_url='https://sap-b1.youngman.co.in:50000/b1s/v1'):
        if self._initialized:
            return
        self.service_url = service_url
        self.session_id = None
        self.company_db = 'YOUNGMAN_LIVE'
        self.connected_at = None
        self.request_count = 0
        self._initialized = True

    def connect(self) -> str:
        """
        Establish SAP B1 session (expensive operation - simulated).

        In production this would POST to /b1s/v1/Login with:
        {"CompanyDB": "YOUNGMAN_LIVE", "UserName": "manager", "Password": "..."}
        and store the returned B1SESSION cookie.
        """
        time.sleep(0.1)  # Simulate connection delay
        self.session_id = f"SAP-B1-{uuid.uuid4().hex[:12].upper()}"
        self.connected_at = time.time()
        self.request_count = 0
        # Save to DB
        from .models import SapConnection
        SapConnection.objects.create(
            service_url=self.service_url,
            session_id=self.session_id,
            company_db=self.company_db,
        )
        return self.session_id

    def get_session(self) -> str:
        """Return existing session or create one (lazy initialization)."""
        if not self.session_id:
            self.connect()
        return self.session_id

    def _log_request(self, entity_type, action, endpoint, success=True, error=''):
        """Log every SAP API call for audit trail."""
        self.request_count += 1
        from .models import ConnectionLog, SapConnection
        conn = SapConnection.objects.filter(session_id=self.session_id).first()
        if conn:
            conn.request_count = self.request_count
            conn.save()
            ConnectionLog.objects.create(
                connection=conn,
                entity_type=entity_type,
                action=action,
                endpoint=endpoint,
                success=success,
                error_message=error,
            )

    def post_invoice(self, invoice_data: dict) -> dict:
        """POST /Invoices - Create A/R Invoice in SAP B1."""
        session = self.get_session()
        self._log_request('Invoices', 'POST', f'{self.service_url}/Invoices')
        return {
            "session": session,
            "entity": "Invoices",
            "doc_entry": 1001 + self.request_count,
            "status": "success",
            "data": invoice_data,
        }

    def post_credit_note(self, cn_data: dict) -> dict:
        """POST /CreditNotes - Create A/R Credit Note in SAP B1."""
        session = self.get_session()
        self._log_request('CreditNotes', 'POST', f'{self.service_url}/CreditNotes')
        return {
            "session": session,
            "entity": "CreditNotes",
            "doc_entry": 2001 + self.request_count,
            "status": "success",
            "data": cn_data,
        }

    def add_journal_entry(self, je_data: dict) -> dict:
        """POST /JournalEntries - Create Journal Entry in SAP B1."""
        session = self.get_session()
        self._log_request('JournalEntries', 'POST', f'{self.service_url}/JournalEntries')
        return {
            "session": session,
            "entity": "JournalEntries",
            "trans_id": 3001 + self.request_count,
            "status": "success",
        }

    def get_business_partner(self, card_code: str) -> dict:
        """GET /BusinessPartners('C001') - Fetch BP from SAP B1."""
        session = self.get_session()
        endpoint = f"{self.service_url}/BusinessPartners('{card_code}')"
        self._log_request('BusinessPartners', 'GET', endpoint)
        return {
            "session": session,
            "card_code": card_code,
            "name": f"Customer {card_code}",
            "status": "success",
        }

    def disconnect(self):
        """
        POST /Logout - End SAP B1 session and reset singleton.
        In production this would POST to /b1s/v1/Logout to release the session.
        """
        if self.session_id:
            self._log_request('Session', 'POST', f'{self.service_url}/Logout')
            from .models import SapConnection
            SapConnection.objects.filter(session_id=self.session_id).update(is_active=False)
            self.session_id = None
            self._initialized = False
            SapConnectionManager._instance = None

    def get_status(self) -> dict:
        """Return current connection status including Python object id (singleton proof)."""
        return {
            "is_connected": self.session_id is not None,
            "session_id": self.session_id,
            "service_url": self.service_url,
            "company_db": self.company_db,
            "request_count": self.request_count,
            "instance_id": id(self),
        }

    @classmethod
    def reset(cls):
        """For testing - reset singleton instance so tests are isolated."""
        cls._instance = None
