from django.urls import path

from . import views

app_name = 'reports'

urlpatterns = [
    path('reports/', views.ReportListView.as_view(), name='report-list'),
    path('reports/<int:pk>/', views.ReportDetailView.as_view(), name='report-detail'),
    path('reports/<int:pk>/generate/', views.ReportGenerateView.as_view(), name='report-generate'),
    path('reports/<int:pk>/generated/', views.GeneratedReportListView.as_view(), name='report-generated'),
    path('reports/<int:pk>/recipients/', views.ReportRecipientView.as_view(), name='report-recipients'),
    path('generated/<int:pk>/', views.GeneratedReportDetailView.as_view(), name='generated-detail'),
    path('generators/', views.GeneratorRegistryView.as_view(), name='generator-registry'),
]
