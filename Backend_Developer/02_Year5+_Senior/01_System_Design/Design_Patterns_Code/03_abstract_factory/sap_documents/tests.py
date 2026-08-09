"""
Tests for the Abstract Factory pattern (SapDocumentFactory + four SAP
document families).

Behavioural guarantee under test: asking a concrete factory for its three
products always yields a MUTUALLY CONSISTENT trio — header, lines and
endpoint from the same SAP document family. The client code selects a
family once and can never afterwards combine a Delivery header with a
Return poster.

FamilyConsistencyTests is the class that matters most. It hand-assembles
the mismatched combinations that the pattern is designed to make
unreachable, and proves they are rejected — because a test suite that only
ever exercises the happy path cannot tell a real Abstract Factory apart
from four unrelated helper functions that happen to be named alike.
"""
from datetime import date
from decimal import Decimal

from django.db import IntegrityError
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from .factories import (
    SAP_DOCUMENT_FACTORIES,
    DeliveryHeaderBuilder,
    DeliveryLinesBuilder,
    DeliveryNoteFactory,
    DeliveryPoster,
    DocumentPoster,
    HeaderBuilder,
    InventoryTransferFactory,
    InvoiceFactory,
    InvoiceHeaderBuilder,
    InvoiceLinesBuilder,
    InvoicePoster,
    LinesBuilder,
    ReturnFactory,
    ReturnHeaderBuilder,
    ReturnLinesBuilder,
    ReturnPoster,
    SapDocumentFactory,
    SapFamilyMismatchError,
    SapPostingClient,
    SapPostingError,
    SapValidationError,
    TransferHeaderBuilder,
    TransferLinesBuilder,
    TransferPoster,
    get_factory,
    post_document,
    preview_payload,
    reset_sap_sequence,
)
from .models import SapDocument, SapDocumentLine, SapPostingLog


def make_document(**overrides):
    defaults = dict(
        doc_family='delivery',
        reference_no='DC-000101',
        card_code='C00421',
        card_name='Metro Constructions Pvt Ltd',
        from_warehouse='MUM-01',
        posting_date=date(2026, 8, 8),
        comments='Site delivery for Worli tower',
    )
    defaults.update(overrides)
    return SapDocument.objects.create(**defaults)


def add_line(document, **overrides):
    defaults = dict(
        line_num=document.lines.count(),
        item_code='SCAF-01',
        item_name='Standard Frame',
        quantity=Decimal('250.000'),
        unit_price=Decimal('120.00'),
        warehouse_code='MUM-01',
    )
    defaults.update(overrides)
    return SapDocumentLine.objects.create(document=document, **defaults)


def delivery_document():
    doc = make_document()
    add_line(doc)
    return doc


def return_document():
    doc = make_document(
        doc_family='return', reference_no='PC-000055',
        from_warehouse='', to_warehouse='MUM-01',
        return_reason='Project completed')
    add_line(doc, warehouse_code='MUM-01', base_entry=41, base_line=0)
    return doc


def transfer_document():
    doc = make_document(
        doc_family='transfer', reference_no='TR-000012',
        card_code='', card_name='',
        from_warehouse='MUM-01', to_warehouse='DEL-02')
    add_line(doc, warehouse_code='')
    return doc


def invoice_document():
    doc = make_document(
        doc_family='invoice', reference_no='INV-000900',
        doc_total=Decimal('30000.00'))
    add_line(doc, quantity=Decimal('250.000'), unit_price=Decimal('120.00'))
    return doc


class SapTestCase(TestCase):
    """Base class that keeps the fake SAP DocEntry sequence deterministic."""

    def setUp(self):
        reset_sap_sequence()


class AbstractInterfaceTests(SapTestCase):
    """The abstract layer must actually be abstract."""

    def test_the_abstract_factory_cannot_be_instantiated(self):
        with self.assertRaises(TypeError):
            SapDocumentFactory()

    def test_the_abstract_products_cannot_be_instantiated(self):
        for abstract_product in (HeaderBuilder, LinesBuilder, DocumentPoster):
            with self.assertRaises(TypeError):
                abstract_product()

    def test_a_factory_missing_a_creator_cannot_be_instantiated(self):
        class HalfFinishedFactory(SapDocumentFactory):
            family = 'half'

            def create_header_builder(self):
                return DeliveryHeaderBuilder()

            # create_lines_builder and create_poster are missing.

        with self.assertRaises(TypeError):
            HalfFinishedFactory()

    def test_every_concrete_factory_implements_the_abstract_factory(self):
        for family, factory_class in SAP_DOCUMENT_FACTORIES.items():
            self.assertTrue(issubclass(factory_class, SapDocumentFactory), family)

    def test_every_factory_declares_its_family_and_sap_object(self):
        for family, factory_class in SAP_DOCUMENT_FACTORIES.items():
            factory = factory_class()
            self.assertEqual(factory.family, family)
            self.assertTrue(factory.sap_object)

    def test_every_factory_returns_products_of_the_abstract_types(self):
        for factory_class in SAP_DOCUMENT_FACTORIES.values():
            factory = factory_class()
            self.assertIsInstance(factory.create_header_builder(), HeaderBuilder)
            self.assertIsInstance(factory.create_lines_builder(), LinesBuilder)
            self.assertIsInstance(factory.create_poster(), DocumentPoster)

    def test_creators_return_a_fresh_product_each_call(self):
        # Products must not be shared singletons - they are cheap, and
        # sharing them would make the factory stateful across documents.
        factory = DeliveryNoteFactory()
        self.assertIsNot(factory.create_header_builder(),
                         factory.create_header_builder())
        self.assertIsNot(factory.create_poster(), factory.create_poster())


class RegistryTests(SapTestCase):
    def test_registry_covers_every_doc_family_choice_on_the_model(self):
        model_families = {value for value, _ in SapDocument.DOC_FAMILY_CHOICES}
        self.assertEqual(set(SAP_DOCUMENT_FACTORIES.keys()), model_families)

    def test_get_factory_returns_the_matching_concrete_factory(self):
        self.assertIsInstance(get_factory('delivery'), DeliveryNoteFactory)
        self.assertIsInstance(get_factory('return'), ReturnFactory)
        self.assertIsInstance(get_factory('transfer'), InventoryTransferFactory)
        self.assertIsInstance(get_factory('invoice'), InvoiceFactory)

    def test_an_unknown_family_raises_with_a_helpful_message(self):
        with self.assertRaises(ValueError) as ctx:
            get_factory('purchase_order')
        self.assertIn('purchase_order', str(ctx.exception))
        self.assertIn('delivery', str(ctx.exception))

    def test_each_family_maps_to_a_distinct_sap_endpoint(self):
        endpoints = [factory_class().create_poster().endpoint
                     for factory_class in SAP_DOCUMENT_FACTORIES.values()]
        self.assertEqual(len(endpoints), len(set(endpoints)))


class FamilyConsistencyTests(SapTestCase):
    """
    The heart of the pattern.

    Every product trio produced by one factory must agree, and every
    hand-assembled cross-family combination must be rejected.
    """

    def test_each_factory_produces_a_self_consistent_trio(self):
        for factory_class in SAP_DOCUMENT_FACTORIES.values():
            factory = factory_class()
            header_builder = factory.create_header_builder()
            poster = factory.create_poster()

            self.assertEqual(
                header_builder.doc_object_code, poster.accepts_object_code,
                f'{factory_class.__name__} builds a header its own poster '
                f'would reject',
            )
            self.assertEqual(poster.endpoint, factory.sap_object)

    def test_a_delivery_payload_is_refused_by_the_returns_endpoint(self):
        document = delivery_document()
        payload = DeliveryNoteFactory().build_payload(document)

        with self.assertRaises(SapFamilyMismatchError) as ctx:
            ReturnPoster().post(payload)

        self.assertIn('oDeliveryNotes', str(ctx.exception))
        self.assertIn('oReturns', str(ctx.exception))

    def test_a_return_payload_is_refused_by_the_delivery_endpoint(self):
        document = return_document()
        payload = ReturnFactory().build_payload(document)

        with self.assertRaises(SapFamilyMismatchError):
            DeliveryPoster().post(payload)

    def test_a_transfer_payload_is_refused_by_the_invoice_endpoint(self):
        document = transfer_document()
        payload = InventoryTransferFactory().build_payload(document)

        with self.assertRaises(SapFamilyMismatchError):
            InvoicePoster().post(payload)

    def test_every_cross_family_combination_is_rejected(self):
        documents = {
            'delivery': delivery_document(),
            'return': return_document(),
            'transfer': transfer_document(),
            'invoice': invoice_document(),
        }
        payloads = {
            family: get_factory(family).build_payload(document)
            for family, document in documents.items()
        }

        for payload_family, payload in payloads.items():
            for poster_family, factory_class in SAP_DOCUMENT_FACTORIES.items():
                poster = factory_class().create_poster()
                if payload_family == poster_family:
                    continue  # matching pair - covered by the happy-path tests
                with self.assertRaises(
                    SapFamilyMismatchError,
                    msg=f'{payload_family} payload was accepted by '
                        f'{poster_family} poster',
                ):
                    poster.post(payload)

    def test_mixing_a_header_from_one_family_with_lines_from_another_is_caught(self):
        # This is the bug the pattern removes. Hand-built here precisely
        # because build_payload() makes it impossible to write by accident.
        document = return_document()
        frankenstein = ReturnHeaderBuilder().build(document)
        frankenstein['DocumentLines'] = DeliveryLinesBuilder().build(document)

        # The header says 'oReturns' so it reaches the right endpoint, but
        # the Delivery lines carry no BaseEntry - caught by validation.
        with self.assertRaises(SapValidationError) as ctx:
            ReturnPoster().post(frankenstein)
        self.assertIn('BaseEntry', str(ctx.exception))

    def test_build_payload_never_mixes_families(self):
        # Whatever the family, the DocObjectCode on the assembled payload
        # matches the poster the same factory hands out.
        for family in SAP_DOCUMENT_FACTORIES:
            document = {
                'delivery': delivery_document,
                'return': return_document,
                'transfer': transfer_document,
                'invoice': invoice_document,
            }[family]()
            factory = get_factory(family)
            payload = factory.build_payload(document)
            self.assertEqual(payload['DocObjectCode'],
                             factory.create_poster().accepts_object_code)
            document.delete()


class DeliveryFamilyTests(SapTestCase):
    def test_header_carries_the_business_partner_and_object_code(self):
        header = DeliveryHeaderBuilder().build(delivery_document())
        self.assertEqual(header['DocObjectCode'], 'oDeliveryNotes')
        self.assertEqual(header['CardCode'], 'C00421')
        self.assertEqual(header['U_FromWarehouse'], 'MUM-01')
        self.assertEqual(header['U_ReferenceNo'], 'DC-000101')

    def test_lines_carry_the_issuing_warehouse(self):
        lines = DeliveryLinesBuilder().build(delivery_document())
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]['WarehouseCode'], 'MUM-01')
        self.assertEqual(lines[0]['ItemCode'], 'SCAF-01')
        self.assertEqual(lines[0]['Quantity'], 250.0)

    def test_lines_fall_back_to_the_document_warehouse(self):
        document = make_document()
        add_line(document, warehouse_code='')
        lines = DeliveryLinesBuilder().build(document)
        self.assertEqual(lines[0]['WarehouseCode'], 'MUM-01')

    def test_posting_without_a_card_code_is_rejected(self):
        document = make_document(card_code='')
        add_line(document)
        payload = DeliveryNoteFactory().build_payload(document)

        with self.assertRaises(SapValidationError) as ctx:
            DeliveryPoster().post(payload)
        self.assertIn('CardCode', str(ctx.exception))

    def test_posting_with_no_lines_is_rejected(self):
        payload = DeliveryNoteFactory().build_payload(make_document())
        with self.assertRaises(SapValidationError):
            DeliveryPoster().post(payload)

    def test_a_line_with_no_warehouse_anywhere_is_rejected(self):
        document = make_document(from_warehouse='')
        add_line(document, warehouse_code='')
        payload = DeliveryNoteFactory().build_payload(document)

        with self.assertRaises(SapValidationError) as ctx:
            DeliveryPoster().post(payload)
        self.assertIn('WarehouseCode', str(ctx.exception))


class ReturnFamilyTests(SapTestCase):
    def test_header_carries_the_receiving_warehouse_and_reason(self):
        header = ReturnHeaderBuilder().build(return_document())
        self.assertEqual(header['DocObjectCode'], 'oReturns')
        self.assertEqual(header['U_ToWarehouse'], 'MUM-01')
        self.assertEqual(header['U_ReturnReason'], 'Project completed')

    def test_lines_reference_the_delivery_note_being_reversed(self):
        lines = ReturnLinesBuilder().build(return_document())
        self.assertEqual(lines[0]['BaseType'], 15)
        self.assertEqual(lines[0]['BaseEntry'], 41)
        self.assertEqual(lines[0]['BaseLine'], 0)

    def test_a_return_line_without_a_base_entry_is_rejected(self):
        document = make_document(
            doc_family='return', reference_no='PC-000056', to_warehouse='MUM-01')
        add_line(document, base_entry=None)
        payload = ReturnFactory().build_payload(document)

        with self.assertRaises(SapValidationError) as ctx:
            ReturnPoster().post(payload)
        self.assertIn('BaseEntry', str(ctx.exception))

    def test_delivery_lines_never_carry_base_entry(self):
        # Proof that the two lines builders genuinely differ rather than
        # sharing one implementation with a flag.
        delivery_lines = DeliveryLinesBuilder().build(return_document())
        self.assertNotIn('BaseEntry', delivery_lines[0])


class TransferFamilyTests(SapTestCase):
    def test_header_has_no_business_partner(self):
        header = TransferHeaderBuilder().build(transfer_document())
        self.assertEqual(header['DocObjectCode'], 'oStockTransfer')
        self.assertNotIn('CardCode', header)
        self.assertEqual(header['FromWarehouse'], 'MUM-01')
        self.assertEqual(header['ToWarehouse'], 'DEL-02')

    def test_lines_name_both_the_source_and_destination_warehouse(self):
        lines = TransferLinesBuilder().build(transfer_document())
        self.assertEqual(lines[0]['FromWarehouseCode'], 'MUM-01')
        self.assertEqual(lines[0]['WarehouseCode'], 'DEL-02')

    def test_a_transfer_carrying_a_card_code_is_rejected(self):
        document = transfer_document()
        payload = InventoryTransferFactory().build_payload(document)
        payload['CardCode'] = 'C00421'  # smuggled in by hand

        with self.assertRaises(SapValidationError) as ctx:
            TransferPoster().post(payload)
        self.assertIn('CardCode', str(ctx.exception))

    def test_a_transfer_to_the_same_warehouse_is_rejected(self):
        document = make_document(
            doc_family='transfer', reference_no='TR-000013',
            card_code='', from_warehouse='MUM-01', to_warehouse='MUM-01')
        add_line(document)
        payload = InventoryTransferFactory().build_payload(document)

        with self.assertRaises(SapValidationError) as ctx:
            TransferPoster().post(payload)
        self.assertIn('transfer to itself', str(ctx.exception))

    def test_a_transfer_missing_a_warehouse_is_rejected(self):
        document = make_document(
            doc_family='transfer', reference_no='TR-000014',
            card_code='', from_warehouse='MUM-01', to_warehouse='')
        add_line(document)
        payload = InventoryTransferFactory().build_payload(document)

        with self.assertRaises(SapValidationError):
            TransferPoster().post(payload)


class InvoiceFamilyTests(SapTestCase):
    def test_header_carries_currency_and_total(self):
        header = InvoiceHeaderBuilder().build(invoice_document())
        self.assertEqual(header['DocObjectCode'], 'oInvoices')
        self.assertEqual(header['DocCurrency'], 'INR')
        self.assertEqual(header['DocTotal'], 30000.0)

    def test_lines_carry_price_tax_and_computed_line_total(self):
        lines = InvoiceLinesBuilder().build(invoice_document())
        self.assertEqual(lines[0]['UnitPrice'], 120.0)
        self.assertEqual(lines[0]['TaxCode'], 'GST18')
        self.assertEqual(lines[0]['LineTotal'], 30000.0)  # 250 * 120

    def test_a_zero_priced_invoice_line_is_rejected(self):
        document = make_document(
            doc_family='invoice', reference_no='INV-000901')
        add_line(document, unit_price=Decimal('0.00'))
        payload = InvoiceFactory().build_payload(document)

        with self.assertRaises(SapValidationError) as ctx:
            InvoicePoster().post(payload)
        self.assertIn('UnitPrice', str(ctx.exception))

    def test_delivery_lines_carry_no_tax_code(self):
        # Again: different families, genuinely different line shapes.
        delivery_lines = DeliveryLinesBuilder().build(invoice_document())
        self.assertNotIn('TaxCode', delivery_lines[0])
        self.assertNotIn('LineTotal', delivery_lines[0])


class SapPostingClientTests(SapTestCase):
    """
    The client works against the abstract types only. These tests drive it
    with all four families through the identical call sequence.
    """

    def test_posting_marks_the_document_posted_and_records_sap_identifiers(self):
        document = delivery_document()
        result = SapPostingClient(DeliveryNoteFactory()).post(document)

        self.assertTrue(result['success'])
        document.refresh_from_db()
        self.assertEqual(document.status, 'posted')
        self.assertEqual(document.sap_doc_entry, result['DocEntry'])
        self.assertEqual(document.sap_doc_num, result['DocNum'])
        self.assertEqual(document.error_message, '')

    def test_posting_writes_a_success_audit_row(self):
        document = delivery_document()
        SapPostingClient(DeliveryNoteFactory()).post(document)

        log = SapPostingLog.objects.get(document=document)
        self.assertTrue(log.succeeded)
        self.assertEqual(log.factory_used, 'DeliveryNoteFactory')
        self.assertEqual(log.endpoint, 'DeliveryNotes')

    def test_a_rejected_post_marks_the_document_failed_without_raising(self):
        document = make_document(card_code='')  # no lines, no card code
        result = SapPostingClient(DeliveryNoteFactory()).post(document)

        self.assertFalse(result['success'])
        self.assertEqual(result['error_type'], 'SapValidationError')
        document.refresh_from_db()
        self.assertEqual(document.status, 'failed')
        self.assertTrue(document.error_message)

    def test_a_rejected_post_writes_a_failure_audit_row(self):
        document = make_document(card_code='')
        SapPostingClient(DeliveryNoteFactory()).post(document)

        log = SapPostingLog.objects.get(document=document)
        self.assertFalse(log.succeeded)
        self.assertIn('CardCode', log.message)

    def test_the_identical_client_call_drives_all_four_families(self):
        cases = [
            (delivery_document(), 'delivery', 'DeliveryNotes'),
            (return_document(), 'return', 'Returns'),
            (transfer_document(), 'transfer', 'StockTransfers'),
            (invoice_document(), 'invoice', 'Invoices'),
        ]
        for document, family, expected_endpoint in cases:
            client = SapPostingClient(get_factory(family))
            result = client.post(document)

            self.assertTrue(result['success'], f'{family} failed: {result}')
            self.assertEqual(result['endpoint'], expected_endpoint)
            document.refresh_from_db()
            self.assertEqual(document.status, 'posted')

    def test_each_endpoint_numbers_documents_on_its_own_sequence(self):
        first = delivery_document()
        second = make_document(reference_no='DC-000102')
        add_line(second)
        transfer = transfer_document()

        first_result = post_document(first)
        second_result = post_document(second)
        transfer_result = post_document(transfer)

        self.assertEqual(first_result['DocEntry'], 1)
        self.assertEqual(second_result['DocEntry'], 2)
        # A different SAP object, so its own counter starts at 1 again.
        self.assertEqual(transfer_result['DocEntry'], 1)

    def test_a_retry_after_fixing_the_data_succeeds_and_keeps_both_logs(self):
        document = make_document(card_code='')
        add_line(document)

        failure = post_document(document)
        self.assertFalse(failure['success'])

        document.card_code = 'C00421'
        document.save(update_fields=['card_code'])
        success = post_document(document)

        self.assertTrue(success['success'])
        self.assertEqual(SapPostingLog.objects.filter(document=document).count(), 2)
        document.refresh_from_db()
        self.assertEqual(document.status, 'posted')
        self.assertEqual(document.error_message, '')

    def test_post_document_selects_the_factory_from_the_document_itself(self):
        document = invoice_document()
        result = post_document(document)
        self.assertEqual(result['factory_used'], 'InvoiceFactory')
        self.assertEqual(result['endpoint'], 'Invoices')

    def test_preview_payload_builds_without_touching_the_document(self):
        document = delivery_document()
        payload = preview_payload(document)

        self.assertEqual(payload['DocObjectCode'], 'oDeliveryNotes')
        document.refresh_from_db()
        self.assertEqual(document.status, 'draft')
        self.assertEqual(SapPostingLog.objects.count(), 0)

    def test_family_mismatch_surfaces_as_a_sap_posting_error_subclass(self):
        self.assertTrue(issubclass(SapFamilyMismatchError, SapPostingError))
        self.assertTrue(issubclass(SapValidationError, SapPostingError))


class ModelTests(SapTestCase):
    def test_document_str_is_readable(self):
        document = make_document()
        self.assertEqual(str(document), 'DC-000101 | Delivery Note | draft')

    def test_line_str_is_readable(self):
        line = add_line(make_document())
        self.assertEqual(str(line), 'SCAF-01 x 250.000')

    def test_posting_log_str_shows_the_outcome(self):
        document = delivery_document()
        post_document(document)
        log = SapPostingLog.objects.get(document=document)
        self.assertTrue(str(log).endswith('-> DeliveryNotes [OK]'))

    def test_reference_no_is_unique(self):
        make_document()
        with self.assertRaises(IntegrityError):
            make_document()

    def test_lines_are_ordered_by_line_num(self):
        document = make_document()
        add_line(document, line_num=2, item_code='SCAF-03')
        add_line(document, line_num=0, item_code='SCAF-01')
        add_line(document, line_num=1, item_code='SCAF-02')

        self.assertEqual([line.item_code for line in document.lines.all()],
                         ['SCAF-01', 'SCAF-02', 'SCAF-03'])

    def test_deleting_a_document_cascades_to_lines_and_logs(self):
        document = delivery_document()
        post_document(document)
        document.delete()

        self.assertEqual(SapDocumentLine.objects.count(), 0)
        self.assertEqual(SapPostingLog.objects.count(), 0)


class SapDocumentHttpEndpointTests(APITestCase):
    """End to end through the real API surface."""

    def setUp(self):
        reset_sap_sequence()

    def test_create_a_document_with_its_lines_in_one_call(self):
        response = self.client.post(reverse('sap_documents:document-list'), {
            'doc_family': 'delivery',
            'reference_no': 'DC-000200',
            'card_code': 'C00421',
            'card_name': 'Metro Constructions',
            'from_warehouse': 'MUM-01',
            'posting_date': '2026-08-08',
            'lines': [
                {'item_code': 'SCAF-01', 'item_name': 'Frame',
                 'quantity': '250', 'unit_price': '120.00',
                 'warehouse_code': 'MUM-01'},
                {'item_code': 'SCAF-02', 'item_name': 'Board',
                 'quantity': '400', 'unit_price': '90.00',
                 'warehouse_code': 'MUM-01'},
            ],
        }, format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(len(response.data['lines']), 2)
        self.assertEqual(response.data['status'], 'draft')

    def test_line_numbers_are_assigned_by_position_when_omitted(self):
        response = self.client.post(reverse('sap_documents:document-list'), {
            'doc_family': 'delivery',
            'reference_no': 'DC-000201',
            'card_code': 'C00421',
            'from_warehouse': 'MUM-01',
            'posting_date': '2026-08-08',
            'lines': [
                {'item_code': 'SCAF-01', 'quantity': '10'},
                {'item_code': 'SCAF-02', 'quantity': '20'},
            ],
        }, format='json')
        self.assertEqual([line['line_num'] for line in response.data['lines']],
                         [0, 1])

    def test_an_unknown_family_is_rejected_by_the_serializer(self):
        response = self.client.post(reverse('sap_documents:document-list'), {
            'doc_family': 'purchase_order',
            'reference_no': 'PO-1',
            'posting_date': '2026-08-08',
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_payload_endpoint_reports_which_products_were_used(self):
        document = return_document()
        response = self.client.get(
            reverse('sap_documents:document-payload', args=[document.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['factory'], 'ReturnFactory')
        self.assertEqual(response.data['endpoint'], 'Returns')
        self.assertEqual(response.data['header_builder'], 'ReturnHeaderBuilder')
        self.assertEqual(response.data['lines_builder'], 'ReturnLinesBuilder')
        self.assertEqual(response.data['payload']['DocObjectCode'], 'oReturns')

    def test_payload_endpoint_shape_differs_per_family_with_one_code_path(self):
        delivery = delivery_document()
        transfer = transfer_document()

        delivery_payload = self.client.get(
            reverse('sap_documents:document-payload',
                    args=[delivery.pk])).data['payload']
        transfer_payload = self.client.get(
            reverse('sap_documents:document-payload',
                    args=[transfer.pk])).data['payload']

        self.assertIn('CardCode', delivery_payload)
        self.assertNotIn('CardCode', transfer_payload)
        self.assertIn('FromWarehouse', transfer_payload)

    def test_post_endpoint_posts_a_valid_document(self):
        document = delivery_document()
        response = self.client.post(
            reverse('sap_documents:document-post', args=[document.pk]),
            format='json')

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['endpoint'], 'DeliveryNotes')

    def test_post_endpoint_returns_400_with_the_reason_on_rejection(self):
        document = make_document(card_code='')
        response = self.client.post(
            reverse('sap_documents:document-post', args=[document.pk]),
            format='json')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.data['success'])
        self.assertIn('CardCode', response.data['error'])

    def test_post_endpoint_refuses_to_double_post(self):
        document = delivery_document()
        url = reverse('sap_documents:document-post', args=[document.pk])
        self.client.post(url, format='json')
        second = self.client.post(url, format='json')

        self.assertEqual(second.status_code, 400)
        self.assertIn('already posted', second.data['error'])
        self.assertEqual(SapPostingLog.objects.filter(document=document).count(), 1)

    def test_post_endpoint_returns_404_for_a_missing_document(self):
        response = self.client.post(
            reverse('sap_documents:document-post', args=[9999]), format='json')
        self.assertEqual(response.status_code, 404)

    def test_posting_logs_endpoint_lists_every_attempt(self):
        document = make_document(card_code='')
        add_line(document)
        url = reverse('sap_documents:document-post', args=[document.pk])
        self.client.post(url, format='json')          # fails

        document.card_code = 'C00421'
        document.save(update_fields=['card_code'])
        self.client.post(url, format='json')          # succeeds

        logs = self.client.get(
            reverse('sap_documents:document-posting-logs', args=[document.pk]))
        self.assertEqual(len(logs.data), 2)
        self.assertEqual({row['succeeded'] for row in logs.data}, {True, False})

    def test_list_endpoint_filters_by_family(self):
        delivery_document()
        transfer_document()

        response = self.client.get(reverse('sap_documents:document-list'),
                                   {'doc_family': 'transfer'})
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['doc_family'], 'transfer')

    def test_list_endpoint_filters_by_status(self):
        posted = delivery_document()
        transfer_document()  # stays draft
        self.client.post(
            reverse('sap_documents:document-post', args=[posted.pk]), format='json')

        response = self.client.get(reverse('sap_documents:document-list'),
                                   {'status': 'posted'})
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['reference_no'], 'DC-000101')

    def test_families_endpoint_documents_the_whole_pattern(self):
        response = self.client.get(reverse('sap_documents:family-registry'))

        self.assertEqual(response.data['count'], 4)
        by_family = {row['doc_family']: row for row in response.data['families']}
        self.assertEqual(by_family['return']['products']['lines_builder'],
                         'ReturnLinesBuilder')
        self.assertEqual(by_family['transfer']['sap_object'], 'StockTransfers')

        # Every family advertises a distinct product trio.
        trios = [tuple(sorted(row['products'].values()))
                 for row in response.data['families']]
        self.assertEqual(len(trios), len(set(trios)))

    def test_adding_a_line_to_an_existing_document(self):
        document = make_document()
        response = self.client.post(
            reverse('sap_documents:document-lines', args=[document.pk]),
            {'line_num': 0, 'item_code': 'SCAF-09', 'item_name': 'Jack',
             'quantity': '12.000', 'unit_price': '75.00',
             'warehouse_code': 'MUM-01'},
            format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(document.lines.count(), 1)

    def test_detail_endpoint_returns_lines_and_posting_history(self):
        document = delivery_document()
        post_document(document)

        response = self.client.get(
            reverse('sap_documents:document-detail', args=[document.pk]))
        self.assertEqual(response.data['family_display'], 'Delivery Note')
        self.assertEqual(len(response.data['lines']), 1)
        self.assertEqual(len(response.data['posting_logs']), 1)
