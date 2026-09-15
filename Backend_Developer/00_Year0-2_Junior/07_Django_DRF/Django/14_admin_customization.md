# Django Admin Customization — ModelAdmin Deep Dive

## Why It Matters (Senior 5 YOE Context)

Django Admin = **free production-ready CMS** that 80% of teams underutilize. Senior engineers customize it for:

- **Ops/support team UI** → no need for custom dashboards
- **Data correction** → CSV import, bulk edits
- **Audit visibility** → who changed what, when
- **Read-only views** → safe production debugging

Interview ask: "Admin slow on table with 10M rows — fix?" → `list_select_related`, `autocomplete_fields`, `show_full_result_count=False`, pagination tuning.

---

## Core Concepts

### Level 1: Basic ModelAdmin

```python
# admin.py
from django.contrib import admin
from blog.models import Article


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'status', 'created_at')
    list_filter = ('status', 'created_at', 'author')
    search_fields = ('title', 'body')
    date_hierarchy = 'created_at'
    ordering = ('-created_at',)
    list_per_page = 50
```

### Level 2: Performance Tuning (Critical for Large Tables)

```python
@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'author_name', 'category_name')
    list_select_related = ('author', 'category')   # avoid N+1
    list_per_page = 25
    show_full_result_count = False  # avoids slow COUNT(*) on huge tables
    autocomplete_fields = ('author', 'category')   # avoid loading all FK options

    @admin.display(description='Author', ordering='author__username')
    def author_name(self, obj):
        return obj.author.username


# Autocomplete target must define search_fields:
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    search_fields = ('username', 'email')
```

### Level 3: Custom Actions

```python
@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    actions = ['mark_as_published', 'export_to_csv']

    @admin.action(description='Publish selected articles')
    def mark_as_published(self, request, queryset):
        updated = queryset.update(status='published')
        self.message_user(request, f'{updated} articles published.')

    @admin.action(description='Export to CSV')
    def export_to_csv(self, request, queryset):
        import csv
        from django.http import HttpResponse
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="articles.csv"'
        writer = csv.writer(response)
        writer.writerow(['ID', 'Title', 'Author', 'Status'])
        for a in queryset.iterator(chunk_size=1000):
            writer.writerow([a.id, a.title, a.author.username, a.status])
        return response
```

### Level 4: Inlines (Related Objects in Same Form)

```python
class CommentInline(admin.TabularInline):     # or StackedInline
    model = Comment
    extra = 0
    can_delete = False
    readonly_fields = ('created_at',)
    fields = ('author', 'body', 'created_at')
    classes = ('collapse',)
    show_change_link = True


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    inlines = [CommentInline]
```

### Level 5: Fieldsets + Readonly + Custom Forms

```python
class ArticleAdminForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = '__all__'
        widgets = {
            'body': forms.Textarea(attrs={'rows': 20, 'cols': 80}),
        }

    def clean_title(self):
        title = self.cleaned_data['title']
        if title.lower().startswith('test'):
            raise forms.ValidationError("No 'test' titles in prod")
        return title


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    form = ArticleAdminForm
    readonly_fields = ('id', 'created_at', 'updated_at')

    fieldsets = (
        ('Basic Info', {
            'fields': ('title', 'slug', 'author'),
        }),
        ('Content', {
            'fields': ('body', 'excerpt'),
            'classes': ('wide',),
        }),
        ('Publishing', {
            'fields': ('status', 'published_at'),
            'classes': ('collapse',),
        }),
        ('Metadata', {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )
```

### Level 6: Permissions + Readonly Production Access

```python
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'amount', 'status')

    def has_add_permission(self, request):
        return False  # No manual add

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm('orders.change_order')

    def has_delete_permission(self, request, obj=None):
        return False  # Soft delete only

    def get_readonly_fields(self, request, obj=None):
        # All fields readonly unless superuser
        if not request.user.is_superuser:
            return [f.name for f in self.model._meta.fields]
        return self.readonly_fields
```

### Level 7: Custom List Filter

```python
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


@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    list_filter = (HasCommentsFilter, 'status')
```

### Level 8: Custom URLs / Views in Admin

```python
@admin.register(Article)
class ArticleAdmin(admin.ModelAdmin):
    change_list_template = 'admin/blog/article_changelist.html'

    def get_urls(self):
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('import-csv/', self.admin_site.admin_view(self.import_csv), name='blog_article_import_csv'),
            path('<int:pk>/audit/', self.admin_site.admin_view(self.audit_view), name='blog_article_audit'),
        ]
        return custom_urls + urls

    def import_csv(self, request):
        # ... CSV import view
        from django.shortcuts import render
        return render(request, 'admin/import_csv.html')

    def audit_view(self, request, pk):
        # ... show audit log for this article
        ...
```

---

## How It Works Internally

### `get_queryset()` Override (Tenant/Soft-Delete Visibility)

```python
@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        # Include soft-deleted in admin
        return Comment.all_objects.get_queryset()
```

### Admin Sites

Multiple admin sites for separation:

```python
# myapp/admin.py
class SupportAdminSite(admin.AdminSite):
    site_header = 'Support Console'
    site_url = '/support/'


support_site = SupportAdminSite(name='support')

# Register subset of models
support_site.register(Ticket, TicketAdmin)
support_site.register(User, ReadOnlyUserAdmin)
```

---

## Common Pitfalls

### 1. N+1 in List View

```python
# BAD — N+1
list_display = ('title', 'author', 'category')

# GOOD — preload
list_select_related = ('author', 'category')
```

### 2. Slow Count on Huge Tables

```python
class ArticleAdmin(admin.ModelAdmin):
    show_full_result_count = False  # No "1 of 50,000,000"
```

### 3. Autocomplete Without `search_fields`

Target model must declare `search_fields`, else autocomplete shows nothing.

### 4. Inlines Slow Page Load

Each inline = extra queries. Use `max_num`, `extra=0`, lazy load via `show_change_link`.

### 5. Custom Action Doesn't Iterate Efficiently

```python
# BAD
def my_action(self, request, queryset):
    for obj in queryset:  # loads all into memory
        process(obj)

# GOOD
def my_action(self, request, queryset):
    for obj in queryset.iterator(chunk_size=1000):
        process(obj)
```

### 6. Permissions Don't Cascade to Inlines

`has_change_permission` on parent doesn't automatically restrict inline. Override `has_change_permission` on InlineModelAdmin too.

---

## Interview Q&A

**Q1:** Admin slow ho gaya 10M rows pe — kya optimize karoge?
**A:** (1) `list_select_related` for FKs in list_display, (2) `autocomplete_fields` instead of dropdown for FK, (3) `show_full_result_count = False`, (4) Increase `list_per_page` not, decrease it, (5) Custom indexes for `list_filter` columns, (6) Disable inlines or paginate them, (7) `raw_id_fields` for very large FK tables (no autocomplete query).

**Q2:** Admin pe role-based visibility kaise control karoge?
**A:** Override `has_view_permission`, `has_change_permission`, `has_add_permission`, `has_delete_permission`. Combine with Django's permission framework (`request.user.has_perm('app.change_model')`). For row-level, override `get_queryset(self, request)`.

**Q3:** Custom action ke andar large queryset safe kaise process karoge?
**A:** `queryset.iterator(chunk_size=1000)` for streaming. For very long ops, dispatch to Celery: `process_async.delay(list(queryset.values_list('pk', flat=True)))`. Return immediately with "Processing in background" message.

**Q4:** Admin mein soft-deleted records dikhane ke liye kya karoge?
**A:** Override `get_queryset` to use `all_objects` manager. Add a `list_filter` for `deleted_at__isnull` to filter. Add "Restore" action that sets `deleted_at = None`.

**Q5:** Multiple admin sites kab use karoge?
**A:** Different audiences — `/admin/` for engineering, `/support/` for support team with limited models. Subclass `AdminSite`, register only relevant models there. Separate URL conf entries.

**Q6:** `raw_id_fields` vs `autocomplete_fields` vs default dropdown?
**A:** Dropdown = loads all rows (bad for 10K+). Autocomplete = AJAX search, needs `search_fields` on target. `raw_id_fields` = pure ID input + popup search, fastest. Use raw_id when target has 100K+ rows.

**Q7:** Admin pe CSV import kaise add karoge?
**A:** Override `get_urls()`, add custom view returning a form. On POST, parse CSV with `csv.DictReader`, validate, bulk_create with `transaction.atomic`. Show errors in messages framework.

**Q8:** Admin form mein validation kaise add karoge?
**A:** Create custom `ModelForm` with `clean_<field>` methods or overall `clean()`. Assign via `form = MyForm` on ModelAdmin. ValidationError shown inline.

---

## Real-World Use Cases

### 1. Support Team Read-Only Dashboard

```python
class SupportArticleAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'status')

    def has_change_permission(self, request, obj=None):
        return False  # read-only

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


support_site.register(Article, SupportArticleAdmin)
```

### 2. Bulk Refund Action (Ops Team)

```python
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    actions = ['issue_refund']

    @admin.action(description='Issue full refund (USE WITH CARE)')
    def issue_refund(self, request, queryset):
        from billing.tasks import process_refund
        for order in queryset.iterator():
            process_refund.delay(order.pk)
        self.message_user(request, f'{queryset.count()} refunds queued.')
```

---

## References

- [Django admin docs](https://docs.djangoproject.com/en/5.0/ref/contrib/admin/)
- `django-import-export` package — CSV/Excel
- `django-jazzmin` — modern admin theme
- `django-admin-honeypot` — fake admin URL to catch bots
