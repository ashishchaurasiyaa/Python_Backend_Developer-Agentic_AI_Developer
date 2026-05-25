"""
Object-Level Permissions — Production Patterns

Uses django-guardian + custom backends + DRF integration.
"""

# ==========================================================================
# 1. SETTINGS
# ==========================================================================
"""
# pip install django-guardian
INSTALLED_APPS += ['guardian']

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'guardian.backends.ObjectPermissionBackend',
    'core.auth_backends.OwnerPermissionBackend',
]

ANONYMOUS_USER_NAME = 'AnonymousUser'
"""


# ==========================================================================
# 2. CUSTOM PERMISSION BACKEND — Owner check
# ==========================================================================

class OwnerPermissionBackend:
    """Auto-grant perms to owner of object."""

    def authenticate(self, request, **credentials):
        return None  # not for auth

    def has_perm(self, user_obj, perm, obj=None):
        if obj is None:
            return False
        if not user_obj.is_authenticated:
            return False

        # Detect owner field
        for owner_field in ('owner_id', 'author_id', 'user_id', 'created_by_id'):
            if hasattr(obj, owner_field):
                if getattr(obj, owner_field) == user_obj.pk:
                    return True
                break  # first matching field wins
        return False


# ==========================================================================
# 3. HIERARCHICAL BACKEND (manager sees reports)
# ==========================================================================

class HierarchyPermissionBackend:
    """Managers can view their direct reports' records."""

    def authenticate(self, request, **credentials):
        return None

    def has_perm(self, user_obj, perm, obj=None):
        if obj is None or not user_obj.is_authenticated:
            return False

        if perm in ('hr.view_employee', 'hr.view_attendance'):
            # Check if obj belongs to a direct report
            target_owner_id = getattr(obj, 'owner_id', None) or getattr(obj, 'employee_id', None)
            if not target_owner_id:
                return False

            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                target = User.objects.only('manager_id').get(pk=target_owner_id)
                return target.manager_id == user_obj.pk
            except User.DoesNotExist:
                return False

        return False


# ==========================================================================
# 4. MODEL WITH CUSTOM PERMISSIONS
# ==========================================================================

from django.db import models


class Document(models.Model):
    title = models.CharField(max_length=200)
    body = models.TextField()
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='documents')
    is_public = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = 'blog'
        permissions = [
            ('share_document', 'Can share document'),
            ('publish_document', 'Can publish document'),
            ('archive_document', 'Can archive document'),
        ]


# ==========================================================================
# 5. GRANTING / REVOKING via django-guardian
# ==========================================================================

# from guardian.shortcuts import assign_perm, remove_perm, get_perms
#
#
# # Grant view perm to user
# def share_document(doc, target_user, perm='view_document'):
#     assign_perm(f'blog.{perm}', target_user, doc)
#
#
# def revoke_share(doc, target_user, perm='view_document'):
#     remove_perm(f'blog.{perm}', target_user, doc)
#
#
# # List perms a user has on a doc
# def list_perms(doc, user):
#     return get_perms(user, doc)  # ['view_document', 'change_document']
#
#
# # All users who can view a doc
# from guardian.shortcuts import get_users_with_perms
#
# def doc_audience(doc):
#     return get_users_with_perms(doc, attach_perms=True)
#     # {<User>: ['view_document'], <User>: ['view_document', 'change_document']}


# ==========================================================================
# 6. DRF PERMISSIONS
# ==========================================================================

from rest_framework import permissions
from rest_framework import viewsets, status
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied


class IsOwnerOrSharedReadOnly(permissions.BasePermission):
    """Owner: full access. Shared users: based on granted perms. Others: read-only if public."""

    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Owner always has access
        if obj.owner_id == request.user.pk:
            return True

        # Public read allowed
        if request.method in permissions.SAFE_METHODS and obj.is_public:
            return True

        # Granted perms via guardian
        if request.method in permissions.SAFE_METHODS:
            return request.user.has_perm('blog.view_document', obj)

        # Write
        return request.user.has_perm('blog.change_document', obj)


class CanShareDocument(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return (
            obj.owner_id == request.user.pk or
            request.user.has_perm('blog.share_document', obj)
        )


# ==========================================================================
# 7. VIEWSET with object-level filtering
# ==========================================================================

# from rest_framework import serializers
# from guardian.shortcuts import get_objects_for_user
# from django.db.models import Q
# from django.contrib.auth import get_user_model
# User = get_user_model()
#
#
# class DocumentSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = Document
#         fields = ['id', 'title', 'body', 'owner', 'is_public', 'created_at']
#         read_only_fields = ['owner', 'created_at']
#
#
# class DocumentViewSet(viewsets.ModelViewSet):
#     serializer_class = DocumentSerializer
#     permission_classes = [IsOwnerOrSharedReadOnly]
#
#     def get_queryset(self):
#         user = self.request.user
#         shared = get_objects_for_user(user, 'blog.view_document', klass=Document)
#         return (
#             Document.objects.filter(
#                 Q(owner=user) | Q(is_public=True) | Q(pk__in=shared.values('pk'))
#             )
#             .select_related('owner')
#             .distinct()
#         )
#
#     def perform_create(self, serializer):
#         serializer.save(owner=self.request.user)
#
#     @action(detail=True, methods=['post'], permission_classes=[CanShareDocument])
#     def share(self, request, pk=None):
#         doc = self.get_object()
#         target_user_id = request.data.get('user_id')
#         perm = request.data.get('permission', 'view_document')
#
#         if perm not in ('view_document', 'change_document'):
#             return Response({'error': 'Invalid permission'}, status=400)
#
#         try:
#             target = User.objects.get(pk=target_user_id)
#         except User.DoesNotExist:
#             return Response({'error': 'User not found'}, status=404)
#
#         from guardian.shortcuts import assign_perm
#         assign_perm(f'blog.{perm}', target, doc)
#         return Response({
#             'shared_with': target.username,
#             'permission': perm,
#         })
#
#     @action(detail=True, methods=['post'], permission_classes=[CanShareDocument])
#     def revoke(self, request, pk=None):
#         doc = self.get_object()
#         target_user_id = request.data.get('user_id')
#         perm = request.data.get('permission', 'view_document')
#
#         target = User.objects.get(pk=target_user_id)
#         from guardian.shortcuts import remove_perm
#         remove_perm(f'blog.{perm}', target, doc)
#         return Response({'revoked': True})


# ==========================================================================
# 8. TEMPLATE / VIEW USAGE
# ==========================================================================

# Function-based view
# from django.contrib.auth.decorators import permission_required
# from django.shortcuts import get_object_or_404
#
#
# def document_detail(request, pk):
#     doc = get_object_or_404(Document, pk=pk)
#     if not request.user.has_perm('blog.view_document', doc):
#         if not doc.is_public:
#             return HttpResponseForbidden()
#     return render(request, 'doc_detail.html', {'doc': doc})


# Template tag check
"""
{% load guardian_tags %}
{% get_obj_perms request.user for doc as 'doc_perms' %}
{% if 'change_document' in doc_perms %}
    <button>Edit</button>
{% endif %}
"""


# ==========================================================================
# 9. GROUP-BASED PERMS (preferred for teams)
# ==========================================================================

# from django.contrib.auth.models import Group
# from guardian.shortcuts import assign_perm
#
#
# def setup_tenant_team(tenant_id):
#     group, _ = Group.objects.get_or_create(name=f'tenant_{tenant_id}_team')
#     # ... add users to group via group.user_set.add(user)
#     return group
#
#
# def share_with_team(doc, team_group, perm='view_document'):
#     assign_perm(f'blog.{perm}', team_group, doc)
#
#
# # Check works transparently
# # user.has_perm('blog.view_document', doc)  ← True if user in team_group


# ==========================================================================
# 10. POSTGRESQL ROW-LEVEL SECURITY (defense-in-depth)
# ==========================================================================

# Apply via Django migration or directly via SQL
"""
-- Enable RLS on documents table
ALTER TABLE blog_document ENABLE ROW LEVEL SECURITY;

-- Policy: only see own + public + shared
CREATE POLICY doc_isolation ON blog_document
USING (
    owner_id = current_setting('app.current_user_id')::int
    OR is_public = true
    OR id IN (
        SELECT object_pk::int FROM guardian_userobjectpermission
        WHERE user_id = current_setting('app.current_user_id')::int
    )
);
"""


# Middleware to set DB session var per-request
from django.db import connection


class DBContextMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            with connection.cursor() as c:
                c.execute(
                    "SELECT set_config('app.current_user_id', %s, true)",
                    [str(request.user.pk)],
                )
        return self.get_response(request)


# ==========================================================================
# 11. BULK PERM ASSIGNMENT (efficient)
# ==========================================================================

# from guardian.models import UserObjectPermission
# from guardian.shortcuts import get_perm_obj
#
#
# def bulk_grant_view(users, docs):
#     """Grant view_document perm to many users on many docs efficiently."""
#     perm = get_perm_obj('blog.view_document')
#     ct = ContentType.objects.get_for_model(Document)
#
#     entries = []
#     for user in users:
#         for doc in docs:
#             entries.append(UserObjectPermission(
#                 user=user,
#                 permission=perm,
#                 content_type=ct,
#                 object_pk=str(doc.pk),
#             ))
#     UserObjectPermission.objects.bulk_create(entries, ignore_conflicts=True)
