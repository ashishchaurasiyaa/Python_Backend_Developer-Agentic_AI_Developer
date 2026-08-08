from django.urls import path

from . import views

app_name = 'credit_pipeline'

urlpatterns = [
    path('entries/', views.EntryListView.as_view(), name='entry-list'),
    path('entries/<str:invoice_doc_number>/', views.EntryDetailView.as_view(), name='entry-detail'),
    path('entries/<str:invoice_doc_number>/advance/', views.AdvanceStatusView.as_view(), name='entry-advance'),
    path('entries/<str:invoice_doc_number>/mark-paid/', views.MarkPaidView.as_view(), name='entry-mark-paid'),
    path('entries/<str:invoice_doc_number>/escalate/', views.EscalateToLegalView.as_view(), name='entry-escalate'),
    path('entries/<str:invoice_doc_number>/sales-issue/', views.MarkSalesIssueView.as_view(), name='entry-sales-issue'),
    path('entries/<str:invoice_doc_number>/transitions/', views.TransitionLogListView.as_view(), name='entry-transitions'),
    path('undo-last/', views.UndoLastCommandView.as_view(), name='undo-last'),
    path('invoker-history/', views.InvokerHistoryView.as_view(), name='invoker-history'),
]
