from django.contrib import admin

from .models import Challan, ChallanItem, ChallanStageLog


class ChallanItemInline(admin.TabularInline):
    model = ChallanItem
    extra = 0


class ChallanStageLogInline(admin.TabularInline):
    model = ChallanStageLog
    extra = 0
    readonly_fields = ('from_stage', 'to_stage', 'changed_by', 'remarks',
                       'changed_at')
    can_delete = False


@admin.register(Challan)
class ChallanAdmin(admin.ModelAdmin):
    list_display = ('challan_no', 'challan_type', 'challan_movement_type',
                    'order_id', 'is_authorized', 'current_stage',
                    'freight_amount', 'created_at')
    list_filter = ('challan_type', 'challan_movement_type', 'is_authorized',
                   'current_stage')
    search_fields = ('challan_no', 'pickup_location', 'delivery_location')
    readonly_fields = ('challan_no', 'created_at', 'updated_at')
    inlines = [ChallanItemInline, ChallanStageLogInline]


@admin.register(ChallanItem)
class ChallanItemAdmin(admin.ModelAdmin):
    list_display = ('item_code', 'item_name', 'quantity', 'ok_quantity',
                    'damaged_quantity', 'missing_quantity', 'challan')
    search_fields = ('item_code', 'item_name')


@admin.register(ChallanStageLog)
class ChallanStageLogAdmin(admin.ModelAdmin):
    list_display = ('challan', 'from_stage', 'to_stage', 'changed_by',
                    'changed_at')
    list_filter = ('from_stage', 'to_stage')
    readonly_fields = ('changed_at',)
