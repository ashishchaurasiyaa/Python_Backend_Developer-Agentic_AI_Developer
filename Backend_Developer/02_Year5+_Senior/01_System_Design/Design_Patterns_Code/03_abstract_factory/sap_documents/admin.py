from django.contrib import admin

from .models import SapDocument, SapDocumentLine, SapPostingLog


class SapDocumentLineInline(admin.TabularInline):
    model = SapDocumentLine
    extra = 0


class SapPostingLogInline(admin.TabularInline):
    model = SapPostingLog
    extra = 0
    readonly_fields = ('factory_used', 'endpoint', 'succeeded', 'message',
                       'attempted_at')
    can_delete = False


@admin.register(SapDocument)
class SapDocumentAdmin(admin.ModelAdmin):
    list_display = ('reference_no', 'doc_family', 'card_code', 'status',
                    'sap_doc_entry', 'sap_doc_num', 'posting_date')
    list_filter = ('doc_family', 'status')
    search_fields = ('reference_no', 'card_code', 'card_name')
    readonly_fields = ('sap_doc_entry', 'sap_doc_num', 'created_at')
    inlines = [SapDocumentLineInline, SapPostingLogInline]


@admin.register(SapDocumentLine)
class SapDocumentLineAdmin(admin.ModelAdmin):
    list_display = ('item_code', 'item_name', 'quantity', 'unit_price',
                    'warehouse_code', 'base_entry', 'document')
    search_fields = ('item_code', 'item_name')


@admin.register(SapPostingLog)
class SapPostingLogAdmin(admin.ModelAdmin):
    list_display = ('document', 'factory_used', 'endpoint', 'succeeded',
                    'attempted_at')
    list_filter = ('succeeded', 'endpoint')
    readonly_fields = ('attempted_at',)
