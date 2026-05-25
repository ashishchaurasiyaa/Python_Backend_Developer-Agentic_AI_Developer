# 12. Repository Design Pattern

## What is the Repository Pattern?

The Repository Pattern provides an abstraction layer between the domain/business logic and the data access layer. It acts as a **collection-like interface** for accessing domain objects, hiding the details of data storage and retrieval (SQL queries, ORM calls, API requests) behind a clean, testable API. By centralizing data access logic, it prevents query duplication, makes code easier to test, and allows you to swap out the data source without touching business logic.

---

## Youngman India Scenario

At Youngman India (B2B scaffolding rental ERP), our Laravel codebase uses **~19 repositories** to manage data access across the application:

| Repository               | Purpose                                      |
|--------------------------|----------------------------------------------|
| `CustomerRepository`     | Customer master data, SAP sync, credit checks |
| `QuotationRepository`    | Quotation CRUD, status transitions            |
| `OrderRepository`        | Rental orders, scheduling, billing            |
| `InvoiceRepository`      | Invoice generation, SAP posting               |
| `ItemRepository`         | Scaffolding items, stock tracking             |
| `DepotRepository`        | Warehouse/depot management                    |
| `LogisticsRepository`    | Dispatch, delivery, vehicle tracking          |
| `UserRepository`         | User management, role-based access            |
| ... and 11 more          |                                              |

**The `CustomerRepository`** is central to our CRM module. It handles:
- **SAP reference lookups** — nightly sync between our app and SAP Business One
- **GSTN-based search** — for GST compliance and invoice validation
- **Credit control queries** — aggregating outstanding balances for the credit team
- **Role-based filtered views** — sales reps see only their customers, branch managers see branch customers, admins see everything

This demo recreates the core `CustomerRepository` in Django to demonstrate the pattern.

---

## Project Structure

```
12_repository/
├── manage.py
├── README.md
├── repository_project/
│   ├── __init__.py
│   ├── settings.py          # Django + DRF config
│   ├── urls.py               # Root URL conf
│   ├── wsgi.py
│   └── asgi.py
└── customers/
    ├── __init__.py
    ├── models.py              # Customer, CustomerContact, CustomerOutstanding
    ├── repositories.py        # BaseRepository (ABC) + CustomerRepository
    ├── serializers.py         # DRF serializers
    ├── views.py               # Thin API views delegating to repository
    ├── urls.py                # App URL routes
    ├── tests.py               # Unit + integration tests
    ├── admin.py
    ├── apps.py
    └── migrations/
```

---

## How to Run

```bash
# Install dependencies (from the design_patterns root)
pip install -r ../requirements.txt

# Run migrations
python manage.py migrate

# Start the dev server on port 8012
python manage.py runserver 8012

# Run tests
python manage.py test customers -v2
```

---

## API Endpoints

| Method | Endpoint                             | Description                          |
|--------|--------------------------------------|--------------------------------------|
| GET    | `/api/customers/`                    | List all customers                   |
| POST   | `/api/customers/`                    | Create a new customer                |
| GET    | `/api/customers/<id>/`               | Get customer detail with contacts    |
| PUT    | `/api/customers/<id>/`               | Update a customer                    |
| DELETE | `/api/customers/<id>/`               | Delete a customer                    |
| GET    | `/api/customers/search/?q=<query>`   | Search across company, name, phone, GSTN |
| GET    | `/api/customers/outstanding/`        | Customers with outstanding balances  |
| GET    | `/api/customers/business-type/?type=construction` | Filter by business type |

### curl Examples

```bash
# Create a customer
curl -X POST http://localhost:8012/api/customers/ \
  -H "Content-Type: application/json" \
  -d '{
    "company": "Metro Constructions Pvt Ltd",
    "first_name": "Rajesh",
    "last_name": "Sharma",
    "email": "rajesh@metroconstructions.in",
    "phone_number": "9876543210",
    "gstn": "27AABCM1234F1Z5",
    "credit_limit": "500000.00",
    "business_type": "construction",
    "is_verified": true
  }'

# List all customers
curl http://localhost:8012/api/customers/

# Get customer detail (with contacts and outstandings)
curl http://localhost:8012/api/customers/1/

# Update a customer
curl -X PUT http://localhost:8012/api/customers/1/ \
  -H "Content-Type: application/json" \
  -d '{"credit_rating": "A", "credit_limit": "750000.00"}'

# Search customers
curl "http://localhost:8012/api/customers/search/?q=Metro"

# Get customers with outstanding
curl http://localhost:8012/api/customers/outstanding/

# Filter by business type
curl "http://localhost:8012/api/customers/business-type/?type=construction"

# Delete a customer
curl -X DELETE http://localhost:8012/api/customers/1/
```

---

## The Pattern in Code

### 1. BaseRepository — Generic CRUD (Abstract)

```python
class BaseRepository(ABC):
    @abstractmethod
    def get_model(self):
        pass

    def all(self):
        return self.get_model().objects.all()

    def find(self, pk):
        try:
            return self.get_model().objects.get(pk=pk)
        except self.get_model().DoesNotExist:
            return None

    def create(self, data: dict):
        return self.get_model().objects.create(**data)

    def update(self, pk, data: dict): ...
    def delete(self, pk): ...
    def filter_by(self, **kwargs): ...
    def count(self): ...
```

### 2. CustomerRepository — Domain-Specific Queries

```python
class CustomerRepository(BaseRepository):
    def get_model(self):
        return Customer

    def find_by_sap_ref(self, sap_ref): ...
    def find_by_gstn(self, gstn): ...
    def get_verified_customers(self): ...
    def get_customers_with_outstanding(self):
        return Customer.objects.annotate(
            total_outstanding=Sum("outstandings__balance")
        ).filter(total_outstanding__gt=0)
    def search(self, query):
        return Customer.objects.filter(
            Q(company__icontains=query) | Q(first_name__icontains=query) | ...
        )
```

### 3. Thin Views — Only HTTP, No Data Logic

```python
class CustomerListView(APIView):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.repo = CustomerRepository()

    def get(self, request):
        customers = self.repo.all()            # <-- repository call
        serializer = CustomerSerializer(customers, many=True)
        return Response(serializer.data)
```

---

## Interview Talking Points

1. **What problem does Repository solve?**
   It decouples business logic from data access. Without it, queries leak into views, services, and serializers, making code hard to test and maintain. With 19 repositories at Youngman, each module has a single place for all its data queries.

2. **BaseRepository with generics:**
   The abstract `BaseRepository` provides CRUD for free — any new model repository only needs to implement `get_model()` and add domain-specific methods. DRY principle in action.

3. **Why not just use Django ORM directly in views?**
   - Query duplication: the same filter logic appears in 5 different views
   - Testing: you cannot mock `Customer.objects.filter(...)` easily, but you can mock `repo.search()`
   - Swappability: if you move from Django ORM to an external API (e.g., SAP RFC calls), only the repository changes
   - Single Responsibility: views handle HTTP, repositories handle data

4. **Real Youngman example — CustomerRepository:**
   Our Laravel `CustomerRepository` has ~35 methods including role-based scoping (`scopeForUser`), SAP sync helpers, credit control aggregations, and full-text search. The Django version here demonstrates the core pattern.

5. **Repository vs Active Record:**
   Django models use the Active Record pattern (`customer.save()`). The Repository pattern wraps Active Record to centralize queries. They complement each other — Repository provides the "collection" interface, Active Record provides the persistence.

6. **Testing advantage:**
   With Repository, you can create an `InMemoryCustomerRepository` for unit tests that uses a plain Python list instead of the database. This makes tests 10x faster and removes database dependency.

7. **When NOT to use Repository:**
   For simple CRUD-only apps with no complex queries, Repository adds unnecessary abstraction. Use it when you have domain-specific query methods, role-based access, or need to abstract the data source.
