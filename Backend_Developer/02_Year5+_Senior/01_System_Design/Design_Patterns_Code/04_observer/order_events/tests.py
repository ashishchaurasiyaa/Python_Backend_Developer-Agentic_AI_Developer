"""
tests.py - Observer Pattern Tests
==================================

Tests:
  1. Subscribe / Unsubscribe
  2. Notify fires all observers
  3. Approved event generates 4 notifications
  4. Rejected event generates 2 notifications
  5. Amended event generates 3 notifications
  6. Observer can be dynamically added/removed
  7. API endpoint integration tests
"""

from decimal import Decimal
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Order, Notification, EventLog
from .observers import (
    EventManager,
    AccountManagerNotifier,
    PlanningTeamNotifier,
    CustomerSMSNotifier,
    DatabaseNotifier,
    WhatsAppNotifier,
    get_default_event_manager,
)


class EventManagerSubscriptionTest(TestCase):
    """Test subscribe and unsubscribe functionality."""

    def setUp(self):
        self.manager = EventManager()

    def test_subscribe_adds_observer(self):
        """An observer should be registered for the event type."""
        observer = AccountManagerNotifier()
        self.manager.subscribe('approved', observer)
        subs = self.manager.get_subscribers('approved')
        self.assertIn('AccountManagerNotifier', subs['approved'])

    def test_subscribe_prevents_duplicates(self):
        """Same observer should not be registered twice."""
        observer1 = AccountManagerNotifier()
        observer2 = AccountManagerNotifier()
        self.manager.subscribe('approved', observer1)
        self.manager.subscribe('approved', observer2)
        subs = self.manager.get_subscribers('approved')
        self.assertEqual(len(subs['approved']), 1)

    def test_unsubscribe_removes_observer(self):
        """Unsubscribe should remove the observer by name."""
        self.manager.subscribe('approved', AccountManagerNotifier())
        self.manager.subscribe('approved', PlanningTeamNotifier())
        self.manager.unsubscribe('approved', 'AccountManagerNotifier')
        subs = self.manager.get_subscribers('approved')
        self.assertNotIn('AccountManagerNotifier', subs['approved'])
        self.assertIn('PlanningTeamNotifier', subs['approved'])

    def test_unsubscribe_nonexistent_does_not_fail(self):
        """Unsubscribing a non-existent observer should not raise."""
        self.manager.subscribe('approved', AccountManagerNotifier())
        self.manager.unsubscribe('approved', 'NonExistent')
        subs = self.manager.get_subscribers('approved')
        self.assertEqual(len(subs['approved']), 1)

    def test_get_all_event_types(self):
        """Should return all registered event types."""
        self.manager.subscribe('approved', AccountManagerNotifier())
        self.manager.subscribe('rejected', DatabaseNotifier())
        event_types = self.manager.get_all_event_types()
        self.assertIn('approved', event_types)
        self.assertIn('rejected', event_types)


class EventManagerNotifyTest(TestCase):
    """Test that notify fires all observers correctly."""

    def setUp(self):
        self.manager = get_default_event_manager()
        self.sample_data = {
            'job_order': 'JO-TEST-001',
            'customer_name': 'Test Corp',
            'godown': 'Delhi',
            'po_no': 'PO-123',
            'total_amount': '50000.00',
            'account_manager_email': 'am@test.com',
            'customer_phone': '+919999999999',
            'created_by': 'test_user',
        }

    def test_approved_event_fires_4_observers(self):
        """Approved event should notify 4 observers."""
        results = self.manager.notify('approved', self.sample_data)
        self.assertEqual(len(results), 4)
        observer_names = [r['observer'] for r in results]
        self.assertIn('AccountManagerNotifier', observer_names)
        self.assertIn('PlanningTeamNotifier', observer_names)
        self.assertIn('CustomerSMSNotifier', observer_names)
        self.assertIn('DatabaseNotifier', observer_names)

    def test_rejected_event_fires_2_observers(self):
        """Rejected event should notify 2 observers."""
        results = self.manager.notify('rejected', self.sample_data)
        self.assertEqual(len(results), 2)
        observer_names = [r['observer'] for r in results]
        self.assertIn('AccountManagerNotifier', observer_names)
        self.assertIn('DatabaseNotifier', observer_names)

    def test_amended_event_fires_3_observers(self):
        """Amended event should notify 3 observers."""
        results = self.manager.notify('amended', self.sample_data)
        self.assertEqual(len(results), 3)

    def test_unknown_event_fires_0_observers(self):
        """Unknown event type should not fire any observers."""
        results = self.manager.notify('unknown_event', self.sample_data)
        self.assertEqual(len(results), 0)

    def test_all_results_have_sent_status(self):
        """All successful notifications should have status=sent."""
        results = self.manager.notify('approved', self.sample_data)
        for result in results:
            self.assertEqual(result['status'], 'sent')

    def test_email_channel_for_account_manager(self):
        """AccountManagerNotifier should use email channel."""
        results = self.manager.notify('approved', self.sample_data)
        am_result = next(r for r in results if r['observer'] == 'AccountManagerNotifier')
        self.assertEqual(am_result['channel'], 'email')
        self.assertEqual(am_result['recipient'], 'am@test.com')

    def test_sms_channel_for_customer(self):
        """CustomerSMSNotifier should use sms channel."""
        results = self.manager.notify('approved', self.sample_data)
        sms_result = next(r for r in results if r['observer'] == 'CustomerSMSNotifier')
        self.assertEqual(sms_result['channel'], 'sms')
        self.assertEqual(sms_result['recipient'], '+919999999999')


class DynamicObserverTest(TestCase):
    """Test dynamically adding/removing observers."""

    def setUp(self):
        self.manager = get_default_event_manager()
        self.sample_data = {
            'job_order': 'JO-DYN-001',
            'customer_name': 'Dynamic Corp',
            'godown': 'Mumbai',
            'total_amount': '75000.00',
            'customer_phone': '+918888888888',
            'created_by': 'admin',
        }

    def test_add_whatsapp_observer_to_approved(self):
        """Adding WhatsApp observer should increase approved observers to 5."""
        self.manager.subscribe('approved', WhatsAppNotifier())
        results = self.manager.notify('approved', self.sample_data)
        self.assertEqual(len(results), 5)
        observer_names = [r['observer'] for r in results]
        self.assertIn('WhatsAppNotifier', observer_names)

    def test_remove_sms_observer_from_approved(self):
        """Removing SMS observer should decrease approved observers to 3."""
        self.manager.unsubscribe('approved', 'CustomerSMSNotifier')
        results = self.manager.notify('approved', self.sample_data)
        self.assertEqual(len(results), 3)
        observer_names = [r['observer'] for r in results]
        self.assertNotIn('CustomerSMSNotifier', observer_names)

    def test_subscribe_to_new_event_type(self):
        """Should be able to create new event types dynamically."""
        self.manager.subscribe('cancelled', DatabaseNotifier())
        self.manager.subscribe('cancelled', AccountManagerNotifier())
        results = self.manager.notify('cancelled', self.sample_data)
        self.assertEqual(len(results), 2)


class OrderAPITest(TestCase):
    """Integration tests for API endpoints."""

    def setUp(self):
        self.client = APIClient()
        self.order_data = {
            'job_order': 'JO-API-001',
            'customer_name': 'API Test Corp',
            'godown': 'Bangalore',
            'po_no': 'PO-API-001',
            'total_amount': '100000.00',
            'account_manager_email': 'am@apitest.com',
            'customer_phone': '+917777777777',
            'created_by': 'api_tester',
        }

    def test_create_order(self):
        """POST /api/orders/ should create an order."""
        response = self.client.post('/api/orders/', self.order_data, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data['order']['job_order'], 'JO-API-001')
        self.assertEqual(response.data['order']['status'], 'under_review')

    def test_list_orders(self):
        """GET /api/orders/ should list all orders."""
        Order.objects.create(**{
            'job_order': 'JO-LIST-001',
            'customer_name': 'List Corp',
            'godown': 'Delhi',
        })
        response = self.client.get('/api/orders/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 1)

    def test_approve_order_creates_notifications(self):
        """POST /api/orders/<id>/approve/ should create 4 notifications."""
        order = Order.objects.create(**{
            'job_order': 'JO-APPROVE-001',
            'customer_name': 'Approve Corp',
            'godown': 'Chennai',
            'account_manager_email': 'am@approve.com',
            'customer_phone': '+916666666666',
            'created_by': 'tester',
        })
        response = self.client.post(f'/api/orders/{order.id}/approve/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['observers_notified'], 4)

        # Check DB notifications
        notifications = Notification.objects.filter(order=order)
        self.assertEqual(notifications.count(), 4)

        # Check EventLog
        log = EventLog.objects.filter(order=order, event_type='approved').first()
        self.assertIsNotNone(log)
        self.assertEqual(log.observers_notified, 4)

    def test_reject_order_creates_2_notifications(self):
        """POST /api/orders/<id>/reject/ should create 2 notifications."""
        order = Order.objects.create(**{
            'job_order': 'JO-REJECT-001',
            'customer_name': 'Reject Corp',
            'godown': 'Hyderabad',
        })
        response = self.client.post(f'/api/orders/{order.id}/reject/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['observers_notified'], 2)

    def test_amend_order_creates_3_notifications(self):
        """POST /api/orders/<id>/amend/ should create 3 notifications."""
        order = Order.objects.create(**{
            'job_order': 'JO-AMEND-001',
            'customer_name': 'Amend Corp',
            'godown': 'Pune',
        })
        response = self.client.post(f'/api/orders/{order.id}/amend/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['observers_notified'], 3)

    def test_approve_already_approved_returns_error(self):
        """Approving an already-approved order should return 400."""
        order = Order.objects.create(**{
            'job_order': 'JO-DOUBLE-001',
            'customer_name': 'Double Corp',
            'godown': 'Delhi',
            'status': 'approved',
        })
        response = self.client.post(f'/api/orders/{order.id}/approve/')
        self.assertEqual(response.status_code, 400)

    def test_approve_nonexistent_order_returns_404(self):
        """Approving a non-existent order should return 404."""
        response = self.client.post('/api/orders/9999/approve/')
        self.assertEqual(response.status_code, 404)

    def test_order_notifications_endpoint(self):
        """GET /api/orders/<id>/notifications/ should return notifications."""
        order = Order.objects.create(**{
            'job_order': 'JO-NOTIF-001',
            'customer_name': 'Notif Corp',
            'godown': 'Kolkata',
        })
        # Approve to generate notifications
        self.client.post(f'/api/orders/{order.id}/approve/')
        response = self.client.get(f'/api/orders/{order.id}/notifications/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['count'], 4)

    def test_event_logs_endpoint(self):
        """GET /api/event-logs/ should return event logs."""
        order = Order.objects.create(**{
            'job_order': 'JO-LOG-001',
            'customer_name': 'Log Corp',
            'godown': 'Jaipur',
        })
        self.client.post(f'/api/orders/{order.id}/approve/')
        response = self.client.get('/api/event-logs/')
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(response.data['count'], 1)

    def test_subscribers_endpoint(self):
        """GET /api/subscribers/ should return event->observer map."""
        response = self.client.get('/api/subscribers/')
        self.assertEqual(response.status_code, 200)
        self.assertIn('event_subscriber_map', response.data)
        self.assertIn('approved', response.data['event_subscriber_map'])

    def test_register_observer_endpoint(self):
        """POST /api/subscribers/register/ should add an observer."""
        response = self.client.post('/api/subscribers/register/', {
            'event_type': 'approved',
            'observer_name': 'WhatsAppNotifier',
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertIn('WhatsAppNotifier', response.data['current_subscribers']['approved'])

    def test_register_invalid_observer_returns_error(self):
        """Registering a non-existent observer should return 400."""
        response = self.client.post('/api/subscribers/register/', {
            'event_type': 'approved',
            'observer_name': 'FakeObserver',
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_unsubscribe_observer_endpoint(self):
        """POST /api/subscribers/unsubscribe/ should remove an observer."""
        response = self.client.post('/api/subscribers/unsubscribe/', {
            'event_type': 'approved',
            'observer_name': 'CustomerSMSNotifier',
        }, format='json')
        self.assertEqual(response.status_code, 200)
