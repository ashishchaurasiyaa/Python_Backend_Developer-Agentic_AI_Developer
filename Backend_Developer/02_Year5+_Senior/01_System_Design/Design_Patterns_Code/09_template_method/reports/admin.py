from django.contrib import admin

from .models import GeneratedReport, Report, ReportRecipient


class ReportRecipientInline(admin.TabularInline):
    model = ReportRecipient
    extra = 1


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ('name', 'report_type', 'output_format', 'interval',
                    'is_active', 'last_generated')
    list_filter = ('report_type', 'output_format', 'interval', 'is_active')
    search_fields = ('name', 'description')
    inlines = [ReportRecipientInline]


@admin.register(ReportRecipient)
class ReportRecipientAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'report')
    search_fields = ('name', 'email')


@admin.register(GeneratedReport)
class GeneratedReportAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'report', 'row_count', 'column_count',
                    'status', 'generated_at')
    list_filter = ('status',)
    readonly_fields = ('generated_at',)
