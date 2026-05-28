"""
DRF Advanced Patterns — Production-grade

Throttles, nested writable serializers, dynamic fields, envelope renderer.
"""

# ==========================================================================
# 1. CUSTOM THROTTLES
# ==========================================================================

from rest_framework.throttling import UserRateThrottle, SimpleRateThrottle, ScopedRateThrottle


class BurstUserThrottle(UserRateThrottle):
    """60/minute burst protection."""
    scope = 'burst'


class SustainedUserThrottle(UserRateThrottle):
    """1000/day sustained limit."""
    scope = 'sustained'


class TieredUserThrottle(SimpleRateThrottle):
    """Rate based on user.tier (free/pro/enterprise)."""
    scope = 'tiered'
    rates_by_tier = {
        'free': '100/hour',
        'pro': '1000/hour',
        'enterprise': '10000/hour',
    }
    anon_rate = '20/hour'

    def get_cache_key(self, request, view):
        if request.user.is_authenticated:
            ident = f'user:{request.user.pk}'
        else:
            ident = f'ip:{self.get_ident(request)}'
        return f'throttle_{self.scope}_{ident}'

    def allow_request(self, request, view):
        if request.user.is_authenticated:
            tier = getattr(request.user, 'tier', 'free')
            self.rate = self.rates_by_tier.get(tier, 'free')
        else:
            self.rate = self.anon_rate
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request, view)


# ==========================================================================
# 2. SETTINGS for throttling
# ==========================================================================
"""
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'core.throttles.BurstUserThrottle',
        'core.throttles.SustainedUserThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'burst': '60/minute',
        'sustained': '1000/day',
        'articles': '500/hour',
        'expensive_action': '10/hour',
    },
}
"""


# ==========================================================================
# 3. NESTED WRITABLE SERIALIZER
# ==========================================================================

from rest_framework import serializers
from django.db import transaction


# from blog.models import Article, Comment, Tag


class CommentNestedSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)  # optional → identifies existing

    class Meta:
        # model = Comment
        fields = ['id', 'body', 'author']


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        # model = Tag
        fields = ['id', 'name']


class ArticleWriteSerializer(serializers.ModelSerializer):
    comments = CommentNestedSerializer(many=True, required=False)
    tags = TagSerializer(many=True, required=False)

    class Meta:
        # model = Article
        fields = ['id', 'title', 'body', 'comments', 'tags']

    @transaction.atomic
    def create(self, validated_data):
        comments_data = validated_data.pop('comments', [])
        tags_data = validated_data.pop('tags', [])

        # article = Article.objects.create(**validated_data)
        article = None  # placeholder

        # for cd in comments_data:
        #     Comment.objects.create(article=article, **cd)

        # M2M with get_or_create
        # tag_objs = []
        # for td in tags_data:
        #     tag, _ = Tag.objects.get_or_create(name=td['name'])
        #     tag_objs.append(tag)
        # article.tags.set(tag_objs)

        return article

    @transaction.atomic
    def update(self, instance, validated_data):
        comments_data = validated_data.pop('comments', None)
        tags_data = validated_data.pop('tags', None)

        # Update article fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Smart nested update — match by id
        if comments_data is not None:
            # existing = {c.id: c for c in instance.comments.all()}
            # incoming_ids = {cd['id'] for cd in comments_data if 'id' in cd}
            #
            # # Delete missing
            # for cid, cobj in existing.items():
            #     if cid not in incoming_ids:
            #         cobj.delete()
            #
            # # Update existing + create new
            # for cd in comments_data:
            #     cid = cd.pop('id', None)
            #     if cid and cid in existing:
            #         for k, v in cd.items():
            #             setattr(existing[cid], k, v)
            #         existing[cid].save()
            #     else:
            #         Comment.objects.create(article=instance, **cd)
            pass

        return instance


# ==========================================================================
# 4. DYNAMIC FIELDS SERIALIZER
# ==========================================================================

class DynamicFieldsModelSerializer(serializers.ModelSerializer):
    """
    Subclass to support `?fields=id,name` query param.
    Allowlist optional — pass `safe_fields` to restrict exposure.
    """

    safe_fields = None  # None = allow all declared fields

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get('request')
        if not request:
            return

        fields_param = request.query_params.get('fields')
        if not fields_param:
            return

        requested = set(fields_param.split(','))
        declared = set(self.fields)
        allowed = set(self.safe_fields) if self.safe_fields else declared

        # Only keep declared ∩ requested ∩ allowed
        keep = declared & requested & allowed
        for f in declared - keep:
            self.fields.pop(f)


class UserSerializer(DynamicFieldsModelSerializer):
    # Whitelist to prevent password_hash exposure
    safe_fields = ('id', 'username', 'email', 'first_name', 'last_name', 'date_joined')

    class Meta:
        # model = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name',
                  'date_joined', 'last_login')


# ==========================================================================
# 5. ENVELOPE RENDERER
# ==========================================================================

from rest_framework.renderers import JSONRenderer
from rest_framework import status as drf_status


class EnvelopeJSONRenderer(JSONRenderer):
    """Wrap all responses in {data, meta, errors}."""

    def render(self, data, accepted_media_type=None, renderer_context=None):
        response = renderer_context.get('response') if renderer_context else None
        status_code = response.status_code if response else 200

        # Skip for non-error / non-data (e.g., schema docs)
        if accepted_media_type and 'openapi' in accepted_media_type:
            return super().render(data, accepted_media_type, renderer_context)

        if drf_status.is_client_error(status_code) or drf_status.is_server_error(status_code):
            envelope = {
                'data': None,
                'errors': data,
                'meta': {'status': status_code},
            }
        elif isinstance(data, dict) and 'results' in data and 'count' in data:
            # Paginated response
            envelope = {
                'data': data['results'],
                'errors': None,
                'meta': {
                    'status': status_code,
                    'count': data['count'],
                    'next': data.get('next'),
                    'previous': data.get('previous'),
                },
            }
        else:
            envelope = {
                'data': data,
                'errors': None,
                'meta': {'status': status_code},
            }

        return super().render(envelope, accepted_media_type, renderer_context)


# ==========================================================================
# 6. ACTION-SPECIFIC SERIALIZERS
# ==========================================================================

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response


# Different shapes for list/detail/write
class ArticleListSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source='author.username', read_only=True)

    class Meta:
        # model = Article
        fields = ['id', 'title', 'author_name', 'created_at']


class ArticleDetailSerializer(serializers.ModelSerializer):
    # comments = CommentSerializer(many=True, read_only=True)
    author = UserSerializer(read_only=True)

    class Meta:
        # model = Article
        fields = ['id', 'title', 'body', 'author', 'comments', 'created_at']


class ArticleViewSet(viewsets.ModelViewSet):
    # queryset = Article.objects.select_related('author').prefetch_related('comments')
    throttle_classes = [TieredUserThrottle]

    def get_serializer_class(self):
        if self.action == 'list':
            return ArticleListSerializer
        if self.action == 'retrieve':
            return ArticleDetailSerializer
        if self.action in ('create', 'update', 'partial_update'):
            return ArticleWriteSerializer
        return ArticleListSerializer

    def get_throttles(self):
        # Different throttle per action
        if self.action == 'export':
            return [ScopedRateThrottle()]
        return super().get_throttles()

    throttle_scope = 'articles'

    @action(detail=False, methods=['get'])
    def export(self, request):
        self.throttle_scope = 'expensive_action'  # link to settings
        # ... heavy export
        return Response({'status': 'queued'})


# ==========================================================================
# 7. CONDITIONAL FIELD VISIBILITY (RBAC)
# ==========================================================================

class ArticleSerializerSecure(serializers.ModelSerializer):
    private_notes = serializers.CharField(required=False)

    class Meta:
        # model = Article
        fields = ['id', 'title', 'body', 'private_notes']

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get('request')
        user = request.user if request else None
        # Hide private_notes from non-author non-staff
        if not user or (user != getattr(instance, 'author', None) and not user.is_staff):
            data.pop('private_notes', None)
        return data


# ==========================================================================
# 8. CUSTOM EXCEPTION HANDLER (consistent errors)
# ==========================================================================

from rest_framework.views import exception_handler
from rest_framework.exceptions import ValidationError


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None

    # Transform DRF errors to consistent shape
    if isinstance(exc, ValidationError):
        # exc.detail is a dict of field → list of errors
        details = []
        if isinstance(exc.detail, dict):
            for field, msgs in exc.detail.items():
                if isinstance(msgs, list):
                    for m in msgs:
                        details.append({'field': field, 'message': str(m)})
                else:
                    details.append({'field': field, 'message': str(msgs)})
        else:
            details.append({'field': None, 'message': str(exc.detail)})

        response.data = {
            'code': 'validation_error',
            'message': 'Validation failed',
            'details': details,
        }
    else:
        # Other errors
        response.data = {
            'code': exc.__class__.__name__,
            'message': str(exc.detail) if hasattr(exc, 'detail') else str(exc),
            'details': [],
        }
    return response


# settings
# REST_FRAMEWORK['EXCEPTION_HANDLER'] = 'core.exception_handlers.custom_exception_handler'
