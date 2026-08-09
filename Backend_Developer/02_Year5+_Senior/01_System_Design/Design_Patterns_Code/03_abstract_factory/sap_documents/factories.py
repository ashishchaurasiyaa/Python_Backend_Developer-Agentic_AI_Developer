"""
Abstract Factory — SAP Business One document families.
======================================================

THE PROBLEM THIS SOLVES
-----------------------
Posting a document to SAP Business One needs THREE things that must all
agree with each other:

    1. a header payload   (CardCode / DocObjectCode / warehouses / ...)
    2. a lines payload    (BaseEntry for returns, FromWarehouseCode for
                           transfers, UnitPrice for invoices, ...)
    3. an endpoint        ('DeliveryNotes', 'Returns', 'StockTransfers',
                           'Invoices')

Get any ONE of them from the wrong family and SAP either rejects the call
or — much worse — silently books the wrong document. A Return posted with
Delivery Note lines has no BaseEntry, so stock comes back into the system
with no link to what went out, and the reconciliation report is wrong for
the rest of the financial year.

Factory Method would only solve one product at a time. Abstract Factory is
the pattern for a FAMILY of products that must be created together and must
stay mutually consistent.

THE SHAPE
---------
    SapDocumentFactory (abstract factory)
        create_header_builder()  -> HeaderBuilder   (abstract product A)
        create_lines_builder()   -> LinesBuilder    (abstract product B)
        create_poster()          -> DocumentPoster  (abstract product C)

    DeliveryNoteFactory / ReturnFactory / InventoryTransferFactory /
    InvoiceFactory  are the concrete factories. Each one returns the three
    products that belong to ITS family and no other.

    SapPostingClient is the client code. Note that it names the abstract
    factory type in its constructor and never mentions a concrete product
    class anywhere. Adding a fifth family (Purchase Delivery Notes, say)
    means writing one factory plus three products and adding one registry
    entry — this file's client code and every view stay untouched. That is
    the Open/Closed Principle paying rent.

WHY THE MISMATCH GUARD EXISTS
-----------------------------
Every header carries SAP's `DocObjectCode`, and every poster checks it
before sending. In production SAP itself would reject the mismatch; here
the guard makes the pattern's central promise *testable* — see
FamilyConsistencyTests in tests.py, which deliberately hand-assembles a
mismatched pair to prove the guard fires.
"""
from abc import ABC, abstractmethod


# ----------------------------------------------------------------------
# Errors
# ----------------------------------------------------------------------

class SapPostingError(Exception):
    """Base class for anything that stops a document reaching SAP."""


class SapFamilyMismatchError(SapPostingError):
    """A payload from one family was handed to another family's poster."""


class SapValidationError(SapPostingError):
    """The payload is internally invalid for its own family."""


# ----------------------------------------------------------------------
# Fake SAP Service Layer — deterministic stand-in for the real HTTP API.
# ----------------------------------------------------------------------

_SAP_SEQUENCE = {}


def reset_sap_sequence():
    """Reset the fake SAP DocEntry counters. Call this in test setUp."""
    _SAP_SEQUENCE.clear()


def _next_sap_doc_entry(endpoint):
    """SAP numbers each object type on its own sequence; so do we."""
    _SAP_SEQUENCE[endpoint] = _SAP_SEQUENCE.get(endpoint, 0) + 1
    return _SAP_SEQUENCE[endpoint]


# ----------------------------------------------------------------------
# ABSTRACT PRODUCTS
# ----------------------------------------------------------------------

class HeaderBuilder(ABC):
    """Abstract Product A — builds the SAP document header."""

    #: SAP's own discriminator, e.g. 'oDeliveryNotes'.
    doc_object_code = None

    @abstractmethod
    def build(self, document) -> dict:
        """Return the header portion of the SAP payload."""

    def _common_fields(self, document) -> dict:
        """Fields every SAP document header carries, whatever the family."""
        return {
            'DocObjectCode': self.doc_object_code,
            'DocDate': document.posting_date.isoformat(),
            'DocDueDate': document.posting_date.isoformat(),
            'Comments': document.comments,
            'U_ReferenceNo': document.reference_no,
        }


class LinesBuilder(ABC):
    """Abstract Product B — builds the SAP DocumentLines array."""

    @abstractmethod
    def build(self, document) -> list:
        """Return the list of line dicts for the SAP payload."""

    def _base_line(self, line) -> dict:
        """The fields every family puts on every line."""
        return {
            'LineNum': line.line_num,
            'ItemCode': line.item_code,
            'Quantity': float(line.quantity),
        }


class DocumentPoster(ABC):
    """Abstract Product C — knows the endpoint and posts the payload."""

    #: SAP Service Layer object name.
    endpoint = None
    #: The DocObjectCode this poster will accept.
    accepts_object_code = None

    @abstractmethod
    def validate(self, payload):
        """Family-specific payload checks. Raise SapValidationError to reject."""

    def post(self, payload) -> dict:
        """
        Push the payload to SAP.

        The family guard runs FIRST and is deliberately not overridable by
        subclasses — it is the invariant the whole pattern exists to protect.
        """
        object_code = payload.get('DocObjectCode')
        if object_code != self.accepts_object_code:
            raise SapFamilyMismatchError(
                f"{type(self).__name__} posts to '{self.endpoint}' and only "
                f"accepts '{self.accepts_object_code}', but the payload is "
                f"'{object_code}'. Mixing document families is not allowed."
            )

        self.validate(payload)

        doc_entry = _next_sap_doc_entry(self.endpoint)
        return {
            'success': True,
            'endpoint': self.endpoint,
            'DocEntry': doc_entry,
            'DocNum': 1000 + doc_entry,
        }


# ----------------------------------------------------------------------
# ABSTRACT FACTORY
# ----------------------------------------------------------------------

class SapDocumentFactory(ABC):
    """
    The Abstract Factory itself.

    Three creators, one per abstract product. A concrete factory implements
    all three and — this is the invariant — returns products that belong to
    the SAME family.
    """

    #: doc_family value this factory serves.
    family = None
    #: SAP Service Layer object this family posts to.
    sap_object = None

    @abstractmethod
    def create_header_builder(self) -> HeaderBuilder:
        """Product A."""

    @abstractmethod
    def create_lines_builder(self) -> LinesBuilder:
        """Product B."""

    @abstractmethod
    def create_poster(self) -> DocumentPoster:
        """Product C."""

    def build_payload(self, document) -> dict:
        """
        Assemble the complete SAP payload using THIS family's products only.

        The client never calls the three creators itself, so it cannot
        accidentally combine a header from one family with lines from
        another — the mistake the pattern exists to prevent.
        """
        header = self.create_header_builder().build(document)
        header['DocumentLines'] = self.create_lines_builder().build(document)
        return header


# ----------------------------------------------------------------------
# FAMILY 1 — Delivery Note  (material going out to a customer site)
# ----------------------------------------------------------------------

class DeliveryHeaderBuilder(HeaderBuilder):
    doc_object_code = 'oDeliveryNotes'

    def build(self, document):
        header = self._common_fields(document)
        header.update({
            'CardCode': document.card_code,
            'CardName': document.card_name,
            # Goods leave a warehouse; there is no receiving warehouse.
            'U_FromWarehouse': document.from_warehouse,
        })
        return header


class DeliveryLinesBuilder(LinesBuilder):
    def build(self, document):
        lines = []
        for line in document.lines.all():
            row = self._base_line(line)
            row['WarehouseCode'] = line.warehouse_code or document.from_warehouse
            row['UnitPrice'] = float(line.unit_price)
            lines.append(row)
        return lines


class DeliveryPoster(DocumentPoster):
    endpoint = 'DeliveryNotes'
    accepts_object_code = 'oDeliveryNotes'

    def validate(self, payload):
        if not payload.get('CardCode'):
            raise SapValidationError(
                'A Delivery Note needs a CardCode — SAP will not accept a '
                'delivery with no business partner.'
            )
        if not payload.get('DocumentLines'):
            raise SapValidationError('A Delivery Note needs at least one line.')
        for row in payload['DocumentLines']:
            if not row.get('WarehouseCode'):
                raise SapValidationError(
                    f"Line {row.get('LineNum')} has no WarehouseCode; SAP "
                    f"cannot decide which stock to relieve."
                )


class DeliveryNoteFactory(SapDocumentFactory):
    """Concrete Factory — the Delivery Note family."""

    family = 'delivery'
    sap_object = 'DeliveryNotes'

    def create_header_builder(self):
        return DeliveryHeaderBuilder()

    def create_lines_builder(self):
        return DeliveryLinesBuilder()

    def create_poster(self):
        return DeliveryPoster()


# ----------------------------------------------------------------------
# FAMILY 2 — Return  (material coming back from site)
# ----------------------------------------------------------------------

class ReturnHeaderBuilder(HeaderBuilder):
    doc_object_code = 'oReturns'

    def build(self, document):
        header = self._common_fields(document)
        header.update({
            'CardCode': document.card_code,
            'CardName': document.card_name,
            # Goods come BACK, so the warehouse is the receiving one.
            'U_ToWarehouse': document.to_warehouse,
            'U_ReturnReason': document.return_reason,
        })
        return header


class ReturnLinesBuilder(LinesBuilder):
    def build(self, document):
        lines = []
        for line in document.lines.all():
            row = self._base_line(line)
            row['WarehouseCode'] = line.warehouse_code or document.to_warehouse
            # THE field that makes this family different: a Return must
            # point at the Delivery Note it reverses.
            row['BaseType'] = 15          # SAP object type for Delivery Notes
            row['BaseEntry'] = line.base_entry
            row['BaseLine'] = line.base_line
            lines.append(row)
        return lines


class ReturnPoster(DocumentPoster):
    endpoint = 'Returns'
    accepts_object_code = 'oReturns'

    def validate(self, payload):
        if not payload.get('CardCode'):
            raise SapValidationError('A Return needs a CardCode.')
        if not payload.get('DocumentLines'):
            raise SapValidationError('A Return needs at least one line.')
        for row in payload['DocumentLines']:
            if row.get('BaseEntry') is None:
                raise SapValidationError(
                    f"Line {row.get('LineNum')} has no BaseEntry. A Return "
                    f"must reference the Delivery Note it reverses, or the "
                    f"stock comes back unlinked."
                )


class ReturnFactory(SapDocumentFactory):
    """Concrete Factory — the Return family."""

    family = 'return'
    sap_object = 'Returns'

    def create_header_builder(self):
        return ReturnHeaderBuilder()

    def create_lines_builder(self):
        return ReturnLinesBuilder()

    def create_poster(self):
        return ReturnPoster()


# ----------------------------------------------------------------------
# FAMILY 3 — Inventory Transfer  (branch to branch, no customer involved)
# ----------------------------------------------------------------------

class TransferHeaderBuilder(HeaderBuilder):
    doc_object_code = 'oStockTransfer'

    def build(self, document):
        header = self._common_fields(document)
        # Note what is ABSENT: no CardCode. An internal transfer has no
        # business partner, and this is the clearest proof that families
        # are genuinely different rather than cosmetic variants.
        header.update({
            'FromWarehouse': document.from_warehouse,
            'ToWarehouse': document.to_warehouse,
        })
        return header


class TransferLinesBuilder(LinesBuilder):
    def build(self, document):
        lines = []
        for line in document.lines.all():
            row = self._base_line(line)
            row['FromWarehouseCode'] = document.from_warehouse
            row['WarehouseCode'] = document.to_warehouse
            lines.append(row)
        return lines


class TransferPoster(DocumentPoster):
    endpoint = 'StockTransfers'
    accepts_object_code = 'oStockTransfer'

    def validate(self, payload):
        if payload.get('CardCode'):
            raise SapValidationError(
                'An Inventory Transfer must NOT carry a CardCode — it is an '
                'internal movement, not a customer transaction.'
            )
        from_wh = payload.get('FromWarehouse')
        to_wh = payload.get('ToWarehouse')
        if not from_wh or not to_wh:
            raise SapValidationError(
                'An Inventory Transfer needs both FromWarehouse and ToWarehouse.'
            )
        if from_wh == to_wh:
            raise SapValidationError(
                f"FromWarehouse and ToWarehouse are both '{from_wh}'. "
                f"A transfer to itself is not a movement."
            )
        if not payload.get('DocumentLines'):
            raise SapValidationError('An Inventory Transfer needs at least one line.')


class InventoryTransferFactory(SapDocumentFactory):
    """Concrete Factory — the Inventory Transfer family."""

    family = 'transfer'
    sap_object = 'StockTransfers'

    def create_header_builder(self):
        return TransferHeaderBuilder()

    def create_lines_builder(self):
        return TransferLinesBuilder()

    def create_poster(self):
        return TransferPoster()


# ----------------------------------------------------------------------
# FAMILY 4 — A/R Invoice  (the billable event)
# ----------------------------------------------------------------------

class InvoiceHeaderBuilder(HeaderBuilder):
    doc_object_code = 'oInvoices'

    def build(self, document):
        header = self._common_fields(document)
        header.update({
            'CardCode': document.card_code,
            'CardName': document.card_name,
            'DocCurrency': 'INR',
            'DocTotal': float(document.doc_total),
        })
        return header


class InvoiceLinesBuilder(LinesBuilder):
    def build(self, document):
        lines = []
        for line in document.lines.all():
            row = self._base_line(line)
            row['WarehouseCode'] = line.warehouse_code or document.from_warehouse
            row['UnitPrice'] = float(line.unit_price)
            row['LineTotal'] = float(line.quantity * line.unit_price)
            row['TaxCode'] = 'GST18'
            lines.append(row)
        return lines


class InvoicePoster(DocumentPoster):
    endpoint = 'Invoices'
    accepts_object_code = 'oInvoices'

    def validate(self, payload):
        if not payload.get('CardCode'):
            raise SapValidationError('An Invoice needs a CardCode.')
        if not payload.get('DocumentLines'):
            raise SapValidationError('An Invoice needs at least one line.')
        for row in payload['DocumentLines']:
            if not row.get('UnitPrice'):
                raise SapValidationError(
                    f"Line {row.get('LineNum')} has no UnitPrice. An invoice "
                    f"line worth nothing is always a data-entry bug."
                )
            if not row.get('TaxCode'):
                raise SapValidationError(
                    f"Line {row.get('LineNum')} has no TaxCode."
                )


class InvoiceFactory(SapDocumentFactory):
    """Concrete Factory — the A/R Invoice family."""

    family = 'invoice'
    sap_object = 'Invoices'

    def create_header_builder(self):
        return InvoiceHeaderBuilder()

    def create_lines_builder(self):
        return InvoiceLinesBuilder()

    def create_poster(self):
        return InvoicePoster()


# ----------------------------------------------------------------------
# REGISTRY — the one place that maps a family string to a factory.
# ----------------------------------------------------------------------

SAP_DOCUMENT_FACTORIES = {
    'delivery': DeliveryNoteFactory,
    'return': ReturnFactory,
    'transfer': InventoryTransferFactory,
    'invoice': InvoiceFactory,
}


def get_factory(doc_family):
    """
    Return the concrete factory for a document family.

    This function is the ONLY place in the codebase that knows a concrete
    factory class by name. Everything else depends on the abstract interface.
    """
    factory_class = SAP_DOCUMENT_FACTORIES.get(doc_family)
    if factory_class is None:
        raise ValueError(
            f"Unknown SAP document family: '{doc_family}'. "
            f"Known families: {sorted(SAP_DOCUMENT_FACTORIES)}"
        )
    return factory_class()


# ----------------------------------------------------------------------
# CLIENT CODE
# ----------------------------------------------------------------------

class SapPostingClient:
    """
    The client of the Abstract Factory.

    Read the body of `post` and notice what is NOT there: no `if
    doc_family == 'return'`, no concrete product class, no endpoint string.
    The client works against the abstract factory and abstract products
    only. That is the acceptance test for whether you have actually applied
    the pattern or merely arranged some classes.
    """

    def __init__(self, factory: SapDocumentFactory):
        self.factory = factory

    def post(self, document):
        """
        Build and post one document, recording the attempt either way.

        Returns a result dict; never raises for a business-level rejection,
        because a failed SAP post is a normal outcome that belongs in the
        audit log rather than a 500.
        """
        from .models import SapPostingLog

        poster = self.factory.create_poster()
        payload = self.factory.build_payload(document)

        try:
            result = poster.post(payload)
        except SapPostingError as exc:
            document.status = 'failed'
            document.error_message = str(exc)
            document.save(update_fields=['status', 'error_message'])
            SapPostingLog.objects.create(
                document=document,
                factory_used=type(self.factory).__name__,
                endpoint=poster.endpoint,
                succeeded=False,
                message=str(exc),
            )
            return {
                'success': False,
                'error': str(exc),
                'error_type': type(exc).__name__,
                'endpoint': poster.endpoint,
                'payload': payload,
            }

        document.status = 'posted'
        document.sap_doc_entry = result['DocEntry']
        document.sap_doc_num = result['DocNum']
        document.error_message = ''
        document.save(update_fields=[
            'status', 'sap_doc_entry', 'sap_doc_num', 'error_message'])
        SapPostingLog.objects.create(
            document=document,
            factory_used=type(self.factory).__name__,
            endpoint=poster.endpoint,
            succeeded=True,
            message=f"Posted as DocEntry {result['DocEntry']}",
        )

        result['payload'] = payload
        result['factory_used'] = type(self.factory).__name__
        return result


def post_document(document):
    """Convenience entry point: pick the family's factory and post."""
    return SapPostingClient(get_factory(document.doc_family)).post(document)


def preview_payload(document):
    """Build the payload without posting — handy for debugging and for the API."""
    return get_factory(document.doc_family).build_payload(document)
