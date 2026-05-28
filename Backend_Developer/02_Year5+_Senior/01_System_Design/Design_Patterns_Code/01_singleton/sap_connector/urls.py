from django.urls import path
from . import views

app_name = 'sap_connector'

urlpatterns = [
    # Connection management
    path('connection/status/', views.ConnectionStatusView.as_view(), name='connection-status'),
    path('connection/connect/', views.ConnectionConnectView.as_view(), name='connection-connect'),
    path('connection/disconnect/', views.ConnectionDisconnectView.as_view(), name='connection-disconnect'),
    path('connection/logs/', views.ConnectionLogsView.as_view(), name='connection-logs'),

    # SAP B1 entity operations (all use the singleton connection)
    path('sap/invoices/', views.SapInvoiceView.as_view(), name='sap-invoices'),
    path('sap/credit-notes/', views.SapCreditNoteView.as_view(), name='sap-credit-notes'),
    path('sap/journal-entries/', views.SapJournalEntryView.as_view(), name='sap-journal-entries'),
    path('sap/business-partners/', views.SapBusinessPartnerView.as_view(), name='sap-business-partners'),

    # Singleton proof
    path('singleton-proof/', views.SingletonProofView.as_view(), name='singleton-proof'),
]
