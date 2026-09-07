from django.contrib import admin

from ledger.models import AuditLog, LedgerEntry, Transaction


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ["id", "txn_type", "status", "amount", "currency", "source_account", "dest_account", "initiated_at"]
    list_filter = ["txn_type", "status", "currency"]
    search_fields = ["id", "idempotency_key"]


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ["id", "transaction", "account", "entry_type", "amount", "balance_after", "created_at"]
    list_filter = ["entry_type"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ["id", "action", "resource_type", "resource_id", "actor", "created_at"]
    list_filter = ["action", "resource_type"]

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
