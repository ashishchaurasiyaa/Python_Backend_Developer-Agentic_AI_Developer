from django.contrib import admin

from accounts.models import Account, Balance


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ["account_number", "user", "account_type", "currency", "status", "opened_at"]
    list_filter = ["account_type", "status", "currency"]
    search_fields = ["account_number", "user__username", "user__email"]


@admin.register(Balance)
class BalanceAdmin(admin.ModelAdmin):
    list_display = ["account", "current_balance", "available_balance", "version", "updated_at"]
