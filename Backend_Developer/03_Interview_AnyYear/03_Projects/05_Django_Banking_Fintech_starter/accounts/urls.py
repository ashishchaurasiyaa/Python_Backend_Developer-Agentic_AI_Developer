from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts.views import AccountBalanceView, AccountDetailView, AccountListCreateView, SignupView

urlpatterns = [
    path("auth/signup", SignupView.as_view(), name="signup"),
    path("auth/login", TokenObtainPairView.as_view(), name="login"),
    path("auth/refresh", TokenRefreshView.as_view(), name="refresh"),
    path("accounts", AccountListCreateView.as_view(), name="account-list"),
    path("accounts/<int:pk>", AccountDetailView.as_view(), name="account-detail"),
    path("accounts/<int:pk>/balance", AccountBalanceView.as_view(), name="account-balance"),
]
