"""
MySQL Practical 04 — SQLAlchemy ORM + FastAPI Integration
==========================================================

Run app:
    uvicorn 04_sqlalchemy_fastapi:app --reload --port 8003

Run with MySQL:
    DATABASE_URL="mysql+aiomysql://myuser:mypass@localhost:3306/mydb" \
        uvicorn 04_sqlalchemy_fastapi:app --reload --port 8003

Run seed data:
    python 04_sqlalchemy_fastapi.py seed

Endpoints:
    POST   /products          — Create product
    GET    /products          — List with search/filter/pagination
    GET    /products/{id}     — Get by ID
    PUT    /products/{id}     — Update product
    DELETE /products/{id}     — Soft delete (is_active = False)
    POST   /products/bulk     — Bulk upsert (ON DUPLICATE KEY UPDATE for MySQL)
    GET    /orders/{id}       — Get order with items + product details
    POST   /orders            — Create order (stock check + transaction)
    GET    /stats/categories  — Category stats (raw SQL)
    GET    /health            — DB health check

Dependencies:
    pip install fastapi uvicorn sqlalchemy aiomysql aiosqlite pymysql pydantic
"""

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    and_,
    delete,
    func,
    or_,
    select,
    text,
    update,
)
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# ─────────────────────────────────────────────
# DATABASE URL
# MySQL production:  mysql+aiomysql://user:pass@host:3306/dbname
# SQLite fallback:   sqlite+aiosqlite:///./mysql_demo.db
# ─────────────────────────────────────────────
DB_URL = os.getenv(
    "DATABASE_URL",
    "sqlite+aiosqlite:///./mysql_demo.db",  # Fallback for testing without MySQL
)

IS_MYSQL = DB_URL.startswith("mysql")

# Engine configuration
engine_kwargs = dict(
    pool_pre_ping=True,
    echo=False,
)

if IS_MYSQL:
    # MySQL-specific pool settings
    engine_kwargs.update(
        pool_size=20,
        max_overflow=40,
        pool_recycle=1800,  # 30 min — MySQL ke 8hr wait_timeout se pehle recycle
    )

async_engine = create_async_engine(DB_URL, **engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Commit ke baad bhi objects access ho sakein
)


# ─────────────────────────────────────────────
# MODELS
# ─────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    tags: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    order_items: Mapped[list["OrderItem"]] = relationship(back_populates="product")

    __table_args__ = (
        Index("idx_category_active", "category", "is_active"),
        Index("idx_price", "price"),
        # MySQL-specific table options (ignored by SQLite)
        {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"}
        if IS_MYSQL
        else {},
    )

    def __repr__(self) -> str:
        return f"<Product(id={self.id}, sku={self.sku!r}, price={self.price})>"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    hashed_pwd: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    orders: Mapped[list["Order"]] = relationship(back_populates="user")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username!r})>"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    total_amount: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now()
    )

    user: Mapped[Optional["User"]] = relationship(back_populates="orders")
    order_items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_order_user_status", "user_id", "status"),
        Index("idx_order_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Order(id={self.id}, status={self.status!r}, total={self.total_amount})>"


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id: Mapped[int] = mapped_column(
        ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    order: Mapped["Order"] = relationship(back_populates="order_items")
    product: Mapped["Product"] = relationship(back_populates="order_items")

    def __repr__(self) -> str:
        return (
            f"<OrderItem(order_id={self.order_id}, "
            f"product_id={self.product_id}, qty={self.quantity})>"
        )


# ─────────────────────────────────────────────
# PYDANTIC SCHEMAS
# ─────────────────────────────────────────────
class ProductCreate(BaseModel):
    sku: str = Field(..., min_length=3, max_length=50, description="Unique product code")
    name: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = None
    price: float = Field(..., gt=0, description="Price must be > 0")
    stock: int = Field(default=0, ge=0)
    category: str = Field(..., min_length=2, max_length=50)
    tags: Optional[dict] = None


class ProductUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = None
    price: Optional[float] = Field(None, gt=0)
    stock: Optional[int] = Field(None, ge=0)
    category: Optional[str] = None
    tags: Optional[dict] = None
    is_active: Optional[bool] = None


class ProductResponse(BaseModel):
    id: int
    sku: str
    name: str
    description: Optional[str]
    price: float
    stock: int
    category: str
    is_active: bool
    tags: Optional[dict]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}  # SQLAlchemy ORM → Pydantic (v2)


class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    page: int
    page_size: int
    pages: int


class BulkProductItem(BaseModel):
    sku: str = Field(..., min_length=3, max_length=50)
    name: str = Field(..., min_length=2, max_length=200)
    price: float = Field(..., gt=0)
    stock: int = Field(default=0, ge=0)
    category: str
    description: Optional[str] = None
    tags: Optional[dict] = None


class BulkCreateRequest(BaseModel):
    items: list[BulkProductItem] = Field(..., min_length=1, max_length=500)


class BulkCreateResponse(BaseModel):
    affected_rows: int
    message: str


class OrderItemCreate(BaseModel):
    product_id: int = Field(..., gt=0)
    quantity: int = Field(..., gt=0)


class OrderCreate(BaseModel):
    user_id: Optional[int] = None
    items: list[OrderItemCreate] = Field(..., min_length=1)


class OrderItemResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    unit_price: float
    product: Optional[ProductResponse] = None

    model_config = {"from_attributes": True}


class UserInOrder(BaseModel):
    id: int
    username: str
    email: str

    model_config = {"from_attributes": True}


class OrderResponse(BaseModel):
    id: int
    user_id: Optional[int]
    total_amount: float
    status: str
    created_at: Optional[datetime]
    order_items: list[OrderItemResponse] = []
    user: Optional[UserInOrder] = None

    model_config = {"from_attributes": True}


class CategoryStat(BaseModel):
    category: str
    product_count: int
    avg_price: float
    inventory_value: float


class HealthResponse(BaseModel):
    status: str
    db_url_type: str
    db_reachable: bool
    message: str


# ─────────────────────────────────────────────
# REPOSITORY — PRODUCT
# ─────────────────────────────────────────────
class ProductRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, product_id: int) -> Optional[Product]:
        result = await self.session.execute(
            select(Product).where(
                Product.id == product_id,
                Product.is_active == True,  # noqa: E712
            )
        )
        return result.scalar_one_or_none()

    async def get_by_id_any_status(self, product_id: int) -> Optional[Product]:
        """Soft-deleted products bhi milenge (admin use)."""
        result = await self.session.execute(
            select(Product).where(Product.id == product_id)
        )
        return result.scalar_one_or_none()

    async def get_by_sku(self, sku: str) -> Optional[Product]:
        result = await self.session.execute(
            select(Product).where(Product.sku == sku)
        )
        return result.scalar_one_or_none()

    async def search(
        self,
        q: Optional[str] = None,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> tuple[list[Product], int]:
        base_filter = Product.is_active == True  # noqa: E712

        query = select(Product).where(base_filter)
        count_query = (
            select(func.count()).select_from(Product).where(base_filter)
        )

        filters = []
        if q:
            filters.append(
                or_(
                    Product.name.ilike(f"%{q}%"),
                    Product.description.ilike(f"%{q}%"),
                )
            )
        if category:
            filters.append(Product.category == category)
        if min_price is not None:
            filters.append(Product.price >= min_price)
        if max_price is not None:
            filters.append(Product.price <= max_price)

        if filters:
            combined = and_(*filters)
            query = query.where(combined)
            count_query = count_query.where(combined)

        # Sort
        valid_sort_cols = {"id", "name", "price", "stock", "created_at", "updated_at"}
        sort_field = sort_by if sort_by in valid_sort_cols else "created_at"
        sort_col = getattr(Product, sort_field)
        query = query.order_by(
            sort_col.desc() if sort_order == "desc" else sort_col.asc()
        )

        # Paginate
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        # Parallel execution — dono queries ek saath chalaao
        result, count_result = await asyncio.gather(
            self.session.execute(query),
            self.session.execute(count_query),
        )

        return list(result.scalars().all()), count_result.scalar() or 0

    async def create(self, data: dict) -> Product:
        product = Product(**data)
        self.session.add(product)
        await self.session.flush()        # ID generate karo (bina commit ke)
        await self.session.refresh(product)  # DB se latest values load karo
        return product

    async def update(self, product_id: int, data: dict) -> Optional[Product]:
        # Filter out None values — sirf provided fields update karo
        update_data = {k: v for k, v in data.items() if v is not None}
        if not update_data:
            return await self.get_by_id(product_id)

        await self.session.execute(
            update(Product)
            .where(Product.id == product_id)
            .values(**update_data)
        )
        await self.session.flush()
        return await self.get_by_id_any_status(product_id)

    async def soft_delete(self, product_id: int) -> bool:
        result = await self.session.execute(
            update(Product)
            .where(Product.id == product_id, Product.is_active == True)  # noqa: E712
            .values(is_active=False)
        )
        return result.rowcount > 0

    async def bulk_upsert(self, items: list[dict]) -> int:
        """
        MySQL: INSERT ... ON DUPLICATE KEY UPDATE
        SQLite fallback: manual upsert (one by one)
        """
        if IS_MYSQL:
            from sqlalchemy.dialects.mysql import insert as mysql_insert

            stmt = mysql_insert(Product).values(items)
            stmt = stmt.on_duplicate_key_update(
                name=stmt.inserted.name,
                price=stmt.inserted.price,
                stock=stmt.inserted.stock,
                category=stmt.inserted.category,
                description=stmt.inserted.description,
                tags=stmt.inserted.tags,
                updated_at=func.now(),
            )
            result = await self.session.execute(stmt)
            await self.session.flush()
            return result.rowcount
        else:
            # SQLite fallback: INSERT OR REPLACE
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert

            stmt = sqlite_insert(Product).values(items)
            stmt = stmt.on_conflict_do_update(
                index_elements=["sku"],
                set_={
                    "name": stmt.excluded.name,
                    "price": stmt.excluded.price,
                    "stock": stmt.excluded.stock,
                    "category": stmt.excluded.category,
                    "description": stmt.excluded.description,
                    "tags": stmt.excluded.tags,
                },
            )
            result = await self.session.execute(stmt)
            await self.session.flush()
            return result.rowcount


# ─────────────────────────────────────────────
# REPOSITORY — ORDER
# ─────────────────────────────────────────────
class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_with_items(self, order_id: int) -> Optional[Order]:
        from sqlalchemy.orm import joinedload, selectinload

        result = await self.session.execute(
            select(Order)
            .options(
                # to-many: selectinload (2 queries, no row duplication)
                selectinload(Order.order_items).selectinload(OrderItem.product),
                # to-one: joinedload (single JOIN)
                joinedload(Order.user),
            )
            .where(Order.id == order_id)
        )
        return result.unique().scalar_one_or_none()

    async def get_user_orders(self, user_id: int) -> list[Order]:
        from sqlalchemy.orm import selectinload

        result = await self.session.execute(
            select(Order)
            .where(Order.user_id == user_id)
            .options(selectinload(Order.order_items))
            .order_by(Order.created_at.desc())
        )
        return list(result.scalars().all())

    async def create_order(
        self,
        user_id: Optional[int],
        items_data: list[dict],  # [{"product": Product, "quantity": int}]
    ) -> Order:
        """
        Transaction mein:
        1. Order row insert karo
        2. Har item ke liye OrderItem insert karo
        3. Product stock decrement karo
        4. Total amount calculate karo
        """
        total = sum(
            item["product"].price * item["quantity"] for item in items_data
        )

        order = Order(user_id=user_id, total_amount=total, status="pending")
        self.session.add(order)
        await self.session.flush()  # order.id generate ho jaaye

        for item in items_data:
            product: Product = item["product"]
            qty: int = item["quantity"]

            order_item = OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=qty,
                unit_price=float(product.price),
            )
            self.session.add(order_item)

            # Stock decrement
            await self.session.execute(
                update(Product)
                .where(Product.id == product.id)
                .values(stock=Product.stock - qty)
            )

        await self.session.flush()
        await self.session.refresh(order)
        return order


# ─────────────────────────────────────────────
# DEPENDENCY — DB SESSION
# ─────────────────────────────────────────────
async def get_session():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


# ─────────────────────────────────────────────
# LIFESPAN
# ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP ──
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    db_type = "MySQL" if IS_MYSQL else "SQLite (fallback)"
    print(f"[DB] Tables ready on {db_type}")
    print(f"[DB] URL: {DB_URL[:50]}...")

    yield

    # ── SHUTDOWN ──
    await async_engine.dispose()
    print("[DB] Connection pool closed")


# ─────────────────────────────────────────────
# FASTAPI APP
# ─────────────────────────────────────────────
app = FastAPI(
    title="SQLAlchemy + MySQL + FastAPI Demo",
    description="MySQL Practical 04 — Complete ORM integration with repository pattern",
    version="1.0.0",
    lifespan=lifespan,
)


# ─────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse, tags=["Utility"])
async def health_check(session: AsyncSession = Depends(get_session)):
    """Database connection health check."""
    try:
        await session.execute(text("SELECT 1"))
        return HealthResponse(
            status="ok",
            db_url_type="MySQL" if IS_MYSQL else "SQLite",
            db_reachable=True,
            message="Database connection successful",
        )
    except Exception as exc:
        return HealthResponse(
            status="error",
            db_url_type="MySQL" if IS_MYSQL else "SQLite",
            db_reachable=False,
            message=str(exc),
        )


# ─────────────────────────────────────────────
# PRODUCT ENDPOINTS
# ─────────────────────────────────────────────
@app.post(
    "/products",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Products"],
)
async def create_product(
    data: ProductCreate,
    session: AsyncSession = Depends(get_session),
):
    """Naya product create karo. SKU unique hona chahiye."""
    repo = ProductRepository(session)
    existing = await repo.get_by_sku(data.sku)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Product with SKU '{data.sku}' already exists",
        )
    product = await repo.create(data.model_dump())
    await session.commit()
    return product


@app.get("/products", response_model=ProductListResponse, tags=["Products"])
async def list_products(
    q: Optional[str] = Query(None, description="Search in name or description"),
    category: Optional[str] = Query(None, description="Filter by category"),
    min_price: Optional[float] = Query(None, ge=0, description="Minimum price"),
    max_price: Optional[float] = Query(None, ge=0, description="Maximum price"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    sort_by: str = Query("created_at", description="Sort field"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="asc or desc"),
    session: AsyncSession = Depends(get_session),
):
    """Products ki paginated list with search, filter, aur sort."""
    repo = ProductRepository(session)
    products, total = await repo.search(
        q=q,
        category=category,
        min_price=min_price,
        max_price=max_price,
        page=page,
        page_size=page_size,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return ProductListResponse(
        items=products,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size if total > 0 else 0,
    )


@app.get("/products/{product_id}", response_model=ProductResponse, tags=["Products"])
async def get_product(
    product_id: int,
    session: AsyncSession = Depends(get_session),
):
    """ID se product fetch karo."""
    product = await ProductRepository(session).get_by_id(product_id)
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id={product_id} not found",
        )
    return product


@app.put("/products/{product_id}", response_model=ProductResponse, tags=["Products"])
async def update_product(
    product_id: int,
    data: ProductUpdate,
    session: AsyncSession = Depends(get_session),
):
    """Product ke fields update karo (partial update supported)."""
    repo = ProductRepository(session)
    existing = await repo.get_by_id_any_status(product_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id={product_id} not found",
        )
    updated = await repo.update(product_id, data.model_dump(exclude_unset=True))
    await session.commit()
    return updated


@app.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Products"],
)
async def delete_product(
    product_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Product ko soft delete karo (is_active = False). Data preserve hota hai."""
    repo = ProductRepository(session)
    deleted = await repo.soft_delete(product_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Product with id={product_id} not found or already deleted",
        )
    await session.commit()


@app.post(
    "/products/bulk",
    response_model=BulkCreateResponse,
    tags=["Products"],
)
async def bulk_create_products(
    request: BulkCreateRequest,
    session: AsyncSession = Depends(get_session),
):
    """
    Bulk product upsert.
    MySQL: INSERT ... ON DUPLICATE KEY UPDATE (SKU ke basis pe)
    SQLite: INSERT OR REPLACE
    """
    repo = ProductRepository(session)
    items_data = [item.model_dump() for item in request.items]
    affected = await repo.bulk_upsert(items_data)
    await session.commit()
    return BulkCreateResponse(
        affected_rows=affected,
        message=f"Bulk upsert complete. Affected rows: {affected}",
    )


# ─────────────────────────────────────────────
# ORDER ENDPOINTS
# ─────────────────────────────────────────────
@app.post(
    "/orders",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Orders"],
)
async def create_order(
    data: OrderCreate,
    session: AsyncSession = Depends(get_session),
):
    """
    Order create karo.
    - Stock check karta hai har product ke liye
    - Sab kuch ek transaction mein hota hai
    - Stock decrement hota hai
    """
    product_repo = ProductRepository(session)
    order_repo = OrderRepository(session)

    # ── Validate products & stock ──
    items_to_create = []
    for item in data.items:
        product = await product_repo.get_by_id(item.product_id)
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Product id={item.product_id} not found or inactive",
            )
        if product.stock < item.quantity:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Insufficient stock for '{product.name}'. "
                    f"Available: {product.stock}, Requested: {item.quantity}"
                ),
            )
        items_to_create.append({"product": product, "quantity": item.quantity})

    # ── Create order in single transaction ──
    order = await order_repo.create_order(
        user_id=data.user_id,
        items_data=items_to_create,
    )
    await session.commit()

    # Reload with relationships
    order_with_items = await order_repo.get_with_items(order.id)
    return order_with_items


@app.get("/orders/{order_id}", response_model=OrderResponse, tags=["Orders"])
async def get_order(
    order_id: int,
    session: AsyncSession = Depends(get_session),
):
    """Order ke saath uske items aur product details fetch karo."""
    order = await OrderRepository(session).get_with_items(order_id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order id={order_id} not found",
        )
    return order


# ─────────────────────────────────────────────
# STATS ENDPOINT (Raw SQL)
# ─────────────────────────────────────────────
@app.get("/stats/categories", response_model=list[CategoryStat], tags=["Stats"])
async def category_stats(session: AsyncSession = Depends(get_session)):
    """
    Category-wise product stats.
    Raw SQL use karta hai (GROUP BY, AVG, SUM).
    """
    result = await session.execute(
        text("""
            SELECT
                category,
                COUNT(*) AS product_count,
                COALESCE(AVG(price), 0) AS avg_price,
                COALESCE(SUM(stock * price), 0) AS inventory_value
            FROM products
            WHERE is_active = 1
            GROUP BY category
            ORDER BY inventory_value DESC
        """)
    )
    rows = result.mappings().all()
    return [
        CategoryStat(
            category=row["category"],
            product_count=row["product_count"],
            avg_price=round(float(row["avg_price"]), 2),
            inventory_value=round(float(row["inventory_value"]), 2),
        )
        for row in rows
    ]


# ─────────────────────────────────────────────
# SEED DATA
# ─────────────────────────────────────────────
async def seed_data() -> None:
    """Sample data insert karo (dev/testing ke liye)."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        # Check: already seeded?
        result = await session.execute(select(func.count()).select_from(Product))
        count = result.scalar()
        if count and count > 0:
            print(f"[Seed] Already {count} products exist. Skipping.")
            return

        print("[Seed] Inserting sample data...")

        # ── Users ──
        users = [
            User(username="alice", email="alice@example.com", hashed_pwd="hashed_pw_1"),
            User(username="bob", email="bob@example.com", hashed_pwd="hashed_pw_2"),
            User(username="charlie", email="charlie@example.com", hashed_pwd="hashed_pw_3"),
        ]
        session.add_all(users)
        await session.flush()

        # ── Products ──
        products = [
            Product(
                sku="ELEC-001", name="Wireless Headphones",
                description="Noise-cancelling over-ear headphones",
                price=2999.00, stock=50, category="electronics",
                tags={"brand": "Sony", "color": "black", "bestseller": True},
            ),
            Product(
                sku="ELEC-002", name="Mechanical Keyboard",
                description="RGB backlit mechanical gaming keyboard",
                price=4500.00, stock=30, category="electronics",
                tags={"brand": "Keychron", "switch": "brown"},
            ),
            Product(
                sku="ELEC-003", name="USB-C Hub 7-in-1",
                description="Multiport hub with HDMI, USB-A, SD card",
                price=1299.00, stock=100, category="electronics",
                tags={"ports": 7, "brand": "Anker"},
            ),
            Product(
                sku="BOOK-001", name="Clean Code",
                description="A handbook of agile software craftsmanship",
                price=599.00, stock=75, category="books",
                tags={"author": "Robert C. Martin", "language": "English"},
            ),
            Product(
                sku="BOOK-002", name="Designing Data-Intensive Applications",
                description="The big ideas behind reliable, scalable, and maintainable systems",
                price=899.00, stock=40, category="books",
                tags={"author": "Martin Kleppmann", "year": 2017},
            ),
            Product(
                sku="CLTH-001", name="Cotton T-Shirt",
                description="100% organic cotton round-neck t-shirt",
                price=499.00, stock=200, category="clothing",
                tags={"material": "cotton", "sizes": ["S", "M", "L", "XL"]},
            ),
            Product(
                sku="SPRT-001", name="Yoga Mat",
                description="Non-slip 6mm thick yoga mat with carry strap",
                price=799.00, stock=60, category="sports",
                tags={"thickness": "6mm", "color": "purple"},
            ),
            Product(
                sku="SPRT-002", name="Resistance Bands Set",
                description="Set of 5 resistance bands for home workout",
                price=349.00, stock=120, category="sports",
                tags={"pieces": 5, "levels": ["light", "medium", "heavy"]},
            ),
        ]
        session.add_all(products)
        await session.flush()

        # ── Orders ──
        order1 = Order(user_id=users[0].id, total_amount=4298.00, status="completed")
        session.add(order1)
        await session.flush()

        session.add_all([
            OrderItem(
                order_id=order1.id, product_id=products[0].id,
                quantity=1, unit_price=float(products[0].price),
            ),
            OrderItem(
                order_id=order1.id, product_id=products[3].id,
                quantity=2, unit_price=float(products[3].price),
            ),
        ])

        order2 = Order(user_id=users[1].id, total_amount=1648.00, status="pending")
        session.add(order2)
        await session.flush()

        session.add_all([
            OrderItem(
                order_id=order2.id, product_id=products[5].id,
                quantity=2, unit_price=float(products[5].price),
            ),
            OrderItem(
                order_id=order2.id, product_id=products[6].id,
                quantity=1, unit_price=float(products[6].price),
            ),
        ])

        await session.commit()
        print(f"[Seed] Inserted: {len(users)} users, {len(products)} products, 2 orders")


# ─────────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    if len(sys.argv) > 1 and sys.argv[1] == "seed":
        print("[Seed] Running seed_data()...")
        asyncio.run(seed_data())
        print("[Seed] Done.")
    else:
        print(f"[App] Starting FastAPI on http://127.0.0.1:8003")
        print(f"[App] Docs: http://127.0.0.1:8003/docs")
        print(f"[App] DB:   {'MySQL' if IS_MYSQL else 'SQLite (fallback)'}")
        print()
        print("Usage:")
        print("  python 04_sqlalchemy_fastapi.py              # start server")
        print("  python 04_sqlalchemy_fastapi.py seed         # seed sample data")
        print("  uvicorn 04_sqlalchemy_fastapi:app --reload   # dev mode")
        print()

        # Auto-seed on first run
        asyncio.run(seed_data())

        uvicorn.run(
            "04_sqlalchemy_fastapi:app",
            host="127.0.0.1",
            port=8003,
            reload=False,  # reload=True for dev: uvicorn command se run karo
            log_level="info",
        )
