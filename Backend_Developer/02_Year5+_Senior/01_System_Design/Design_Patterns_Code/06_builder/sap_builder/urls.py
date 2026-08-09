from django.urls import path

from . import views

app_name = 'sap_builder'

urlpatterns = [
    path('drafts/', views.DraftListView.as_view(), name='draft-list'),
    path('drafts/<int:pk>/', views.DraftDetailView.as_view(), name='draft-detail'),
    path('drafts/<int:pk>/lines/', views.DraftLineView.as_view(), name='draft-lines'),
    path('drafts/<int:pk>/build/', views.BuildPayloadView.as_view(), name='draft-build'),
    path('drafts/<int:pk>/eway-bill/', views.BuildEwayBillView.as_view(), name='draft-eway-bill'),
    path('drafts/<int:pk>/payloads/', views.BuiltPayloadListView.as_view(), name='draft-payloads'),
    path('payloads/<int:pk>/', views.BuiltPayloadDetailView.as_view(), name='payload-detail'),
    path('builders/', views.BuilderCatalogueView.as_view(), name='builder-catalogue'),
]
