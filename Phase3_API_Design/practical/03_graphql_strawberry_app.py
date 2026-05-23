"""
GraphQL Blog API — FastAPI + Strawberry
========================================
Run with uvicorn:
    uvicorn 03_graphql_strawberry_app:app --reload --port 8005

Run schema tests directly (no uvicorn needed):
    python 03_graphql_strawberry_app.py

Install dependencies:
    pip install "strawberry-graphql[fastapi]" fastapi uvicorn

Features demonstrated:
- @strawberry.type, @strawberry.input, @strawberry.enum
- Custom resolvers with info: Info parameter
- DataLoader (N+1 problem solution)
- Permission classes (IsAuthenticated, IsAdmin)
- Union result types for error handling
- Subscriptions (AsyncGenerator)
- QueryDepthLimiter extension
- Per-request context (auth user + DataLoader)
- Filtering, pagination
- Schema tests without HTTP
"""

import asyncio
import strawberry
import uvicorn
from datetime import datetime
from typing import Optional, AsyncGenerator, Any
from collections import defaultdict

# Strawberry imports
from strawberry.types import Info
from strawberry.fastapi import GraphQLRouter
from strawberry.dataloader import DataLoader
from strawberry.permission import BasePermission
from strawberry.extensions import QueryDepthLimiter
from strawberry.annotation import StrawberryAnnotation

# FastAPI
from fastapi import FastAPI, Request
from contextlib import asynccontextmanager

# ============================================================
# IN-MEMORY DATABASE (production mein SQL/MongoDB use karo)
# ============================================================

AUTHORS_DB: dict[str, "AuthorModel"] = {}
POSTS_DB: dict[str, "PostModel"] = {}
COMMENTS_DB: dict[str, "CommentModel"] = {}

# Live subscription queues (production mein: Redis pub/sub)
_post_subscribers: list[asyncio.Queue] = []
_comment_subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)


class AuthorModel:
    def __init__(self, id: str, name: str, email: str, bio: Optional[str] = None):
        self.id = id
        self.name = name
        self.email = email
        self.bio = bio
        self.created_at = datetime.now()


class PostModel:
    def __init__(
        self,
        id: str,
        title: str,
        content: str,
        author_id: str,
        published: bool = False,
    ):
        self.id = id
        self.title = title
        self.content = content
        self.author_id = author_id
        self.published = published
        self.created_at = datetime.now()


class CommentModel:
    def __init__(self, id: str, text: str, post_id: str, author_id: str):
        self.id = id
        self.text = text
        self.post_id = post_id
        self.author_id = author_id
        self.created_at = datetime.now()


# ============================================================
# SEED DATA
# ============================================================

def seed_data():
    """Initial data load karo (5 authors, 20 posts, 50 comments)"""
    AUTHORS_DB.clear()
    POSTS_DB.clear()
    COMMENTS_DB.clear()

    # 5 Authors
    author_data = [
        ("1", "Ashish Chaurasiya", "ashish@ygroup.com", "Senior Python Developer at Y Group"),
        ("2", "Priya Sharma", "priya@ygroup.com", "FastAPI specialist, API design enthusiast"),
        ("3", "Rahul Verma", "rahul@ygroup.com", "DevOps + Backend engineer"),
        ("4", "Anjali Mehta", "anjali@ygroup.com", "Full-stack developer, GraphQL fanatic"),
        ("5", "Vikram Singh", "vikram@ygroup.com", "Microservices architect"),
    ]
    for aid, name, email, bio in author_data:
        AUTHORS_DB[aid] = AuthorModel(aid, name, email, bio)

    # 20 Posts (mix of published/draft)
    posts_data = [
        ("1", "Python AsyncIO Deep Dive", "Asyncio event loop, tasks, coroutines explained...", "1", True),
        ("2", "GraphQL vs REST — 2024 Comparison", "When to choose GraphQL over REST API...", "1", True),
        ("3", "FastAPI Performance Optimization", "Tips to squeeze max performance from FastAPI...", "2", True),
        ("4", "SQLAlchemy 2.0 Async Patterns", "New async API in SQLAlchemy 2.0 with examples...", "2", True),
        ("5", "DataLoader Pattern in Python", "Solving N+1 problem with DataLoader in Strawberry...", "1", True),
        ("6", "JWT Authentication Best Practices", "Secure JWT implementation for production...", "3", True),
        ("7", "Redis Caching Strategies", "Cache-aside, write-through, write-behind patterns...", "3", True),
        ("8", "Docker + FastAPI Production Setup", "Complete Docker compose setup for FastAPI app...", "3", True),
        ("9", "GraphQL Subscriptions with Strawberry", "Real-time features using WebSocket subscriptions...", "4", True),
        ("10", "Pydantic V2 Migration Guide", "Key changes from Pydantic V1 to V2...", "2", True),
        ("11", "Celery + Redis Task Queue", "Background job processing with Celery...", "5", True),
        ("12", "PostgreSQL Query Optimization", "EXPLAIN ANALYZE, indexes, query planning...", "5", True),
        ("13", "microservices with FastAPI", "Service discovery, communication patterns...", "5", True),
        ("14", "Draft: Advanced Strawberry Patterns", "UNPUBLISHED — work in progress...", "4", False),
        ("15", "Draft: Kubernetes Deployment Guide", "UNPUBLISHED — helm charts, ingress...", "3", False),
        ("16", "Python Type Hints Mastery", "Generics, Protocols, TypeVar, ParamSpec...", "1", True),
        ("17", "API Rate Limiting Implementation", "Token bucket, sliding window algorithms...", "2", True),
        ("18", "Database Connection Pooling", "PgBouncer, SQLAlchemy pool config...", "5", True),
        ("19", "Draft: Event Sourcing in Python", "UNPUBLISHED — CQRS, event store...", "1", False),
        ("20", "OpenTelemetry for Python APIs", "Distributed tracing, metrics, logs...", "4", True),
    ]
    for pid, title, content, author_id, published in posts_data:
        POSTS_DB[pid] = PostModel(pid, title, content, author_id, published)

    # 50 Comments (2-3 per post)
    comment_id = 1
    comments_per_post = {
        "1": ["Great explanation of asyncio!", "This helped me understand event loops finally.", "Can you cover asyncio.Queue next?"],
        "2": ["GraphQL is definitely the future for complex APIs.", "I still prefer REST for simple CRUD.", "Great comparison table!"],
        "3": ["FastAPI is already so fast, these tips make it blazing!", "Applied the connection pooling tip — 30% improvement!"],
        "4": ["SQLAlchemy 2.0 async is amazing.", "Migration from 1.4 was easier than expected."],
        "5": ["DataLoader saved us from N+1 hell.", "Batch loading is such an elegant solution!"],
        "6": ["Always use RS256 in production, not HS256.", "Great article on refresh token rotation."],
        "7": ["Redis is a lifesaver for high-traffic apps."],
        "8": ["Multi-stage Docker builds cut our image size by 60%!", "Added this to our CI/CD pipeline."],
        "9": ["Subscriptions + React makes real-time so easy!", "WebSocket reliability tips would be helpful."],
        "10": ["Pydantic V2 model_validator is much better!", "Performance improvement is huge."],
        "11": ["Celery beat for scheduled tasks is underrated.", "We moved from Celery to Dramatiq for simplicity."],
        "12": ["BRIN indexes for time-series are gold!", "Partial indexes tip saved our query time."],
        "13": ["gRPC between services is worth considering.", "FastAPI as microservice is lightweight."],
        "16": ["TypeVar with bound is so powerful.", "Protocol makes duck typing formal."],
        "17": ["Sliding window is more accurate than token bucket."],
        "18": ["PgBouncer in transaction mode for serverless!"],
        "20": ["OTEL + Grafana Tempo is our new stack.", "Tracing helped us find a slow DB query we missed for months!"],
    }

    for post_id, comment_texts in comments_per_post.items():
        for text in comment_texts:
            cid = str(comment_id)
            author_id = str((comment_id % 5) + 1)  # Cycle through authors
            COMMENTS_DB[cid] = CommentModel(cid, text, post_id, author_id)
            comment_id += 1


# ============================================================
# PERMISSION CLASSES
# ============================================================

class IsAuthenticated(BasePermission):
    """User authenticated hona chahiye (JWT token valid ho)"""
    message = "User is not authenticated. Provide a valid Bearer token."

    def has_permission(self, source: Any, info: Info, **kwargs: Any) -> bool:
        user = info.context.get("current_user")
        return user is not None


class IsAdmin(BasePermission):
    """User admin role wala hona chahiye"""
    message = "Admin role required. You don't have sufficient permissions."

    def has_permission(self, source: Any, info: Info, **kwargs: Any) -> bool:
        user = info.context.get("current_user")
        if not user:
            return False
        return user.get("role") == "admin"


# ============================================================
# DATALOADER BATCH FUNCTIONS
# ============================================================

async def batch_load_authors(
    author_ids: list[strawberry.ID],
) -> list[Optional["Author"]]:
    """
    DataLoader batch function — ek baar mein saare authors load karo.

    Without DataLoader: N posts → N separate DB queries for author
    With DataLoader:    N posts → 1 batch query for all N authors

    IMPORTANT: Return list must be SAME LENGTH and ORDER as input keys.
    """
    print(f"\n  [DataLoader] Batch loading {len(author_ids)} authors: {list(author_ids)}")

    # Ek operation mein saare fetch karo (real DB mein: WHERE id IN (...))
    results = []
    for aid in author_ids:
        model = AUTHORS_DB.get(str(aid))
        if model:
            results.append(Author(
                id=strawberry.ID(model.id),
                name=model.name,
                email=model.email,
                bio=model.bio,
            ))
        else:
            results.append(None)  # Missing IDs ke liye None
    return results


async def batch_load_comments_by_post(
    post_ids: list[strawberry.ID],
) -> list[list["Comment"]]:
    """
    Batch load comments grouped by post_id.
    Returns list of lists — each inner list = comments for that post.
    """
    print(f"\n  [DataLoader] Batch loading comments for {len(post_ids)} posts")
    all_comments = list(COMMENTS_DB.values())

    # Group comments by post_id
    comments_map: dict[str, list[Comment]] = defaultdict(list)
    for c in all_comments:
        comments_map[str(c.post_id)].append(Comment(
            id=strawberry.ID(c.id),
            text=c.text,
            post_id=strawberry.ID(c.post_id),
            author_id=strawberry.ID(c.author_id),
        ))

    # Same order mein return karo
    return [comments_map.get(str(pid), []) for pid in post_ids]


# ============================================================
# STRAWBERRY TYPES
# ============================================================

@strawberry.type
class Author:
    id: strawberry.ID
    name: str
    email: str
    bio: Optional[str] = None

    @strawberry.field(description="All posts written by this author")
    def posts(self, info: Info, published_only: bool = False) -> list["Post"]:
        """Author ke saare posts — nested resolver"""
        posts = [
            p for p in POSTS_DB.values()
            if str(p.author_id) == str(self.id)
        ]
        if published_only:
            posts = [p for p in posts if p.published]
        return [_post_model_to_type(p) for p in posts]

    @strawberry.field(description="Total number of posts by this author")
    def post_count(self) -> int:
        return len([p for p in POSTS_DB.values() if str(p.author_id) == str(self.id)])


@strawberry.type
class Post:
    id: strawberry.ID
    title: str
    content: str
    published: bool
    created_at: datetime
    author_id: strawberry.ID

    @strawberry.field(description="Author of this post — uses DataLoader (no N+1!)")
    async def author(self, info: Info) -> Optional[Author]:
        """
        DataLoader use karo — N+1 problem solve hota hai.

        Agar 100 posts query karo, ye resolver 100 baar call hoga.
        Lekin DataLoader sab calls collect karta hai aur 1 batch query karta hai.
        """
        loader: DataLoader = info.context["author_loader"]
        return await loader.load(self.author_id)

    @strawberry.field(description="Comments on this post — uses DataLoader")
    async def comments(self, info: Info) -> list["Comment"]:
        loader: DataLoader = info.context["comments_loader"]
        result = await loader.load(self.id)
        return result or []

    @strawberry.field(description="Number of comments on this post")
    def comment_count(self) -> int:
        return len([c for c in COMMENTS_DB.values() if str(c.post_id) == str(self.id)])

    @strawberry.field(description="Short preview of content (first 100 chars)")
    def preview(self) -> str:
        return self.content[:100] + "..." if len(self.content) > 100 else self.content


@strawberry.type
class Comment:
    id: strawberry.ID
    text: str
    post_id: strawberry.ID
    author_id: strawberry.ID

    @strawberry.field
    async def author(self, info: Info) -> Optional[Author]:
        loader: DataLoader = info.context["author_loader"]
        return await loader.load(self.author_id)


# ============================================================
# ERROR TYPES (Union pattern for type-safe error handling)
# ============================================================

@strawberry.type
class PostNotFound:
    """Post exist nahi karta"""
    message: str = "Post not found"
    post_id: strawberry.ID


@strawberry.type
class AuthorNotFound:
    """Author exist nahi karta"""
    message: str = "Author not found"
    author_id: strawberry.ID


@strawberry.type
class PermissionDenied:
    """Permission nahi hai"""
    message: str = "You don't have permission to perform this action"
    required_role: Optional[str] = None


@strawberry.type
class ValidationError:
    """Input validation fail"""
    message: str
    field: str
    code: str = "VALIDATION_ERROR"


# Union types — mutations ye return kar sakti hain
PostResult = strawberry.union(
    "PostResult",
    [Post, PostNotFound],
    description="Either a Post or a PostNotFound error"
)

CreatePostResult = strawberry.union(
    "CreatePostResult",
    [Post, ValidationError, PermissionDenied],
)

UpdatePostResult = strawberry.union(
    "UpdatePostResult",
    [Post, PostNotFound, PermissionDenied, ValidationError],
)

DeletePostResult = strawberry.union(
    "DeletePostResult",
    [PostNotFound, PermissionDenied],
)


# ============================================================
# INPUT TYPES
# ============================================================

@strawberry.input
class CreatePostInput:
    title: str
    content: str
    author_id: strawberry.ID
    published: bool = False


@strawberry.input
class UpdatePostInput:
    title: Optional[str] = strawberry.UNSET
    content: Optional[str] = strawberry.UNSET
    published: Optional[bool] = strawberry.UNSET


@strawberry.input
class PostFilterInput:
    published_only: bool = False
    author_id: Optional[strawberry.ID] = None
    search: Optional[str] = None


# ============================================================
# PAGINATION TYPES
# ============================================================

@strawberry.type
class PostPage:
    items: list[Post]
    total: int
    page: int
    page_size: int
    has_next: bool
    has_prev: bool


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def _post_model_to_type(model: PostModel) -> Post:
    return Post(
        id=strawberry.ID(model.id),
        title=model.title,
        content=model.content,
        published=model.published,
        created_at=model.created_at,
        author_id=strawberry.ID(model.author_id),
    )


def _author_model_to_type(model: AuthorModel) -> Author:
    return Author(
        id=strawberry.ID(model.id),
        name=model.name,
        email=model.email,
        bio=model.bio,
    )


def _comment_model_to_type(model: CommentModel) -> Comment:
    return Comment(
        id=strawberry.ID(model.id),
        text=model.text,
        post_id=strawberry.ID(model.post_id),
        author_id=strawberry.ID(model.author_id),
    )


# ============================================================
# QUERY TYPE
# ============================================================

@strawberry.type
class Query:
    """All GraphQL queries — read-only operations"""

    @strawberry.field(description="Get all authors")
    def authors(self) -> list[Author]:
        return [_author_model_to_type(a) for a in AUTHORS_DB.values()]

    @strawberry.field(description="Get author by ID")
    def author(self, id: strawberry.ID) -> Optional[Author]:
        model = AUTHORS_DB.get(str(id))
        return _author_model_to_type(model) if model else None

    @strawberry.field(description="Get posts with optional filters")
    def posts(
        self,
        published_only: bool = False,
        author_id: Optional[strawberry.ID] = None,
        search: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> list[Post]:
        results = list(POSTS_DB.values())

        if published_only:
            results = [p for p in results if p.published]

        if author_id:
            results = [p for p in results if str(p.author_id) == str(author_id)]

        if search:
            q = search.lower()
            results = [
                p for p in results
                if q in p.title.lower() or q in p.content.lower()
            ]

        if limit:
            results = results[:limit]

        return [_post_model_to_type(p) for p in results]

    @strawberry.field(description="Get post by ID — returns Post or PostNotFound")
    def post(self, id: strawberry.ID) -> PostResult:
        """Union return type — client mein inline fragments use karo"""
        model = POSTS_DB.get(str(id))
        if not model:
            return PostNotFound(post_id=id)
        return _post_model_to_type(model)

    @strawberry.field(description="Search posts by title or content")
    def search_posts(self, query: str) -> list[Post]:
        q = query.lower()
        return [
            _post_model_to_type(p)
            for p in POSTS_DB.values()
            if q in p.title.lower() or q in p.content.lower()
        ]

    @strawberry.field(description="Paginated posts — offset-based")
    def paginated_posts(
        self,
        page: int = 1,
        page_size: int = 5,
        published_only: bool = False,
    ) -> PostPage:
        all_posts = list(POSTS_DB.values())
        if published_only:
            all_posts = [p for p in all_posts if p.published]

        total = len(all_posts)
        start = (page - 1) * page_size
        end = start + page_size
        items = all_posts[start:end]

        return PostPage(
            items=[_post_model_to_type(p) for p in items],
            total=total,
            page=page,
            page_size=page_size,
            has_next=end < total,
            has_prev=page > 1,
        )

    @strawberry.field(description="Get comments for a post")
    def comments(self, post_id: strawberry.ID) -> list[Comment]:
        return [
            _comment_model_to_type(c)
            for c in COMMENTS_DB.values()
            if str(c.post_id) == str(post_id)
        ]

    # Protected field — only admins can see ALL users with emails
    @strawberry.field(
        permission_classes=[IsAuthenticated],
        description="Get all authors (authenticated only)",
    )
    def my_profile(self, info: Info) -> Optional[Author]:
        user = info.context.get("current_user")
        if not user:
            return None
        model = AUTHORS_DB.get(str(user["id"]))
        return _author_model_to_type(model) if model else None

    @strawberry.field(description="Statistics (admin only)")
    def stats(self, info: Info) -> Optional[str]:
        user = info.context.get("current_user")
        if not user or user.get("role") != "admin":
            return None
        total_posts = len(POSTS_DB)
        published = len([p for p in POSTS_DB.values() if p.published])
        total_comments = len(COMMENTS_DB)
        total_authors = len(AUTHORS_DB)
        return (
            f"Authors: {total_authors} | "
            f"Posts: {total_posts} (Published: {published}) | "
            f"Comments: {total_comments}"
        )


# ============================================================
# MUTATION TYPE
# ============================================================

@strawberry.type
class Mutation:
    """All GraphQL mutations — write operations"""

    @strawberry.mutation(description="Create a new author")
    def create_author(
        self, name: str, email: str, bio: Optional[str] = None
    ) -> Author:
        author_id = str(len(AUTHORS_DB) + 1)
        # Email uniqueness check
        if any(a.email == email for a in AUTHORS_DB.values()):
            # In real app: return union with EmailAlreadyExists
            raise ValueError(f"Email '{email}' already registered")

        model = AuthorModel(author_id, name, email, bio)
        AUTHORS_DB[author_id] = model
        print(f"  [Mutation] Author created: {name} ({email})")
        return _author_model_to_type(model)

    @strawberry.mutation(
        permission_classes=[IsAuthenticated],
        description="Create a new post (requires authentication)",
    )
    def create_post(self, input: CreatePostInput, info: Info) -> CreatePostResult:
        """
        Union return type — can return Post, ValidationError, or PermissionDenied.

        Client query:
        mutation {
            createPost(input: {title: "...", content: "...", authorId: "1"}) {
                ... on Post { id title }
                ... on ValidationError { message field }
                ... on PermissionDenied { message }
            }
        }
        """
        # Validation
        if len(input.title.strip()) < 3:
            return ValidationError(
                message="Title must be at least 3 characters long",
                field="title",
                code="TOO_SHORT",
            )
        if len(input.title) > 200:
            return ValidationError(
                message="Title cannot exceed 200 characters",
                field="title",
                code="TOO_LONG",
            )
        if len(input.content.strip()) < 10:
            return ValidationError(
                message="Content must be at least 10 characters long",
                field="content",
                code="TOO_SHORT",
            )

        # Author exists?
        if str(input.author_id) not in AUTHORS_DB:
            return ValidationError(
                message=f"Author with id '{input.author_id}' not found",
                field="authorId",
                code="NOT_FOUND",
            )

        # Auth check: user sirf apne naam se post kar sakta hai (or admin)
        user = info.context.get("current_user")
        if user and user.get("role") != "admin":
            if str(input.author_id) != str(user["id"]):
                return PermissionDenied(
                    message="You can only create posts as yourself",
                    required_role="admin_or_own_author",
                )

        # Create post
        post_id = str(len(POSTS_DB) + 1)
        model = PostModel(
            post_id,
            input.title.strip(),
            input.content.strip(),
            str(input.author_id),
            input.published,
        )
        POSTS_DB[post_id] = model
        print(f"  [Mutation] Post created: '{model.title}' by author {model.author_id}")

        post = _post_model_to_type(model)

        # Subscribers ko notify karo
        for queue in _post_subscribers:
            asyncio.create_task(queue.put(post))

        return post

    @strawberry.mutation(
        permission_classes=[IsAuthenticated],
        description="Update an existing post",
    )
    def update_post(
        self,
        id: strawberry.ID,
        input: UpdatePostInput,
        info: Info,
    ) -> UpdatePostResult:
        model = POSTS_DB.get(str(id))
        if not model:
            return PostNotFound(post_id=id)

        user = info.context.get("current_user")
        # Only author ya admin update kar sakta hai
        if user and user.get("role") != "admin":
            if str(model.author_id) != str(user["id"]):
                return PermissionDenied(
                    message="Only the post author or an admin can update this post",
                    required_role="admin_or_post_author",
                )

        # UNSET fields skip karo, None/value update karo
        if input.title is not strawberry.UNSET:
            if input.title and len(input.title.strip()) < 3:
                return ValidationError(
                    message="Title must be at least 3 characters",
                    field="title",
                    code="TOO_SHORT",
                )
            model.title = input.title.strip()

        if input.content is not strawberry.UNSET:
            model.content = input.content

        if input.published is not strawberry.UNSET:
            model.published = input.published

        POSTS_DB[str(id)] = model
        print(f"  [Mutation] Post updated: id={id}")
        return _post_model_to_type(model)

    @strawberry.mutation(
        permission_classes=[IsAdmin],
        description="Delete a post (admin only)",
    )
    def delete_post(self, id: strawberry.ID, info: Info) -> bool:
        if str(id) not in POSTS_DB:
            return False

        # Related comments bhi delete karo
        comment_ids_to_delete = [
            cid for cid, c in COMMENTS_DB.items()
            if str(c.post_id) == str(id)
        ]
        for cid in comment_ids_to_delete:
            del COMMENTS_DB[cid]

        del POSTS_DB[str(id)]
        print(f"  [Mutation] Post deleted: id={id} (admin action)")
        return True

    @strawberry.mutation(description="Add a comment to a post")
    def add_comment(
        self,
        post_id: strawberry.ID,
        text: str,
        author_id: strawberry.ID,
    ) -> Optional[Comment]:
        if str(post_id) not in POSTS_DB:
            return None
        if str(author_id) not in AUTHORS_DB:
            return None
        if len(text.strip()) < 2:
            return None

        comment_id = str(len(COMMENTS_DB) + 1)
        model = CommentModel(comment_id, text.strip(), str(post_id), str(author_id))
        COMMENTS_DB[comment_id] = model
        print(f"  [Mutation] Comment added to post {post_id}: '{text[:30]}...'")

        comment = _comment_model_to_type(model)

        # Subscribers ko notify karo
        for queue in _comment_subscribers[str(post_id)]:
            asyncio.create_task(queue.put(comment))

        return comment


# ============================================================
# SUBSCRIPTION TYPE
# ============================================================

@strawberry.type
class Subscription:
    """Real-time subscriptions via WebSocket"""

    @strawberry.subscription(
        description="Stream of newly created posts — subscribe for real-time updates"
    )
    async def post_added(self) -> AsyncGenerator[Post, None]:
        """
        New post add hone pe notify karo.

        In production: Redis pub/sub ya Apache Kafka use karo multiple
        instances ke liye. Yahan asyncio.Queue demo ke liye hai.

        Client (JavaScript):
            const client = createClient({ url: 'ws://localhost:8005/graphql' });
            client.subscribe({ query: 'subscription { postAdded { id title } }' }, {
                next: (data) => console.log('New post:', data),
            });
        """
        queue: asyncio.Queue[Post] = asyncio.Queue()
        _post_subscribers.append(queue)
        print(f"\n  [Subscription] Client subscribed to postAdded ({len(_post_subscribers)} total subscribers)")

        try:
            while True:
                post = await queue.get()
                print(f"  [Subscription] Sending post '{post.title}' to subscriber")
                yield post
        finally:
            # Client disconnect hone pe cleanup
            _post_subscribers.remove(queue)
            print(f"  [Subscription] Client unsubscribed from postAdded ({len(_post_subscribers)} remaining)")

    @strawberry.subscription(
        description="Stream comments for a specific post"
    )
    async def comment_added(
        self, post_id: strawberry.ID
    ) -> AsyncGenerator[Comment, None]:
        """
        Specific post ke naye comments watch karo.

        Example:
        subscription {
            commentAdded(postId: "1") {
                id text
                author { name }
            }
        }
        """
        queue: asyncio.Queue[Comment] = asyncio.Queue()
        _comment_subscribers[str(post_id)].append(queue)
        print(f"\n  [Subscription] Watching comments for post {post_id}")

        try:
            while True:
                comment = await queue.get()
                yield comment
        finally:
            _comment_subscribers[str(post_id)].remove(queue)

    @strawberry.subscription(
        description="Demo subscription — count from 1 to N (for testing WebSocket)"
    )
    async def live_count(self, up_to: int = 5) -> AsyncGenerator[int, None]:
        """
        Testing ke liye simple counter.

        subscription { liveCount(upTo: 10) }
        """
        for i in range(1, up_to + 1):
            yield i
            await asyncio.sleep(0.5)


# ============================================================
# CONTEXT
# ============================================================

async def get_context(request: Request = None) -> dict:
    """
    Per-request context — har request ke liye fresh context.

    Includes:
    - current_user: Mock auth (real app mein JWT verify karo)
    - author_loader: Fresh DataLoader (per-request cache)
    - comments_loader: Fresh DataLoader for comments
    """
    # Mock auth — real app mein JWT token verify karo
    user = None
    if request:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth.split(" ", 1)[1]
            # Mock tokens for testing
            if token == "admin-token":
                user = {"id": "1", "role": "admin", "name": "Ashish"}
            elif token == "user-token":
                user = {"id": "2", "role": "editor", "name": "Priya"}
            elif token.startswith("user-"):
                user_id = token.replace("user-", "")
                user = {"id": user_id, "role": "editor"}

    return {
        "current_user": user,
        # Fresh DataLoader instances — per-request cache, no stale data
        "author_loader": DataLoader(load_fn=batch_load_authors),
        "comments_loader": DataLoader(load_fn=batch_load_comments_by_post),
        "request": request,
    }


def get_test_context(user: Optional[dict] = None) -> dict:
    """Test context — no request object needed"""
    return {
        "current_user": user,
        "author_loader": DataLoader(load_fn=batch_load_authors),
        "comments_loader": DataLoader(load_fn=batch_load_comments_by_post),
        "request": None,
    }


# ============================================================
# SCHEMA ASSEMBLY
# ============================================================

schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
    extensions=[
        QueryDepthLimiter(max_depth=6),  # Max 6 levels deep nesting allow
    ],
)


# ============================================================
# FASTAPI APP
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """App startup / shutdown"""
    print("\n" + "=" * 60)
    print("  GraphQL Blog API Starting Up")
    print("=" * 60)
    seed_data()
    print(f"  Seeded: {len(AUTHORS_DB)} authors, {len(POSTS_DB)} posts, {len(COMMENTS_DB)} comments")
    print(f"  GraphQL Playground: http://localhost:8005/graphql")
    print(f"  Health check:       http://localhost:8005/")
    print("=" * 60 + "\n")
    yield
    print("\nApp shutting down...")


app = FastAPI(
    title="GraphQL Blog API",
    description="FastAPI + Strawberry GraphQL demo with DataLoader, Auth, Subscriptions",
    version="1.0.0",
    lifespan=lifespan,
)

# GraphQL router
graphql_router = GraphQLRouter(
    schema,
    context_getter=get_context,
    graphiql=True,  # Production mein False karo ya restrict karo
)

app.include_router(graphql_router, prefix="/graphql")


@app.get("/")
async def root():
    return {
        "message": "GraphQL Blog API",
        "playground": "http://localhost:8005/graphql",
        "endpoints": {
            "graphql": "/graphql (POST for queries/mutations)",
            "playground": "/graphql (GET for GraphiQL browser)",
            "websocket": "ws://localhost:8005/graphql (subscriptions)",
        },
        "sample_auth_tokens": {
            "admin": "Bearer admin-token",
            "editor": "Bearer user-token",
        },
        "sample_queries": {
            "all_posts": "{ posts(publishedOnly: true) { id title commentCount } }",
            "union_result": '{ post(id: "999") { ... on Post { title } ... on PostNotFound { message } } }',
            "search": '{ searchPosts(query: "Python") { id title } }',
            "paginated": "{ paginatedPosts(page: 1, pageSize: 3) { items { title } hasNext total } }",
        },
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "authors": len(AUTHORS_DB),
        "posts": len(POSTS_DB),
        "comments": len(COMMENTS_DB),
    }


# ============================================================
# SCHEMA TESTS — python 03_graphql_strawberry_app.py
# ============================================================

async def run_schema_tests():
    """
    GraphQL queries schema ke against directly run karo — uvicorn needed nahi.
    Test cases:
    1. Basic queries
    2. N+1 DataLoader demo
    3. Union result types
    4. Mutations
    5. Permission enforcement
    6. Filtering + pagination
    """

    print("\n" + "=" * 60)
    print("  RUNNING SCHEMA TESTS (no HTTP server needed)")
    print("=" * 60)

    # ── Test 1: Basic authors query ──
    print("\n[TEST 1] Basic authors query")
    result = await schema.execute_async(
        """
        query {
            authors {
                id
                name
                email
                postCount
            }
        }
        """,
        context_value=get_test_context(),
    )
    assert not result.errors, f"Test 1 FAILED: {result.errors}"
    authors = result.data["authors"]
    assert len(authors) == 5, f"Expected 5 authors, got {len(authors)}"
    print(f"  ✓ Got {len(authors)} authors")
    for a in authors[:2]:
        print(f"    - {a['name']} ({a['email']}) — {a['postCount']} posts")

    # ── Test 2: N+1 DataLoader demo ──
    print("\n[TEST 2] N+1 Problem → DataLoader demo")
    print("  Without DataLoader: 1 post query + 1 query per post for author = N+1")
    print("  With DataLoader: 1 post query + 1 BATCH query for all authors")
    print()

    result = await schema.execute_async(
        """
        query PostsWithAuthors {
            posts(publishedOnly: true, limit: 8) {
                id
                title
                author {
                    name
                }
                commentCount
            }
        }
        """,
        context_value=get_test_context(),
    )
    assert not result.errors, f"Test 2 FAILED: {result.errors}"
    posts = result.data["posts"]
    print(f"  ✓ Got {len(posts)} posts (with batched author loading)")
    for p in posts[:3]:
        print(f"    - '{p['title']}' by {p['author']['name']} ({p['commentCount']} comments)")

    # ── Test 3: Union result — existing post ──
    print("\n[TEST 3A] Union result — existing post")
    result = await schema.execute_async(
        """
        query {
            post(id: "1") {
                ... on Post {
                    id
                    title
                    author { name }
                }
                ... on PostNotFound {
                    message
                    postId
                }
            }
        }
        """,
        context_value=get_test_context(),
    )
    assert not result.errors, f"Test 3A FAILED: {result.errors}"
    post_result = result.data["post"]
    assert "title" in post_result, "Expected Post type"
    print(f"  ✓ Found post: '{post_result['title']}' by {post_result['author']['name']}")

    # ── Test 3B: Union result — missing post ──
    print("\n[TEST 3B] Union result — non-existent post")
    result = await schema.execute_async(
        """
        query {
            post(id: "99999") {
                ... on Post {
                    id title
                }
                ... on PostNotFound {
                    message
                    postId
                }
            }
        }
        """,
        context_value=get_test_context(),
    )
    assert not result.errors, f"Test 3B FAILED: {result.errors}"
    not_found = result.data["post"]
    assert "message" in not_found, f"Expected PostNotFound, got: {not_found}"
    print(f"  ✓ Got PostNotFound: '{not_found['message']}' for id={not_found['postId']}")

    # ── Test 4: Mutation — create post (authenticated) ──
    print("\n[TEST 4] Mutation — create post (authenticated)")
    admin_context = get_test_context(user={"id": "1", "role": "admin"})

    result = await schema.execute_async(
        """
        mutation CreatePost($input: CreatePostInput!) {
            createPost(input: $input) {
                ... on Post {
                    id
                    title
                    content
                    published
                }
                ... on ValidationError {
                    message
                    field
                    code
                }
                ... on PermissionDenied {
                    message
                }
            }
        }
        """,
        variable_values={
            "input": {
                "title": "New Test Post from Schema Tests",
                "content": "This post was created during automated schema testing.",
                "authorId": "1",
                "published": True,
            }
        },
        context_value=admin_context,
    )
    assert not result.errors, f"Test 4 FAILED: {result.errors}"
    created = result.data["createPost"]
    assert "id" in created, f"Expected Post, got: {created}"
    print(f"  ✓ Post created: id={created['id']}, title='{created['title']}'")

    # ── Test 5A: Mutation — unauthenticated ──
    print("\n[TEST 5A] Mutation — create post (unauthenticated → PermissionError)")
    unauth_context = get_test_context(user=None)

    result = await schema.execute_async(
        """
        mutation {
            createPost(input: {
                title: "Hack attempt",
                content: "Should not work without auth",
                authorId: "1"
            }) {
                ... on Post { id title }
                ... on ValidationError { message }
                ... on PermissionDenied { message }
            }
        }
        """,
        context_value=unauth_context,
    )
    # Permission classes raise errors — check errors list
    has_permission_error = (
        result.errors is not None and len(result.errors) > 0
    ) or (
        result.data and result.data.get("createPost") and
        "message" in str(result.data["createPost"])
    )
    print(f"  ✓ Unauthenticated request blocked (errors present: {result.errors is not None})")

    # ── Test 5B: Mutation — validation error ──
    print("\n[TEST 5B] Mutation — validation error (short title)")
    result = await schema.execute_async(
        """
        mutation {
            createPost(input: {
                title: "Hi",
                content: "Content here that is long enough",
                authorId: "1"
            }) {
                ... on Post { id title }
                ... on ValidationError { message field code }
                ... on PermissionDenied { message }
            }
        }
        """,
        context_value=admin_context,
    )
    assert not result.errors, f"Test 5B errors: {result.errors}"
    val_err = result.data["createPost"]
    assert "field" in val_err, f"Expected ValidationError, got: {val_err}"
    print(f"  ✓ Validation error: {val_err['message']} (field: {val_err['field']})")

    # ── Test 6: Filtering ──
    print("\n[TEST 6] Posts filtering — search + published")
    result = await schema.execute_async(
        """
        query {
            posts(publishedOnly: true, search: "Python") {
                id title published
            }
        }
        """,
        context_value=get_test_context(),
    )
    assert not result.errors, f"Test 6 FAILED: {result.errors}"
    filtered = result.data["posts"]
    print(f"  ✓ Found {len(filtered)} posts matching 'Python' (published only)")
    for p in filtered:
        print(f"    - '{p['title']}'")

    # ── Test 7: Pagination ──
    print("\n[TEST 7] Paginated posts")
    result = await schema.execute_async(
        """
        query {
            paginatedPosts(page: 1, pageSize: 3, publishedOnly: true) {
                items { id title }
                total
                page
                pageSize
                hasNext
                hasPrev
            }
        }
        """,
        context_value=get_test_context(),
    )
    assert not result.errors, f"Test 7 FAILED: {result.errors}"
    page = result.data["paginatedPosts"]
    print(f"  ✓ Page {page['page']}: {len(page['items'])} items of {page['total']} total")
    print(f"    hasNext={page['hasNext']}, hasPrev={page['hasPrev']}")

    # ── Test 8: Nested comments with DataLoader ──
    print("\n[TEST 8] Nested post with comments (DataLoader)")
    result = await schema.execute_async(
        """
        query {
            posts(publishedOnly: true, limit: 3) {
                title
                author { name }
                comments { text }
                commentCount
            }
        }
        """,
        context_value=get_test_context(),
    )
    assert not result.errors, f"Test 8 FAILED: {result.errors}"
    posts = result.data["posts"]
    print(f"  ✓ Loaded {len(posts)} posts with authors + comments (batched)")

    # ── Test 9: Add comment mutation ──
    print("\n[TEST 9] Add comment mutation")
    result = await schema.execute_async(
        """
        mutation {
            addComment(postId: "1", text: "Great schema test post!", authorId: "2") {
                id
                text
                author { name }
            }
        }
        """,
        context_value=get_test_context(),
    )
    assert not result.errors, f"Test 9 FAILED: {result.errors}"
    comment = result.data["addComment"]
    assert comment is not None
    print(f"  ✓ Comment added: '{comment['text']}' by {comment['author']['name']}")

    # ── Test 10: Stats (admin only) ──
    print("\n[TEST 10] Stats field (admin vs non-admin)")
    admin_result = await schema.execute_async(
        "query { stats }",
        context_value=get_test_context(user={"id": "1", "role": "admin"}),
    )
    non_admin_result = await schema.execute_async(
        "query { stats }",
        context_value=get_test_context(user={"id": "2", "role": "editor"}),
    )
    assert not admin_result.errors
    assert not non_admin_result.errors
    print(f"  ✓ Admin sees stats: {admin_result.data['stats']}")
    print(f"  ✓ Editor sees stats: {non_admin_result.data['stats']} (null — expected)")

    # ── Final Summary ──
    print("\n" + "=" * 60)
    print("  ✅ ALL SCHEMA TESTS PASSED!")
    print("=" * 60)
    print("\nSample queries to try at http://localhost:8005/graphql:\n")

    print("""
┌─ QUERY 1: All posts with author (DataLoader demo) ──────────┐
│  query {                                                       │
│    posts(publishedOnly: true) {                                │
│      id title                                                  │
│      author { name email }                                     │
│      commentCount                                              │
│      preview                                                   │
│    }                                                           │
│  }                                                             │
└────────────────────────────────────────────────────────────────┘

┌─ QUERY 2: Union result pattern ─────────────────────────────┐
│  query {                                                       │
│    post(id: "1") {                                             │
│      ... on Post { id title content author { name } }          │
│      ... on PostNotFound { message postId }                    │
│    }                                                           │
│  }                                                             │
└────────────────────────────────────────────────────────────────┘

┌─ MUTATION: Create post (add Auth header: Bearer admin-token) ─┐
│  mutation {                                                     │
│    createPost(input: {                                          │
│      title: "My New Post"                                       │
│      content: "Content here..."                                 │
│      authorId: "1"                                              │
│      published: true                                            │
│    }) {                                                         │
│      ... on Post { id title }                                   │
│      ... on ValidationError { message field }                   │
│      ... on PermissionDenied { message }                        │
│    }                                                            │
│  }                                                              │
└─────────────────────────────────────────────────────────────────┘

┌─ SUBSCRIPTION (WebSocket) ──────────────────────────────────┐
│  subscription { liveCount(upTo: 5) }                           │
│                                                                │
│  subscription {                                                │
│    commentAdded(postId: "1") {                                 │
│      id text author { name }                                   │
│    }                                                           │
│  }                                                             │
└────────────────────────────────────────────────────────────────┘
    """)

    print("Run the server to test interactively:")
    print("  uvicorn 03_graphql_strawberry_app:app --reload --port 8005\n")


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    """
    Two modes:
    1. uvicorn 03_graphql_strawberry_app:app --reload --port 8005
       → Full HTTP server with GraphiQL playground

    2. python 03_graphql_strawberry_app.py
       → Schema tests only, no server needed
    """
    print("\nMode: Direct Python execution → Running schema tests")
    print("(For full server: uvicorn 03_graphql_strawberry_app:app --reload --port 8005)\n")

    # Fresh seed data for tests
    seed_data()

    # Run schema tests
    asyncio.run(run_schema_tests())
