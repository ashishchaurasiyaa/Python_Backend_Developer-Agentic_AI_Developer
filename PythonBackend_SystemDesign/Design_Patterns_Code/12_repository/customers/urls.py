"""
URL routes for the customers app.
All routes are prefixed with /api/ via the project-level urls.py.
"""

from django.urls import path
from customers.views import (
    CustomerListView,
    CustomerDetailView,
    CustomerSearchView,
    CustomerOutstandingView,
    CustomerByBusinessTypeView,
)

app_name = "customers"

urlpatterns = [
    # -- Search & filtered views (placed before <pk> to avoid conflicts) ----
    path("search/", CustomerSearchView.as_view(), name="customer-search"),
    path("outstanding/", CustomerOutstandingView.as_view(), name="customer-outstanding"),
    path("business-type/", CustomerByBusinessTypeView.as_view(), name="customer-by-business-type"),

    # -- CRUD ---------------------------------------------------------------
    path("", CustomerListView.as_view(), name="customer-list"),
    path("<int:pk>/", CustomerDetailView.as_view(), name="customer-detail"),
]
