"""
PHASE 2 FastAPI — Practical 14: Clean Architecture + Domain-Driven Design
Run: uvicorn 14_clean_architecture_app:app --reload --port 8002
Docs: http://127.0.0.1:8002/docs

Install: pip install fastapi uvicorn sqlalchemy aiosqlite

NOTE: Real project mein yeh sab alag files mein split karo:
  app/domain/models/product.py
  app/domain/schemas/product.py
  app/core/exceptions.py
  app/repositories/base.py
  ...etc.
  Yahan sab ek file mein hai — sikhne ke liye (demo purpose)

Endpoints:
  POST   /api/v1/products              → Create product
  GET    /api/v1/products              → List (pagination)
  GET    /api/v1/products/{id}         → Get by ID
  PUT    /api/v1/products/{id}         → Full update
  DELETE /api/v1/products/{id}         → Delete
  PATCH  /api/v1/products/{id}/stock   → Stock adjust (delta)
  POST   /api/v1/orders                → Place order (UoW demo)
  GET    /api/v1/orders/{id}           → Get order
  GET    /health                       → Health check
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Generic, List, Optional, Type, TypeVar

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    delete,
    func,
    select,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# ═══════════════════════════════════════════════════════════════════════════════
# ═══ DATABASE SETUP ═══
# Real project mein: app/core/database.py
# ═══════════════════════════════════════════════════════════════════════════════

DATABASE_URL = "sqlite+aiosqlite:///./clean_arch_demo.db"

engine = create_async_engine(
    DATABASE_URL,
    echo=False,   # True karo queries dekhne ke liye
    connect_args={"check_same_thread": False},
)

AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,   # Commit ke baad attributes expire mat karo
)


async def get_session() -> AsyncSession:
    """
    Dependency: DB session inject karo.
    Real project mein: app/core/database.py
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# ═══════════════════════════════════════════════════════════════════════════════
# ═══ DOMAIN MODELS (SQLAlchemy) ═══
# Real project mein: app/domain/models/product.py, order.py
# ═══════════════════════════════════════════════════════════════════════════════

class Base(DeclarativeBase):
    pass


class Product(Base):
    """
    Product domain entity.
    SQLAlchemy model — DB table ka representation.
    """
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    sku: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    stock: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationship — real project mein yeh hoga
    orders: Mapped[List["Order"]] = relationship("Order", back_populates="product")

    def __repr__(self) -> str:
        return f"<Product id={self.id} sku={self.sku} name={self.name!r}>"


class Order(Base):
    """
    Order domain entity.
    Product purchase record — UoW demo ke liye.
    """
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    product_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("products.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    total_price: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="confirmed")
    customer_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )

    product: Mapped["Product"] = relationship("Product", back_populates="orders")

    def __repr__(self) -> str:
        return f"<Order id={self.id} product_id={self.product_id} qty={self.quantity}>"


# ═══════════════════════════════════════════════════════════════════════════════
# ═══ PYDANTIC SCHEMAS ═══
# Real project mein: app/domain/schemas/product.py, order.py
# ═══════════════════════════════════════════════════════════════════════════════

# ─── Product Schemas ───

class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, example="Laptop Pro X1")
    sku: str = Field(..., min_length=1, max_length=50, example="LAPTOP-PRO-X1")
    description: Optional[str] = Field(None, max_length=1000)
    price: float = Field(..., gt=0, example=49999.99)
    stock: int = Field(0, ge=0, example=100)
    category: Optional[str] = Field(None, max_length=100, example="Electronics")

    @field_validator("sku")
    @classmethod
    def sku_uppercase(cls, v: str) -> str:
        """SKU always uppercase"""
        return v.upper().strip()

    @field_validator("name")
    @classmethod
    def name_strip(cls, v: str) -> str:
        return v.strip()


class ProductUpdate(BaseModel):
    """Partial update — sab fields optional"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    price: Optional[float] = Field(None, gt=0)
    category: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


class StockUpdateRequest(BaseModel):
    quantity_delta: int = Field(
        ...,
        example=10,
        description="Positive = add stock, Negative = reduce stock",
    )


class ProductResponse(BaseModel):
    id: int
    name: str
    sku: str
    description: Optional[str]
    price: float
    stock: int
    category: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}  # ORM mode


class ProductListResponse(BaseModel):
    items: List[ProductResponse]
    total: int
    skip: int
    limit: int


# ─── Order Schemas ───

class OrderCreate(BaseModel):
    product_id: int = Field(..., gt=0, example=1)
    quantity: int = Field(..., gt=0, example=2)
    customer_name: Optional[str] = Field(None, max_length=200, example="Rahul Kumar")


class OrderResponse(BaseModel):
    id: int
    product_id: int
    quantity: int
    total_price: float
    status: str
    customer_name: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


# ─── Generic Responses ───

class MessageResponse(BaseModel):
    message: str
    detail: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    timestamp: datetime
    db: str


# ═══════════════════════════════════════════════════════════════════════════════
# ═══ DOMAIN EXCEPTIONS ═══
# Real project mein: app/core/exceptions.py
# HTTP ka koi knowledge nahi yahan — transport-agnostic!
# ═══════════════════════════════════════════════════════════════════════════════

class DomainException(Exception):
    """Base class for all domain exceptions"""
    pass


class ProductNotFound(DomainException):
    """Product DB mein nahi mila"""
    pass


class DuplicateSKU(DomainException):
    """Same SKU already exists in system"""
    pass


class InsufficientStock(DomainException):
    """Order quantity > available stock"""
    pass


class OrderNotFound(DomainException):
    """Order DB mein nahi mila"""
    pass


class InvalidOperation(DomainException):
    """Invalid business operation"""
    pass


# ═══════════════════════════════════════════════════════════════════════════════
# ═══ BASE REPOSITORY ═══
# Real project mein: app/repositories/base.py
# Generic CRUD — har model ke liye reusable
# ═══════════════════════════════════════════════════════════════════════════════

ModelType = TypeVar("ModelType")


class BaseRepository(Generic[ModelType]):
    """
    Generic repository — CRUD operations for any SQLAlchemy model.

    Usage:
        class ProductRepository(BaseRepository[Product]):
            def __init__(self, session): super().__init__(Product, session)
    """

    def __init__(self, model: Type[ModelType], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    async def get(self, id: int) -> Optional[ModelType]:
        """ID se single record fetch karo"""
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        """Paginated list"""
        result = await self.session.execute(
            select(self.model).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def count(self) -> int:
        """Total records count"""
        result = await self.session.execute(
            select(func.count()).select_from(self.model)
        )
        return result.scalar() or 0

    async def create(self, data: dict) -> ModelType:
        """New record create karo aur refresh karke return karo"""
        instance = self.model(**data)
        self.session.add(instance)
        await self.session.flush()        # ID generate karo (commit nahi abhi)
        await self.session.refresh(instance)
        return instance

    async def update(self, id: int, data: dict) -> Optional[ModelType]:
        """Partial update — sirf provided fields change karo"""
        if not data:
            return await self.get(id)
        await self.session.execute(
            update(self.model).where(self.model.id == id).values(**data)
        )
        await self.session.flush()
        return await self.get(id)

    async def delete(self, id: int) -> bool:
        """Delete karo — True if deleted, False if not found"""
        result = await self.session.execute(
            delete(self.model).where(self.model.id == id)
        )
        await self.session.flush()
        return result.rowcount > 0

    async def exists(self, id: int) -> bool:
        """Record exist karta hai?"""
        result = await self.session.execute(
            select(func.count()).select_from(self.model).where(self.model.id == id)
        )
        return (result.scalar() or 0) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# ═══ PRODUCT REPOSITORY ═══
# Real project mein: app/repositories/product.py
# Product-specific DB queries
# ═══════════════════════════════════════════════════════════════════════════════

class ProductRepository(BaseRepository[Product]):
    """
    Product-specific repository.
    BaseRepository se CRUD milta hai.
    Yahan sirf product-specific queries.
    """

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Product, session)

    async def get_by_sku(self, sku: str) -> Optional[Product]:
        """SKU uniqueness check ke liye"""
        result = await self.session.execute(
            select(Product).where(Product.sku == sku)
        )
        return result.scalar_one_or_none()

    async def get_active(self, skip: int = 0, limit: int = 100) -> List[Product]:
        """Sirf active products"""
        result = await self.session.execute(
            select(Product)
            .where(Product.is_active == True)
            .order_by(Product.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_active(self) -> int:
        """Active products ka count"""
        result = await self.session.execute(
            select(func.count()).select_from(Product).where(Product.is_active == True)
        )
        return result.scalar() or 0

    async def get_by_category(
        self, category: str, skip: int = 0, limit: int = 20
    ) -> List[Product]:
        result = await self.session.execute(
            select(Product)
            .where(Product.category == category, Product.is_active == True)
            .order_by(Product.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def search(self, query: str) -> List[Product]:
        """Name/description mein search"""
        result = await self.session.execute(
            select(Product).where(
                Product.name.ilike(f"%{query}%")
                | Product.description.ilike(f"%{query}%")
            )
        )
        return list(result.scalars().all())


# ═══════════════════════════════════════════════════════════════════════════════
# ═══ ORDER REPOSITORY ═══
# Real project mein: app/repositories/order.py
# ═══════════════════════════════════════════════════════════════════════════════

class OrderRepository(BaseRepository[Order]):
    """Order-specific DB queries"""

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Order, session)

    async def get_by_product(self, product_id: int) -> List[Order]:
        """Kisi product ke saare orders"""
        result = await self.session.execute(
            select(Order)
            .where(Order.product_id == product_id)
            .order_by(Order.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_with_product(self, order_id: int) -> Optional[Order]:
        """Order + product details (joined)"""
        from sqlalchemy.orm import selectinload

        result = await self.session.execute(
            select(Order)
            .options(selectinload(Order.product))
            .where(Order.id == order_id)
        )
        return result.scalar_one_or_none()


# ═══════════════════════════════════════════════════════════════════════════════
# ═══ UNIT OF WORK ═══
# Real project mein: app/repositories/unit_of_work.py
# Multiple repos ko ek atomic transaction mein wrap karta hai
# ═══════════════════════════════════════════════════════════════════════════════

class UnitOfWork:
    """
    Unit of Work Pattern — Multiple DB operations ek atomic transaction mein.

    Use case: Order place karo:
      1. Product stock check
      2. Order record create
      3. Stock deduct
    → Teeno succeed ya teeno fail (no partial state!)

    Usage:
        async with UnitOfWork(session) as uow:
            order = await uow.orders.create({...})
            await uow.session.execute(update(Product)...)
            # exception → rollback, success → commit
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        # Repositories initialize karo — same session share karte hain!
        self.products = ProductRepository(session)
        self.orders = OrderRepository(session)

    async def __aenter__(self) -> "UnitOfWork":
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[Exception],
        exc_tb: Any,
    ) -> None:
        if exc_type is not None:
            # Exception aaya → rollback — kuch bhi save nahi hua
            await self.session.rollback()
        else:
            # Sab theek → commit — teeno operations atomically save
            await self.session.commit()

    async def commit(self) -> None:
        """Manual commit — zaroorat pe use karo"""
        await self.session.commit()

    async def rollback(self) -> None:
        """Manual rollback"""
        await self.session.rollback()


# ═══════════════════════════════════════════════════════════════════════════════
# ═══ PRODUCT SERVICE ═══
# Real project mein: app/services/product.py
# Business rules yahan — HTTP ka koi kaam nahi yahan
# ═══════════════════════════════════════════════════════════════════════════════

class ProductService:
    """
    Product business logic.

    RULE: Agar koi business validation hai → yahan
          Agar koi DB query hai             → repository mein
          Agar koi HTTP status code hai     → API layer mein

    Testing ke liye: mock ProductRepository inject karo — no DB needed!
    """

    def __init__(self, repository: ProductRepository) -> None:
        self.repo = repository

    async def create_product(self, data: ProductCreate) -> Product:
        """
        Business rules:
        - SKU unique hona chahiye
        - Price positive (Pydantic already validates, but double-check)
        """
        # Business rule: SKU unique check
        existing = await self.repo.get_by_sku(data.sku)
        if existing:
            raise DuplicateSKU(f"SKU '{data.sku}' already exists")

        # Create karo
        product_dict = data.model_dump()
        # updated_at manually set karo SQLite ke liye (onupdate SQLite mein nahi)
        product_dict["created_at"] = datetime.utcnow()
        product_dict["updated_at"] = datetime.utcnow()
        return await self.repo.create(product_dict)

    async def get_product(self, product_id: int) -> Product:
        """Single product — not found pe domain exception"""
        product = await self.repo.get(product_id)
        if not product:
            raise ProductNotFound(f"Product with id={product_id} not found")
        return product

    async def list_products(
        self, skip: int = 0, limit: int = 20
    ) -> tuple[List[Product], int]:
        """Paginated list — (items, total) tuple return karo"""
        items = await self.repo.get_active(skip=skip, limit=limit)
        total = await self.repo.count_active()
        return items, total

    async def update_product(
        self, product_id: int, data: ProductUpdate
    ) -> Product:
        """Partial update — sirf provided fields"""
        # Existence check
        await self.get_product(product_id)

        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            raise InvalidOperation("No fields to update — sab fields None hain")

        update_data["updated_at"] = datetime.utcnow()
        product = await self.repo.update(product_id, update_data)
        if not product:
            raise ProductNotFound(f"Product with id={product_id} not found")
        return product

    async def delete_product(self, product_id: int) -> None:
        """Delete — existence check pehle"""
        await self.get_product(product_id)
        deleted = await self.repo.delete(product_id)
        if not deleted:
            raise ProductNotFound(f"Product with id={product_id} delete failed")

    async def update_stock(
        self, product_id: int, quantity_delta: int
    ) -> Product:
        """
        Stock adjust karo.
        quantity_delta: positive = add, negative = reduce
        Business rule: stock 0 se neeche nahi ja sakta.
        """
        product = await self.repo.get(product_id)
        if not product:
            raise ProductNotFound(f"Product with id={product_id} not found")

        new_stock = product.stock + quantity_delta
        if new_stock < 0:
            raise InsufficientStock(
                f"Insufficient stock. Available: {product.stock}, "
                f"Requested change: {quantity_delta}. "
                f"Result would be: {new_stock}"
            )

        updated = await self.repo.update(
            product_id,
            {"stock": new_stock, "updated_at": datetime.utcnow()},
        )
        if not updated:
            raise ProductNotFound(f"Product with id={product_id} not found")
        return updated


# ═══════════════════════════════════════════════════════════════════════════════
# ═══ ORDER SERVICE ═══
# Real project mein: app/services/order.py
# UoW use karta hai — atomic order placement
# ═══════════════════════════════════════════════════════════════════════════════

class OrderService:
    """
    Order business logic.
    UnitOfWork use karta hai — order + stock update atomic hona chahiye.

    Session directly inject hota hai (UoW ke liye) — repository nahi.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def place_order(self, data: OrderCreate) -> Order:
        """
        Order place karo — atomically:
        1. Product exist karta hai?
        2. Enough stock hai?
        3. Order create karo
        4. Stock deduct karo
        → Teeno ya kuch nahi!
        """
        async with UnitOfWork(self.session) as uow:
            # Step 1: Product fetch
            product = await uow.products.get(data.product_id)
            if not product:
                raise ProductNotFound(
                    f"Product with id={data.product_id} not found"
                )

            # Step 2: Active check
            if not product.is_active:
                raise InvalidOperation(
                    f"Product '{product.name}' is not active — order nahi ho sakta"
                )

            # Step 3: Stock check
            if product.stock < data.quantity:
                raise InsufficientStock(
                    f"Insufficient stock for '{product.name}'. "
                    f"Available: {product.stock}, Requested: {data.quantity}"
                )

            # Step 4: Order create
            total_price = round(product.price * data.quantity, 2)
            order = await uow.orders.create(
                {
                    "product_id": data.product_id,
                    "quantity": data.quantity,
                    "total_price": total_price,
                    "status": "confirmed",
                    "customer_name": data.customer_name,
                    "created_at": datetime.utcnow(),
                }
            )

            # Step 5: Stock deduct
            # UoW ke andar flush/commit nahi karna chahiye repo ke through
            # Direct session.execute use karo
            await self.session.execute(
                update(Product)
                .where(Product.id == product.id)
                .values(
                    stock=product.stock - data.quantity,
                    updated_at=datetime.utcnow(),
                )
            )

            # UoW.__aexit__ commit karega — dono operations ek saath!

        return order

    async def get_order(self, order_id: int) -> Order:
        """Order fetch — not found pe exception"""
        repo = OrderRepository(self.session)
        order = await repo.get(order_id)
        if not order:
            raise OrderNotFound(f"Order with id={order_id} not found")
        return order


# ═══════════════════════════════════════════════════════════════════════════════
# ═══ DEPENDENCY INJECTION ═══
# Real project mein: app/api/dependencies.py
# DI chain: Session → Repository → Service
# FastAPI automatically resolve karta hai pura chain!
# ═══════════════════════════════════════════════════════════════════════════════

async def get_product_repository(
    session: AsyncSession = Depends(get_session),
) -> ProductRepository:
    """
    Step 1 of DI chain: Session se Repository banao.
    Route mein directly use karo: repo: ProductRepository = Depends(get_product_repository)
    """
    return ProductRepository(session)


async def get_product_service(
    repo: ProductRepository = Depends(get_product_repository),
) -> ProductService:
    """
    Step 2 of DI chain: Repository se Service banao.
    Route mein: service: ProductService = Depends(get_product_service)
    """
    return ProductService(repo)


async def get_order_service(
    session: AsyncSession = Depends(get_session),
) -> OrderService:
    """
    OrderService ko session chahiye (UoW ke liye).
    """
    return OrderService(session)


# ═══════════════════════════════════════════════════════════════════════════════
# ═══ API ROUTES ═══
# Real project mein: app/api/v1/products.py, orders.py
# Routes sirf: HTTP in/out + service call + exception → HTTP mapping
# ═══════════════════════════════════════════════════════════════════════════════

from fastapi import APIRouter

products_router = APIRouter(prefix="/api/v1/products", tags=["Products"])
orders_router = APIRouter(prefix="/api/v1/orders", tags=["Orders"])


# ─── Product Routes ───

@products_router.post(
    "/",
    response_model=ProductResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Product create karo",
)
async def create_product(
    data: ProductCreate,
    service: ProductService = Depends(get_product_service),
):
    """
    Naya product create karo.
    - SKU unique hona chahiye
    - Price > 0
    - Stock >= 0
    """
    return await service.create_product(data)


@products_router.get(
    "/",
    response_model=ProductListResponse,
    summary="Products list karo (paginated)",
)
async def list_products(
    skip: int = Query(0, ge=0, description="Kitne skip karo"),
    limit: int = Query(20, ge=1, le=100, description="Kitne return karo"),
    service: ProductService = Depends(get_product_service),
):
    """Paginated product list — sirf active products."""
    items, total = await service.list_products(skip=skip, limit=limit)
    return ProductListResponse(items=items, total=total, skip=skip, limit=limit)


@products_router.get(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Product ID se fetch karo",
)
async def get_product(
    product_id: int,
    service: ProductService = Depends(get_product_service),
):
    return await service.get_product(product_id)


@products_router.put(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Product update karo",
)
async def update_product(
    product_id: int,
    data: ProductUpdate,
    service: ProductService = Depends(get_product_service),
):
    """Partial update — sirf jo fields bhejo woh update honge."""
    return await service.update_product(product_id, data)


@products_router.delete(
    "/{product_id}",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Product delete karo",
)
async def delete_product(
    product_id: int,
    service: ProductService = Depends(get_product_service),
):
    await service.delete_product(product_id)
    return MessageResponse(
        message="Product deleted", detail=f"Product {product_id} successfully deleted"
    )


@products_router.patch(
    "/{product_id}/stock",
    response_model=ProductResponse,
    summary="Stock adjust karo (delta)",
)
async def update_stock(
    product_id: int,
    body: StockUpdateRequest,
    service: ProductService = Depends(get_product_service),
):
    """
    Stock adjust karo.
    - quantity_delta = +10 → 10 add karo
    - quantity_delta = -5  → 5 reduce karo
    - Stock 0 se neeche nahi ja sakta
    """
    return await service.update_stock(product_id, body.quantity_delta)


# ─── Order Routes ───

@orders_router.post(
    "/",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Order place karo (UoW demo)",
)
async def place_order(
    data: OrderCreate,
    service: OrderService = Depends(get_order_service),
):
    """
    Order place karo — Unit of Work demo.
    Order create + stock deduct — atomic operation.
    Agar koi bhi step fail ho → rollback!
    """
    return await service.place_order(data)


@orders_router.get(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Order ID se fetch karo",
)
async def get_order(
    order_id: int,
    service: OrderService = Depends(get_order_service),
):
    return await service.get_order(order_id)


# ═══════════════════════════════════════════════════════════════════════════════
# ═══ EXCEPTION HANDLERS ═══
# Real project mein: app/core/exception_handlers.py
# Domain exceptions → HTTP responses
# Yahan service mein raise kiya, yahan HTTP status code decide hota hai
# ═══════════════════════════════════════════════════════════════════════════════

def register_exception_handlers(app: FastAPI) -> None:
    """
    Saare domain exceptions ko HTTP responses mein map karo.

    WHY global handlers?
    - Consistent error format everywhere
    - Route mein try/except likhna nahi padta
    - Domain exception → HTTP mapping ek jagah
    """

    @app.exception_handler(ProductNotFound)
    async def product_not_found_handler(
        request: Request, exc: ProductNotFound
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "ProductNotFound", "detail": str(exc)},
        )

    @app.exception_handler(DuplicateSKU)
    async def duplicate_sku_handler(
        request: Request, exc: DuplicateSKU
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": "DuplicateSKU", "detail": str(exc)},
        )

    @app.exception_handler(InsufficientStock)
    async def insufficient_stock_handler(
        request: Request, exc: InsufficientStock
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "InsufficientStock", "detail": str(exc)},
        )

    @app.exception_handler(OrderNotFound)
    async def order_not_found_handler(
        request: Request, exc: OrderNotFound
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "OrderNotFound", "detail": str(exc)},
        )

    @app.exception_handler(InvalidOperation)
    async def invalid_operation_handler(
        request: Request, exc: InvalidOperation
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "InvalidOperation", "detail": str(exc)},
        )

    @app.exception_handler(DomainException)
    async def generic_domain_handler(
        request: Request, exc: DomainException
    ) -> JSONResponse:
        # Catch-all for any unhandled domain exception
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "DomainError", "detail": str(exc)},
        )


# ═══════════════════════════════════════════════════════════════════════════════
# ═══ SEED DATA ═══
# Demo ke liye sample data insert karo
# ═══════════════════════════════════════════════════════════════════════════════

async def seed_demo_data() -> None:
    """
    Demo data insert karo — fresh DB pe.
    Real project mein alembic migrations use karo.
    """
    async with AsyncSessionFactory() as session:
        # Check karo agar already seeded hai
        result = await session.execute(select(func.count()).select_from(Product))
        count = result.scalar() or 0
        if count > 0:
            print(f"  → DB already has {count} products — seed skip kar raha hoon")
            return

        now = datetime.utcnow()
        products = [
            Product(
                name="Laptop Pro X1",
                sku="LAPTOP-PRO-X1",
                description="15.6 inch, i7, 16GB RAM, 512GB SSD",
                price=49999.99,
                stock=50,
                category="Electronics",
                is_active=True,
                created_at=now,
                updated_at=now,
            ),
            Product(
                name="Wireless Mouse M200",
                sku="MOUSE-M200",
                description="Ergonomic wireless mouse, 1600 DPI",
                price=999.00,
                stock=200,
                category="Accessories",
                is_active=True,
                created_at=now,
                updated_at=now,
            ),
            Product(
                name="USB-C Hub 7-in-1",
                sku="HUB-USBC-7IN1",
                description="HDMI 4K, USB 3.0 x3, SD card, PD charging",
                price=2499.00,
                stock=75,
                category="Accessories",
                is_active=True,
                created_at=now,
                updated_at=now,
            ),
            Product(
                name="Mechanical Keyboard KB500",
                sku="KB-MECH-500",
                description="TKL layout, Cherry MX Red switches, RGB",
                price=4999.00,
                stock=30,
                category="Accessories",
                is_active=True,
                created_at=now,
                updated_at=now,
            ),
            Product(
                name="Discontinued Webcam OLD",
                sku="WEBCAM-OLD-V1",
                description="Old model — discontinued",
                price=1999.00,
                stock=0,
                category="Accessories",
                is_active=False,   # Inactive product
                created_at=now,
                updated_at=now,
            ),
        ]

        session.add_all(products)
        await session.commit()
        print(f"  → {len(products)} demo products inserted ✓")


# ═══════════════════════════════════════════════════════════════════════════════
# ═══ FASTAPI APP ═══
# Real project mein: app/main.py
# ═══════════════════════════════════════════════════════════════════════════════

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    App startup/shutdown lifecycle.
    startup: DB tables create + seed data
    shutdown: DB connections close
    """
    # Startup
    print("\n🚀 Clean Architecture Demo — Starting up...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("  → DB tables created ✓")

    await seed_demo_data()
    print("  → App ready! Visit http://127.0.0.1:8002/docs\n")

    yield  # ← App yahan run karta hai

    # Shutdown
    print("\n🛑 Shutting down — closing DB connections...")
    await engine.dispose()
    print("  → Done.\n")


app = FastAPI(
    title="Clean Architecture Demo — E-Commerce API",
    description="""
## FastAPI Clean Architecture + DDD Demo

Yeh demo Clean Architecture ke saare patterns show karta hai:

### Architecture Layers
- **API Layer** (`products_router`, `orders_router`) — HTTP handling
- **Service Layer** (`ProductService`, `OrderService`) — Business rules
- **Repository Layer** (`ProductRepository`, `OrderRepository`) — DB queries
- **Domain Layer** (Models + Schemas + Exceptions) — Core entities

### Patterns Demonstrated
- **Repository Pattern** — Generic `BaseRepository[T]`
- **Service Layer** — Business logic isolated from HTTP
- **Unit of Work** — Atomic order placement (order + stock deduct)
- **Dependency Injection** — Session → Repo → Service chain
- **Domain Exceptions** — HTTP-free business errors

### Try This Flow
1. `GET /api/v1/products` — demo products dekho (seeded on startup)
2. `POST /api/v1/products` — naya product banao
3. `POST /api/v1/orders` — order place karo (stock automatically deduct hoga!)
4. `GET /api/v1/products/{id}` — stock reduced dekho
5. `PATCH /api/v1/products/{id}/stock` — stock manually adjust karo
    """,
    version="1.0.0",
    lifespan=lifespan,
)

# Exception handlers register karo
register_exception_handlers(app)

# Routers include karo
app.include_router(products_router)
app.include_router(orders_router)


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check(session: AsyncSession = Depends(get_session)):
    """App aur DB health check"""
    # DB connectivity check
    try:
        await session.execute(select(func.count()).select_from(Product))
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {e}"

    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        timestamp=datetime.utcnow(),
        db=db_status,
    )


@app.get("/", tags=["Info"])
async def root():
    """API info"""
    return {
        "app": "Clean Architecture Demo",
        "docs": "/docs",
        "health": "/health",
        "architecture": {
            "api_layer": "routes (HTTP handling)",
            "service_layer": "business logic",
            "repository_layer": "DB queries",
            "domain_layer": "models + schemas + exceptions",
        },
        "patterns": [
            "Repository Pattern",
            "Service Layer",
            "Unit of Work (try placing an order!)",
            "Dependency Injection",
            "Domain Exceptions",
            "Generic BaseRepository[T]",
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Entry point
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "14_clean_architecture_app:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
    )
