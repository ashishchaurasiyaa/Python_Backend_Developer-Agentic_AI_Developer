"""
Root URL configuration for the repository_project.
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/customers/", include("customers.urls")),
]
