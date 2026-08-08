from django.test import TestCase
from django.urls import reverse

from .models import ConnectionLog, SapConnection
from .singleton import SapConnectionManager


class SingletonPatternTests(TestCase):
    """
    Proves the actual behavioural guarantee of the Singleton pattern:
    every call to SapConnectionManager() returns the SAME Python object,
    and state set on one "instance" is visible through every other
    reference, exactly like Youngman's real SapRepository session reuse.
    """

    def setUp(self):
        # Singleton state is a class attribute shared across the whole
        # test run - reset it before every test so tests don't leak
        # session_id / request_count into each other.
        SapConnectionManager.reset()

    def tearDown(self):
        SapConnectionManager.reset()

    def test_constructor_returns_identical_object(self):
        a = SapConnectionManager()
        b = SapConnectionManager()
        self.assertIs(a, b)
        self.assertEqual(id(a), id(b))

    def test_third_and_later_calls_are_also_identical(self):
        instances = [SapConnectionManager() for _ in range(5)]
        first_id = id(instances[0])
        for inst in instances[1:]:
            self.assertIs(inst, instances[0])
            self.assertEqual(id(inst), first_id)

    def test_state_set_on_one_reference_visible_on_another(self):
        a = SapConnectionManager()
        a.connect()
        b = SapConnectionManager()
        # b was "constructed" separately but is the same object, so it
        # already has the session a just created.
        self.assertEqual(a.session_id, b.session_id)
        self.assertIsNotNone(b.session_id)

    def test_init_does_not_reset_state_on_repeat_construction(self):
        a = SapConnectionManager()
        a.connect()
        session_before = a.session_id
        # Calling the constructor again must NOT re-run __init__'s setup
        # logic (that would silently wipe out the live session).
        b = SapConnectionManager(service_url='https://different-host/b1s/v1')
        self.assertEqual(b.session_id, session_before)
        self.assertEqual(b.service_url, a.service_url)
        self.assertNotEqual(b.service_url, 'https://different-host/b1s/v1')

    def test_get_session_is_lazy_and_idempotent(self):
        manager = SapConnectionManager()
        self.assertIsNone(manager.session_id)
        first = manager.get_session()
        second = manager.get_session()
        self.assertEqual(first, second)
        self.assertEqual(manager.session_id, first)

    def test_request_count_accumulates_across_separate_instantiations(self):
        # Simulates two different Django views each doing
        # `manager = SapConnectionManager()` independently.
        view_one_manager = SapConnectionManager()
        view_one_manager.post_invoice({'CardCode': 'C001'})

        view_two_manager = SapConnectionManager()
        view_two_manager.post_invoice({'CardCode': 'C002'})

        self.assertIs(view_one_manager, view_two_manager)
        self.assertEqual(view_two_manager.request_count, 2)

    def test_disconnect_resets_singleton_for_next_construction(self):
        a = SapConnectionManager()
        a.connect()
        old_id = id(a)
        a.disconnect()

        b = SapConnectionManager()
        # After disconnect() explicitly clears _instance, the next
        # construction MUST produce a fresh object with no session -
        # this is the pattern's documented reset escape hatch, not a bug.
        self.assertNotEqual(id(b), old_id)
        self.assertIsNone(b.session_id)

    def test_reset_classmethod_forces_new_instance(self):
        a = SapConnectionManager()
        SapConnectionManager.reset()
        b = SapConnectionManager()
        self.assertNotEqual(id(a), id(b))


class SingletonProofEndpointTests(TestCase):
    """
    Exercises the actual HTTP surface (/api/singleton-proof/ and friends)
    through Django's test client, proving the singleton guarantee holds
    across independent view invocations - not just direct Python calls.
    """

    def setUp(self):
        SapConnectionManager.reset()

    def tearDown(self):
        SapConnectionManager.reset()

    def test_singleton_proof_endpoint_reports_same_object(self):
        url = reverse('sap_connector:singleton-proof')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        proof = response.data['proof']
        self.assertTrue(proof['are_same_object'])
        self.assertTrue(proof['id_match'])
        self.assertEqual(proof['instance_a_id'], proof['instance_b_id'])

    def test_instance_id_stable_across_independent_requests(self):
        status_url = reverse('sap_connector:connection-status')

        first = self.client.get(status_url)
        second = self.client.get(status_url)

        first_id = first.data['status']['instance_id']
        second_id = second.data['status']['instance_id']
        self.assertEqual(first_id, second_id)

    def test_connect_endpoint_reuses_session_on_second_call(self):
        connect_url = reverse('sap_connector:connection-connect')

        first = self.client.post(connect_url)
        self.assertEqual(first.status_code, 201)
        first_session = first.data['session_id']

        second = self.client.post(connect_url)
        self.assertEqual(second.status_code, 200)
        self.assertIn('Already connected', second.data['message'])
        self.assertEqual(second.data['session_id'], first_session)
        self.assertEqual(second.data['instance_id'], first.data['instance_id'])

    def test_request_count_persists_across_different_endpoint_calls(self):
        # Two DIFFERENT views, each doing its own SapConnectionManager()
        # construction - request_count must still accumulate on the one
        # shared object, proving state genuinely crosses request/view
        # boundaries within the process.
        invoice_url = reverse('sap_connector:sap-invoices')
        bp_url = reverse('sap_connector:sap-business-partners')

        r1 = self.client.post(invoice_url, data={}, content_type='application/json')
        r2 = self.client.get(bp_url, {'card_code': 'C001'})

        manager = SapConnectionManager()
        self.assertEqual(manager.request_count, 2)
        self.assertEqual(r1.data['instance_id'], r2.data['instance_id'])

    def test_disconnect_endpoint_clears_session_and_persists_to_db(self):
        connect_url = reverse('sap_connector:connection-connect')
        disconnect_url = reverse('sap_connector:connection-disconnect')

        self.client.post(connect_url)
        self.assertEqual(SapConnection.objects.filter(is_active=True).count(), 1)

        response = self.client.post(disconnect_url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(SapConnection.objects.filter(is_active=True).exists())

    def test_logs_endpoint_records_every_sap_call(self):
        invoice_url = reverse('sap_connector:sap-invoices')
        logs_url = reverse('sap_connector:connection-logs')

        self.client.post(invoice_url, data={}, content_type='application/json')
        self.client.post(invoice_url, data={}, content_type='application/json')

        response = self.client.get(logs_url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ConnectionLog.objects.filter(entity_type='Invoices').count(), 2)
        self.assertGreaterEqual(len(response.data['recent_logs']), 2)
