# Lecture 1 — Practical Hands-On: Building a Monolithic Layered App

> **Theory file:** [01_Monolithic_and_Layered_Architecture.md](01_Monolithic_and_Layered_Architecture.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

Ek **fully working monolithic e-commerce app** with:

1. ✅ **3-layered design** (Presentation / Business / Data)
2. ✅ **FastAPI + SQLAlchemy + PostgreSQL** stack
3. ✅ **Docker-based** single-unit deployment
4. ✅ **Horizontal scaling** with load balancer
5. ✅ **Migration path** from 3-tier to N-tier
6. ✅ **Tests** at each layer
7. ✅ **Common monolith mistakes** + how to fix them

By end of this practical: aap **layered monolith likhna seekh jaoge production-quality**.

---

## 1. Project Structure (Reflects Architecture)

### Folder Layout

```
ecommerce_monolith/
├── docker-compose.yml             # Single deployment unit
├── Dockerfile                     # App container
├── nginx.conf                     # Load balancer config
├── pyproject.toml
├── alembic.ini
├── README.md
│
├── src/
│   ├── __init__.py
│   ├── main.py                    # FastAPI entry point
│   │
│   ├── presentation/              # 🖼 LAYER 1: UI / API
│   │   ├── __init__.py
│   │   ├── routers/
│   │   │   ├── products.py
│   │   │   ├── cart.py
│   │   │   ├── orders.py
│   │   │   ├── users.py
│   │   │   └── admin.py
│   │   ├── schemas/               # Pydantic models
│   │   │   ├── product.py
│   │   │   ├── order.py
│   │   │   └── user.py
│   │   └── dependencies.py        # FastAPI deps
│   │
│   ├── business/                  # ⚙️ LAYER 2: Business Logic
│   │   ├── __init__.py
│   │   ├── services/
│   │   │   ├── product_service.py
│   │   │   ├── order_service.py
│   │   │   ├── payment_service.py
│   │   │   └── user_service.py
│   │   ├── rules/
│   │   │   ├── pricing_rules.py
│   │   │   └── inventory_rules.py
│   │   └── exceptions.py
│   │
│   ├── data/                      # 💾 LAYER 3: Data Access
│   │   ├── __init__.py
│   │   ├── models/                # SQLAlchemy models
│   │   │   ├── product.py
│   │   │   ├── order.py
│   │   │   └── user.py
│   │   ├── repositories/
│   │   │   ├── product_repo.py
│   │   │   ├── order_repo.py
│   │   │   └── user_repo.py
│   │   └── database.py            # DB connection
│   │
│   └── core/                      # Cross-cutting
│       ├── config.py
│       ├── logging.py
│       └── security.py
│
├── migrations/                    # Alembic
│   └── versions/
│
└── tests/
    ├── unit/                      # Per-layer tests
    │   ├── test_business/
    │   └── test_data/
    └── integration/
        └── test_api/
```

**Notice:** Folder names **literally** reflect the layered architecture.

---

## 2. 🖼 Presentation Layer (UI / API)

### FastAPI Entry Point

```python
# src/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from src.presentation.routers import products, cart, orders, users, admin
from src.core.config import settings
from src.data.database import init_db

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="E-Commerce Monolith",
    description="Layered architecture monolithic e-commerce app",
    version="1.0.0",
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include all routers (each is a feature in the monolith)
app.include_router(products.router, prefix="/api/products", tags=["Products"])
app.include_router(cart.router, prefix="/api/cart", tags=["Cart"])
app.include_router(orders.router, prefix="/api/orders", tags=["Orders"])
app.include_router(users.router, prefix="/api/users", tags=["Users"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin"])


@app.on_event("startup")
async def startup():
    logger.info("Monolith starting up...")
    await init_db()


@app.on_event("shutdown")
async def shutdown():
    logger.info("Monolith shutting down...")


@app.get("/health")
def health_check():
    """Health check for load balancer."""
    return {"status": "healthy", "version": "1.0.0"}
```

### Product Router (Presentation Layer)

```python
# src/presentation/routers/products.py
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from sqlalchemy.orm import Session

from src.presentation.schemas.product import ProductResponse, ProductCreate
from src.presentation.dependencies import get_db, require_admin
from src.business.services.product_service import ProductService
from src.business.exceptions import ProductNotFound, InvalidProductData

router = APIRouter()


@router.get("/", response_model=list[ProductResponse])
def list_products(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, le=100),
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    PRESENTATION LAYER:
    - Validates HTTP input
    - Calls business layer
    - Returns HTTP response
    - NO BUSINESS LOGIC HERE
    """
    service = ProductService(db)
    products = service.list_products(skip=skip, limit=limit, category=category)
    return [ProductResponse.from_orm(p) for p in products]


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, db: Session = Depends(get_db)):
    service = ProductService(db)
    try:
        product = service.get_product(product_id)
        return ProductResponse.from_orm(product)
    except ProductNotFound:
        raise HTTPException(404, "Product not found")


@router.post("/", response_model=ProductResponse, status_code=201)
def create_product(
    product: ProductCreate,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),  # Authorization
):
    service = ProductService(db)
    try:
        new_product = service.create_product(
            name=product.name,
            price=product.price,
            stock=product.stock,
            category=product.category,
        )
        return ProductResponse.from_orm(new_product)
    except InvalidProductData as e:
        raise HTTPException(400, str(e))


@router.delete("/{product_id}", status_code=204)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    service = ProductService(db)
    try:
        service.delete_product(product_id)
    except ProductNotFound:
        raise HTTPException(404, "Product not found")
```

### Pydantic Schemas

```python
# src/presentation/schemas/product.py
from pydantic import BaseModel, Field
from datetime import datetime
from decimal import Decimal


class ProductCreate(BaseModel):
    """Input schema — what UI sends to create a product."""
    name: str = Field(..., min_length=1, max_length=200)
    price: Decimal = Field(..., gt=0, max_digits=10, decimal_places=2)
    stock: int = Field(..., ge=0)
    category: str = Field(..., min_length=1, max_length=50)


class ProductResponse(BaseModel):
    """Output schema — what UI receives back."""
    id: int
    name: str
    price: Decimal
    stock: int
    category: str
    created_at: datetime

    class Config:
        from_attributes = True  # Pydantic v2 — was orm_mode
```

### Dependencies

```python
# src/presentation/dependencies.py
from fastapi import Depends, HTTPException, Header
from sqlalchemy.orm import Session
from typing import Generator

from src.data.database import SessionLocal
from src.business.services.user_service import UserService


def get_db() -> Generator:
    """Dependency: yields DB session per request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    authorization: str = Header(...),
    db: Session = Depends(get_db),
):
    """Dependency: validates JWT and returns current user."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing token")

    token = authorization.split(" ")[1]
    service = UserService(db)
    user = service.get_user_by_token(token)
    if not user:
        raise HTTPException(401, "Invalid token")
    return user


def require_admin(user=Depends(get_current_user)):
    """Dependency: ensures user is admin."""
    if not user.is_admin:
        raise HTTPException(403, "Admin access required")
    return user
```

---

## 3. ⚙️ Business Logic Layer

> **The brain.** All business rules, decisions, workflows live here.

### Product Service

```python
# src/business/services/product_service.py
from typing import Optional
from decimal import Decimal
from sqlalchemy.orm import Session

from src.data.repositories.product_repo import ProductRepository
from src.business.exceptions import ProductNotFound, InvalidProductData
from src.business.rules.pricing_rules import PricingRules
from src.business.rules.inventory_rules import InventoryRules


class ProductService:
    """
    BUSINESS LAYER:
    - All product-related business logic
    - Uses repositories (data layer) but NOT direct DB access
    - Enforces rules
    """

    def __init__(self, db: Session):
        self.repo = ProductRepository(db)
        self.pricing = PricingRules()
        self.inventory = InventoryRules()

    def list_products(
        self,
        skip: int = 0,
        limit: int = 20,
        category: Optional[str] = None,
    ):
        """List products with optional filtering."""
        if limit > 100:
            limit = 100  # Business rule: max page size
        return self.repo.list_products(skip=skip, limit=limit, category=category)

    def get_product(self, product_id: int):
        """Get single product, raise if not found."""
        product = self.repo.get_by_id(product_id)
        if not product:
            raise ProductNotFound(f"Product {product_id} not found")
        return product

    def create_product(
        self,
        name: str,
        price: Decimal,
        stock: int,
        category: str,
    ):
        """Create new product with business rule validation."""
        # Business rule: validate pricing
        if not self.pricing.is_valid_price(price):
            raise InvalidProductData(f"Invalid price: {price}")

        # Business rule: validate inventory
        if not self.inventory.is_valid_stock(stock):
            raise InvalidProductData(f"Invalid stock: {stock}")

        # Business rule: check for duplicates
        existing = self.repo.find_by_name(name)
        if existing:
            raise InvalidProductData(f"Product '{name}' already exists")

        # Delegate to repository (data layer)
        product = self.repo.create(
            name=name,
            price=price,
            stock=stock,
            category=category,
        )
        return product

    def delete_product(self, product_id: int):
        """Delete product with business rule check."""
        product = self.get_product(product_id)

        # Business rule: can't delete if pending orders exist
        # (Real implementation would call OrderService)
        # ...

        self.repo.delete(product_id)

    def adjust_stock(self, product_id: int, delta: int):
        """Adjust stock (used by order service)."""
        product = self.get_product(product_id)

        new_stock = product.stock + delta
        if new_stock < 0:
            raise InvalidProductData(f"Insufficient stock for product {product_id}")

        return self.repo.update_stock(product_id, new_stock)
```

### Business Rules (Pure Logic)

```python
# src/business/rules/pricing_rules.py
from decimal import Decimal


class PricingRules:
    """Pure business rules — no I/O, no DB, no framework."""

    MIN_PRICE = Decimal("0.01")
    MAX_PRICE = Decimal("999999.99")

    def is_valid_price(self, price: Decimal) -> bool:
        return self.MIN_PRICE <= price <= self.MAX_PRICE

    def calculate_discount(
        self,
        base_price: Decimal,
        discount_percent: int,
    ) -> Decimal:
        """Apply discount to base price."""
        if not 0 <= discount_percent <= 100:
            raise ValueError("Discount must be 0-100%")
        discount = base_price * Decimal(discount_percent) / Decimal(100)
        return base_price - discount

    def calculate_tax(self, price: Decimal, tax_rate: Decimal = Decimal("0.18")) -> Decimal:
        """India GST = 18% by default."""
        return price * tax_rate

    def calculate_total(
        self,
        base_price: Decimal,
        discount_percent: int = 0,
        tax_rate: Decimal = Decimal("0.18"),
    ) -> Decimal:
        """Full pricing calculation."""
        after_discount = self.calculate_discount(base_price, discount_percent)
        tax = self.calculate_tax(after_discount, tax_rate)
        return after_discount + tax


# src/business/rules/inventory_rules.py
class InventoryRules:
    LOW_STOCK_THRESHOLD = 10
    MAX_STOCK = 100000

    def is_valid_stock(self, stock: int) -> bool:
        return 0 <= stock <= self.MAX_STOCK

    def needs_reorder(self, current_stock: int) -> bool:
        return current_stock < self.LOW_STOCK_THRESHOLD

    def can_fulfill_order(self, current_stock: int, requested_qty: int) -> bool:
        return current_stock >= requested_qty
```

### Order Service (Cross-Cutting Logic)

```python
# src/business/services/order_service.py
from decimal import Decimal
from typing import List
from sqlalchemy.orm import Session

from src.data.repositories.order_repo import OrderRepository
from src.business.services.product_service import ProductService
from src.business.services.payment_service import PaymentService
from src.business.rules.pricing_rules import PricingRules
from src.business.exceptions import OrderError, InsufficientStock


class OrderService:
    """
    Cross-cutting: orchestrates product + payment + order.
    Shows monolith advantage: easy to call other services directly.
    """

    def __init__(self, db: Session):
        self.repo = OrderRepository(db)
        self.product_svc = ProductService(db)
        self.payment_svc = PaymentService(db)
        self.pricing = PricingRules()
        self.db = db

    def place_order(
        self,
        user_id: int,
        items: List[dict],   # [{"product_id": 1, "qty": 2}]
        payment_method: str,
    ):
        """
        Multi-step transactional flow:
        1. Validate products + stock
        2. Calculate total
        3. Charge payment
        4. Decrement stock
        5. Create order
        """
        try:
            # 1. Validate all products
            product_details = []
            total = Decimal("0")
            for item in items:
                product = self.product_svc.get_product(item["product_id"])
                if product.stock < item["qty"]:
                    raise InsufficientStock(f"Product {product.name} out of stock")
                product_details.append({
                    "product": product,
                    "qty": item["qty"],
                })
                total += product.price * item["qty"]

            # 2. Calculate total with tax
            total_with_tax = self.pricing.calculate_total(
                total,
                discount_percent=0,
                tax_rate=Decimal("0.18"),
            )

            # 3. Charge payment (synchronous in monolith)
            payment = self.payment_svc.charge(
                user_id=user_id,
                amount=total_with_tax,
                method=payment_method,
            )

            # 4. Decrement stock
            for detail in product_details:
                self.product_svc.adjust_stock(
                    detail["product"].id,
                    -detail["qty"],
                )

            # 5. Create order
            order = self.repo.create(
                user_id=user_id,
                total_amount=total_with_tax,
                payment_id=payment.id,
                items=items,
            )

            self.db.commit()  # All in same DB transaction (monolith advantage)
            return order

        except Exception as e:
            self.db.rollback()
            raise OrderError(str(e))
```

### Custom Exceptions

```python
# src/business/exceptions.py
class BusinessException(Exception):
    """Base business exception."""
    pass


class ProductNotFound(BusinessException):
    pass


class InvalidProductData(BusinessException):
    pass


class OrderError(BusinessException):
    pass


class InsufficientStock(OrderError):
    pass


class PaymentFailed(BusinessException):
    pass


class UserNotFound(BusinessException):
    pass
```

---

## 4. 💾 Data Access Layer

> **The plumbing.** Only this layer talks to the database.

### SQLAlchemy Database Setup

```python
# src/data/database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from src.core.config import settings

# Single shared engine (monolith advantage)
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=20,
    max_overflow=10,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


async def init_db():
    """Create tables if not exist (dev only — use Alembic in prod)."""
    Base.metadata.create_all(bind=engine)
```

### Models (SQLAlchemy)

```python
# src/data/models/product.py
from sqlalchemy import Column, Integer, String, Numeric, DateTime, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.data.database import Base


class Product(Base):
    """Database model — owned by data layer."""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, unique=True)
    price = Column(Numeric(10, 2), nullable=False)
    stock = Column(Integer, nullable=False, default=0)
    category = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("idx_products_category", "category"),
        Index("idx_products_name", "name"),
    )


# src/data/models/order.py
class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    total_amount = Column(Numeric(10, 2), nullable=False)
    payment_id = Column(Integer, nullable=False)
    status = Column(String(50), default="pending")
    created_at = Column(DateTime, server_default=func.now())

    items = relationship("OrderItem", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, nullable=False)
    quantity = Column(Integer, nullable=False)
    price_at_purchase = Column(Numeric(10, 2), nullable=False)

    order = relationship("Order", back_populates="items")
```

### Repository (Data Access)

```python
# src/data/repositories/product_repo.py
from typing import List, Optional
from decimal import Decimal
from sqlalchemy.orm import Session

from src.data.models.product import Product


class ProductRepository:
    """
    DATA LAYER:
    - Only this class talks to the DB
    - Returns SQLAlchemy models OR domain entities (preferred)
    - NO BUSINESS LOGIC HERE
    """

    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, product_id: int) -> Optional[Product]:
        return self.db.query(Product).filter(Product.id == product_id).first()

    def find_by_name(self, name: str) -> Optional[Product]:
        return self.db.query(Product).filter(Product.name == name).first()

    def list_products(
        self,
        skip: int = 0,
        limit: int = 20,
        category: Optional[str] = None,
    ) -> List[Product]:
        query = self.db.query(Product)
        if category:
            query = query.filter(Product.category == category)
        return query.offset(skip).limit(limit).all()

    def create(
        self,
        name: str,
        price: Decimal,
        stock: int,
        category: str,
    ) -> Product:
        product = Product(
            name=name,
            price=price,
            stock=stock,
            category=category,
        )
        self.db.add(product)
        self.db.flush()  # Get ID without committing
        return product

    def update_stock(self, product_id: int, new_stock: int) -> Product:
        product = self.get_by_id(product_id)
        if product:
            product.stock = new_stock
            self.db.flush()
        return product

    def delete(self, product_id: int):
        product = self.get_by_id(product_id)
        if product:
            self.db.delete(product)
            self.db.flush()
```

---

## 5. Configuration (Cross-Cutting)

```python
# src/core/config.py
from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    """All app config in one place."""

    # App
    app_name: str = "E-Commerce Monolith"
    environment: str = "development"
    debug: bool = False

    # Database
    database_url: str = "postgresql://user:pass@localhost:5432/ecommerce"

    # Security
    secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30

    # CORS
    cors_origins: List[str] = ["*"]

    # Payment
    stripe_api_key: str = ""
    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
```

---

## 6. Docker Deployment (Single Unit)

### Dockerfile

```dockerfile
# Dockerfile — monolith packaged as one container
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen

# Copy entire app
COPY . .

# Single artifact
EXPOSE 8000
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### docker-compose.yml (3-tier — Single Process)

```yaml
# docker-compose.yml — 3-tier monolith
version: '3.8'

services:
  # The monolith app (all layers in single container)
  app:
    build: .
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgresql://ecommerce:secret@db:5432/ecommerce
    depends_on: [db]
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 5s
      retries: 3

  # Database
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: ecommerce
      POSTGRES_PASSWORD: secret
      POSTGRES_DB: ecommerce
    volumes:
      - dbdata:/var/lib/postgresql/data
    ports: ["5432:5432"]

volumes:
  dbdata:
```

### docker-compose.scaled.yml (Horizontal Scaling)

```yaml
# docker-compose.scaled.yml — multiple monolith instances behind LB
version: '3.8'

services:
  # Load balancer
  nginx:
    image: nginx:1.27
    ports: ["80:80"]
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on: [app1, app2, app3]

  # Multiple monolith instances (identical copies)
  app1:
    build: .
    environment:
      DATABASE_URL: postgresql://ecommerce:secret@db:5432/ecommerce
    depends_on: [db]

  app2:
    build: .
    environment:
      DATABASE_URL: postgresql://ecommerce:secret@db:5432/ecommerce
    depends_on: [db]

  app3:
    build: .
    environment:
      DATABASE_URL: postgresql://ecommerce:secret@db:5432/ecommerce
    depends_on: [db]

  # Shared database
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: ecommerce
      POSTGRES_PASSWORD: secret
      POSTGRES_DB: ecommerce
    volumes:
      - dbdata:/var/lib/postgresql/data

volumes:
  dbdata:
```

### Nginx Load Balancer Config

```nginx
# nginx.conf — load balances across monolith instances
worker_processes auto;

events {
    worker_connections 1024;
}

http {
    upstream monolith_backend {
        # Round-robin load balancing across 3 monolith instances
        server app1:8000;
        server app2:8000;
        server app3:8000;
    }

    server {
        listen 80;

        location / {
            proxy_pass http://monolith_backend;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;

            # Health checks
            proxy_next_upstream error timeout invalid_header http_500 http_502 http_503;
        }

        location /health {
            access_log off;
            proxy_pass http://monolith_backend/health;
        }
    }
}
```

### Run It

```bash
# Single instance (3-tier)
docker-compose up -d

# Horizontally scaled (3 monolith copies)
docker-compose -f docker-compose.scaled.yml up -d

# Verify
curl http://localhost:8000/health
# {"status":"healthy","version":"1.0.0"}

# Test load balancing
for i in {1..10}; do curl http://localhost/api/products; done
```

---

## 7. Migration: From 3-Tier to N-Tier

Sometimes you want to **physically separate** layers — N-tier deployment.

### Step 1: Split into Separate Services (but still monolithic at code level)

```yaml
# docker-compose.ntier.yml — N-tier deployment
version: '3.8'

services:
  # Tier 1: Web/UI server
  web:
    image: nginx:1.27
    ports: ["80:80"]
    volumes:
      - ./web/dist:/usr/share/nginx/html   # Static React build
      - ./nginx-web.conf:/etc/nginx/nginx.conf

  # Tier 2: Application server (business logic)
  app:
    build:
      context: .
      dockerfile: Dockerfile.app   # Only loads business + presentation
    environment:
      DATABASE_URL: postgresql://ecommerce:secret@db-server:5432/ecommerce
      REPOSITORY_SERVICE_URL: http://repo-service:8001
    depends_on: [repo-service]

  # Tier 3: Repository/Data service (data layer only)
  repo-service:
    build:
      context: .
      dockerfile: Dockerfile.repo  # Only data layer
    environment:
      DATABASE_URL: postgresql://ecommerce:secret@db-server:5432/ecommerce
    depends_on: [db-server]

  # Tier 4: Database server
  db-server:
    image: postgres:16
    environment:
      POSTGRES_USER: ecommerce
      POSTGRES_PASSWORD: secret
      POSTGRES_DB: ecommerce
    volumes:
      - dbdata:/var/lib/postgresql/data

volumes:
  dbdata:
```

### Step 2: Wrap Data Layer as Service

```python
# src/data_service/main.py — Standalone repository service
from fastapi import FastAPI, Depends
from src.data.repositories.product_repo import ProductRepository
from src.data.database import SessionLocal, init_db

app = FastAPI(title="Repository Service")


@app.on_event("startup")
async def startup():
    await init_db()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/internal/products/{product_id}")
def get_product(product_id: int, db=Depends(get_db)):
    """Internal API for app tier to call."""
    repo = ProductRepository(db)
    product = repo.get_by_id(product_id)
    return {
        "id": product.id,
        "name": product.name,
        "price": float(product.price),
        "stock": product.stock,
    } if product else None
```

### Step 3: App Tier Calls Repository Service

```python
# src/business/services/product_service.py — N-tier version
import httpx
from src.core.config import settings


class ProductService:
    """Business layer — now calls repository over HTTP."""

    def __init__(self, db_session=None):  # db_session no longer needed
        self.repo_url = settings.repository_service_url

    async def get_product(self, product_id: int):
        """Network call to repository service."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{self.repo_url}/internal/products/{product_id}")
            if response.status_code == 404:
                raise ProductNotFound(f"Product {product_id}")
            return response.json()
```

### Trade-offs (3-tier vs N-tier)

```
3-tier (in-process):
  ✅ Fast (function calls)
  ✅ Simple
  ❌ Can't scale layers independently

N-tier (network):
  ✅ Scale per tier
  ✅ Different tech per tier (e.g., Go for repo, Python for app)
  ❌ Network latency
  ❌ More operational complexity
```

---

## 8. Testing at Each Layer

### Test Structure

```
tests/
├── unit/
│   ├── test_business/
│   │   ├── test_product_service.py   ← Business logic tests
│   │   └── test_pricing_rules.py     ← Pure rules tests
│   └── test_data/
│       └── test_product_repo.py      ← Data layer tests
└── integration/
    └── test_api/
        └── test_products_endpoint.py  ← E2E API tests
```

### Unit Test: Business Logic

```python
# tests/unit/test_business/test_pricing_rules.py
from decimal import Decimal
import pytest
from src.business.rules.pricing_rules import PricingRules


@pytest.fixture
def pricing():
    return PricingRules()


def test_valid_price(pricing):
    assert pricing.is_valid_price(Decimal("100"))
    assert not pricing.is_valid_price(Decimal("0"))
    assert not pricing.is_valid_price(Decimal("1000000"))


def test_calculate_discount(pricing):
    result = pricing.calculate_discount(Decimal("100"), 20)
    assert result == Decimal("80")


def test_calculate_total_with_tax_and_discount(pricing):
    # 100 - 20% discount = 80
    # 80 + 18% tax = 94.40
    result = pricing.calculate_total(Decimal("100"), 20, Decimal("0.18"))
    assert result == Decimal("94.40")
```

### Unit Test: Service Layer

```python
# tests/unit/test_business/test_product_service.py
from unittest.mock import MagicMock
from decimal import Decimal
import pytest

from src.business.services.product_service import ProductService
from src.business.exceptions import ProductNotFound, InvalidProductData


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def service(mock_db, monkeypatch):
    # Mock the repository
    mock_repo = MagicMock()
    monkeypatch.setattr(
        "src.business.services.product_service.ProductRepository",
        lambda db: mock_repo,
    )
    svc = ProductService(mock_db)
    svc.repo = mock_repo  # Easier access
    return svc


def test_get_product_not_found(service):
    service.repo.get_by_id.return_value = None
    with pytest.raises(ProductNotFound):
        service.get_product(999)


def test_create_product_invalid_price(service):
    with pytest.raises(InvalidProductData):
        service.create_product(
            name="Test",
            price=Decimal("0"),    # Invalid
            stock=10,
            category="Books",
        )


def test_create_product_duplicate_name(service):
    service.repo.find_by_name.return_value = MagicMock()  # Existing
    with pytest.raises(InvalidProductData) as exc:
        service.create_product(
            name="Existing",
            price=Decimal("100"),
            stock=10,
            category="Books",
        )
    assert "already exists" in str(exc.value)
```

### Integration Test: API

```python
# tests/integration/test_api/test_products_endpoint.py
import pytest
from fastapi.testclient import TestClient
from src.main import app
from src.data.database import init_db


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_list_products(client):
    response = client.get("/api/products/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_create_product(client):
    response = client.post(
        "/api/products/",
        json={
            "name": "Test Product",
            "price": 99.99,
            "stock": 100,
            "category": "Test",
        },
        headers={"Authorization": "Bearer admin-token"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Product"


def test_get_nonexistent_product(client):
    response = client.get("/api/products/99999")
    assert response.status_code == 404
```

---

## 9. Common Monolith Mistakes

### Mistake 1: Mixing Layers

```python
# ❌ BAD — UI layer doing business logic
@router.get("/products/{id}")
def get_product(id: int, db=Depends(get_db)):
    # ❌ DB query in router
    product = db.query(Product).filter(Product.id == id).first()
    # ❌ Business logic in router
    if product.stock < 10:
        product.warning = "Low stock!"
    return product

# ✅ GOOD — clear layering
@router.get("/products/{id}")
def get_product(id: int, db=Depends(get_db)):
    service = ProductService(db)
    product = service.get_product_with_warnings(id)
    return ProductResponse.from_orm(product)
```

### Mistake 2: Circular Dependencies

```python
# ❌ BAD — circular import
# order_service.py
from src.business.services.product_service import ProductService

# product_service.py
from src.business.services.order_service import OrderService  # CIRCULAR!

# ✅ GOOD — use dependency injection or events
# product_service.py
class ProductService:
    def __init__(self, db, order_check_fn=None):
        self.order_check = order_check_fn  # Inject as function
```

### Mistake 3: Database Leak Through UI

```python
# ❌ BAD — exposing SQLAlchemy models directly to UI
@router.get("/products")
def list_products(db=Depends(get_db)):
    return db.query(Product).all()  # Leaks DB schema!

# ✅ GOOD — return Pydantic schemas
@router.get("/products", response_model=List[ProductResponse])
def list_products(db=Depends(get_db)):
    products = ProductService(db).list_products()
    return [ProductResponse.from_orm(p) for p in products]
```

### Mistake 4: Global Database Session

```python
# ❌ BAD — shared session across requests
db = SessionLocal()  # Created once at startup, used everywhere

# ✅ GOOD — per-request session via dependency
def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### Mistake 5: Hardcoded Configs

```python
# ❌ BAD — secrets in code
DATABASE_URL = "postgresql://prod-user:secret123@db.acme.com/prod"
STRIPE_KEY = "sk_live_xxx"

# ✅ GOOD — env-based config
from src.core.config import settings
DATABASE_URL = settings.database_url  # From env
```

---

## 10. Migration to Modular Monolith (Preview)

When monolith starts hurting, **first step** is modularizing **without** going to microservices.

```
ecommerce_monolith/
├── modules/                       # NEW: Modular structure
│   ├── catalog/
│   │   ├── presentation/
│   │   ├── business/
│   │   └── data/
│   ├── orders/
│   │   ├── presentation/
│   │   ├── business/
│   │   └── data/
│   ├── payments/
│   │   └── ...
│   └── shared/                    # Cross-module shared
│       └── ...
└── main.py
```

**Each module is internally layered**, but **externally treated as a black box**.

(Detail in Lecture 4 of Section 2)

---

## 11. Pre-Production Checklist

```markdown
# Monolith Production Readiness Checklist

## Code Quality
- [ ] Layers cleanly separated (no leaks)
- [ ] Each service has single responsibility
- [ ] No circular dependencies
- [ ] Pydantic schemas separate from SQLAlchemy models
- [ ] Custom exceptions for business errors

## Database
- [ ] Connection pooling configured
- [ ] Alembic migrations set up
- [ ] Indexes on commonly queried columns
- [ ] Backup strategy in place
- [ ] Health check tests DB connectivity

## Security
- [ ] No hardcoded secrets
- [ ] Auth/authz on all endpoints
- [ ] Input validation via Pydantic
- [ ] SQL injection prevented (using ORM properly)
- [ ] Rate limiting

## Performance
- [ ] Connection pooling
- [ ] Caching where applicable
- [ ] Database queries N+1 free
- [ ] Async I/O where needed

## Deployment
- [ ] Dockerfile multi-stage builds
- [ ] docker-compose for local dev
- [ ] CI/CD pipeline
- [ ] Health check endpoint
- [ ] Load balancer config (if scaling)

## Observability
- [ ] Structured logging
- [ ] Metrics (Prometheus)
- [ ] Error tracking (Sentry)
- [ ] Request tracing
```

---

## 12. Summary

### Key Takeaways

```
✅ Monolithic + Layered = Powerful combo for early-stage products
✅ Folder structure reflects architecture decisions
✅ Each layer has clear responsibility (no mixing)
✅ Same code can be deployed as 3-tier OR N-tier
✅ Tests at each layer catch different bugs
✅ Start simple, evolve as needed
```

### Quick Decision Framework

```
Q: Should you go monolith?
   ├── Yes if: < 10 engineers, < 1M users, MVP/startup, internal tool
   └── Consider modular monolith if: > 10 engineers OR > 1M users

Q: 3-tier or N-tier?
   ├── 3-tier: Simple, fast (default for monoliths)
   └── N-tier: Need to scale layers independently
```

### Files We Created

```
✅ docker-compose.yml (3-tier)
✅ docker-compose.scaled.yml (Horizontal scaling)
✅ docker-compose.ntier.yml (N-tier)
✅ Dockerfile
✅ nginx.conf (Load balancer)

✅ src/presentation/ (UI layer)
✅ src/business/ (Logic layer)
✅ src/data/ (Data layer)
✅ src/core/ (Config + utilities)

✅ tests/ (Unit + integration)
```

---

## 13. Action Items

1. ✅ **Build this entire monolith** end-to-end
2. ✅ **Run docker-compose up** and test all endpoints
3. ✅ **Scale horizontally** with docker-compose.scaled.yml
4. ✅ **Write tests** for one service at each layer
5. ✅ **Identify naturally grouped features** for future modularization

---

## 14. Related Resources

- [Phase2_FastAPI/](../../Phase2_FastAPI/) — FastAPI deep dive
- [Phase2_Database/](../../Phase2_Database/) — PostgreSQL patterns
- [Phase3_DevOps/01_docker.md](../../Phase3_DevOps/01_docker.md) — Docker
- [Phase3_DevOps/06_kubernetes_helm.md](../../Phase3_DevOps/06_kubernetes_helm.md) — K8s
- [Section_01_Foundations/02_Practical_Hands_On.md](../Section_01_Foundations/02_Practical_Hands_On.md) — Food delivery example
