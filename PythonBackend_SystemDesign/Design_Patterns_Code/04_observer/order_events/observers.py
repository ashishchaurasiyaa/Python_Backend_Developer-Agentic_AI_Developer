"""
observers.py - Observer Design Pattern Implementation
=====================================================

This is the CORE of the Observer pattern:
  - Observer (ABC)        : Interface that all listeners implement
  - Concrete Observers    : AccountManagerNotifier, PlanningTeamNotifier, etc.
  - EventManager (Subject): Maintains subscriptions, dispatches events

Mirrors Laravel's EventServiceProvider with 16 events -> 16 listeners.
"""

from abc import ABC, abstractmethod
from typing import List, Dict


class Observer(ABC):
    """Base Observer - all observers implement update()."""

    @abstractmethod
    def update(self, event_type: str, data: dict) -> dict:
        """Handle the event. Return notification details."""
        pass

    @abstractmethod
    def get_name(self) -> str:
        pass


class AccountManagerNotifier(Observer):
    """Mirrors: SendOrderApprovedNotification -> email to AM"""

    def update(self, event_type, data):
        recipient = data.get('account_manager_email', 'am@youngman.co.in')
        return {
            'channel': 'email',
            'recipient': recipient,
            'subject': f"Order {data['job_order']} has been {event_type}",
            'message': (
                f"Dear Account Manager,\n\n"
                f"Order {data['job_order']} for customer {data['customer_name']} "
                f"at godown {data['godown']} has been {event_type}.\n\n"
                f"Amount: Rs.{data.get('total_amount', 0)}\n"
                f"PO: {data.get('po_no', 'N/A')}"
            ),
        }

    def get_name(self):
        return "AccountManagerNotifier"


class PlanningTeamNotifier(Observer):
    """Mirrors: cc to planning@youngman.co.in"""

    def update(self, event_type, data):
        return {
            'channel': 'email',
            'recipient': 'planning@youngman.co.in',
            'subject': f"New order for planning: {data['job_order']}",
            'message': (
                f"Order {data['job_order']} needs planning.\n"
                f"Customer: {data['customer_name']}\n"
                f"Godown: {data['godown']}\n"
                f"Amount: Rs.{data.get('total_amount', 0)}"
            ),
        }

    def get_name(self):
        return "PlanningTeamNotifier"


class CustomerSMSNotifier(Observer):
    """Mirrors: SMSChannel sends to customer phone"""

    def update(self, event_type, data):
        phone = data.get('customer_phone', '')
        return {
            'channel': 'sms',
            'recipient': phone,
            'subject': '',
            'message': (
                f"Youngman: Your order {data['job_order']} has been {event_type}. "
                f"For queries call 1800-XXX-XXXX"
            ),
        }

    def get_name(self):
        return "CustomerSMSNotifier"


class DatabaseNotifier(Observer):
    """Mirrors: toDatabase() - in-app notification log"""

    def update(self, event_type, data):
        return {
            'channel': 'database',
            'recipient': data.get('created_by', 'system'),
            'subject': f"Order {event_type}",
            'message': f"Order {data['job_order']} status changed to {event_type}",
        }

    def get_name(self):
        return "DatabaseNotifier"


class WhatsAppNotifier(Observer):
    """For future - WhatsApp via WATI"""

    def update(self, event_type, data):
        phone = data.get('customer_phone', '')
        return {
            'channel': 'whatsapp',
            'recipient': phone,
            'subject': '',
            'message': f"Youngman Update: Order {data['job_order']} is now {event_type}.",
        }

    def get_name(self):
        return "WhatsAppNotifier"


# ---------------------------------------------------------------------------
# Registry of all available observer classes (for dynamic registration)
# ---------------------------------------------------------------------------
AVAILABLE_OBSERVERS = {
    'AccountManagerNotifier': AccountManagerNotifier,
    'PlanningTeamNotifier': PlanningTeamNotifier,
    'CustomerSMSNotifier': CustomerSMSNotifier,
    'DatabaseNotifier': DatabaseNotifier,
    'WhatsAppNotifier': WhatsAppNotifier,
}


class EventManager:
    """
    The Subject in the Observer pattern.
    Manages event subscriptions and dispatches notifications.
    Mirrors Laravel's EventServiceProvider mapping.
    """

    def __init__(self):
        self._observers: Dict[str, List[Observer]] = {}

    def subscribe(self, event_type: str, observer: Observer):
        """Register an observer for an event type."""
        if event_type not in self._observers:
            self._observers[event_type] = []
        # Avoid duplicates
        if not any(o.get_name() == observer.get_name() for o in self._observers[event_type]):
            self._observers[event_type].append(observer)

    def unsubscribe(self, event_type: str, observer_name: str):
        """Remove an observer by name."""
        if event_type in self._observers:
            self._observers[event_type] = [
                o for o in self._observers[event_type]
                if o.get_name() != observer_name
            ]

    def notify(self, event_type: str, data: dict) -> list:
        """Notify all observers for this event. Return list of results."""
        results = []
        for observer in self._observers.get(event_type, []):
            try:
                result = observer.update(event_type, data)
                result['observer'] = observer.get_name()
                result['status'] = 'sent'
                results.append(result)
            except Exception as e:
                results.append({
                    'observer': observer.get_name(),
                    'status': 'failed',
                    'error': str(e),
                })
        return results

    def get_subscribers(self, event_type: str = None) -> dict:
        """List all subscribers, optionally filtered by event type."""
        if event_type:
            return {
                event_type: [o.get_name() for o in self._observers.get(event_type, [])]
            }
        return {
            et: [o.get_name() for o in observers]
            for et, observers in self._observers.items()
        }

    def get_all_event_types(self) -> list:
        """Return list of all registered event types."""
        return list(self._observers.keys())


def get_default_event_manager() -> EventManager:
    """
    Pre-configured event manager - mirrors EventServiceProvider.
    Sets up default observers for each event type.

    Laravel equivalent:
        protected $listen = [
            OrderApproved::class => [
                SendOrderApprovedNotification::class,   // AM email
                NotifyPlanningTeam::class,               // Planning email
                SendCustomerSMS::class,                  // Customer SMS
                LogOrderApproval::class,                 // DB log
            ],
            OrderRejected::class => [
                SendOrderRejectedNotification::class,
                LogOrderRejection::class,
            ],
            ...
        ];
    """
    manager = EventManager()

    # Order Approved - 4 observers
    manager.subscribe('approved', AccountManagerNotifier())
    manager.subscribe('approved', PlanningTeamNotifier())
    manager.subscribe('approved', CustomerSMSNotifier())
    manager.subscribe('approved', DatabaseNotifier())

    # Order Rejected - 2 observers
    manager.subscribe('rejected', AccountManagerNotifier())
    manager.subscribe('rejected', DatabaseNotifier())

    # Order Amended - 3 observers
    manager.subscribe('amended', AccountManagerNotifier())
    manager.subscribe('amended', PlanningTeamNotifier())
    manager.subscribe('amended', DatabaseNotifier())

    return manager
