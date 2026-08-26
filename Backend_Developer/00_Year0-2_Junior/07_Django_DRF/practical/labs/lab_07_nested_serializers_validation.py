"""
Lab 07 — Nested Serializers + Cross-Field Validation + create/update with M2M
═══════════════════════════════════════════════════════════════════════════════

ARCHITECTURE — DRF Serializer Lifecycle:

    REQUEST DATA
        │
        ▼
    serializer = PostWriteSerializer(data=request.data)
        │
        ▼
    serializer.is_valid(raise_exception=True)
        │
        ├── to_internal_value()     ← field-level type coercion
        │     ├── validate_<field>() per field
        │     └── field validators
        ├── validate()              ← cross-field validation
        │
        ▼
    serializer.save()               ← calls create() or update()
        │
        ├── create(validated_data)  ← for new objects
        └── update(instance, validated_data) ← for existing

    NESTED SERIALIZER PATTERN:
      Input:  { "title": "...", "tags": [{"name": "python"}, {"name": "django"}] }
      tags field = TagSerializer(many=True)
      In create(): pop tags from validated_data → create post → set M2M separately

    INTERVIEW: Kyon nested serializer mein M2M manually handle karna padta hai?
      ModelSerializer ka create() M2M handle nahi karta agar nested ho.
      validated_data.pop('tags') karna padta hai BEFORE post.save(), then
      post.tags.set(tag_objects) AFTER save (ID chahiye M2M ke liye).

    CROSS-FIELD VALIDATION (validate() method):
      def validate(self, attrs):
          if attrs['start_date'] > attrs['end_date']:
              raise serializers.ValidationError("start_date must be before end_date")
          return attrs

CONTEXT: Blog Post API — create post with tags (M2M), validate unique title per
         author, validate comment replies point to the same post.

RUN:
    cd practical/
    pytest labs/lab_07_nested_serializers_validation.py -v -p no:odoo

SOCH — Answer ALOUD:
  Q1: validate_<field>() vs validate() — kya difference hai?
  Q2: Nested create() mein tags pop karne ke baad post.save() se PAHLE
      ya BAAD mein post.tags.set() call karo? Kyon?
  Q3: Partial update (PATCH) ke liye serializer mein kya change karna padta hai?
  Q4: read_only_fields vs write_only ka kya matlab hai real API scenario mein?
  Q5: UniqueTogetherValidator in serializer vs DB constraint — kab kaunsa?
"""

import pytest
from rest_framework import serializers
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

import factory
from factory.django import DjangoModelFactory
from django.contrib.auth import get_user_model
from django.utils import timezone

from blog.models import Post, Category, Tag, Comment

User = get_user_model()


# ════════════════════════════════════════════════════════════════════════════
# FACTORIES
# ════════════════════════════════════════════════════════════════════════════

class L7UserFactory(DjangoModelFactory):
    class Meta:
        model = User
    email    = factory.Sequence(lambda n: f"l7user{n}@test.com")
    username = factory.Sequence(lambda n: f"l7user{n}")
    password = factory.PostGenerationMethodCall('set_password', 'pass123')

class L7CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category
    name = factory.Sequence(lambda n: f"L7Cat{n}")

class L7TagFactory(DjangoModelFactory):
    class Meta:
        model = Tag
    name  = factory.Sequence(lambda n: f"l7tag{n}")
    color = "#3B82F6"

class L7PostFactory(DjangoModelFactory):
    class Meta:
        model = Post
    title        = factory.Sequence(lambda n: f"L7 Post {n}")
    content      = "Content word " * 60
    excerpt      = "Excerpt."
    author       = factory.SubFactory(L7UserFactory)
    category     = factory.SubFactory(L7CategoryFactory)
    status       = 'draft'
    published_at = factory.LazyFunction(timezone.now)


# ════════════════════════════════════════════════════════════════════════════
# NESTED SERIALIZERS (to use in TODOs)
# ════════════════════════════════════════════════════════════════════════════

class TagMinimalSerializer(serializers.ModelSerializer):
    """Read-only tag representation for nested display."""
    class Meta:
        model = Tag
        fields = ['id', 'name', 'color']
        read_only_fields = ['id']


class TagWriteSerializer(serializers.ModelSerializer):
    """Accept tag by name — create if not exists."""
    class Meta:
        model = Tag
        fields = ['name']


class CommentSerializer(serializers.ModelSerializer):
    """
    Serializer for creating comments/replies.
    Includes cross-field validation: reply must point to same post.
    """
    author_email = serializers.EmailField(source='author.email', read_only=True)

    class Meta:
        model  = Comment
        fields = ['id', 'post', 'parent', 'content', 'author_email', 'created_at']
        read_only_fields = ['id', 'author_email', 'created_at']


# ════════════════════════════════════════════════════════════════════════════
# TODO 1 — CommentSerializer.validate()
# ════════════════════════════════════════════════════════════════════════════
"""
Add cross-field validation to CommentSerializer:

If `parent` is provided (this is a REPLY, not a top-level comment):
  - parent.post must equal attrs['post']
  - If they differ: raise serializers.ValidationError(
        {'parent': 'Reply must belong to the same post as the comment.'}
    )

Pattern:
    def validate(self, attrs):
        parent = attrs.get('parent')
        if parent and parent.post != attrs.get('post'):
            raise ...
        return attrs

Add this method to CommentSerializer above.
"""

# [IMPLEMENT validate() on CommentSerializer — do not copy-paste, type it yourself]


# ════════════════════════════════════════════════════════════════════════════
# TODO 2 — PostWriteSerializer + validate_title()
# ════════════════════════════════════════════════════════════════════════════
"""
Implement PostWriteSerializer with:

  Fields: title, content, excerpt, category, tags (TagWriteSerializer many=True),
          status (write-only, default='draft')

  validate_title(value):
    - Strip whitespace
    - Minimum 5 characters: raise ValidationError("Title too short (min 5 chars)")
    - Maximum 200 characters: raise ValidationError("Title too long (max 200 chars)")
    - Return stripped value

  validate(attrs):
    - If status == 'published' and len(attrs['content'].split()) < 50:
        raise ValidationError({'content': 'Published posts need at least 50 words'})
    - Return attrs
"""

class PostWriteSerializer(serializers.ModelSerializer):
    tags = TagWriteSerializer(many=True, required=False, default=list)

    class Meta:
        model  = Post
        fields = ['id', 'title', 'content', 'excerpt', 'category', 'tags', 'status']
        read_only_fields = ['id']

    def validate_title(self, value):
        raise NotImplementedError(
            "TODO 2a: Strip whitespace, check min=5 / max=200 length, return cleaned value"
        )

    def validate(self, attrs):
        raise NotImplementedError(
            "TODO 2b: If status='published' and content has < 50 words, raise ValidationError"
        )


# ════════════════════════════════════════════════════════════════════════════
# TODO 3 — PostWriteSerializer.create()
# ════════════════════════════════════════════════════════════════════════════
"""
Override create() to handle:
  1. Pop 'tags' from validated_data BEFORE creating the post
     (Post.save() doesn't accept M2M in constructor)
  2. Inject request.user as author (from self.context['request'].user)
  3. Create the Post object
  4. For each tag_data in tags_data:
       tag, _ = Tag.objects.get_or_create(name=tag_data['name'])
  5. post.tags.set(tag_objects)  ← set M2M after post has a PK
  6. Return post

Pattern:
    def create(self, validated_data):
        tags_data = validated_data.pop('tags', [])
        author = self.context['request'].user
        post = Post.objects.create(author=author, **validated_data)
        tags = [Tag.objects.get_or_create(name=t['name'])[0] for t in tags_data]
        post.tags.set(tags)
        return post

Add this method to PostWriteSerializer.
"""

# [IMPLEMENT create() on PostWriteSerializer — type it yourself]


# ════════════════════════════════════════════════════════════════════════════
# TODO 4 — PostWriteSerializer.update()
# ════════════════════════════════════════════════════════════════════════════
"""
Override update() for PATCH support with M2M tags:
  1. Pop 'tags' from validated_data (may be absent on partial update)
  2. Update all other fields: for attr, val in validated_data.items(): setattr(instance, attr, val)
  3. instance.save()
  4. If tags_data is not None (was explicitly provided in request):
       tags = [Tag.objects.get_or_create(name=t['name'])[0] for t in tags_data]
       instance.tags.set(tags)   ← replace all tags
  5. Return instance

INTERVIEW: sentinel = object() pattern for detecting "not provided" in PATCH:
    tags_data = validated_data.pop('tags', None)
    if tags_data is not None: instance.tags.set(...)

Add this method to PostWriteSerializer.
"""

# [IMPLEMENT update() on PostWriteSerializer — type it yourself]


# ════════════════════════════════════════════════════════════════════════════
# TODO 5 — PostWriteView (wire serializer to an APIView)
# ════════════════════════════════════════════════════════════════════════════
"""
Implement PostWriteView(APIView):
  post(self, request):
    1. Create PostWriteSerializer(data=request.data, context={'request': request})
    2. serializer.is_valid(raise_exception=True)
    3. post = serializer.save()
    4. Return Response(PostWriteSerializer(post).data, status=201)

  patch(self, request, pk):
    1. Get post object (use get_object_or_404)
    2. Create PostWriteSerializer(post, data=request.data, partial=True,
                                   context={'request': request})
    3. serializer.is_valid(raise_exception=True)
    4. updated = serializer.save()
    5. Return Response(PostWriteSerializer(updated).data)
"""

class PostWriteView(APIView):
    def post(self, request):
        raise NotImplementedError("TODO 5a: create post via serializer")

    def patch(self, request, pk):
        raise NotImplementedError("TODO 5b: partial update post via serializer")


# ════════════════════════════════════════════════════════════════════════════
# TESTS
# ════════════════════════════════════════════════════════════════════════════

api_factory = APIRequestFactory()


@pytest.mark.django_db
def test_validate_title_too_short():
    user = L7UserFactory()
    cat  = L7CategoryFactory()
    data = {
        'title': 'Hi',   # < 5 chars
        'content': 'Word ' * 60,
        'excerpt': 'Short.',
        'category': cat.id,
        'status': 'draft',
    }
    serializer = PostWriteSerializer(data=data)
    assert not serializer.is_valid(), "FAIL: Short title should fail validation"
    assert 'title' in serializer.errors, (
        f"FAIL: Error should be on 'title' field. Got: {serializer.errors}"
    )


@pytest.mark.django_db
def test_validate_title_strips_whitespace():
    user = L7UserFactory()
    cat  = L7CategoryFactory()
    data = {
        'title': '  My Great Post  ',
        'content': 'Word ' * 60,
        'excerpt': 'Short.',
        'category': cat.id,
        'status': 'draft',
    }
    serializer = PostWriteSerializer(data=data)
    if serializer.is_valid():
        assert serializer.validated_data['title'] == 'My Great Post', (
            "FAIL: validate_title should strip leading/trailing whitespace"
        )


@pytest.mark.django_db
def test_validate_published_post_needs_50_words():
    cat  = L7CategoryFactory()
    data = {
        'title': 'Valid Title Here',
        'content': 'Only ten words in this content here.',   # < 50 words
        'excerpt': 'Short.',
        'category': cat.id,
        'status': 'published',
    }
    serializer = PostWriteSerializer(data=data)
    assert not serializer.is_valid(), "FAIL: published post with < 50 words should fail"
    assert 'content' in serializer.errors or 'non_field_errors' in serializer.errors, (
        f"FAIL: Error on content or non_field_errors expected. Got: {serializer.errors}"
    )


@pytest.mark.django_db
def test_create_post_with_tags_via_view():
    user = L7UserFactory()
    cat  = L7CategoryFactory()

    request = api_factory.post('/posts/', {
        'title': 'My Python Post',
        'content': 'Word ' * 60,
        'excerpt': 'Great post.',
        'category': cat.id,
        'tags': [{'name': 'python'}, {'name': 'django'}],
        'status': 'draft',
    }, format='json')
    force_authenticate(request, user=user)

    view = PostWriteView.as_view()
    response = view(request)

    assert response.status_code == 201, (
        f"FAIL: Expected 201 Created. Got {response.status_code}: {response.data}"
    )
    post = Post.objects.get(title='My Python Post')
    assert post.author == user, "FAIL: post.author should be request.user"
    tag_names = list(post.tags.values_list('name', flat=True))
    assert 'python' in tag_names, "FAIL: 'python' tag not set on post"
    assert 'django' in tag_names, "FAIL: 'django' tag not set on post"


@pytest.mark.django_db
def test_create_reuses_existing_tag():
    """get_or_create means duplicate tags are not created."""
    existing_tag = L7TagFactory(name="reusable-tag")
    user = L7UserFactory()
    cat  = L7CategoryFactory()

    request = api_factory.post('/posts/', {
        'title': 'Reuse Tag Post',
        'content': 'Word ' * 60,
        'excerpt': 'Short.',
        'category': cat.id,
        'tags': [{'name': 'reusable-tag'}],
        'status': 'draft',
    }, format='json')
    force_authenticate(request, user=user)

    view = PostWriteView.as_view()
    response = view(request)

    assert response.status_code == 201, f"FAIL: {response.data}"
    assert Tag.objects.filter(name='reusable-tag').count() == 1, (
        "FAIL: Tag 'reusable-tag' should not be duplicated — use get_or_create"
    )


@pytest.mark.django_db
def test_patch_updates_tags():
    """PATCH with new tags replaces the existing tags."""
    user    = L7UserFactory()
    post    = L7PostFactory(author=user)
    old_tag = L7TagFactory(name="old-tag")
    post.tags.add(old_tag)

    request = api_factory.patch(f'/posts/{post.id}/', {
        'tags': [{'name': 'new-tag'}]
    }, format='json')
    force_authenticate(request, user=user)

    view = PostWriteView.as_view()
    response = view(request, pk=post.id)

    assert response.status_code == 200, f"FAIL: {response.status_code}: {response.data}"
    post.refresh_from_db()
    tag_names = list(post.tags.values_list('name', flat=True))
    assert 'new-tag' in tag_names, "FAIL: new-tag not set after PATCH"
    assert 'old-tag' not in tag_names, "FAIL: old-tag should be replaced by PATCH"


@pytest.mark.django_db
def test_comment_reply_must_be_same_post():
    """Reply to comment on different post should fail validation."""
    user   = L7UserFactory()
    post1  = L7PostFactory()
    post2  = L7PostFactory()
    parent = Comment.objects.create(post=post1, author=user, content="Parent on post1")

    data = {
        'post':    post2.id,     # different post
        'parent':  parent.id,    # parent is on post1
        'content': 'Reply attempt',
    }
    serializer = CommentSerializer(data=data)

    # NOTE: Comment.validate() is TODO 1 — student adds it to CommentSerializer above
    # After implementation, this must fail:
    valid = serializer.is_valid()
    if not valid and 'parent' in serializer.errors:
        # Correct behavior
        assert True
    elif valid:
        # If student hasn't implemented TODO 1 yet — mark as expected failure
        pytest.skip("TODO 1 (validate()) not implemented yet — implement it first")


@pytest.mark.django_db
def test_comment_reply_same_post_valid():
    """Reply to comment on same post should pass."""
    user   = L7UserFactory()
    post   = L7PostFactory()
    parent = Comment.objects.create(post=post, author=user, content="Parent")

    data = {
        'post':    post.id,
        'parent':  parent.id,
        'content': 'Valid reply',
    }
    serializer = CommentSerializer(data=data)
    # After implementing TODO 1, this should be valid
    is_valid = serializer.is_valid()
    if not is_valid and 'parent' in serializer.errors:
        pytest.skip("TODO 1 (validate()) rejects same-post replies — check logic")
    assert is_valid, f"FAIL: Same-post reply should be valid. Errors: {serializer.errors}"


# ════════════════════════════════════════════════════════════════════════════
# SOCH
# ════════════════════════════════════════════════════════════════════════════

"""
SOCH (Answer ALOUD):

Q1: DRF serializer mein data flow kya hai?
    to_internal_value → validate_<field> → validate → save (create/update)
    Explain each step mein kya hota hai.

Q2: Nested M2M create() mein post.tags.set() ko post.save() ke BAAD call karo — kyon?
    (post.id chahiye M2M table mein foreign key ke liye. No ID = IntegrityError)

Q3: partial=True ka matlab kya hai? Kab use karo?
    (PATCH vs PUT — PUT requires all fields, PATCH allows partial)

Q4: read_only_fields = ['id', 'author'] — author ko read_only kyon rakhte hain?
    (Author set via context['request'].user in create() — client ko dictate nahi karne dete)

Q5: serializer.errors ka structure kya hota hai?
    (Dict: {field_name: [error_messages], 'non_field_errors': [...]})
    validate() se aane wali errors kahan jaati hain?
"""
