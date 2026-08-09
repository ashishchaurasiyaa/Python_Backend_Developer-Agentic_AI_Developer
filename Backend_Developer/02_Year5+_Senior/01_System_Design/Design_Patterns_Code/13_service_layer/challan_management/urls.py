from django.urls import path

from . import views

app_name = 'challan_management'

urlpatterns = [
    # Static segments first so they cannot be shadowed by the <int:pk> routes.
    path('challans/pending-authorization/', views.PendingAuthorizationView.as_view(), name='challan-pending'),
    path('challans/', views.ChallanListView.as_view(), name='challan-list'),
    path('challans/<int:pk>/', views.ChallanDetailView.as_view(), name='challan-detail'),
    path('challans/<int:pk>/authorize/', views.AuthorizeChallanView.as_view(), name='challan-authorize'),
    path('challans/<int:pk>/advance-stage/', views.AdvanceStageView.as_view(), name='challan-advance-stage'),
    path('challans/<int:pk>/items/', views.ChallanItemsView.as_view(), name='challan-items'),
    path('challans/<int:pk>/close/', views.CloseChallanView.as_view(), name='challan-close'),
    path('challans/<int:pk>/stage-logs/', views.ChallanStageLogView.as_view(), name='challan-stage-logs'),
    path('stage-flow/', views.StageFlowView.as_view(), name='stage-flow'),
]
