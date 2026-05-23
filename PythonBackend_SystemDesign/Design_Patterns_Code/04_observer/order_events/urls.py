from django.urls import path
from . import views

app_name = 'order_events'

urlpatterns = [
    # Order CRUD
    path('orders/', views.order_list_create, name='order-list-create'),

    # Status change (fires observers)
    path('orders/<int:pk>/approve/', views.order_approve, name='order-approve'),
    path('orders/<int:pk>/reject/', views.order_reject, name='order-reject'),
    path('orders/<int:pk>/amend/', views.order_amend, name='order-amend'),

    # Notifications for an order
    path('orders/<int:pk>/notifications/', views.order_notifications, name='order-notifications'),

    # Event logs
    path('event-logs/', views.event_log_list, name='event-log-list'),

    # Observer registry
    path('subscribers/', views.subscribers_list, name='subscribers-list'),
    path('subscribers/register/', views.register_observer, name='register-observer'),
    path('subscribers/unsubscribe/', views.unsubscribe_observer, name='unsubscribe-observer'),
]
