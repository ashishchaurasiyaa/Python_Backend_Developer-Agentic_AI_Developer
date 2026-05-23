"""
views.py - Observer Pattern API Views
======================================

Endpoints:
  POST   /api/orders/                   - Create an order
  GET    /api/orders/                   - List all orders
  POST   /api/orders/<id>/approve/      - Approve order (fires observers)
  POST   /api/orders/<id>/reject/       - Reject order (fires observers)
  POST   /api/orders/<id>/amend/        - Amend order (fires observers)
  GET    /api/orders/<id>/notifications/ - List notifications for an order
  GET    /api/event-logs/               - List all event logs
  GET    /api/subscribers/              - Show event->observer mappings
  POST   /api/subscribers/register/     - Dynamically add an observer
  POST   /api/subscribers/unsubscribe/  - Remove an observer
"""

from decimal import Decimal
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from .models import Order, Notification, EventLog
from .serializers import (
    OrderSerializer,
    OrderCreateSerializer,
    NotificationSerializer,
    EventLogSerializer,
    RegisterObserverSerializer,
    UnsubscribeObserverSerializer,
)
from .observers import get_default_event_manager, AVAILABLE_OBSERVERS


# ---------------------------------------------------------------------------
# Module-level event manager (singleton for the app lifecycle)
# ---------------------------------------------------------------------------
event_manager = get_default_event_manager()


def _build_order_data(order: Order) -> dict:
    """Convert Order model to dict for observer consumption."""
    return {
        'id': order.id,
        'job_order': order.job_order,
        'customer_name': order.customer_name,
        'godown': order.godown,
        'po_no': order.po_no or 'N/A',
        'total_amount': str(order.total_amount),
        'account_manager_email': order.account_manager_email,
        'customer_phone': order.customer_phone,
        'created_by': order.created_by,
    }


def _fire_event(order: Order, event_type: str) -> list:
    """
    Fire an event through the EventManager.
    1. Notify all observers
    2. Save each notification to DB
    3. Create an EventLog entry
    Returns the list of notification results.
    """
    data = _build_order_data(order)

    # --- Notify all observers ---
    results = event_manager.notify(event_type, data)

    # --- Persist notifications to DB ---
    for result in results:
        if result.get('status') == 'sent':
            Notification.objects.create(
                order=order,
                recipient=result.get('recipient', ''),
                channel=result.get('channel', 'database'),
                subject=result.get('subject', ''),
                message=result.get('message', ''),
                event_type=event_type,
            )

    # --- Create EventLog ---
    observer_names = [r.get('observer', '') for r in results]
    EventLog.objects.create(
        event_type=event_type,
        order=order,
        payload=data,
        observers_notified=len(results),
        observer_names=observer_names,
    )

    return results


# ===========================================================================
# Order CRUD
# ===========================================================================
@api_view(['GET', 'POST'])
def order_list_create(request):
    """
    GET  - List all orders.
    POST - Create a new order (status defaults to under_review).
    """
    if request.method == 'GET':
        orders = Order.objects.all()
        serializer = OrderSerializer(orders, many=True)
        return Response({
            'pattern': 'Observer',
            'count': orders.count(),
            'orders': serializer.data,
        })

    # POST
    serializer = OrderCreateSerializer(data=request.data)
    if serializer.is_valid():
        order = serializer.save()
        return Response({
            'message': f"Order {order.job_order} created successfully",
            'order': OrderSerializer(order).data,
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ===========================================================================
# Status Change Endpoints (fire observers)
# ===========================================================================
@api_view(['POST'])
def order_approve(request, pk):
    """
    Approve an order -> fires 'approved' event -> notifies 4 observers.
    """
    try:
        order = Order.objects.get(pk=pk)
    except Order.DoesNotExist:
        return Response(
            {'error': f'Order {pk} not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if order.status == 'approved':
        return Response(
            {'error': f'Order {order.job_order} is already approved'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Update status
    order.status = 'approved'
    order.save()

    # Fire event
    results = _fire_event(order, 'approved')

    return Response({
        'message': f"Order {order.job_order} approved successfully",
        'order': OrderSerializer(order).data,
        'observers_notified': len(results),
        'notifications': results,
        'pattern_explanation': (
            'Observer pattern: The EventManager (subject) notified all '
            'subscribed observers for the "approved" event. Each observer '
            'independently processed the event without the order knowing '
            'about them.'
        ),
    })


@api_view(['POST'])
def order_reject(request, pk):
    """
    Reject an order -> fires 'rejected' event -> notifies 2 observers.
    """
    try:
        order = Order.objects.get(pk=pk)
    except Order.DoesNotExist:
        return Response(
            {'error': f'Order {pk} not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    if order.status == 'rejected':
        return Response(
            {'error': f'Order {order.job_order} is already rejected'},
            status=status.HTTP_400_BAD_REQUEST
        )

    order.status = 'rejected'
    order.save()

    results = _fire_event(order, 'rejected')

    return Response({
        'message': f"Order {order.job_order} rejected",
        'order': OrderSerializer(order).data,
        'observers_notified': len(results),
        'notifications': results,
    })


@api_view(['POST'])
def order_amend(request, pk):
    """
    Amend an order -> fires 'amended' event -> notifies 3 observers.
    """
    try:
        order = Order.objects.get(pk=pk)
    except Order.DoesNotExist:
        return Response(
            {'error': f'Order {pk} not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    order.status = 'amended'
    order.save()

    results = _fire_event(order, 'amended')

    return Response({
        'message': f"Order {order.job_order} amended",
        'order': OrderSerializer(order).data,
        'observers_notified': len(results),
        'notifications': results,
    })


# ===========================================================================
# Notifications for an Order
# ===========================================================================
@api_view(['GET'])
def order_notifications(request, pk):
    """List all notifications for a specific order."""
    try:
        order = Order.objects.get(pk=pk)
    except Order.DoesNotExist:
        return Response(
            {'error': f'Order {pk} not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    notifications = Notification.objects.filter(order=order)
    serializer = NotificationSerializer(notifications, many=True)
    return Response({
        'order': order.job_order,
        'count': notifications.count(),
        'notifications': serializer.data,
    })


# ===========================================================================
# Event Logs
# ===========================================================================
@api_view(['GET'])
def event_log_list(request):
    """List all event logs."""
    logs = EventLog.objects.all()
    serializer = EventLogSerializer(logs, many=True)
    return Response({
        'count': logs.count(),
        'event_logs': serializer.data,
    })


# ===========================================================================
# Subscribers (Observer Registry)
# ===========================================================================
@api_view(['GET'])
def subscribers_list(request):
    """Show all event type -> observer mappings."""
    subscribers = event_manager.get_subscribers()
    event_types = event_manager.get_all_event_types()

    return Response({
        'pattern': 'Observer',
        'description': (
            'Each event type has a list of observers subscribed to it. '
            'When an event fires, all subscribed observers are notified.'
        ),
        'total_event_types': len(event_types),
        'total_observers': sum(len(v) for v in subscribers.values()),
        'event_subscriber_map': subscribers,
        'available_observers': list(AVAILABLE_OBSERVERS.keys()),
        'laravel_equivalent': 'EventServiceProvider::$listen',
    })


@api_view(['POST'])
def register_observer(request):
    """
    Dynamically register an observer for an event type.
    POST body: {"event_type": "approved", "observer_name": "WhatsAppNotifier"}
    """
    serializer = RegisterObserverSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    event_type = serializer.validated_data['event_type']
    observer_name = serializer.validated_data['observer_name']

    if observer_name not in AVAILABLE_OBSERVERS:
        return Response({
            'error': f"Observer '{observer_name}' not found",
            'available': list(AVAILABLE_OBSERVERS.keys()),
        }, status=status.HTTP_400_BAD_REQUEST)

    observer_cls = AVAILABLE_OBSERVERS[observer_name]
    event_manager.subscribe(event_type, observer_cls())

    return Response({
        'message': f"Observer '{observer_name}' registered for event '{event_type}'",
        'current_subscribers': event_manager.get_subscribers(event_type),
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
def unsubscribe_observer(request):
    """
    Dynamically remove an observer from an event type.
    POST body: {"event_type": "approved", "observer_name": "CustomerSMSNotifier"}
    """
    serializer = UnsubscribeObserverSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    event_type = serializer.validated_data['event_type']
    observer_name = serializer.validated_data['observer_name']

    event_manager.unsubscribe(event_type, observer_name)

    return Response({
        'message': f"Observer '{observer_name}' removed from event '{event_type}'",
        'current_subscribers': event_manager.get_subscribers(event_type),
    })
