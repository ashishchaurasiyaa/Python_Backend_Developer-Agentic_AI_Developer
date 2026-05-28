"""
Django Forms — Production Patterns
"""

from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone


# ==========================================================================
# 1. MODEL FORM with validation
# ==========================================================================

"""
from blog.models import Article


class ArticleForm(forms.ModelForm):
    # Override field
    tags = forms.CharField(
        required=False,
        help_text='Comma-separated tags',
        widget=forms.TextInput(attrs={'placeholder': 'python, django'}),
    )

    class Meta:
        model = Article
        fields = ['title', 'body', 'slug', 'status', 'category']
        widgets = {
            'body': forms.Textarea(attrs={'rows': 20, 'cols': 80, 'class': 'editor'}),
            'status': forms.RadioSelect(),
        }
        labels = {'body': 'Content'}
        help_texts = {'title': 'Max 200 chars'}
        error_messages = {
            'title': {'required': 'Please enter a title.'},
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # Filter category choices by user
        if self.user:
            self.fields['category'].queryset = Category.objects.filter(
                owner=self.user
            )

    def clean_title(self):
        title = self.cleaned_data['title'].strip()
        if len(title) < 5:
            raise ValidationError('Title too short (min 5 chars)')
        if title.lower().startswith('test'):
            raise ValidationError("No 'test' titles in production")
        return title

    def clean_slug(self):
        slug = self.cleaned_data['slug']
        qs = Article.objects.filter(slug=slug)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError('Slug already taken')
        return slug

    def clean_tags(self):
        tags_str = self.cleaned_data.get('tags', '')
        tag_list = [t.strip().lower() for t in tags_str.split(',') if t.strip()]
        if len(tag_list) > 10:
            raise ValidationError('Max 10 tags')
        return tag_list

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get('status')
        body = cleaned.get('body')

        if status == 'published':
            if not body or len(body) < 100:
                self.add_error('body', 'Published articles need body >= 100 chars')

        return cleaned

    def save(self, commit=True):
        # Custom save logic
        article = super().save(commit=False)
        if self.user and not article.author_id:
            article.author = self.user

        if commit:
            article.save()
            # Handle tags M2M (must be after save)
            tags = self.cleaned_data.get('tags', [])
            tag_objs = []
            for name in tags:
                tag, _ = Tag.objects.get_or_create(name=name)
                tag_objs.append(tag)
            article.tags.set(tag_objs)

        return article
"""


# ==========================================================================
# 2. NON-MODEL FORM (login, search)
# ==========================================================================

class LoginForm(forms.Form):
    email = forms.EmailField(label='Email')
    password = forms.CharField(widget=forms.PasswordInput, label='Password')
    remember_me = forms.BooleanField(required=False, label='Remember me')

    def clean(self):
        cleaned = super().clean()
        email = cleaned.get('email')
        password = cleaned.get('password')

        if email and password:
            from django.contrib.auth import authenticate
            user = authenticate(username=email, password=password)
            if user is None:
                raise ValidationError('Invalid credentials')
            cleaned['user'] = user

        return cleaned


# ==========================================================================
# 3. SEARCH FORM with filter helper
# ==========================================================================

class ArticleSearchForm(forms.Form):
    q = forms.CharField(required=False, label='Search')
    status = forms.ChoiceField(
        choices=[('', 'All'), ('published', 'Published'), ('draft', 'Draft')],
        required=False,
    )
    date_from = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    date_to = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    min_views = forms.IntegerField(required=False, min_value=0)

    def filter_queryset(self, queryset):
        d = self.cleaned_data
        if d.get('q'):
            from django.db.models import Q
            queryset = queryset.filter(
                Q(title__icontains=d['q']) | Q(body__icontains=d['q'])
            )
        if d.get('status'):
            queryset = queryset.filter(status=d['status'])
        if d.get('date_from'):
            queryset = queryset.filter(created_at__gte=d['date_from'])
        if d.get('date_to'):
            queryset = queryset.filter(created_at__lte=d['date_to'])
        if d.get('min_views'):
            queryset = queryset.filter(view_count__gte=d['min_views'])
        return queryset


# Usage in view
# def search(request):
#     form = ArticleSearchForm(request.GET)
#     if form.is_valid():
#         qs = form.filter_queryset(Article.objects.all())
#     else:
#         qs = Article.objects.none()
#     return render(request, 'search.html', {'form': form, 'results': qs})


# ==========================================================================
# 4. FILE UPLOAD FORM with validation
# ==========================================================================

class CSVImportForm(forms.Form):
    file = forms.FileField(label='CSV file')
    has_header = forms.BooleanField(required=False, initial=True)
    delimiter = forms.ChoiceField(
        choices=[(',', 'Comma'), (';', 'Semicolon'), ('\t', 'Tab')],
        initial=',',
    )

    def clean_file(self):
        f = self.cleaned_data['file']

        # Extension check
        if not f.name.lower().endswith('.csv'):
            raise ValidationError('File must be .csv')

        # Size check
        max_size = 10 * 1024 * 1024  # 10MB
        if f.size > max_size:
            raise ValidationError(f'Max {max_size // 1024 // 1024}MB')

        # MIME check via libmagic
        try:
            import magic
            head = f.read(2048)
            f.seek(0)
            mime = magic.from_buffer(head, mime=True)
            if mime not in {'text/csv', 'text/plain', 'application/csv'}:
                raise ValidationError(f'Invalid type: {mime}')
        except ImportError:
            pass

        return f


# ==========================================================================
# 5. FORMSET (multiple of same form)
# ==========================================================================

from django.forms import formset_factory


class ContactForm(forms.Form):
    name = forms.CharField()
    email = forms.EmailField()
    relationship = forms.CharField()


ContactFormSet = formset_factory(
    ContactForm,
    extra=3,         # 3 empty forms
    min_num=1,       # at least 1
    max_num=10,      # at most 10
    can_delete=True,
    validate_min=True,
    validate_max=True,
)


# Usage
"""
def add_contacts(request):
    if request.method == 'POST':
        formset = ContactFormSet(request.POST, prefix='contacts')
        if formset.is_valid():
            for form in formset:
                if form.cleaned_data and not form.cleaned_data.get('DELETE'):
                    Contact.objects.create(
                        user=request.user,
                        **{k: v for k, v in form.cleaned_data.items() if k != 'DELETE'}
                    )
            return redirect('contacts-done')
    else:
        formset = ContactFormSet(prefix='contacts')

    return render(request, 'add_contacts.html', {'formset': formset})
"""


# ==========================================================================
# 6. MODELFORMSET (multiple instances of model)
# ==========================================================================

from django.forms import modelformset_factory


# ArticleFormSet = modelformset_factory(
#     Article,
#     fields=['title', 'status'],
#     extra=1,
#     can_delete=True,
# )


"""
def edit_my_articles(request):
    qs = Article.objects.filter(author=request.user)

    if request.method == 'POST':
        formset = ArticleFormSet(request.POST, queryset=qs)
        if formset.is_valid():
            instances = formset.save(commit=False)
            for instance in instances:
                instance.author = request.user
                instance.save()
            for obj in formset.deleted_objects:
                obj.delete()
            return redirect('my-articles')
    else:
        formset = ArticleFormSet(queryset=qs)

    return render(request, 'edit_articles.html', {'formset': formset})
"""


# ==========================================================================
# 7. INLINE FORMSET (parent-child)
# ==========================================================================

from django.forms import inlineformset_factory


# CommentInlineFormSet = inlineformset_factory(
#     Article,                # parent model
#     Comment,                # child model
#     fields=['body', 'author'],
#     extra=2,
#     max_num=10,
#     can_delete=True,
# )


"""
def edit_article(request, pk):
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
"""


# ==========================================================================
# 8. MULTI-STEP WIZARD
# ==========================================================================

"""
# pip install django-formtools
from formtools.wizard.views import SessionWizardView


class PersonalInfoForm(forms.Form):
    first_name = forms.CharField()
    last_name = forms.CharField()
    phone = forms.CharField()


class AccountForm(forms.Form):
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)


class AgreementForm(forms.Form):
    accept_tos = forms.BooleanField(required=True)
    marketing_optin = forms.BooleanField(required=False)


class SignupWizard(SessionWizardView):
    form_list = [PersonalInfoForm, AccountForm, AgreementForm]
    template_name = 'signup_wizard.html'

    def done(self, form_list, **kwargs):
        # Combine data
        data = {}
        for form in form_list:
            data.update(form.cleaned_data)

        # Create user
        User.objects.create_user(
            email=data['email'],
            password=data['password'],
            first_name=data['first_name'],
            last_name=data['last_name'],
        )

        return redirect('signup-complete')


# urls.py
# urlpatterns += [path('signup/', SignupWizard.as_view())]
"""


# ==========================================================================
# 9. AJAX FORM SUBMISSION (HTMX-friendly)
# ==========================================================================

"""
# views.py

from django.http import HttpResponse, JsonResponse


def ajax_article_create(request):
    if request.method == 'POST':
        form = ArticleForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            article = form.save()
            # Return HTMX partial
            return HttpResponse(f'<div>Created: {article.title}</div>')
        # Errors — return form with errors
        return render(request, 'partial_form.html', {'form': form}, status=422)
    else:
        form = ArticleForm(user=request.user)
    return render(request, 'partial_form.html', {'form': form})


# Template
'''
<form hx-post="{% url 'ajax-article-create' %}" hx-swap="outerHTML">
    {% csrf_token %}
    {{ form|crispy }}
    <button>Submit</button>
</form>
'''
"""


# ==========================================================================
# 10. CRISPY FORMS (Bootstrap rendering)
# ==========================================================================

"""
# pip install django-crispy-forms crispy-bootstrap5

# settings.py
INSTALLED_APPS += ['crispy_forms', 'crispy_bootstrap5']
CRISPY_ALLOWED_TEMPLATE_PACKS = 'bootstrap5'
CRISPY_TEMPLATE_PACK = 'bootstrap5'


# Form
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit


class ArticleFormCrispy(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column('title', css_class='col-md-8'),
                Column('status', css_class='col-md-4'),
            ),
            'body',
            'tags',
            Submit('submit', 'Save', css_class='btn-primary'),
        )

    class Meta:
        # model = Article
        fields = ['title', 'status', 'body']


# Template
'''
{% load crispy_forms_tags %}
{% crispy form %}
'''
"""


# ==========================================================================
# 11. CUSTOM WIDGET
# ==========================================================================

class ColorPickerWidget(forms.Widget):
    """Custom color picker widget."""

    template_name = 'widgets/color_picker.html'

    def __init__(self, attrs=None):
        default_attrs = {'type': 'color'}
        if attrs:
            default_attrs.update(attrs)
        super().__init__(default_attrs)


class StylableModelForm(forms.ModelForm):
    """Example with custom widget."""

    color = forms.CharField(widget=ColorPickerWidget())

    class Meta:
        # model = Theme
        fields = ['name', 'color']


# ==========================================================================
# 12. FORM TESTING
# ==========================================================================

"""
# tests/test_forms.py
from django.test import TestCase


class ArticleFormTests(TestCase):
    def test_short_title_invalid(self):
        form = ArticleForm(data={'title': 'X', 'body': '...'})
        self.assertFalse(form.is_valid())
        self.assertIn('title', form.errors)

    def test_published_requires_body(self):
        form = ArticleForm(data={
            'title': 'Long enough title',
            'status': 'published',
            'body': '',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('body', form.errors)

    def test_unique_slug(self):
        Article.objects.create(slug='existing')
        form = ArticleForm(data={'title': 'New', 'slug': 'existing', 'body': '...' * 100})
        self.assertFalse(form.is_valid())
        self.assertIn('slug', form.errors)

    def test_valid_form_creates_article(self):
        form = ArticleForm(data={
            'title': 'Good Title',
            'slug': 'good-title',
            'status': 'draft',
            'body': 'X' * 200,
        }, user=self.user)
        self.assertTrue(form.is_valid())
        article = form.save()
        self.assertEqual(article.author, self.user)
"""
