# Object-Level Permissions — Row-Level Access Control

## Why It Matters (Senior 5 YOE Context)

Django's default permissions are **model-level**: "can_change_article" applies to ALL articles or NONE. Real apps need **row-level**: "Alice can edit her own article but not Bob's".

Use cases:
- **Multi-tenant SaaS** → each tenant sees only their data
- **Document collaboration** → owner + shared users
- **Hierarchical** → manager sees team members' records
- **Compliance** → only HR sees salary data

Senior interview: "Implement document sharing — owner can grant view/edit access to specific users." → object-level permissions.

---

## Core Concepts

### Built-in `has_perm` with `obj`

Django's `User.has_perm()` accepts an `obj` argument but built-in `ModelBackend` ignores it. You need a custom backend OR library.

```python
# This returns True/False but ignores obj at default backend
user.has_perm('blog.change_article', obj=article)
```

### Custom Permission Backend

```python
class OwnerPermissionBackend:
    """Allow users to change/delete their own objects."""

    def authenticate(self, request, **credentials):
        return None  # not for auth

    def has_perm(self, user_obj, perm, obj=None):
        if obj is None:
            return False
        if not user_obj.is_authenticated:
            return False

        # Allow if user is owner
        if hasattr(obj, 'author_id') and obj.author_id == user_obj.pk:
            return True
        if hasattr(obj, 'owner_id') and obj.owner_id == user_obj.pk:
            return True
        return False


# settings.py
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'core.auth_backends.OwnerPermissionBackend',
]
```

Django checks all backends — any `True` allows.

### django-guardian (Recommended Library)

```python
# pip install django-guardian
INSTALLED_APPS += ['guardian']
AUTHENTICATION_BACKENDS += ['guardian.backends.ObjectPermissionBackend']

ANONYMOUS_USER_NAME = 'AnonymousUser'  # required


from guardian.shortcuts import assign_perm, remove_perm, get_objects_for_user


# Assign perm
assign_perm('blog.change_article', user, article)
assign_perm('blog.view_article', group, article)


# Check
user.has_perm('blog.change_article', article)  # True


# Revoke
remove_perm('blog.change_article', user, article)


# Query all articles user can change
articles = get_objects_for_user(user, 'blog.change_article')


# Query all users with perm on an article
from guardian.shortcuts import get_users_with_perms
users = get_users_with_perms(article, attach_perms=True)
# {<User>: ['change_article', 'view_article'], ...}
```

### Custom Permissions (Verb-Based)

```python
class Document(models.Model):
    title = models.CharField(max_length=200)
    owner = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    body = models.TextField()

    class Meta:
        permissions = [
            ('share_document', 'Can share document'),
            ('publish_document', 'Can publish document'),
            ('archive_document', 'Can archive document'),
        ]


# Use
assign_perm('blog.share_document', user, doc)
user.has_perm('blog.share_document', doc)
```

### DRF Object-Level Permissions

```python
from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        # SAFE_METHODS = GET, HEAD, OPTIONS — read allowed for all
        if request.method in permissions.SAFE_METHODS:
            return True
        # Only owner can write
        return obj.owner == request.user


class CanEditDocument(permissions.BasePermission):
    """Uses django-guardian under the hood."""

    def has_object_permission(self, request, view, obj):
        return request.user.has_perm('blog.change_document', obj)


class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrReadOnly]
```

### Filtering Queryset by Permission

```python
from guardian.shortcuts import get_objects_for_user


class DocumentViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        user = self.request.user
        # User sees: own + shared + public
        own = Document.objects.filter(owner=user)
        shared = get_objects_for_user(user, 'blog.view_document', klass=Document)
        public = Document.objects.filter(is_public=True)
        return (own | shared | public).distinct()
```

### Sharing Endpoint

```python
@action(detail=True, methods=['post'])
def share(self, request, pk=None):
    doc = self.get_object()
    if doc.owner != request.user:
        raise PermissionDenied("Only owner can share")

    target_user_id = request.data.get('user_id')
    perm = request.data.get('permission', 'view_document')  # view or change

    if perm not in ('view_document', 'change_document'):
        return Response({'error': 'Invalid permission'}, status=400)

    target = User.objects.get(pk=target_user_id)
    assign_perm(f'blog.{perm}', target, doc)
    return Response({'shared_with': target.username, 'permission': perm})
```

### Hierarchical (Manager Sees Team)

```python
class HierarchyPermissionBackend:
    def has_perm(self, user_obj, perm, obj=None):
        if obj is None:
            return False
        if not hasattr(obj, 'owner_id'):
            return False

        # Manager can view direct reports
        if perm == 'blog.view_document':
            try:
                target_user = User.objects.get(pk=obj.owner_id)
                return target_user.manager_id == user_obj.pk
            except User.DoesNotExist:
                pass

        return False
```

---

## How It Works Internally

### django-guardian Tables

```sql
-- For each (user, model_instance, perm) triple:
guardian_userobjectpermission (
    user_id, content_type_id, object_pk, permission_id
)

-- For groups
guardian_groupobjectpermission (
    group_id, content_type_id, object_pk, permission_id
)
```

Query cost: each `has_perm(obj)` = 1 SELECT (indexed). For bulk filtering, `get_objects_for_user` does a JOIN.

### Permission Resolution

```python
# Django's has_perm logic:
for backend in self.iter_backends():
    if hasattr(backend, 'has_perm'):
        if backend.has_perm(self, perm, obj):
            return True
return False
```

Any backend returns True → granted.

### Auto-Inherited Permissions

```python
# Often: granting on parent should imply child access
# Custom logic in backend:

class FolderInheritedPermBackend:
    def has_perm(self, user, perm, obj=None):
        if obj and isinstance(obj, Document):
            # Check on parent folder
            folder = obj.folder
            return user.has_perm('blog.change_folder', folder)
        return False
```

---

## Common Pitfalls

### 1. Forgetting `has_object_permission` in DRF

DRF calls `has_permission()` (view-level) by default. `has_object_permission` only called by `get_object()` or `check_object_permissions()`:

```python
# list/create — only has_permission
# retrieve/update/destroy — both
```

If you use raw QuerySet methods without `get_object`, object perms bypassed.

### 2. N+1 in Bulk Check

```python
# BAD
for doc in Document.objects.all():
    if user.has_perm('blog.view_document', doc):  # 1 query per doc
        ...

# GOOD
allowed = get_objects_for_user(user, 'blog.view_document', klass=Document)
```

### 3. Stale Permissions in Cache

Some setups cache permissions per-user. Revoke not reflected immediately. Clear cache on permission change:

```python
@receiver(post_save, sender='guardian.UserObjectPermission')
def invalidate_user_perm_cache(sender, instance, **kwargs):
    cache.delete(f'user_perms:{instance.user_id}')
```

### 4. Migrations + Permissions

`assign_perm` in migration may fail if Permission rows not created yet. Use `RunPython` after `update_contenttypes`:

```python
def assign_initial_perms(apps, schema_editor):
    from guardian.shortcuts import assign_perm
    # ... safe to use here
```

### 5. Group Permissions Easier to Manage

For tenant teams, prefer group-level perms over per-user:

```python
team_group = Group.objects.get_or_create(name=f'tenant_{tenant_id}_team')
assign_perm('blog.view_document', team_group, doc)
# Add/remove users from group instead of individual perms
```

### 6. RLS (Row Level Security) at DB Level

For truly secure (defense-in-depth) — PostgreSQL RLS policies. Even if app code bypasses, DB blocks:

```sql
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON documents
  USING (tenant_id = current_setting('app.current_tenant')::int);
```

Django: set `current_setting` via raw SQL in middleware.

---

## Interview Q&A

**Q1:** Object-level permissions Django built-in support karta hai?
**A:** Partial — `has_perm(obj=...)` API exists but default backend ignores `obj`. Need either custom backend or library like django-guardian. Built-in is model-level only.

**Q2:** django-guardian alternatives?
**A:** (1) django-rules — predicate-based (rule functions). (2) Custom backend with own table. (3) PostgreSQL Row-Level Security (DB-enforced). (4) Application-level filtering in `get_queryset` (no perm storage, logic in code). Choose based on storage flexibility vs. enforcement needs.

**Q3:** DRF mein object permission kab check hota hai?
**A:** Only when `get_object()` is called (retrieve/update/destroy) or you explicitly call `self.check_object_permissions(request, obj)`. List/create don't auto-check object perms. For list: filter `get_queryset` by user's accessible objects.

**Q4:** Document sharing system kaise design karoge?
**A:** Per-document grant table `(doc_id, user_id, perm)` — django-guardian provides. Endpoint: owner posts `{user_id, perm}` → `assign_perm(perm, user, doc)`. List: union of own + `get_objects_for_user`. Optimization: index on `(content_type_id, object_pk)`.

**Q5:** Multi-tenant SaaS mein row-level security kaise enforce karoge?
**A:** Three layers: (1) App: middleware sets `tenant_id` from request, manager filters queries. (2) DB: PostgreSQL RLS — set `SET app.tenant_id = X` per session, policies enforce. (3) Schema-per-tenant: separate Postgres schema (most isolation, most overhead). Defense-in-depth.

**Q6:** Bulk permission check N+1 kaise avoid karoge?
**A:** `get_objects_for_user(user, perm, klass=Model)` returns QuerySet — single JOIN. Use as base queryset. For check on many specific objects: bulk query the permission table once, cache locally.

**Q7:** Group permissions vs user permissions — kab kya?
**A:** Group for role-based (team, department) — easier to manage as team changes. User for individual sharing (one-off doc share). Combine: user permissions inherit through groups. django-guardian supports both natively.

**Q8:** Permission change cache invalidation strategy?
**A:** (1) Signal on perm change → invalidate cache for affected user. (2) Short TTL (60s) — accept brief staleness. (3) Cache version key — bump on any change. (4) No caching — rely on indexed query. For most apps, indexed query is fast enough; caching is premature.

---

## Real-World Use Cases

### 1. Document Sharing (Google Docs Style)

```python
# Owner grants
assign_perm('blog.view_document', viewer, doc)
assign_perm('blog.change_document', editor, doc)

# Listing
docs = (
    Document.objects.filter(owner=request.user) |
    get_objects_for_user(request.user, 'blog.view_document', klass=Document)
).distinct()
```

### 2. Manager Access to Team Records

```python
class HierarchyBackend:
    def has_perm(self, user, perm, obj=None):
        if not obj or perm != 'hr.view_employee':
            return False
        return obj.manager_id == user.pk or self._is_ancestor(user, obj.manager_id)
```

### 3. Public + Private + Shared Documents

```python
def get_queryset(self):
    user = self.request.user
    return Document.objects.filter(
        Q(is_public=True) |
        Q(owner=user) |
        Q(pk__in=get_objects_for_user(user, 'blog.view_document').values('pk'))
    ).distinct()
```

---

## References

- [django-guardian docs](https://django-guardian.readthedocs.io/)
- [django-rules](https://github.com/dfunckt/django-rules)
- [PostgreSQL Row-Level Security](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- DRF permissions guide
