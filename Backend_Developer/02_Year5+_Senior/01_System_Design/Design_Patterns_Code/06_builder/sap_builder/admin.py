from django.contrib import admin

from .models import BuiltPayload, DraftLine, SapDocumentDraft


class DraftLineInline(admin.TabularInline):
    model = DraftLine
    extra = 0


@admin.register(SapDocumentDraft)
class SapDocumentDraftAdmin(admin.ModelAdmin):
    list_display = ('reference_no', 'doc_type', 'card_name', 'from_warehouse',
                    'to_warehouse', 'vehicle_number', 'posting_date')
    list_filter = ('doc_type', 'transport_mode')
    search_fields = ('reference_no', 'card_code', 'card_name', 'vehicle_number')
    inlines = [DraftLineInline]


@admin.register(DraftLine)
class DraftLineAdmin(admin.ModelAdmin):
    list_display = ('item_code', 'item_name', 'hsn_code', 'quantity', 'unit',
                    'rate', 'draft')
    search_fields = ('item_code', 'item_name', 'hsn_code')


@admin.register(BuiltPayload)
class BuiltPayloadAdmin(admin.ModelAdmin):
    list_display = ('draft', 'builder_used', 'recipe', 'line_count',
                    'taxable_value', 'total_value', 'built_at')
    list_filter = ('builder_used', 'recipe')
    readonly_fields = ('built_at',)
