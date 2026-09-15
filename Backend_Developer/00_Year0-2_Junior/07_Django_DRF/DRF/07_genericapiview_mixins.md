# DRF — GenericAPIView + Mixins vs ViewSet

## Quick Concepts
- **APIView** = maximum control, manual everything
- **GenericAPIView** = queryset + serializer_class + pagination built-in
- **Mixins** = ListModelMixin, CreateModelMixin, etc. — plug individual operations
- **ViewSet** = all CRUD in one class + Router auto-generates URLs
- **ReadOnlyModelViewSet** = only list + retrieve

---

## Interview Questions & Answers

### Q1: APIView → GenericAPIView → ViewSet hierarchy kya hai?

**Answer:**
```python
# ─── Level 1: APIView — full manual control ───
from rest_framework.views import APIView
from rest_framework.response import Response

class UserListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        users = User.objects.all()
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data)

    def post(self, request):
        serializer = UserSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=201)

# URLs manually:
# path("users/", UserListView.as_view())
# path("users/<int:pk>/", UserDetailView.as_view())

# ─── Level 2: GenericAPIView + Mixins ───
from rest_framework import generics, mixins

class UserListView(mixins.ListModelMixin,
                   mixins.CreateModelMixin,
                   generics.GenericAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get(self, request, *args, **kwargs):
        return self.list(request, *args, **kwargs)      # from ListModelMixin

    def post(self, request, *args, **kwargs):
        return self.create(request, *args, **kwargs)    # from CreateModelMixin

# ─── Level 2b: Generic Concrete Views (shortcut) ───
class UserListCreateView(generics.ListCreateAPIView):
    # Combines ListModelMixin + CreateModelMixin automatically
    queryset         = User.objects.select_related("profile")
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    # Combines retrieve + update + partial_update + destroy
    queryset         = User.objects.all()
    serializer_class = UserSerializer

# URLs:
# path("users/",       UserListCreateView.as_view())
# path("users/<pk>/",  UserDetailView.as_view())

# ─── Level 3: ModelViewSet — all in one ───
class UserViewSet(viewsets.ModelViewSet):
    queryset         = User.objects.all()
    serializer_class = UserSerializer

# Router auto-generates ALL URLs — no manual path() needed
```

---

### Q2: Concrete Generic Views — kaunsa class kab use karo?

**Answer:**
```python
from rest_framework import generics

# ─── List only ───
class TagListView(generics.ListAPIView):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer
    # GET /tags/ → list

# ─── Create only ───
class RegisterView(generics.CreateAPIView):
    serializer_class = UserRegisterSerializer
    permission_classes = [AllowAny]
    # POST /register/ → create

# ─── List + Create ───
class PostListCreateView(generics.ListCreateAPIView):
    queryset = Post.objects.published()
    serializer_class = PostListSerializer
    # GET  /posts/ → list
    # POST /posts/ → create

# ─── Retrieve only ───
class PostDetailView(generics.RetrieveAPIView):
    queryset = Post.objects.all()
    serializer_class = PostDetailSerializer
    # GET /posts/{pk}/ → retrieve

# ─── Retrieve + Update + Delete ───
class PostRUDView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Post.objects.all()
    serializer_class = PostDetailSerializer
    permission_classes = [IsOwnerOrReadOnly]
    # GET    /posts/{pk}/ → retrieve
    # PUT    /posts/{pk}/ → update
    # PATCH  /posts/{pk}/ → partial_update
    # DELETE /posts/{pk}/ → destroy

# ─── Update only ───
class UserProfileUpdateView(generics.UpdateAPIView):
    serializer_class = UserUpdateSerializer
    # PATCH /users/me/ → partial_update
    def get_object(self):
        return self.request.user

# ─── Complete mapping ───
# ListAPIView             → GET (list)
# CreateAPIView           → POST
# RetrieveAPIView         → GET (detail)
# UpdateAPIView           → PUT + PATCH
# DestroyAPIView          → DELETE
# ListCreateAPIView       → GET (list) + POST
# RetrieveUpdateAPIView   → GET (detail) + PUT + PATCH
# RetrieveDestroyAPIView  → GET (detail) + DELETE
# RetrieveUpdateDestroyAPIView → GET + PUT + PATCH + DELETE
```

---

### Q3: GenericAPIView vs ViewSet — kab kaunsa choose karo?

**Answer:**
```
GenericAPIView / Concrete Views:
  ✅ Use when:
    - Non-standard URL structure (/users/me/, /auth/login/)
    - Only some HTTP methods chahiye (only GET + POST, no DELETE)
    - Custom logic per method — override get(), post() separately
    - Non-model views (analytics, aggregate data)

  Example:
    /auth/login/    → CreateAPIView (POST only)
    /auth/refresh/  → CreateAPIView
    /users/me/      → RetrieveUpdateAPIView
    /users/me/avatar/ → UpdateAPIView

ViewSet (ModelViewSet / ReadOnlyModelViewSet):
  ✅ Use when:
    - Standard CRUD resource
    - Router URL auto-generation chahiye
    - Custom @action methods
    - get_queryset / get_serializer_class per action

  Example:
    /api/v1/users/     → UserViewSet (CRUD)
    /api/v1/blog/posts/ → PostViewSet (CRUD + custom actions)
    /api/v1/tags/       → ReadOnlyModelViewSet (only list + retrieve)

Rule of thumb (5yr experience):
  Resource has CRUD? → ViewSet + Router
  Custom endpoint (login, export, stats)? → GenericAPIView or APIView
```

---

### Q4: `get_queryset()`, `get_serializer_class()`, `get_permissions()` — kyu override karte hain?

**Answer:**
```python
class PostViewSet(viewsets.ModelViewSet):

    def get_queryset(self):
        """
        Dynamic queryset — based on user, request params, action.
        """
        qs = Post.objects.with_all_relations()

        # Action-based filtering
        if self.action == "list":
            if self.request.user.is_authenticated:
                return qs.filter(
                    models.Q(status="published") |
                    models.Q(author=self.request.user)
                )
            return qs.filter(status="published")

        # Detail action — user can see own draft
        return qs.filter(
            models.Q(status="published") |
            models.Q(author=self.request.user)
        )

    def get_serializer_class(self):
        """Different serializer for different actions."""
        action_map = {
            "list":           PostListSerializer,    # lightweight
            "retrieve":       PostDetailSerializer,  # full content
            "create":         PostCreateSerializer,  # write fields
            "update":         PostCreateSerializer,
            "partial_update": PostCreateSerializer,
        }
        return action_map.get(self.action, PostListSerializer)

    def get_permissions(self):
        """Different permissions for different actions."""
        if self.action in ("list", "retrieve", "featured"):
            return [AllowAny()]
        if self.action in ("update", "partial_update", "destroy"):
            return [IsAuthenticated(), IsOwnerOrReadOnly()]
        return [IsAuthenticated()]

    def get_throttles(self):
        """Stricter throttle for expensive operations."""
        if self.action == "create":
            return [CreateThrottle()]  # 10/hour
        return super().get_throttles()
```

---

### Q5: `@action` decorator — custom endpoints ViewSet mein?

**Answer:**
```python
from rest_framework.decorators import action

class PostViewSet(viewsets.ModelViewSet):

    # ─── detail=False — resource-level action ───
    # URL: GET /posts/featured/
    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def featured(self, request):
        posts = Post.objects.published().featured()[:6]
        return Response(PostListSerializer(posts, many=True).data)

    # ─── detail=True — object-level action ───
    # URL: POST /posts/{pk}/publish/
    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        post = self.get_object()
        post.publish()
        return Response({"status": "published"})

    # ─── Custom URL path ───
    # URL: GET /posts/{pk}/similar/
    @action(detail=True, methods=["get"], url_path="similar", url_name="similar")
    def similar_posts(self, request, pk=None):
        post = self.get_object()
        similar = Post.objects.published().filter(
            category=post.category
        ).exclude(pk=post.pk)[:5]
        return Response(PostListSerializer(similar, many=True).data)

    # ─── Multiple HTTP methods ───
    @action(detail=True, methods=["get", "post"], url_path="comments")
    def comments(self, request, pk=None):
        post = self.get_object()
        if request.method == "GET":
            comments = post.comments.filter(is_approved=True)
            return Response(CommentSerializer(comments, many=True).data)
        else:  # POST
            serializer = CommentSerializer(data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save(post=post, author=request.user)
            return Response(serializer.data, status=201)
```

---

## Summary: Choosing the Right View Class

```
Need:                              Use:
─────────────────────────────────────────────────────
Full CRUD resource + auto URLs  →  ModelViewSet
Read-only resource              →  ReadOnlyModelViewSet
Standard CRUD, manual URLs      →  RetrieveUpdateDestroyAPIView etc.
Login / Auth                    →  CreateAPIView (APIView)
Custom business logic           →  APIView
Webhook receiver                →  APIView (no serializer needed)
Admin export endpoint           →  generics.ListAPIView
User's own profile (GET+PATCH)  →  RetrieveUpdateAPIView
```
