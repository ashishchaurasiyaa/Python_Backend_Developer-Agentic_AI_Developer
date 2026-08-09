"""
Tests for the Template Method pattern (ReportGenerator + four concrete
report generators).

Behavioural guarantee under test: generate() is THE template method — its
nine-step sequence is identical for every report type. Subclasses may only
fill in the ABSTRACT steps (fetch_data, format_output) and optionally
override the HOOK steps (filter_data, transform_data, get_recipients). The
FIXED steps (empty check, deliver, save_report, update_timestamp) run the
same way for all of them.

The tests deliberately assert on the *skeleton* as well as the *steps*,
because a Template Method implementation that lets a subclass reorder the
algorithm has lost the entire point of the pattern.
"""
import json

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from .generators import (
    REPORT_GENERATORS,
    ChallanTATReportGenerator,
    CreditPipelineReportGenerator,
    ReportGenerator,
    RevenueReportGenerator,
    UtilizationReportGenerator,
    get_generator,
)
from .models import GeneratedReport, Report, ReportRecipient


def make_report(**overrides):
    defaults = dict(
        name='Daily Credit Pipeline',
        report_type='credit_pipeline',
        description='Invoices at each collection stage',
        output_format='csv',
        interval='daily',
    )
    defaults.update(overrides)
    return Report.objects.create(**defaults)


# ----------------------------------------------------------------------
# Test doubles — minimal subclasses used to probe the skeleton itself.
# ----------------------------------------------------------------------

class RecordingGenerator(ReportGenerator):
    """Records the order in which the template method calls each step."""

    def __init__(self):
        self.calls = []

    def fetch_data(self, report):
        self.calls.append('fetch_data')
        return [{'a': 1, 'b': 2}, {'a': 3, 'b': 4}]

    def filter_data(self, data):
        self.calls.append('filter_data')
        return super().filter_data(data)

    def transform_data(self, data):
        self.calls.append('transform_data')
        return super().transform_data(data)

    def format_output(self, data, report):
        self.calls.append('format_output')
        return 'a,b\n1,2\n3,4\n', 'recording.csv'

    def get_recipients(self, report):
        self.calls.append('get_recipients')
        return super().get_recipients(report)

    def deliver(self, content, file_name, recipients):
        self.calls.append('deliver')
        return super().deliver(content, file_name, recipients)


class EmptyDataGenerator(ReportGenerator):
    """Returns no rows — should short-circuit at the FIXED empty check."""

    def __init__(self):
        self.format_output_called = False

    def fetch_data(self, report):
        return []

    def format_output(self, data, report):
        self.format_output_called = True
        return '', 'never-written.csv'


class BareMinimumGenerator(ReportGenerator):
    """
    Implements only the two ABSTRACT steps. Every HOOK keeps its default,
    which proves the defaults really are no-ops.
    """

    def fetch_data(self, report):
        return [{'x': 10}, {'x': 20}]

    def format_output(self, data, report):
        return json.dumps(data), 'bare.json'


class IncompleteGenerator(ReportGenerator):
    """Missing format_output — must not be instantiable."""

    def fetch_data(self, report):
        return [{'x': 1}]


# ----------------------------------------------------------------------


class TemplateMethodSkeletonTests(TestCase):
    """The skeleton itself: order, abstractness, and the fixed steps."""

    def test_generate_calls_the_nine_steps_in_the_documented_order(self):
        report = make_report()
        generator = RecordingGenerator()
        generator.generate(report)

        self.assertEqual(
            generator.calls,
            [
                'fetch_data',
                'filter_data',
                'transform_data',
                'format_output',
                'get_recipients',
                'deliver',
            ],
        )

    def test_generate_reports_the_full_step_list_it_executed(self):
        report = make_report()
        result = RecordingGenerator().generate(report)

        self.assertEqual(result['steps_executed'], [
            'fetch_data', 'check_empty', 'filter_data', 'transform_data',
            'format_output', 'get_recipients', 'deliver', 'save_report',
            'update_timestamp',
        ])

    def test_subclass_missing_an_abstract_step_cannot_be_instantiated(self):
        with self.assertRaises(TypeError):
            IncompleteGenerator()

    def test_base_generator_itself_cannot_be_instantiated(self):
        with self.assertRaises(TypeError):
            ReportGenerator()

    def test_empty_data_short_circuits_before_format_output_runs(self):
        report = make_report()
        generator = EmptyDataGenerator()
        result = generator.generate(report)

        self.assertEqual(result['status'], 'empty')
        self.assertEqual(result['rows'], 0)
        self.assertFalse(generator.format_output_called)

    def test_empty_data_writes_no_audit_row_and_leaves_timestamp_untouched(self):
        report = make_report()
        EmptyDataGenerator().generate(report)

        self.assertEqual(GeneratedReport.objects.count(), 0)
        report.refresh_from_db()
        self.assertIsNone(report.last_generated)

    def test_default_hooks_are_no_ops_for_a_bare_minimum_subclass(self):
        report = make_report()
        result = BareMinimumGenerator().generate(report)

        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['rows'], 2)
        generated = GeneratedReport.objects.get(pk=result['report_id'])
        # Data survived filter_data and transform_data unchanged.
        self.assertEqual(json.loads(generated.file_content),
                         [{'x': 10}, {'x': 20}])

    def test_fixed_step_save_report_persists_shape_metadata(self):
        report = make_report()
        result = RecordingGenerator().generate(report)

        generated = GeneratedReport.objects.get(pk=result['report_id'])
        self.assertEqual(generated.file_name, 'recording.csv')
        self.assertEqual(generated.row_count, 2)
        self.assertEqual(generated.column_count, 2)  # keys 'a' and 'b'
        self.assertEqual(generated.report_id, report.pk)

    def test_fixed_step_update_timestamp_stamps_the_report(self):
        report = make_report()
        self.assertIsNone(report.last_generated)

        RecordingGenerator().generate(report)

        report.refresh_from_db()
        self.assertIsNotNone(report.last_generated)


class DeliveryAndRecipientTests(TestCase):
    """Step 6 + step 7: recipients drive delivery status."""

    def test_no_recipients_means_delivery_fails_and_status_stays_generated(self):
        report = make_report()
        result = RecordingGenerator().generate(report)

        generated = GeneratedReport.objects.get(pk=result['report_id'])
        self.assertEqual(generated.status, 'generated')
        self.assertEqual(generated.sent_to, [])
        self.assertEqual(result['recipients'], 0)

    def test_recipients_present_means_status_becomes_sent(self):
        report = make_report()
        ReportRecipient.objects.create(
            report=report, name='Ashish', email='ashish@example.com')
        ReportRecipient.objects.create(
            report=report, name='Finance', email='finance@example.com')

        result = RecordingGenerator().generate(report)

        generated = GeneratedReport.objects.get(pk=result['report_id'])
        self.assertEqual(generated.status, 'sent')
        self.assertCountEqual(
            generated.sent_to, ['ashish@example.com', 'finance@example.com'])
        self.assertEqual(result['recipients'], 2)

    def test_default_get_recipients_hook_reads_from_the_related_manager(self):
        report = make_report()
        ReportRecipient.objects.create(
            report=report, name='Ops', email='ops@example.com')

        recipients = BareMinimumGenerator().get_recipients(report)
        self.assertEqual([r.email for r in recipients], ['ops@example.com'])


class CreditPipelineGeneratorTests(TestCase):
    """Overrides fetch_data + filter_data + transform_data + format_output."""

    def test_filter_hook_drops_rows_with_no_outstanding_balance(self):
        generator = CreditPipelineReportGenerator()
        data = generator.fetch_data(None) + [
            {'doc_number': 'INV-006', 'customer': 'Paid Co',
             'status': 'BILL_PAID', 'balance': 0, 'days_overdue': 0},
        ]
        filtered = generator.filter_data(data)

        self.assertEqual(len(filtered), 5)
        self.assertNotIn('INV-006', [row['doc_number'] for row in filtered])

    def test_transform_hook_assigns_the_correct_aging_bucket(self):
        generator = CreditPipelineReportGenerator()
        transformed = generator.transform_data(generator.fetch_data(None))
        buckets = {row['doc_number']: row['bucket'] for row in transformed}

        self.assertEqual(buckets['INV-003'], '0-30 days')    # 10 days
        self.assertEqual(buckets['INV-004'], '0-30 days')    # 30 days (boundary)
        self.assertEqual(buckets['INV-001'], '31-60 days')   # 45 days
        self.assertEqual(buckets['INV-002'], '31-60 days')   # 60 days (boundary)
        self.assertEqual(buckets['INV-005'], '90+ days')     # 120 days

    def test_generate_produces_a_csv_with_a_header_and_the_bucket_column(self):
        report = make_report(report_type='credit_pipeline')
        result = CreditPipelineReportGenerator().generate(report)

        generated = GeneratedReport.objects.get(pk=result['report_id'])
        lines = generated.file_content.strip().splitlines()
        self.assertEqual(len(lines), 6)                 # 1 header + 5 rows
        self.assertIn('bucket', lines[0])
        self.assertTrue(generated.file_name.endswith('.csv'))
        self.assertEqual(generated.column_count, 6)


class ChallanTATGeneratorTests(TestCase):
    """Overrides transform_data to add SLA compliance."""

    def test_sla_limit_differs_by_challan_type(self):
        transformed = ChallanTATReportGenerator().transform_data(
            ChallanTATReportGenerator().fetch_data(None))
        by_no = {row['challan_no']: row for row in transformed}

        self.assertEqual(by_no['DC-000101']['sla_limit_hours'], 48)  # Delivery
        self.assertEqual(by_no['PC-000050']['sla_limit_hours'], 72)  # Pickup

    def test_sla_met_flag_is_computed_against_the_type_specific_limit(self):
        transformed = ChallanTATReportGenerator().transform_data(
            ChallanTATReportGenerator().fetch_data(None))
        by_no = {row['challan_no']: row for row in transformed}

        self.assertEqual(by_no['DC-000101']['sla_met'], 'Yes')  # 48 <= 48
        self.assertEqual(by_no['DC-000102']['sla_met'], 'No')   # 72 > 48
        self.assertEqual(by_no['PC-000050']['sla_met'], 'No')   # 96 > 72
        self.assertEqual(by_no['DC-000103']['sla_met'], 'Yes')  # 24 <= 48

    def test_filter_hook_is_a_deliberate_pass_through_for_this_report(self):
        generator = ChallanTATReportGenerator()
        data = generator.fetch_data(None)
        self.assertEqual(len(generator.filter_data(data)), len(data))


class RevenueGeneratorTests(TestCase):
    """
    Same skeleton, different output format. This generator overrides ONLY
    the two abstract steps — proof that the hooks are genuinely optional.
    """

    def test_format_output_emits_json_not_csv(self):
        report = make_report(report_type='revenue', output_format='json')
        result = RevenueReportGenerator().generate(report)

        generated = GeneratedReport.objects.get(pk=result['report_id'])
        self.assertTrue(generated.file_name.endswith('.json'))
        payload = json.loads(generated.file_content)
        self.assertIn('orders', payload)
        self.assertIn('report_date', payload)

    def test_format_output_aggregates_total_predicted_revenue(self):
        report = make_report(report_type='revenue')
        result = RevenueReportGenerator().generate(report)

        payload = json.loads(
            GeneratedReport.objects.get(pk=result['report_id']).file_content)
        self.assertEqual(payload['total_predicted_revenue'],
                         1500000 + 540000 + 1140000)

    def test_it_still_runs_the_identical_nine_step_skeleton(self):
        report = make_report(report_type='revenue')
        result = RevenueReportGenerator().generate(report)
        self.assertEqual(result['steps_executed'],
                         RecordingGenerator().generate(make_report())['steps_executed'])


class UtilizationGeneratorTests(TestCase):
    """Overrides transform_data to compute utilization percentages."""

    def test_utilization_percentage_is_computed_per_item(self):
        transformed = UtilizationReportGenerator().transform_data(
            UtilizationReportGenerator().fetch_data(None))
        by_code = {row['item_code']: row for row in transformed}

        self.assertEqual(by_code['SCAFFOLD-01']['utilization_pct'], 70.0)
        self.assertEqual(by_code['SCAFFOLD-02']['utilization_pct'], 77.5)
        self.assertEqual(by_code['SCAFFOLD-03']['utilization_pct'], 45.0)

    def test_status_classification_uses_strict_greater_than_thresholds(self):
        transformed = UtilizationReportGenerator().transform_data(
            UtilizationReportGenerator().fetch_data(None))
        by_code = {row['item_code']: row for row in transformed}

        # 70.0 is NOT > 70, so it lands in MEDIUM - an easy off-by-one to miss.
        self.assertEqual(by_code['SCAFFOLD-01']['status'], 'MEDIUM')  # 70.0
        self.assertEqual(by_code['SCAFFOLD-02']['status'], 'HIGH')    # 77.5
        self.assertEqual(by_code['SCAFFOLD-03']['status'], 'MEDIUM')  # 45.0


class GeneratorRegistryTests(TestCase):
    """The registry is the Open/Closed seam in front of the template method."""

    def test_registry_maps_every_report_type_choice_to_a_generator(self):
        model_types = {value for value, _ in Report.REPORT_TYPE_CHOICES}
        self.assertEqual(set(REPORT_GENERATORS.keys()), model_types)

    def test_get_generator_returns_the_matching_concrete_class(self):
        self.assertIsInstance(get_generator('credit_pipeline'),
                              CreditPipelineReportGenerator)
        self.assertIsInstance(get_generator('challan_tat'),
                              ChallanTATReportGenerator)
        self.assertIsInstance(get_generator('revenue'),
                              RevenueReportGenerator)
        self.assertIsInstance(get_generator('utilization'),
                              UtilizationReportGenerator)

    def test_every_registered_generator_is_a_report_generator_subclass(self):
        for report_type, cls in REPORT_GENERATORS.items():
            self.assertTrue(issubclass(cls, ReportGenerator), report_type)

    def test_unknown_report_type_raises_value_error(self):
        with self.assertRaises(ValueError):
            get_generator('does_not_exist')


class ModelTests(TestCase):
    def test_report_str_shows_the_human_readable_type(self):
        report = make_report(name='Weekly TAT', report_type='challan_tat')
        self.assertEqual(str(report), 'Weekly TAT (Challan TAT)')

    def test_recipient_str_is_name_and_email(self):
        report = make_report()
        recipient = ReportRecipient.objects.create(
            report=report, name='Ashish', email='ashish@example.com')
        self.assertEqual(str(recipient), 'Ashish <ashish@example.com>')

    def test_a_recipient_email_is_unique_per_report(self):
        from django.db import IntegrityError

        report = make_report()
        ReportRecipient.objects.create(
            report=report, name='Ashish', email='dup@example.com')
        with self.assertRaises(IntegrityError):
            ReportRecipient.objects.create(
                report=report, name='Ashish Again', email='dup@example.com')

    def test_the_same_email_may_subscribe_to_two_different_reports(self):
        first = make_report(name='One')
        second = make_report(name='Two', report_type='revenue')
        ReportRecipient.objects.create(
            report=first, name='Ashish', email='shared@example.com')
        ReportRecipient.objects.create(
            report=second, name='Ashish', email='shared@example.com')
        self.assertEqual(ReportRecipient.objects.count(), 2)

    def test_generated_reports_are_ordered_newest_first(self):
        report = make_report()
        RecordingGenerator().generate(report)
        RecordingGenerator().generate(report)
        rows = list(GeneratedReport.objects.all())
        self.assertGreaterEqual(rows[0].generated_at, rows[1].generated_at)


class ReportHttpEndpointTests(APITestCase):
    """Exercise the pattern end to end through the real API surface."""

    def test_create_and_fetch_a_report_configuration(self):
        response = self.client.post(reverse('reports:report-list'), {
            'name': 'Monthly Revenue',
            'report_type': 'revenue',
            'output_format': 'json',
            'interval': 'monthly',
        }, format='json')
        self.assertEqual(response.status_code, 201)

        detail = self.client.get(
            reverse('reports:report-detail', args=[response.data['id']]))
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.data['report_type'], 'revenue')
        self.assertEqual(detail.data['recipient_count'], 0)

    def test_generate_endpoint_runs_the_template_method_and_returns_steps(self):
        report = make_report(report_type='utilization')
        response = self.client.post(
            reverse('reports:report-generate', args=[report.pk]), format='json')

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['status'], 'success')
        self.assertEqual(response.data['generator_class'],
                         'UtilizationReportGenerator')
        self.assertEqual(len(response.data['steps_executed']), 9)

    def test_generate_endpoint_dispatches_on_report_type_alone(self):
        csv_report = make_report(report_type='challan_tat')
        json_report = make_report(name='Rev', report_type='revenue')

        csv_result = self.client.post(
            reverse('reports:report-generate', args=[csv_report.pk]), format='json')
        json_result = self.client.post(
            reverse('reports:report-generate', args=[json_report.pk]), format='json')

        self.assertTrue(csv_result.data['file_name'].endswith('.csv'))
        self.assertTrue(json_result.data['file_name'].endswith('.json'))
        # Identical skeleton, different products - that is Template Method.
        self.assertEqual(csv_result.data['steps_executed'],
                         json_result.data['steps_executed'])

    def test_generate_endpoint_refuses_an_inactive_report(self):
        report = make_report(is_active=False)
        response = self.client.post(
            reverse('reports:report-generate', args=[report.pk]), format='json')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data['status'], 'skipped')
        self.assertEqual(GeneratedReport.objects.count(), 0)

    def test_generate_endpoint_returns_404_for_a_missing_report(self):
        response = self.client.post(
            reverse('reports:report-generate', args=[9999]), format='json')
        self.assertEqual(response.status_code, 404)

    def test_generated_endpoint_lists_the_audit_trail(self):
        report = make_report()
        generate_url = reverse('reports:report-generate', args=[report.pk])
        self.client.post(generate_url, format='json')
        self.client.post(generate_url, format='json')

        response = self.client.get(
            reverse('reports:report-generated', args=[report.pk]))
        self.assertEqual(len(response.data), 2)
        self.assertNotIn('file_content', response.data[0])  # list stays light

    def test_generated_detail_endpoint_returns_the_file_body(self):
        report = make_report()
        created = self.client.post(
            reverse('reports:report-generate', args=[report.pk]), format='json')

        response = self.client.get(
            reverse('reports:generated-detail', args=[created.data['report_id']]))
        self.assertEqual(response.status_code, 200)
        self.assertIn('doc_number', response.data['file_content'])

    def test_adding_a_recipient_flips_the_next_run_to_sent(self):
        report = make_report()
        self.client.post(
            reverse('reports:report-recipients', args=[report.pk]),
            {'name': 'Finance', 'email': 'finance@example.com'}, format='json')

        result = self.client.post(
            reverse('reports:report-generate', args=[report.pk]), format='json')
        generated = GeneratedReport.objects.get(pk=result.data['report_id'])
        self.assertEqual(generated.status, 'sent')
        self.assertEqual(generated.sent_to, ['finance@example.com'])

    def test_registry_endpoint_advertises_all_four_generators(self):
        response = self.client.get(reverse('reports:generator-registry'))
        self.assertEqual(response.data['count'], 4)
        types = {row['report_type'] for row in response.data['generators']}
        self.assertEqual(
            types,
            {'credit_pipeline', 'challan_tat', 'revenue', 'utilization'})
