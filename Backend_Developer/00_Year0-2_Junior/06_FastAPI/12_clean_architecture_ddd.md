# FastAPI — Clean Architecture & Domain-Driven Design
**FastAPI · Year 0-2 | Senior Backend + Agentic AI**

## Quick Concepts
- **Clean Architecture** = code ko layers mein organize karo — Domain, Service, Repository, API
- **DDD (Domain-Driven Design)** = business logic ko center mein rakho, framework side pe
- **Repository Pattern** = database queries ek jagah — swap DB bina service touch kiye
- **Service Layer** = business rules yahan — routes mein sirf HTTP handling
- **Unit of Work** = multiple DB operations ko atomic banao (all-or-nothing)
- **Dependency Injection** = dependencies inject karo — testing ke liye easy mock karo
- **Domain Exceptions** = HTTP se alag custom exceptions — transport-agnostic errors

---

## Section A — Why Clean Architecture? (Problem → Solution)

```
Problem with flat structure:
  main.py → 2000 lines → sab kuch ek jagah → nightmare ❌
  
  main.py mein:
    - DB queries bhi
    - Business logic bhi  
    - HTTP handling bhi
    - Validation bhi
    → Test karna impossible, change karna dangerous

Clean Architecture ke benefits:
  ✅ Business logic alag — test karna easy (real DB chahiye hi nahi)
  ✅ DB change karo (PostgreSQL → MongoDB) — sirf repository change
  ✅ Framework change karo (FastAPI → Django) — domain logic untouched
  ✅ Team mein kaam karna easy (separate concerns — parallel development)
  ✅ Interview mein yahi poochha jaata hai 10+ LPA pe

Layers ki responsibility:
  API Layer      → HTTP request/response, validation, status codes
  Service Layer  → Business rules, orchestration, domain exceptions
  Repository     → DB queries only — no business logic
  Domain         → Entities (models), value objects, domain exceptions
```

---

## Section B — Folder Structure (Production-grade)

```
ecommerce_api/
│
├── app/
│   ├── api/                    ← HTTP layer (routes, request/response)
│   │   ├── __init__.py
│   │   ├── dependencies.py     ← Depends() functions — DI wiring
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── products.py     ← Routes: GET /products, POST /products
│   │       └── orders.py
│   │
│   ├── core/                   ← App configuration
│   │   ├── config.py           ← Settings (pydantic-settings)
│   │   ├── database.py         ← DB connection setup (engine, session)
│   │   ├── exceptions.py       ← Domain exceptions (HTTP-free!)
│   │   └── security.py         ← JWT helpers
│   │
│   ├── domain/                 ← Business logic (framework-free!)
│   │   ├── models/             ← Domain entities (SQLAlchemy models)
│   │   │   ├── product.py      ← Product SQLAlchemy model
│   │   │   └── order.py        ← Order SQLAlchemy model
│   │   └── schemas/            ← Pydantic schemas (request/response)
│   │       ├── product.py      ← ProductCreate, ProductResponse
│   │       └── order.py        ← OrderCreate, OrderResponse
│   │
│   ├── repositories/           ← Data access layer (DB queries yahan)
│   │   ├── base.py             ← Generic BaseRepository[T]
│   │   ├── product.py          ← ProductRepository (extends Base)
│   │   └── order.py            ← OrderRepository
│   │
│   ├── services/               ← Business logic layer
│   │   ├── product.py          ← ProductService (uses Repository)
│   │   └── order.py            ← OrderService (uses UoW)
│   │
│   └── main.py                 ← FastAPI app, lifespan, routers
│
├── tests/
│   ├── unit/                   ← Service tests (mock repository — no DB)
│   │   ├── test_product_service.py
│   │   └── test_order_service.py
│   └── integration/            ← API tests (real test DB)
│       ├── test_products_api.py
│       └── test_orders_api.py
│
├── alembic/                    ← DB migrations
│   └── versions/
├── .env                        ← Secrets (never commit!)
└── requirements.txt

KEY RULE:
  Domain → Service → Repository → DB    (imports ek direction mein)
  API    → Service (never directly to Repository!)
  Service → Repository (never directly to DB session!)
```

---

## Section C — Repository Pattern (Data Access Layer)

```python
# ─── repositories/base.py — Generic CRUD repository ───
from typing import Generic, TypeVar, Type, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete

ModelType = TypeVar("ModelType")

class BaseRepository(Generic[ModelType]):
    """
    Generic repository — har model ke liye reusable CRUD.
    Concrete repositories isse extend karenge aur specific queries add karenge.
    """
    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model
        self.session = session
    
    async def get(self, id: int) -> Optional[ModelType]:
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()
    
    async def get_all(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        result = await self.session.execute(
            select(self.model).offset(skip).limit(limit)
        )
        return result.scalars().all()
    
    async def create(self, data: dict) -> ModelType:
        instance = self.model(**data)
        self.session.add(instance)
        await self.session.commit()
        await self.session.refresh(instance)  # DB-generated fields fetch karo
        return instance
    
    async def update(self, id: int, data: dict) -> Optional[ModelType]:
        await self.session.execute(
            update(self.model)
            .where(self.model.id == id)
            .values(**data)
        )
        await self.session.commit()
        return await self.get(id)  # Updated record return karo
    
    async def delete(self, id: int) -> bool:
        result = await self.session.execute(
            delete(self.model).where(self.model.id == id)
        )
        await self.session.commit()
        return result.rowcount > 0  # True = deleted, False = not found


# ─── repositories/product.py — Product-specific queries ───
class ProductRepository(BaseRepository[Product]):
    """
    Product-specific DB queries.
    Base se CRUD milta hai, yahan specific queries add karo.
    """
    async def get_by_sku(self, sku: str) -> Optional[Product]:
        """SKU uniqueness check ke liye"""
        result = await self.session.execute(
            select(Product).where(Product.sku == sku)
        )
        return result.scalar_one_or_none()
    
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
        return result.scalars().all()
    
    async def search(self, query: str) -> List[Product]:
        """Full-text search (basic ilike version)"""
        result = await self.session.execute(
            select(Product).where(
                Product.name.ilike(f"%{query}%") |
                Product.description.ilike(f"%{query}%")
            )
        )
        return result.scalars().all()
    
    async def count(self) -> int:
        from sqlalchemy import func
        result = await self.session.execute(
            select(func.count()).select_from(Product)
        )
        return result.scalar()
```

---

## Section D — Service Layer (Business Logic)

```python
# ─── services/product.py — Business logic yahan, HTTP kuch nahi ───
from repositories.product import ProductRepository
from domain.schemas.product import ProductCreate, ProductUpdate
from core.exceptions import ProductNotFound, DuplicateSKU

class ProductService:
    """
    Business rules yahan live karte hain.
    Repository se baat karta hai — HTTP se bilkul alag.
    
    RULE: Agar koi business validation hai → Service mein
          Agar koi DB query hai             → Repository mein
          Agar koi HTTP status code hai     → API layer mein
    """
    def __init__(self, repository: ProductRepository):
        self.repo = repository  # Dependency injection — test ke liye mock pass karo
    
    async def create_product(self, data: ProductCreate) -> Product:
        # Business rule 1: SKU unique hona chahiye
        existing = await self.repo.get_by_sku(data.sku)
        if existing:
            raise DuplicateSKU(f"SKU '{data.sku}' already exists")
        
        # Business rule 2: price positive hona chahiye
        if data.price <= 0:
            raise ValueError("Price must be positive")
        
        # Business rule 3: stock negative nahi ho sakta at creation
        if data.stock < 0:
            raise ValueError("Initial stock cannot be negative")
        
        return await self.repo.create(data.model_dump())
    
    async def update_stock(self, product_id: int, quantity_delta: int) -> Product:
        """
        Stock update with business validation.
        quantity_delta: positive = stock add, negative = stock reduce
        """
        product = await self.repo.get(product_id)
        if not product:
            raise ProductNotFound(f"Product {product_id} not found")
        
        new_stock = product.stock + quantity_delta
        if new_stock < 0:
            raise ValueError(
                f"Insufficient stock. Available: {product.stock}, "
                f"Requested reduction: {abs(quantity_delta)}"
            )
        
        return await self.repo.update(product_id, {"stock": new_stock})
    
    async def get_product(self, product_id: int) -> Product:
        """Single product fetch — 404 raise karo if not found"""
        product = await self.repo.get(product_id)
        if not product:
            raise ProductNotFound(f"Product {product_id} not found")
        return product
    
    async def update_product(self, product_id: int, data: ProductUpdate) -> Product:
        await self.get_product(product_id)  # Existence check
        
        # Sirf provided fields update karo (partial update support)
        update_data = data.model_dump(exclude_unset=True)
        if not update_data:
            raise ValueError("No fields to update")
        
        return await self.repo.update(product_id, update_data)
    
    async def delete_product(self, product_id: int) -> None:
        await self.get_product(product_id)  # Existence check
        deleted = await self.repo.delete(product_id)
        if not deleted:
            raise ProductNotFound(f"Product {product_id} delete failed")
```

---

## Section E — Dependency Injection Wiring

```python
# ─── api/dependencies.py — DI chain: Session → Repo → Service ───
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_session
from repositories.product import ProductRepository
from services.product import ProductService

# Step 1: Session dependency (already have this in database.py)
# async def get_session() → yields AsyncSession

# Step 2: Repository depends on Session
async def get_product_repository(
    session: AsyncSession = Depends(get_session)
) -> ProductRepository:
    return ProductRepository(Product, session)

# Step 3: Service depends on Repository
async def get_product_service(
    repo: ProductRepository = Depends(get_product_repository)
) -> ProductService:
    return ProductService(repo)

# Chain: Request → get_session → get_product_repository → get_product_service → Route
# FastAPI automatically resolves the whole chain!


# ─── api/v1/products.py — Routes: HTTP handling only ───
from fastapi import APIRouter, Depends, HTTPException, status
from domain.schemas.product import ProductCreate, ProductResponse, ProductUpdate
from services.product import ProductService
from api.dependencies import get_product_service
from core.exceptions import ProductNotFound, DuplicateSKU

router = APIRouter(prefix="/products", tags=["products"])

@router.post("/", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    data: ProductCreate,
    service: ProductService = Depends(get_product_service)
):
    """Route sirf: validate input → call service → convert exception to HTTP"""
    try:
        product = await service.create_product(data)
        return product
    except DuplicateSKU as e:
        raise HTTPException(status_code=409, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    service: ProductService = Depends(get_product_service)
):
    try:
        return await service.get_product(product_id)
    except ProductNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.patch("/{product_id}/stock", response_model=ProductResponse)
async def update_stock(
    product_id: int,
    quantity_delta: int,
    service: ProductService = Depends(get_product_service)
):
    try:
        return await service.update_stock(product_id, quantity_delta)
    except ProductNotFound as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```

---

## Section F — Unit of Work Pattern

```python
# ─── Unit of Work: Multiple repos ek transaction mein ───
from sqlalchemy.ext.asyncio import AsyncSession

class UnitOfWork:
    """
    Multiple repository operations ko ek atomic transaction mein wrap karo.
    
    USE CASE: Order place karo:
      1. Product stock check
      2. Order create
      3. Stock deduct
      → Teeno succeed ya teeno fail (atomic!)
    
    Without UoW: partial failure → inconsistent data 😱
    With UoW:    exception on any step → rollback everything ✅
    """
    def __init__(self, session: AsyncSession):
        self.session = session
        self.products = ProductRepository(Product, session)
        self.orders = OrderRepository(Order, session)
        self.inventory = InventoryRepository(Inventory, session)
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.session.rollback()   # Exception aaya → rollback
        else:
            await self.session.commit()     # Sab theek → commit
        # Note: session closing lifespan/dependency mein handle hoti hai


# ─── services/order.py — UoW usage ───
class OrderService:
    def __init__(self, session: AsyncSession):
        self.session = session  # UoW ke liye session directly
    
    async def place_order(self, order_data: OrderCreate) -> Order:
        async with UnitOfWork(self.session) as uow:
            # Step 1: Product check
            product = await uow.products.get(order_data.product_id)
            if not product:
                raise ProductNotFound(f"Product {order_data.product_id} not found")
            
            # Step 2: Stock validation
            if product.stock < order_data.quantity:
                raise InsufficientStock(
                    f"Need {order_data.quantity}, available {product.stock}"
                )
            
            # Step 3: Order create
            total_price = product.price * order_data.quantity
            order = await uow.orders.create({
                "product_id": order_data.product_id,
                "quantity": order_data.quantity,
                "total_price": total_price,
                "status": "confirmed"
            })
            
            # Step 4: Stock deduct
            # Note: UoW ke andar commit mat karo — __aexit__ karega
            await uow.session.execute(
                update(Product)
                .where(Product.id == product.id)
                .values(stock=product.stock - order_data.quantity)
            )
            
            # No exception = __aexit__ commits both operations atomically
        return order

# WHY NOT just call repo.update() inside UoW?
# BaseRepository.update() apna commit karta hai — UoW ka commit bypass ho jaata
# Solution: UoW ke andar direct session.execute() use karo (no intermediate commit)
# Ya BaseRepository mein commit optional banao (flush-only mode)
```

---

## Section G — Domain Exceptions (HTTP-free)

```python
# ─── core/exceptions.py — Domain exceptions ───
class DomainException(Exception):
    """Base class for all domain exceptions"""
    pass

class ProductNotFound(DomainException):
    """Product DB mein nahi mila"""
    pass

class DuplicateSKU(DomainException):
    """Same SKU already exists"""
    pass

class InsufficientStock(DomainException):
    """Order quantity > available stock"""
    pass

class OrderAlreadyCancelled(DomainException):
    """Cancel already cancelled order"""
    pass

# ─── main.py — Global exception handlers ───
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(ProductNotFound)
async def product_not_found_handler(request: Request, exc: ProductNotFound):
    return JSONResponse(status_code=404, content={"detail": str(exc)})

@app.exception_handler(DuplicateSKU)
async def duplicate_sku_handler(request: Request, exc: DuplicateSKU):
    return JSONResponse(status_code=409, content={"detail": str(exc)})

@app.exception_handler(InsufficientStock)
async def insufficient_stock_handler(request: Request, exc: InsufficientStock):
    return JSONResponse(status_code=400, content={"detail": str(exc)})

# WHY alag rakhte hain?
# Service mein raise ProductNotFound() → HTTP ka koi idea nahi
# API layer ya exception handler mein → 404 ka pata chalta hai
# Kal REST API ko gRPC mein convert karo → service code unchanged!
# gRPC handler mein: ProductNotFound → NOT_FOUND status code
```

---

## Section H — Unit Testing (Clean Architecture ka sabse bada benefit)

```python
# ─── tests/unit/test_product_service.py ───
# Real DB chahiye hi nahi — mock repository pass karo

import pytest
from unittest.mock import AsyncMock, MagicMock
from services.product import ProductService
from domain.schemas.product import ProductCreate, ProductUpdate
from core.exceptions import ProductNotFound, DuplicateSKU

@pytest.mark.asyncio
async def test_create_product_success():
    """Happy path — product create hoga"""
    mock_repo = AsyncMock()
    mock_repo.get_by_sku.return_value = None          # SKU nahi hai
    mock_repo.create.return_value = MagicMock(id=1, name="Test Product")
    
    service = ProductService(mock_repo)
    result = await service.create_product(
        ProductCreate(name="Test", sku="SKU-001", price=99.99, stock=10)
    )
    
    mock_repo.get_by_sku.assert_called_once_with("SKU-001")
    mock_repo.create.assert_called_once()
    assert result.id == 1

@pytest.mark.asyncio
async def test_create_product_duplicate_sku():
    """Duplicate SKU → DuplicateSKU exception"""
    mock_repo = AsyncMock()
    mock_repo.get_by_sku.return_value = MagicMock()   # SKU already exists!
    
    service = ProductService(mock_repo)
    
    with pytest.raises(DuplicateSKU) as exc_info:
        await service.create_product(
            ProductCreate(name="Test", sku="EXISTING-SKU", price=100, stock=5)
        )
    
    assert "EXISTING-SKU" in str(exc_info.value)
    mock_repo.create.assert_not_called()  # Create nahi hua — yahi chahiye tha ✅

@pytest.mark.asyncio
async def test_update_stock_insufficient():
    """Stock se zyada reduce → ValueError"""
    mock_repo = AsyncMock()
    mock_repo.get.return_value = MagicMock(id=1, stock=5)  # Only 5 in stock
    
    service = ProductService(mock_repo)
    
    with pytest.raises(ValueError, match="Insufficient stock"):
        await service.update_stock(product_id=1, quantity_delta=-10)  # -10 maang rahe
    
    mock_repo.update.assert_not_called()  # DB update nahi hua

@pytest.mark.asyncio
async def test_get_product_not_found():
    """Product nahi mila → ProductNotFound"""
    mock_repo = AsyncMock()
    mock_repo.get.return_value = None  # DB mein nahi hai
    
    service = ProductService(mock_repo)
    
    with pytest.raises(ProductNotFound):
        await service.get_product(product_id=999)

# NOTICE: In teeno tests mein:
# - Koi DB connection nahi
# - Koi HTTP request nahi
# - Pure Python — milliseconds mein run
# Yahi Clean Architecture ka POINT hai!
```

---

## Interview Questions & Answers

### Q1: "FastAPI project kaise structure karte ho large scale pe?"
**Answer:**
```
Clean Architecture use karta hoon — 4 layers:

1. API Layer (api/):       HTTP in/out — routes, Depends(), status codes
2. Service Layer (services/): Business logic — rules, validations
3. Repository Layer (repositories/): DB queries only — SQLAlchemy
4. Domain Layer (domain/): Models + Schemas + Exceptions

Dependency flow: API → Service → Repository → DB
Koi layer apne se upar wali layer import nahi karta.

Benefits:
- Service layer test karna easy — repository mock karo, DB ki zaroorat nahi
- DB change karo — sirf repository rewrite, service untouched
- Team parallel kaam kar sakti hai — alag layers alag log
```

---

### Q2: "Repository Pattern ka kya benefit hai? Direct session use kyu nahi karte?"
**Answer:**
```
Problem with direct session in routes/services:
  - DB query logic har jagah scattered
  - Testing ke liye real DB chahiye
  - DB vendor change karo → har jagah change karna padega

Repository Pattern ke benefits:
  1. Centralized queries — ek jagah change, sab jagah effect
  2. Testability — mock repository → no DB needed
  3. Abstraction — service ko pata hi nahi DB PostgreSQL hai ya MongoDB
  4. Reusability — BaseRepository[T] se generic CRUD milta hai

Example:
  # Without repo — service directly queries karta
  products = await session.execute(select(Product).where(...))  # service mein
  
  # With repo — clean abstraction
  products = await self.repo.get_by_category("electronics")     # intent clear!
```

---

### Q3: "Service layer mein kya hona chahiye, kya nahi?"
**Answer:**
```
Service layer MEIN hona chahiye:
  ✅ Business rules (SKU unique check, stock validation)
  ✅ Orchestration (multiple repo calls coordinate karna)
  ✅ Domain exceptions raise karna (ProductNotFound, InsufficientStock)
  ✅ Data transformation (business-level)

Service layer mein NAHI hona chahiye:
  ❌ HTTP status codes (404, 409) — ye API layer ka kaam
  ❌ HTTPException raise karna — domain exceptions use karo
  ❌ Direct DB session queries — ye repository ka kaam
  ❌ Request/Response Pydantic parsing — API layer ka kaam
  ❌ FastAPI specific imports (Request, APIRouter) — transport-agnostic raho

SERVICE = Pure business logic. Isko gRPC, CLI, Celery task se bhi call kar sako.
```

---

### Q4: "Unit of Work pattern kab use karte ho?"
**Answer:**
```
UoW use karo jab:
  - Multiple DB operations ek transaction mein honi chahiye
  - Partial failure acceptable nahi — "all or nothing"
  
Classic example: Order placement
  1. Check stock
  2. Create order record
  3. Deduct stock
  → Agar step 3 fail ho, order bana lekin stock deduct nahi → INCONSISTENCY!
  → UoW se: exception → rollback → teeno revert

Pattern:
  async with UnitOfWork(session) as uow:
      order  = await uow.orders.create(...)
      product = await uow.products.update(id, {"stock": new_stock})
      # Exception → rollback, Success → commit (in __aexit__)

Simple CRUD pe UoW overkill hai — sirf multi-repo operations pe use karo.
```

---

### Q5: "Domain exception aur HTTP exception alag kyun rakhte hain?"
**Answer:**
```
Domain exceptions (core/exceptions.py):
  - Business language mein: ProductNotFound, InsufficientStock, DuplicateSKU
  - HTTP ka koi knowledge nahi
  - Service layer raise karta hai — transport-agnostic

HTTP exceptions (API layer):
  - ProductNotFound   → 404
  - DuplicateSKU      → 409  
  - InsufficientStock → 400

WHY alag?
  1. Same service → REST API (404) + gRPC (NOT_FOUND) + CLI (exit code 1)
     Service code change hi nahi karna padega!
  2. Service unit tests mein HTTP import nahi aata — clean
  3. Error mapping ek jagah (exception handlers) — consistent responses
  4. Domain language preserve hoti hai — business meaning clear

Global exception handlers se mapping karo:
  @app.exception_handler(ProductNotFound) → 404 response
```

---

### Q6: "Dependency injection se testing kaise easy hoti hai?"
**Answer:**
```python
# Production mein:
# FastAPI chain: get_session → get_product_repo → get_product_service → route
# Sab automatically inject hota hai

# Testing mein: override karo!
from fastapi.testclient import TestClient

mock_service = AsyncMock()
mock_service.get_product.return_value = fake_product

app.dependency_overrides[get_product_service] = lambda: mock_service

client = TestClient(app)
response = client.get("/products/1")
# Real DB nahi, real service nahi — sirf route logic test hua!

# Pure unit test (no HTTP at all):
mock_repo = AsyncMock()
mock_repo.get_by_sku.return_value = None
service = ProductService(mock_repo)  # inject mock directly
result = await service.create_product(data)
# DB? HTTP? Nahi chahiye. Pure business logic test hua. ✅
```

---

### Q7: "Generic BaseRepository kaise kaam karta hai? TypeVar kyu use kiya?"
**Answer:**
```python
# TypeVar: "ye koi bhi model ho sakta hai"
ModelType = TypeVar("ModelType")

class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], session: AsyncSession):
        self.model = model  # Actual class pass karo: Product, Order, etc.
    
    async def get(self, id: int) -> Optional[ModelType]:
        # self.model dynamically Product ya Order hai — same code!
        result = await self.session.execute(
            select(self.model).where(self.model.id == id)
        )
        return result.scalar_one_or_none()

# Usage:
product_repo = ProductRepository(Product, session)   # ModelType = Product
order_repo   = OrderRepository(Order, session)        # ModelType = Order

# Type hints kaam karte hain:
product: Optional[Product] = await product_repo.get(1)  # IDE knows it's Product!

# Without Generic: har model ke liye duplicate CRUD code likhna padta — DRY violation
```

---

## Summary Table — Layer Responsibilities

| Layer | File Location | Responsible For | NOT Responsible For |
|-------|--------------|-----------------|---------------------|
| **API** | `api/v1/*.py` | HTTP routing, status codes, input parsing, exception → HTTP mapping | Business logic, DB queries |
| **Service** | `services/*.py` | Business rules, validation, orchestration, domain exceptions | HTTP codes, DB queries, SQLAlchemy |
| **Repository** | `repositories/*.py` | DB queries (select, insert, update, delete), ORM usage | Business rules, HTTP |
| **Domain Models** | `domain/models/*.py` | SQLAlchemy table definitions, relationships | Any logic |
| **Domain Schemas** | `domain/schemas/*.py` | Pydantic request/response models | DB or business logic |
| **Domain Exceptions** | `core/exceptions.py` | Named business errors | HTTP codes |
| **DI Wiring** | `api/dependencies.py` | Session→Repo→Service chain | Any logic |

---

## Quick Reference — What Goes Where?

```
"Price validate karna hai (positive check)"         → Service layer
"SELECT * FROM products WHERE category = ?"         → Repository
"Return 404 if not found"                           → API layer / exception handler
"SKU column define karna hai"                       → Domain model
"ProductCreate pydantic schema"                     → Domain schema
"ProductNotFound raise karna hai"                   → Service layer (domain exception)
"ProductNotFound ko 404 mein convert karna"         → Exception handler / API route
"Order + stock update ek transaction mein"          → Unit of Work
"session inject karna route mein"                   → Dependency (api/dependencies.py)
```
