# 04 — SQLAlchemy 2.0 + FastAPI + MySQL Integration
### Interview Q&A Format | Hinglish Style

---

## Section A — SQLAlchemy 2.0 with MySQL: Engine Setup

```python
# pip install sqlalchemy pymysql aiomysql cryptography aiosqlite fastapi uvicorn pydantic

# ─── Sync Engine (scripts, migrations, etc.) ───
from sqlalchemy import create_engine

# MySQL connection string formats:
# pymysql (sync):     mysql+pymysql://user:pass@host:3306/dbname
# aiomysql (async):   mysql+aiomysql://user:pass@host:3306/dbname
# mysqlconnector:     mysql+mysqlconnector://user:pass@host:3306/dbname

engine = create_engine(
    "mysql+pymysql://myuser:mypass@localhost:3306/mydb",
    pool_size=10,           # Connection pool mein kitne connections rakho
    max_overflow=20,        # pool_size ke upar extra connections (spike ke liye)
    pool_pre_ping=True,     # Use karne se pehle connection alive hai ya nahi check karo
    pool_recycle=3600,      # 1 hour baad connection recycle (MySQL 8hr default timeout se pehle)
    echo=False,             # True = har SQL query console pe print ho (sirf debug mein)
    connect_args={
        "charset": "utf8mb4",   # Emoji + full Unicode support
    }
)

# ─── Async Engine (FastAPI ke saath) ───
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

async_engine = create_async_engine(
    "mysql+aiomysql://myuser:mypass@localhost:3306/mydb",
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
    pool_recycle=1800,      # 30 min recycle (safer for busy apps)
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Commit ke baad objects still accessible rahein
)
```

---

## Section B — SQLAlchemy Models (MySQL-specific)

```python
from sqlalchemy import (
    Column, Integer, String, Text, Numeric, Boolean,
    DateTime, JSON, ForeignKey, Index, func
)
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
from sqlalchemy.dialects.mysql import (
    TINYINT, MEDIUMTEXT, LONGTEXT, BIGINT,
    VARCHAR, CHAR,
    DOUBLE,
    JSON as MYSQL_JSON
)
from datetime import datetime

class Base(DeclarativeBase):
    pass

class Product(Base):
    __tablename__ = "products"

    # mapped_column = SQLAlchemy 2.0 style (type-safe, IDE-friendly)
    id          : Mapped[int]       = mapped_column(Integer, primary_key=True, autoincrement=True)
    sku         : Mapped[str]       = mapped_column(String(50), unique=True, nullable=False)
    name        : Mapped[str]       = mapped_column(String(200), nullable=False)
    description : Mapped[str|None]  = mapped_column(Text, nullable=True)
    price       : Mapped[float]     = mapped_column(Numeric(10, 2), nullable=False)   # 10 digits, 2 decimal
    stock       : Mapped[int]       = mapped_column(Integer, default=0, nullable=False)
    category    : Mapped[str]       = mapped_column(String(50), nullable=False)
    is_active   : Mapped[bool]      = mapped_column(Boolean, default=True)
    tags        : Mapped[dict|None] = mapped_column(JSON, nullable=True)              # MySQL JSON column
    created_at  : Mapped[datetime]  = mapped_column(DateTime, server_default=func.now())
    updated_at  : Mapped[datetime]  = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    order_items : Mapped[list["OrderItem"]] = relationship(back_populates="product")

    __table_args__ = (
        Index("idx_category_active", "category", "is_active"),  # Composite index
        Index("idx_price", "price"),
        {
            "mysql_engine":  "InnoDB",      # ACID transactions + FK support
            "mysql_charset": "utf8mb4",     # Emoji support
        },
    )

    def __repr__(self):
        return f"<Product(id={self.id}, name={self.name!r}, price={self.price})>"


class User(Base):
    __tablename__ = "users"

    id         : Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    username   : Mapped[str]      = mapped_column(String(50), unique=True, nullable=False)
    email      : Mapped[str]      = mapped_column(String(200), unique=True, nullable=False)
    hashed_pwd : Mapped[str]      = mapped_column(String(255), nullable=False)
    is_active  : Mapped[bool]     = mapped_column(Boolean, default=True)
    created_at : Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    orders : Mapped[list["Order"]] = relationship(back_populates="user")


class Order(Base):
    __tablename__ = "orders"

    id           : Mapped[int]      = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id      : Mapped[int|None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    total_amount : Mapped[float]    = mapped_column(Numeric(10, 2), nullable=False)
    status       : Mapped[str]      = mapped_column(String(20), default="pending", nullable=False)
    created_at   : Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user        : Mapped["User"]            = relationship(back_populates="orders")
    order_items : Mapped[list["OrderItem"]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_user_status", "user_id", "status"),
        Index("idx_created_at", "created_at"),
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id         : Mapped[int]   = mapped_column(Integer, primary_key=True, autoincrement=True)
    order_id   : Mapped[int]   = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"))
    product_id : Mapped[int]   = mapped_column(ForeignKey("products.id"))
    quantity   : Mapped[int]   = mapped_column(Integer, nullable=False)
    unit_price : Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    order   : Mapped["Order"]   = relationship(back_populates="order_items")
    product : Mapped["Product"] = relationship(back_populates="order_items")
```

---

## Section C — Repository Pattern (SQLAlchemy + MySQL)

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.orm import selectinload, joinedload
import asyncio

class ProductRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_id(self, id: int) -> Product | None:
        result = await self.session.execute(
            select(Product).where(Product.id == id, Product.is_active == True)
        )
        return result.scalar_one_or_none()

    async def get_by_sku(self, sku: str) -> Product | None:
        result = await self.session.execute(
            select(Product).where(Product.sku == sku)
        )
        return result.scalar_one_or_none()

    async def search(
        self,
        q: str | None = None,
        category: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> tuple[list[Product], int]:

        query = select(Product).where(Product.is_active == True)
        count_query = select(func.count()).select_from(Product).where(Product.is_active == True)

        filters = []
        if q:
            filters.append(
                or_(
                    Product.name.ilike(f"%{q}%"),
                    Product.description.ilike(f"%{q}%")
                )
            )
        if category:
            filters.append(Product.category == category)
        if min_price is not None:
            filters.append(Product.price >= min_price)
        if max_price is not None:
            filters.append(Product.price <= max_price)

        if filters:
            query = query.where(and_(*filters))
            count_query = count_query.where(and_(*filters))

        sort_col = getattr(Product, sort_by, Product.created_at)
        query = query.order_by(sort_col.desc() if sort_order == "desc" else sort_col.asc())

        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        # Dono queries parallel mein run karo (performance improvement)
        result, count_result = await asyncio.gather(
            self.session.execute(query),
            self.session.execute(count_query)
        )

        return result.scalars().all(), count_result.scalar()

    async def create(self, data: dict) -> Product:
        product = Product(**data)
        self.session.add(product)
        await self.session.flush()       # ID generate ho jaata hai bina commit ke
        await self.session.refresh(product)  # DB se fresh data load
        return product

    async def bulk_upsert(self, items: list[dict]) -> int:
        from sqlalchemy.dialects.mysql import insert as mysql_insert

        stmt = mysql_insert(Product).values(items)
        # MySQL-specific: ON DUPLICATE KEY UPDATE
        stmt = stmt.on_duplicate_key_update(
            price=stmt.inserted.price,
            stock=stmt.inserted.stock,
            updated_at=func.now()
        )
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount


class OrderRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_with_items(self, order_id: int) -> Order | None:
        result = await self.session.execute(
            select(Order)
            .options(
                selectinload(Order.order_items).selectinload(OrderItem.product),
                joinedload(Order.user)
            )
            .where(Order.id == order_id)
        )
        return result.unique().scalar_one_or_none()

    async def get_user_orders(self, user_id: int) -> list[Order]:
        result = await self.session.execute(
            select(Order)
            .where(Order.user_id == user_id)
            .options(selectinload(Order.order_items))
            .order_by(Order.created_at.desc())
        )
        return result.scalars().all()
```

---

## Section D — MySQL-Specific SQLAlchemy Features

```python
# 1. INSERT ... ON DUPLICATE KEY UPDATE (MySQL ka upsert)
from sqlalchemy.dialects.mysql import insert as mysql_insert

async def upsert_product(session: AsyncSession, data: dict):
    stmt = mysql_insert(Product).values(**data)
    stmt = stmt.on_duplicate_key_update(
        price=stmt.inserted.price,
        # Conditional update: agar naya stock > 0 toh update, warna purana rakho
        stock=func.IF(
            stmt.inserted.stock > 0,
            stmt.inserted.stock,
            Product.stock
        ),
    )
    await session.execute(stmt)
    await session.commit()

# 2. Raw SQL with text() — jab ORM kaafi na ho
from sqlalchemy import text

async def get_category_stats(session: AsyncSession):
    result = await session.execute(text("""
        SELECT
            category,
            COUNT(*) as product_count,
            AVG(price) as avg_price,
            SUM(stock * price) as inventory_value
        FROM products
        WHERE is_active = 1
        GROUP BY category
        ORDER BY inventory_value DESC
    """))
    return result.mappings().all()   # dict-like rows milte hain

# 3. MySQL JSON column queries
# JSON_CONTAINS — array mein value hai ya nahi
result = await session.execute(
    select(Product).where(
        func.json_contains(Product.tags, '"bestseller"')
    )
)

# JSON_EXTRACT — nested value nikalo
result = await session.execute(
    select(
        Product,
        func.json_extract(Product.tags, '$.brand').label('brand')
    )
)

# 4. Bulk insert with core (ORM se faster for large data)
from sqlalchemy import insert

await session.execute(
    insert(Product),
    [{"sku": "A1", "name": "Item 1", "price": 100, "category": "books"},
     {"sku": "A2", "name": "Item 2", "price": 200, "category": "books"}]
)
```

---

## Section E — FastAPI + MySQL Complete Production Setup

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

# ─── Database ───
DATABASE_URL = "mysql+aiomysql://myuser:mypass@localhost:3306/mydb?charset=utf8mb4"

async_engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
    pool_recycle=1800,
)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)

async def get_session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session    # Context manager auto-close + rollback on error

# ─── Pydantic Schemas ───
class ProductCreate(BaseModel):
    sku: str = Field(..., min_length=3, max_length=50)
    name: str = Field(..., min_length=2, max_length=200)
    description: str | None = None
    price: float = Field(..., gt=0)
    stock: int = Field(default=0, ge=0)
    category: str
    tags: dict | None = None

class ProductResponse(BaseModel):
    id: int
    sku: str
    name: str
    price: float
    stock: int
    category: str
    is_active: bool

    model_config = {"from_attributes": True}   # ORM objects → Pydantic (v2 style)

class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    page: int
    page_size: int
    pages: int

# ─── Lifespan (startup + shutdown) ───
@asynccontextmanager
async def lifespan(app: FastAPI):
    # STARTUP: tables create karo
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("MySQL tables ready")
    yield
    # SHUTDOWN: pool gracefully close
    await async_engine.dispose()
    print("MySQL connection pool closed")

app = FastAPI(lifespan=lifespan)

# ─── Endpoints ───
@app.post("/products", response_model=ProductResponse, status_code=201)
async def create_product(
    data: ProductCreate,
    session: AsyncSession = Depends(get_session)
):
    repo = ProductRepository(session)
    existing = await repo.get_by_sku(data.sku)
    if existing:
        raise HTTPException(409, f"SKU '{data.sku}' already exists")
    product = await repo.create(data.model_dump())
    await session.commit()
    return product

@app.get("/products", response_model=ProductListResponse)
async def list_products(
    q: str | None = Query(None, description="Search in name/description"),
    category: str | None = Query(None),
    min_price: float | None = Query(None, ge=0),
    max_price: float | None = Query(None, ge=0),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sort_by: str = Query("created_at"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    session: AsyncSession = Depends(get_session)
):
    repo = ProductRepository(session)
    products, total = await repo.search(
        q=q, category=category,
        min_price=min_price, max_price=max_price,
        page=page, page_size=page_size,
        sort_by=sort_by, sort_order=sort_order
    )
    return ProductListResponse(
        items=products,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size
    )

@app.get("/products/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    session: AsyncSession = Depends(get_session)
):
    product = await ProductRepository(session).get_by_id(product_id)
    if not product:
        raise HTTPException(404, "Product not found")
    return product
```

---

## Interview Q&A

---

**Q1: pool_recycle MySQL mein kyu zaruri hai?**

**A:** MySQL server ka ek default `wait_timeout` hota hai — usually **8 ghante** (28800 seconds). Iska matlab: agar ek connection 8 ghante tak idle rahe, MySQL server us connection ko **unilaterally band** kar deta hai. Ab SQLAlchemy ka pool woh connection "alive" samajhta hai aur use karne ki koshish karta hai — tab `OperationalError: (2006, 'MySQL server has gone away')` aata hai.

**pool_recycle** SQLAlchemy ko bolta hai: "X seconds baad is connection ko forcefully replace kar do" — server ke timeout se **pehle**.

```python
engine = create_engine(
    url,
    pool_recycle=1800,   # 30 min — MySQL ke 8hr timeout se bahut pehle
    pool_pre_ping=True,  # Double safety: use se pehle ek ping bhejo
)
```

`pool_pre_ping=True` ek extra safety layer hai — `SELECT 1` bhejta hai. Agar connection dead hai, naya le leta hai. Dono saath use karo production mein.

---

**Q2: mysql+pymysql vs mysql+aiomysql — kab kya use karo?**

**A:**

| Feature | `mysql+pymysql` | `mysql+aiomysql` |
|---|---|---|
| Type | Synchronous | Asynchronous |
| Use with | Flask, scripts, Celery, Alembic | FastAPI, async frameworks |
| Performance | Thread-per-request | Event loop — high concurrency |
| Install | `pip install pymysql` | `pip install aiomysql` |

- **FastAPI** async endpoints ke liye: `mysql+aiomysql` — warna `await` karne pe thread block hoga.
- **Alembic migrations**: sync connection chahiye — `pymysql` use karo (ya `run_sync` wrapper).
- **Celery workers**: sync — `pymysql`.
- **Background scripts**: sync `pymysql` simpler hai.

```python
# Alembic env.py mein sync connection
def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        # mysql+pymysql URL use karo yahan
    )
```

---

**Q3: ON DUPLICATE KEY UPDATE vs INSERT IGNORE — kya fark?**

**A:** Dono MySQL-specific statements hain jo duplicate primary key / unique key conflict handle karte hain, lekin **behavior alag** hai:

```sql
-- INSERT IGNORE: conflict pe silently skip karo, koi update nahi
INSERT IGNORE INTO products (sku, name, price) VALUES ('A1', 'Widget', 100);
-- Result: agar A1 pehle se hai → row skipped, purana data unchanged

-- ON DUPLICATE KEY UPDATE: conflict pe specified columns update karo
INSERT INTO products (sku, name, price) VALUES ('A1', 'Widget', 150)
ON DUPLICATE KEY UPDATE price = VALUES(price), updated_at = NOW();
-- Result: agar A1 pehle se hai → price 150 ho jaata hai
```

SQLAlchemy mein:
```python
from sqlalchemy.dialects.mysql import insert as mysql_insert

# ON DUPLICATE KEY UPDATE (recommended upsert)
stmt = mysql_insert(Product).values(sku="A1", name="Widget", price=150)
stmt = stmt.on_duplicate_key_update(
    price=stmt.inserted.price,
    updated_at=func.now()
)

# INSERT IGNORE (sirf naya insert, existing touch mat karo)
stmt = mysql_insert(Product).values(sku="A1", name="Widget", price=150)
stmt = stmt.prefix_with("IGNORE")
```

**Kab kya:**
- `INSERT IGNORE`: seed data, import jobs jahan existing data protect karna ho.
- `ON DUPLICATE KEY UPDATE`: inventory sync, price updates — latest data chahiye.

---

**Q4: selectinload vs joinedload MySQL mein — kya fark?**

**A:** Dono SQLAlchemy ke **eager loading** strategies hain — N+1 problem solve karte hain.

```python
# joinedload: ek hi SQL query mein JOIN karta hai
select(Order).options(joinedload(Order.user))
# SQL: SELECT orders.*, users.* FROM orders LEFT JOIN users ON ...
# Best for: to-one relationships (Order → User)

# selectinload: 2 queries — pehle main, phir related
select(Order).options(selectinload(Order.order_items))
# SQL 1: SELECT * FROM orders WHERE id IN (...)
# SQL 2: SELECT * FROM order_items WHERE order_id IN (1, 2, 3, ...)
# Best for: to-many relationships (Order → many OrderItems)
```

**MySQL performance consideration:**
- `joinedload` to-many relationships ke saath **data duplication** karta hai — agar 1 order ke 100 items hain, toh 100 rows aati hain orders columns ke saath (wasted bandwidth).
- `selectinload` 2 clean queries karta hai — MySQL ka query planner dono ko efficiently handle karta hai.
- **Rule of thumb**: to-one → `joinedload`, to-many → `selectinload`.

```python
# Combined (nested relationships)
select(Order).options(
    joinedload(Order.user),                                    # to-one
    selectinload(Order.order_items).selectinload(OrderItem.product)  # to-many → to-one
)
```

---

**Q5: FastAPI mein MySQL connection pool kaise manage karo?**

**A:** FastAPI mein proper connection management ke 3 layers hain:

**Layer 1: Engine (application-level singleton)**
```python
# Ek baar banao, app lifetime tak rakho
async_engine = create_async_engine(
    DATABASE_URL,
    pool_size=20,        # Minimum connections
    max_overflow=40,     # Burst ke liye extra
    pool_pre_ping=True,
    pool_recycle=1800,
)
```

**Layer 2: Session (request-level)**
```python
# Har request ko apna session milta hai
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()    # Error pe rollback
            raise
        # Context manager auto-closes session → connection pool mein wapas
```

**Layer 3: Lifespan (cleanup)**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await async_engine.dispose()  # App shutdown pe saare connections close
```

**Pool sizing formula:**
```
pool_size = (CPU cores * 2) + effective_spindle_count
# Typical: 10-20 for web apps
# max_overflow = pool_size * 2 (burst traffic ke liye)
```

Avoid karo: har request pe engine banana — bohot slow hoga. Engine ek baar banao.

---

**Q6: SQLAlchemy 2.0 mein func.now() vs datetime.utcnow() — kya prefer karo?**

**A:** Dono alag jagah kaam karte hain, aur **dono chahiye** — lekin alag purposes ke liye.

```python
# func.now() — server_default: MySQL SERVER pe NOW() call hota hai
created_at: Mapped[datetime] = mapped_column(
    DateTime, server_default=func.now()
)
# SQL: created_at DATETIME DEFAULT CURRENT_TIMESTAMP
# Best for: initial row creation (DB server ka time use hota hai)

# func.now() — onupdate: UPDATE pe MySQL trigger
updated_at: Mapped[datetime] = mapped_column(
    DateTime, server_default=func.now(), onupdate=func.now()
)
# SQL: ON UPDATE CURRENT_TIMESTAMP

# datetime.utcnow() — Python side timestamp (application layer)
from datetime import datetime, timezone
created_at = datetime.now(timezone.utc)  # UTC aware (preferred over utcnow())
```

**Prefer karo:**
- `server_default=func.now()` → DB columns ke liye (timezone-safe, consistent)
- `datetime.now(timezone.utc)` → Python objects, comparisons, business logic ke liye
- `datetime.utcnow()` → **deprecated in Python 3.12+**, avoid karo

**Gotcha:** `func.now()` MySQL server ka timezone use karta hai. Agar MySQL `UTC` pe set nahi hai, inconsistency aa sakti hai. Production mein MySQL timezone UTC pe set karo:
```sql
SET GLOBAL time_zone = '+00:00';
```

---

**Q7: MySQL JSON column queries SQLAlchemy mein kaise karo?**

**A:** MySQL 5.7.8+ mein native JSON type hai. SQLAlchemy `func` ke zariye MySQL JSON functions call kar sakte ho:

```python
from sqlalchemy import func, select
from sqlalchemy.orm import Session

# ─── JSON_CONTAINS: array mein value check ───
# SQL: WHERE JSON_CONTAINS(tags, '"bestseller"')
result = await session.execute(
    select(Product).where(
        func.json_contains(Product.tags, '"bestseller"')
    )
)

# ─── JSON_EXTRACT: nested value nikalo ───
# SQL: SELECT JSON_EXTRACT(tags, '$.brand') AS brand
result = await session.execute(
    select(
        Product,
        func.json_extract(Product.tags, '$.brand').label('brand')
    )
)

# ─── JSON_OVERLAPS (MySQL 8.0+): koi bhi value match ho ───
result = await session.execute(
    select(Product).where(
        func.json_overlaps(
            Product.tags,
            func.cast('["sale", "featured"]', MYSQL_JSON)
        )
    )
)

# ─── SQLAlchemy native JSON operators (cross-DB) ───
# Path operator → (dict access)
result = await session.execute(
    select(Product).where(
        Product.tags["brand"].as_string() == "Nike"
    )
)

# ─── UPDATE JSON field ───
from sqlalchemy import update

await session.execute(
    update(Product)
    .where(Product.id == 1)
    .values(tags=func.json_set(Product.tags, '$.discount', 10))
)
```

**Note:** SQLAlchemy ke `[]` JSON path operators SQLite/PostgreSQL ke saath bhi kaam karte hain, lekin `func.json_contains`, `func.json_extract` MySQL-specific hain — portability chahiye toh ORM-level filter prefer karo.
