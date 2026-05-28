# Django Forms Deep — ModelForm, Formsets, Validation

## Why It Matters

DRF dominates APIs, but Django Forms still essential:
- **Django admin** uses forms internally
- **Server-rendered templates** (HTMX, Django CRUD)
- **Multi-step wizards**
- **CSV/Excel import UIs**
- **Internal tools**

Senior interview: "Built-in admin needs custom validation — kaise add karte ho?" → ModelForm with `clean_<field>` methods.

---

## Core Concepts

### ModelForm

```python
# forms.py
from django import forms
from .models import Article


class ArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = ['title', 'body', 'status', 'tags']
        # or exclude = ['created_at']

        widgets = {
            'body': forms.Textarea(attrs={'rows': 20, 'cols': 80, 'class': 'rich-editor'}),
            'tags': forms.SelectMultiple(attrs={'class': 'tags-input'}),
        }

        labels = {
            'body': 'Article Content',
        }

        help_texts = {
            'title': 'Max 200 characters',
        }

        error_messages = {
            'title': {'required': 'Please enter a title.'},
        }
```

### Field-Level Validation

```python
class ArticleForm(forms.ModelForm):
    class Meta:
        model = Article
        fields = ['title', 'body', 'slug']

    def clean_title(self):
        title = self.cleaned_data['title'].strip()
        if title.lower().startswith('test'):
            raise forms.ValidationError("Don't start with 'test'.")
        if len(title) < 5:
            raise forms.ValidationError("Too short.")
        return title

    def clean_slug(self):
        slug = self.cleaned_data['slug']
        if Article.objects.filter(slug=slug).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("Slug already in use.")
        return slug
```

### Form-Level (clean) Validation

```python
def clean(self):
    cleaned = super().clean()
    status = cleaned.get('status')
    body = cleaned.get('body')

    if status == 'published' and not body:
        # Field-specific error
        self.add_error('body', "Published articles must have body.")

    if cleaned.get('publish_at') and cleaned.get('publish_at') < timezone.now():
        # Global error
        raise forms.ValidationError("Publish date in past.")

    return cleaned
```

### Custom Fields

```python
class ArticleForm(forms.Form):
    tags = forms.CharField(
        help_text='Comma-separated',
        widget=forms.TextInput(attrs={'placeholder': 'python, django'}),
    )

    def clean_tags(self):
        tags_str = self.cleaned_data['tags']
        return [t.strip() for t in tags_str.split(',') if t.strip()]


# Reading cleaned data
form = ArticleForm({'tags': 'python, django, web'})
if form.is_valid():
    tags = form.cleaned_data['tags']    # ['python', 'django', 'web']
```

### FormSet (multiple instances of same form)

```python
from django.forms import formset_factory


CommentFormSet = formset_factory(
    CommentForm,
    extra=3,           # 3 empty forms
    max_num=10,        # max 10
    can_delete=True,
)


# In view
def add_comments(request):
    formset = CommentFormSet(request.POST or None)
    if formset.is_valid():
        for form in formset:
            if form.cleaned_data and not form.cleaned_data.get('DELETE'):
                # Save each
                Comment.objects.create(**form.cleaned_data)
    return render(request, 'comments.html', {'formset': formset})
```

### ModelFormSet (multiple instances of ModelForm)

```python
from django.forms import modelformset_factory


ArticleFormSet = modelformset_factory(
    Article,
    fields=['title', 'status'],
    extra=1,
    can_delete=True,
)


def edit_articles(request):
    qs = Article.objects.filter(author=request.user)

    if request.method == 'POST':
        formset = ArticleFormSet(request.POST, queryset=qs)
        if formset.is_valid():
            formset.save()
            return redirect('home')
    else:
        formset = ArticleFormSet(queryset=qs)

    return render(request, 'edit_articles.html', {'formset': formset})
```

### Inline FormSet (parent-child)

```python
from django.forms import inlineformset_factory


CommentInlineFormSet = inlineformset_factory(
    Article,         # parent
    Comment,         # child
    fields=['body', 'author'],
    extra=2,
    can_delete=True,
)


def edit_article_with_comments(request, pk):
    article = get_object_or_404(Article, pk=pk)

    if request.method == 'POST':
        article_form = ArticleForm(request.POST, instance=article)
        comment_formset = CommentInlineFormSet(request.POST, instance=article)

        if article_form.is_valid() and comment_formset.is_valid():
            article_form.save()
            comment_formset.save()
            return redirect('article-detail', pk=article.pk)
    else:
        article_form = ArticleForm(instance=article)
        comment_formset = CommentInlineFormSet(instance=article)

    return render(request, 'edit.html', {
        'article_form': article_form,
        'comment_formset': comment_formset,
    })
```

### Initial Values

```python
form = ArticleForm(initial={
    'status': 'draft',
    'published_at': timezone.now(),
})


# From model instance (auto via ModelForm)
form = ArticleForm(instance=article)


# Mixed
form = ArticleForm(instance=article, initial={'status': 'published'})
```

### Multi-Step Form Wizard

```python
# pip install django-formtools
from formtools.wizard.views import SessionWizardView


class SignupWizard(SessionWizardView):
    form_list = [PersonalInfoForm, AccountForm, AgreementForm]
    template_name = 'wizard.html'

    def done(self, form_list, **kwargs):
        # Combine data from all steps
        data = {}
        for form in form_list:
            data.update(form.cleaned_data)
        # Create user
        return redirect('done')


# urls.py
urlpatterns = [
    path('signup/', SignupWizard.as_view()),
]
```

### File Uploads in Forms

```python
class UploadForm(forms.Form):
    title = forms.CharField()
    file = forms.FileField()


# In view
if request.method == 'POST':
    form = UploadForm(request.POST, request.FILES)  # MUST pass FILES
    if form.is_valid():
        uploaded = form.cleaned_data['file']
        with open(f'/uploads/{uploaded.name}', 'wb+') as dest:
            for chunk in uploaded.chunks():
                dest.write(chunk)
```

### Crispy Forms (Bootstrap rendering)

```python
# pip install django-crispy-forms crispy-bootstrap5
INSTALLED_APPS += ['crispy_forms', 'crispy_bootstrap5']
CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'


# In template
{% load crispy_forms_tags %}
{{ form|crispy }}
{{ formset|crispy }}
```

### Form vs Serializer

| | Form | Serializer (DRF) |
|---|---|---|
| Use | Server-rendered HTML | JSON API |
| Output | HTML + bound data | dict (Python) |
| Validation | clean_field, clean | validate_field, validate |
| Save | save() returns instance | save() returns instance |
| Errors | form.errors (dict) | serializer.errors (dict) |
| Both have validate logic, but separate codebases. Don't mix. |

---

## Common Pitfalls

### 1. Forgetting `request.FILES`

```python
form = UploadForm(request.POST)  # missing FILES
```

File uploads fail silently.

### 2. ModelForm Doesn't Save M2M Without `commit=True` Pattern

```python
form = ArticleForm(request.POST)
if form.is_valid():
    article = form.save(commit=False)
    article.author = request.user
    article.save()
    form.save_m2m()    # zaroori — tags etc.
```

### 3. CSRF Token Missing

```html
<form method="post">
    {{ form }}
    <button>Submit</button>
</form>
```

Always include `{% csrf_token %}`.

### 4. Form Re-renders Without Errors

```python
if form.is_valid():
    ...
return render(request, 'form.html', {})    # form not passed
```

Pass `form` back so errors render: `{'form': form}`.

### 5. Initial vs Instance Confusion

`initial` = display values (override instance/data). `instance` = model object to bind. For edits, use `instance`. For pre-filling new form, use `initial`.

### 6. clean() Returns Wrong Type

```python
def clean(self):
    return {'title': 'X'}    # WRONG — must return dict from super().clean() with adjustments
```

Always: `cleaned = super().clean(); modify; return cleaned`.

### 7. Validating Outside Form

```python
@require_POST
def view(request):
    name = request.POST.get('name')
    if not name:
        ...
```

Use Form. Otherwise scattered validation, no error display, no widgets.

---

## Interview Q&A

**Q1:** Form vs ModelForm?
**A:** Form = generic form, define fields manually. ModelForm = auto-generates from model. ModelForm includes `save()` that creates/updates instance. Use ModelForm when forms map to models; plain Form for non-model use cases (login, search).

**Q2:** clean_<field> vs clean()?
**A:** `clean_<field>(self)` — validate ONE field, return cleaned value, raise ValidationError on invalid. `clean(self)` — cross-field validation, access multiple fields via `self.cleaned_data`, use `self.add_error(field, msg)` or raise ValidationError for global error.

**Q3:** FormSet kab use karte ho?
**A:** Same form repeated multiple times. Examples: edit 10 line items in invoice, multiple addresses for user, bulk add 5 products. `formset_factory(Form, extra=3)` for 3 empty. For model-backed: `modelformset_factory`. For parent-child: `inlineformset_factory`.

**Q4:** M2M save issue with ModelForm?
**A:** `form.save(commit=False)` returns instance without saving (so you can modify before save). M2M relations can't be set until instance saved. After `instance.save()`, call `form.save_m2m()` to save M2M. Or just `form.save()` (commit=True) skips this.

**Q5:** Multi-step form?
**A:** `django-formtools` SessionWizardView. Each step = separate Form/ModelForm. Data persisted in session between steps. `done()` method called when all complete — combine data, create record. Useful for signup with multiple sections.

**Q6:** Form vs DRF serializer trade-off?
**A:** Form: for HTML rendering, request.POST/FILES, errors with field positions for templates. Serializer: for JSON API, more validation features (nested, polymorphic), better with DRF infrastructure. Don't mix — separate apps may have both for same model.

**Q7:** Custom widget?
**A:** Subclass `forms.Widget`. Override `render(name, value, attrs, renderer)`. Provide template. Useful for date picker, color picker, custom UI. Or override widget on existing field via `widgets` dict in Meta.

**Q8:** File upload security in forms?
**A:** Use `FileField` + `validators`. Check MIME via libmagic (not just extension). Cap file size via `FILE_UPLOAD_MAX_MEMORY_SIZE`. Sanitize filename — never trust client. Store outside webroot. Generate UUID-based paths.

---

## Real-World Use Cases

### 1. CSV Import Form

```python
class CSVImportForm(forms.Form):
    file = forms.FileField()
    has_headers = forms.BooleanField(required=False, initial=True)

    def clean_file(self):
        f = self.cleaned_data['file']
        if not f.name.endswith('.csv'):
            raise forms.ValidationError("Must be CSV")
        if f.size > 10 * 1024 * 1024:
            raise forms.ValidationError("Max 10MB")
        return f
```

### 2. Search Form

```python
class ArticleSearchForm(forms.Form):
    q = forms.CharField(required=False)
    category = forms.ModelChoiceField(queryset=Category.objects.all(), required=False)
    date_from = forms.DateField(required=False)
    date_to = forms.DateField(required=False)

    def filter_queryset(self, qs):
        d = self.cleaned_data
        if d.get('q'):
            qs = qs.filter(title__icontains=d['q'])
        if d.get('category'):
            qs = qs.filter(category=d['category'])
        if d.get('date_from'):
            qs = qs.filter(created_at__gte=d['date_from'])
        if d.get('date_to'):
            qs = qs.filter(created_at__lte=d['date_to'])
        return qs
```

### 3. Inline Comments Edit

```python
CommentInlineFormSet = inlineformset_factory(
    Article, Comment,
    fields=['body', 'is_approved'],
    extra=0,
    can_delete=True,
)


def moderate_comments(request, article_id):
    article = Article.objects.get(pk=article_id)
    if request.method == 'POST':
        formset = CommentInlineFormSet(request.POST, instance=article)
        if formset.is_valid():
            formset.save()
            return redirect('moderation-done')
    else:
        formset = CommentInlineFormSet(instance=article)
    return render(request, 'moderate.html', {'formset': formset})
```

---

## References

- [Django Forms](https://docs.djangoproject.com/en/5.0/topics/forms/)
- [FormSets](https://docs.djangoproject.com/en/5.0/topics/forms/formsets/)
- [django-crispy-forms](https://django-crispy-forms.readthedocs.io/)
- [django-formtools](https://django-formtools.readthedocs.io/)
