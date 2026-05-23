from django.contrib import admin
from .models import Order, Notification, EventLog


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['job_order', 'customer_name', 'godown', 'status', 'total_amount', 'created_at']
    list_filter = ['status', 'godown']
    search_fields = ['job_order', 'customer_name']


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['order', 'channel', 'recipient', 'event_type', 'is_read', 'sent_at']
    list_filter = ['channel', 'event_type', 'is_read']
    search_fields = ['recipient', 'subject']


@admin.register(EventLog)
class EventLogAdmin(admin.ModelAdmin):
    list_display = ['event_type', 'order', 'observers_notified', 'created_at']
    list_filter = ['event_type']
