"""
Django Admin Customization — Production Patterns

Place in `<app>/admin.py`. Each section is a complete admin class.
"""

from django.contrib import admin
from django import forms
from django.http import HttpResponse
from django.utils.html import format_html
from django.urls import path, reverse
from django.shortcuts import render, redirect
from django.contrib import messages


# ==========================================================================
# 1. PERFORMANCE-TUNED ADMIN
# ==========================================================================

# @admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    # List view performance
    list_display = (
        'title_link',
        'author_link',
        'category_name',
        'status_badge',
        'view_count',
        'created_at',
    )
    list_select_related = ('author', 'category')
    list_filter = ('status', 'category', 'created_at')
    search_fields = ('title', 'body', 'author__username')
    autocomplete_fields = ('author', 'category')
    date_hierarchy = 'created_at'
    list_per_page = 25
    show_full_result_count = False    # for huge tables
    ordering = ('-created_at',)

    @admin.display(description='Title', ordering='title')
    def title_link(self, obj):
        url = reverse('admin:blog_article_change', args=[obj.pk])
        return format_html('<a href="{}">{}</a>', url, obj.title)

    @admin.display(description='Author', ordering='author__username')
    def author_link(self, obj):
        url = reverse('admin:auth_user_change', args=[obj.author_id])
        return format_html('<a href="{}">{}</a>', url, obj.author.username)

    @admin.display(description='Category')
    def category_name(self, obj):
        return obj.category.name if obj.category else '-'

    @admin.display(description='Status')
    def status_badge(self, obj):
        colors = {
            'draft': 'gray',
            'published': 'green',
            'archived': 'red',
        }
        return format_html(
            '<span style="padding:2px 8px;border-radius:3px;background:{};color:white;">{}</span>',
            colors.get(obj.status, 'gray'),
            obj.status,
        )


# ==========================================================================
# 2. INLINES
# ==========================================================================

# class CommentInline(admin.TabularInline):
#     model = Comment
#     extra = 0                  # don't show blank rows
#     can_delete = True
#     fields = ('author', 'body', 'created_at')
#     readonly_fields = ('created_at',)
#     classes = ('collapse',)    # collapsed by default
#     show_change_link = True
#
#     def get_queryset(self, request):
#         # Only show last 10 comments to keep page fast
#         return super().get_queryset(request).order_by('-created_at')[:10]


# ==========================================================================
# 3. CUSTOM ACTIONS (with safety + Celery dispatch)
# ==========================================================================

@admin.action(description='Mark selected as published')
def mark_as_published(modeladmin, request, queryset):
    updated = queryset.update(status='published')
    modeladmin.message_user(
        request,
        f'{updated} articles marked as published.',
        messages.SUCCESS,
    )


@admin.action(description='Export selected to CSV')
def export_to_csv(modeladmin, request, queryset):
    import csv
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="export.csv"'

    writer = csv.writer(response)
    # Header
    writer.writerow(['ID', 'Title', 'Author', 'Status', 'Created'])
    # Rows — stream
    for obj in queryset.iterator(chunk_size=1000):
        writer.writerow([
            obj.id,
            obj.title,
            obj.author.username,
            obj.status,
            obj.created_at.isoformat(),
        ])
    return response


@admin.action(description='Process via Celery (background)')
def process_async(modeladmin, request, queryset):
    # from blog.tasks import process_article
    pks = list(queryset.values_list('pk', flat=True))
    # process_article.delay(pks)
    modeladmin.message_user(
        request,
        f'{len(pks)} articles queued for processing.',
        messages.INFO,
    )


# ==========================================================================
# 4. CUSTOM LIST FILTER
# ==========================================================================

class HasCommentsFilter(admin.SimpleListFilter):
    title = 'has comments'
    parameter_name = 'has_comments'

    def lookups(self, request, model_admin):
        return (
            ('yes', 'Yes'),
            ('no', 'No'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'yes':
            return queryset.filter(comments__isnull=False).distinct()
        if self.value() == 'no':
            return queryset.filter(comments__isnull=True)
        return queryset


class CreatedInLastNDaysFilter(admin.SimpleListFilter):
    title = 'created in last'
    parameter_name = 'created_last'

    def lookups(self, request, model_admin):
        return (
            ('1', 'Last 24 hours'),
            ('7', 'Last 7 days'),
            ('30', 'Last 30 days'),
        )

    def queryset(self, request, queryset):
        from django.utils import timezone
        from datetime import timedelta
        v = self.value()
        if not v:
            return queryset
        cutoff = timezone.now() - timedelta(days=int(v))
        return queryset.filter(created_at__gte=cutoff)


# ==========================================================================
# 5. CUSTOM FORM + FIELDSETS + READONLY
# ==========================================================================

class ArticleAdminForm(forms.ModelForm):
    class Meta:
        # model = Article
        fields = '__all__'
        widgets = {
            'body': forms.Textarea(attrs={'rows': 25, 'cols': 100}),
        }

    def clean_title(self):
        title = self.cleaned_data['title'].strip()
        if not title:
            raise forms.ValidationError("Title required")
        if title.lower().startswith('test'):
            raise forms.ValidationError("No 'test' titles in prod")
        return title

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('status') == 'published' and not cleaned.get('body'):
            raise forms.ValidationError("Published articles must have body")
        return cleaned


# class FullArticleAdmin(admin.ModelAdmin):
#     form = ArticleAdminForm
#     readonly_fields = ('id', 'created_at', 'updated_at', 'view_count')
#     fieldsets = (
#         ('Basic', {'fields': ('title', 'slug', 'author', 'category')}),
#         ('Content', {'fields': ('excerpt', 'body'), 'classes': ('wide',)}),
#         ('Publishing', {'fields': ('status', 'published_at'), 'classes': ('collapse',)}),
#         ('Metadata', {'fields': ('id', 'view_count', 'created_at', 'updated_at'), 'classes': ('collapse',)}),
#     )


# ==========================================================================
# 6. PERMISSION-RESTRICTED ADMIN (Ops Read-Only)
# ==========================================================================

# @admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'amount', 'status', 'created_at')
    list_select_related = ('user',)
    list_filter = ('status', 'created_at')
    search_fields = ('user__email', 'id')

    def has_add_permission(self, request):
        return False  # no manual add

    def has_delete_permission(self, request, obj=None):
        return False  # soft delete only

    def has_change_permission(self, request, obj=None):
        # Superusers + explicit perm only
        if request.user.is_superuser:
            return True
        return request.user.has_perm('orders.change_order')

    def get_readonly_fields(self, request, obj=None):
        if not request.user.is_superuser:
            return [f.name for f in self.model._meta.fields]
        return ('id', 'created_at')


# ==========================================================================
# 7. CUSTOM URLs / VIEWS IN ADMIN
# ==========================================================================

# @admin.register(Article)
class ArticleAdminWithImport(admin.ModelAdmin):
    change_list_template = 'admin/blog/article_changelist.html'

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('import-csv/', self.admin_site.admin_view(self.import_csv_view),
                 name='blog_article_import_csv'),
        ]
        return custom + urls

    def import_csv_view(self, request):
        if request.method == 'POST':
            csv_file = request.FILES.get('csv_file')
            if not csv_file:
                messages.error(request, 'No file uploaded')
                return redirect('admin:blog_article_import_csv')

            import csv as csvmod
            from io import TextIOWrapper
            from django.db import transaction

            reader = csvmod.DictReader(TextIOWrapper(csv_file, encoding='utf-8'))
            count = 0
            with transaction.atomic():
                for row in reader:
                    # Article.objects.create(
                    #     title=row['title'],
                    #     body=row['body'],
                    #     status=row.get('status', 'draft'),
                    # )
                    count += 1

            messages.success(request, f'Imported {count} articles')
            return redirect('admin:blog_article_changelist')

        return render(request, 'admin/import_csv.html')


# ==========================================================================
# 8. MULTIPLE ADMIN SITES (different audiences)
# ==========================================================================

class SupportAdminSite(admin.AdminSite):
    site_header = 'Support Console'
    site_title = 'Support'
    index_title = 'Customer Support Tools'
    site_url = '/support/'


support_site = SupportAdminSite(name='support')


# class SupportTicketAdmin(admin.ModelAdmin):
#     list_display = ('id', 'subject', 'user', 'status')
#     readonly_fields = ('user', 'created_at')
#
#     def has_add_permission(self, request):
#         return False


# support_site.register(Ticket, SupportTicketAdmin)


# urls.py:
# from myapp.admin_sites import support_site
# urlpatterns = [
#     path('admin/', admin.site.urls),
#     path('support/', support_site.urls),
# ]


# ==========================================================================
# 9. ADMIN WITH SOFT-DELETE VISIBILITY
# ==========================================================================

# class CommentAdmin(admin.ModelAdmin):
#     list_display = ('id', 'author', 'body_preview', 'deleted_status')
#
#     def get_queryset(self, request):
#         # Include soft-deleted in admin
#         return Comment.all_objects.get_queryset()
#
#     @admin.display(description='Deleted')
#     def deleted_status(self, obj):
#         return 'Deleted' if obj.deleted_at else 'Active'
#
#     def get_actions(self, request):
#         actions = super().get_actions(request)
#         actions['restore_selected'] = (
#             self.restore_selected,
#             'restore_selected',
#             'Restore selected (undelete)',
#         )
#         return actions
#
#     def restore_selected(self, request, queryset):
#         updated = queryset.update(deleted_at=None)
#         self.message_user(request, f'{updated} restored.')


# ==========================================================================
# 10. ADMIN MEDIA CUSTOMIZATION
# ==========================================================================
"""
# Branding
admin.site.site_header = 'MyApp Admin'
admin.site.site_title = 'MyApp'
admin.site.index_title = 'Dashboard'

# Custom CSS
class ArticleAdmin(admin.ModelAdmin):
    class Media:
        css = {'all': ('admin/css/custom.css',)}
        js = ('admin/js/article_admin.js',)
"""
