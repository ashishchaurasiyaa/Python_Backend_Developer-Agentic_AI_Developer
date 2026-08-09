from django.urls import path

from . import views

app_name = 'sap_documents'

urlpatterns = [
    path('documents/', views.SapDocumentListView.as_view(), name='document-list'),
    path('documents/<int:pk>/', views.SapDocumentDetailView.as_view(), name='document-detail'),
    path('documents/<int:pk>/lines/', views.SapDocumentLineView.as_view(), name='document-lines'),
    path('documents/<int:pk>/payload/', views.PreviewPayloadView.as_view(), name='document-payload'),
    path('documents/<int:pk>/post/', views.PostDocumentView.as_view(), name='document-post'),
    path('documents/<int:pk>/posting-logs/', views.PostingLogView.as_view(), name='document-posting-logs'),
    path('families/', views.FamilyRegistryView.as_view(), name='family-registry'),
]
