from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("initiate/", views.PaymentInitiateView.as_view(), name="payment-initiate"),
    path("verify/", views.PaymentVerifyView.as_view(), name="payment-verify"),
    path("refund/", views.PaymentRefundView.as_view(), name="payment-refund"),
    path("gateway/", views.ActiveGatewayView.as_view(), name="active-gateway"),
    path("gateway/switch/", views.SwitchGatewayView.as_view(), name="switch-gateway"),
    path("list/", views.PaymentListView.as_view(), name="payment-list"),
]
