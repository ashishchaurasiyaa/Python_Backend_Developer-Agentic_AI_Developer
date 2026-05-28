# Lecture 1 — Practical Hands-On: Building a SOA System

> **Theory file:** [01_Service_Oriented_Architecture.md](01_Service_Oriented_Architecture.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

Ek **complete SOA system** with:

1. ✅ **SOAP service** in Python (Spyne library)
2. ✅ **WSDL contract** generation & inspection
3. ✅ **SOAP client** to consume the service
4. ✅ **Mini-ESB** demonstrating routing/transformation/mediation
5. ✅ **Multiple services** (Billing, Inventory, Customer)
6. ✅ **Service orchestration** through ESB
7. ✅ **Audit logging** & error handling
8. ✅ **SOAP → REST migration** example

By end: aap **enterprise SOA system** likh sakte ho aur **modernization path** samjho ge.

---

## 1. Project Structure

```
soa_demo/
├── pyproject.toml
├── docker-compose.yml
├── README.md
│
├── services/
│   ├── billing_service/
│   │   ├── service.py           # SOAP service implementation
│   │   ├── contracts.py         # Data models
│   │   └── requirements.txt
│   │
│   ├── inventory_service/
│   │   ├── service.py
│   │   └── contracts.py
│   │
│   └── customer_service/
│       ├── service.py
│       └── contracts.py
│
├── esb/
│   ├── bus.py                   # Mini-ESB implementation
│   ├── routes.py                # Routing rules
│   ├── transformers.py          # Data transformers
│   └── security.py              # Auth/audit
│
├── clients/
│   ├── soap_client.py           # Direct SOAP client
│   ├── esb_client.py            # Client via ESB
│   └── orchestration_demo.py    # Multi-service workflow
│
└── tests/
    ├── test_services.py
    └── test_esb.py
```

---

## 2. Setup & Dependencies

### Install Required Packages

```bash
# Create virtual env
python -m venv venv
source venv/bin/activate  # macOS/Linux

# Install SOA libraries
pip install spyne lxml zeep
pip install fastapi uvicorn  # for REST migration demo
pip install httpx pytest
```

### `pyproject.toml`

```toml
[project]
name = "soa-demo"
version = "0.1.0"
requires-python = ">=3.10"

dependencies = [
    "spyne>=2.14",
    "lxml>=4.9",
    "zeep>=4.2",         # SOAP client
    "fastapi>=0.104",    # for REST comparison
    "uvicorn>=0.24",
    "httpx>=0.25",
    "pydantic>=2.0",
]
```

---

## 3. 🏦 Building the Billing SOAP Service

### Service Implementation (`services/billing_service/service.py`)

```python
"""
Billing SOAP Service - the SOA way
Demonstrates: WSDL contracts, XML messaging, service operations
"""
from spyne import Application, rpc, ServiceBase
from spyne import Integer, Unicode, Float, ComplexModel, Iterable
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication
from wsgiref.simple_server import make_server
from datetime import datetime
import uuid

# ─────────────────────────────────────────────────────────────
# DATA CONTRACTS (will appear in WSDL)
# ─────────────────────────────────────────────────────────────

class Invoice(ComplexModel):
    """Invoice data structure - exposed via WSDL"""
    invoice_id = Unicode
    customer_id = Integer
    amount = Float
    tax = Float
    total = Float
    status = Unicode
    created_at = Unicode

class PaymentRequest(ComplexModel):
    invoice_id = Unicode
    payment_method = Unicode
    amount = Float

class PaymentResponse(ComplexModel):
    success = Unicode
    transaction_id = Unicode
    message = Unicode

# ─────────────────────────────────────────────────────────────
# SERVICE IMPLEMENTATION
# ─────────────────────────────────────────────────────────────

# In-memory storage (in real SOA, this would be Oracle DB)
INVOICES = {}

class BillingService(ServiceBase):
    """
    SOA-style coarse-grained service.
    One service = ENTIRE billing domain.
    """
    
    @rpc(Integer, Float, _returns=Invoice)
    def create_invoice(ctx, customer_id, amount):
        """Generate a new invoice"""
        invoice_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
        tax = amount * 0.18  # 18% GST
        total = amount + tax
        
        invoice = Invoice(
            invoice_id=invoice_id,
            customer_id=customer_id,
            amount=amount,
            tax=tax,
            total=total,
            status="PENDING",
            created_at=datetime.now().isoformat()
        )
        INVOICES[invoice_id] = invoice
        return invoice
    
    @rpc(Unicode, _returns=Invoice)
    def get_invoice(ctx, invoice_id):
        """Fetch invoice by ID"""
        if invoice_id not in INVOICES:
            raise ValueError(f"Invoice {invoice_id} not found")
        return INVOICES[invoice_id]
    
    @rpc(PaymentRequest, _returns=PaymentResponse)
    def process_payment(ctx, payment):
        """Process payment for an invoice"""
        if payment.invoice_id not in INVOICES:
            return PaymentResponse(
                success="false",
                transaction_id="",
                message="Invoice not found"
            )
        
        invoice = INVOICES[payment.invoice_id]
        if payment.amount < invoice.total:
            return PaymentResponse(
                success="false",
                transaction_id="",
                message="Insufficient amount"
            )
        
        invoice.status = "PAID"
        txn_id = f"TXN-{uuid.uuid4().hex[:10].upper()}"
        return PaymentResponse(
            success="true",
            transaction_id=txn_id,
            message=f"Payment of {payment.amount} successful"
        )
    
    @rpc(Integer, _returns=Iterable(Invoice))
    def get_customer_invoices(ctx, customer_id):
        """Get all invoices for a customer"""
        for inv in INVOICES.values():
            if inv.customer_id == customer_id:
                yield inv

# ─────────────────────────────────────────────────────────────
# CREATE WSGI APPLICATION
# ─────────────────────────────────────────────────────────────

application = Application(
    [BillingService],
    tns='http://example.com/billing',
    in_protocol=Soap11(validator='lxml'),
    out_protocol=Soap11()
)

wsgi_app = WsgiApplication(application)

if __name__ == '__main__':
    print("=" * 60)
    print("Billing SOAP Service starting on port 8001")
    print("=" * 60)
    print("WSDL URL: http://localhost:8001/?wsdl")
    print("Service URL: http://localhost:8001/")
    print()
    
    server = make_server('0.0.0.0', 8001, wsgi_app)
    server.serve_forever()
```

### Run the Service

```bash
$ python services/billing_service/service.py

============================================================
Billing SOAP Service starting on port 8001
============================================================
WSDL URL: http://localhost:8001/?wsdl
Service URL: http://localhost:8001/
```

### Inspect the Auto-Generated WSDL

```bash
$ curl http://localhost:8001/?wsdl
```

```xml
<?xml version='1.0' encoding='UTF-8'?>
<wsdl:definitions xmlns:wsdl="http://schemas.xmlsoap.org/wsdl/"
                  xmlns:xsd="http://www.w3.org/2001/XMLSchema"
                  xmlns:tns="http://example.com/billing"
                  targetNamespace="http://example.com/billing">
  
  <wsdl:types>
    <xsd:schema targetNamespace="http://example.com/billing">
      <xsd:complexType name="Invoice">
        <xsd:sequence>
          <xsd:element name="invoice_id" type="xsd:string"/>
          <xsd:element name="customer_id" type="xsd:integer"/>
          <xsd:element name="amount" type="xsd:double"/>
          <xsd:element name="tax" type="xsd:double"/>
          <xsd:element name="total" type="xsd:double"/>
          <xsd:element name="status" type="xsd:string"/>
        </xsd:sequence>
      </xsd:complexType>
    </xsd:schema>
  </wsdl:types>
  
  <wsdl:message name="create_invoice">
    <wsdl:part name="customer_id" type="xsd:integer"/>
    <wsdl:part name="amount" type="xsd:double"/>
  </wsdl:message>
  <!-- ... more operations ... -->
</wsdl:definitions>
```

---

## 4. 📦 Building Inventory & Customer Services

### Inventory Service (`services/inventory_service/service.py`)

```python
"""Inventory SOAP Service"""
from spyne import Application, rpc, ServiceBase, Integer, Unicode, ComplexModel
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication
from wsgiref.simple_server import make_server

class Product(ComplexModel):
    sku = Unicode
    name = Unicode
    stock = Integer
    price = Integer  # in paise

# Mock inventory
INVENTORY = {
    "SKU-001": Product(sku="SKU-001", name="iPhone 15", stock=50, price=7999900),
    "SKU-002": Product(sku="SKU-002", name="MacBook Pro", stock=20, price=19999900),
    "SKU-003": Product(sku="SKU-003", name="AirPods", stock=100, price=2499900),
}

class InventoryService(ServiceBase):
    @rpc(Unicode, _returns=Product)
    def get_product(ctx, sku):
        if sku not in INVENTORY:
            raise ValueError(f"Product {sku} not found")
        return INVENTORY[sku]
    
    @rpc(Unicode, Integer, _returns=Unicode)
    def reserve_stock(ctx, sku, quantity):
        if sku not in INVENTORY:
            return "PRODUCT_NOT_FOUND"
        product = INVENTORY[sku]
        if product.stock < quantity:
            return "INSUFFICIENT_STOCK"
        product.stock -= quantity
        return "RESERVED"

application = Application(
    [InventoryService],
    tns='http://example.com/inventory',
    in_protocol=Soap11(validator='lxml'),
    out_protocol=Soap11()
)
wsgi_app = WsgiApplication(application)

if __name__ == '__main__':
    print("Inventory SOAP Service on http://localhost:8002")
    server = make_server('0.0.0.0', 8002, wsgi_app)
    server.serve_forever()
```

### Customer Service (`services/customer_service/service.py`)

```python
"""Customer SOAP Service"""
from spyne import Application, rpc, ServiceBase, Integer, Unicode, ComplexModel
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication
from wsgiref.simple_server import make_server

class Customer(ComplexModel):
    id = Integer
    name = Unicode
    email = Unicode
    tier = Unicode  # GOLD, SILVER, BRONZE
    credit_limit = Integer

CUSTOMERS = {
    1: Customer(id=1, name="Ashish Chaurasiya", email="ashish@ex.com", tier="GOLD", credit_limit=500000),
    2: Customer(id=2, name="Rahul Singh", email="rahul@ex.com", tier="SILVER", credit_limit=200000),
}

class CustomerService(ServiceBase):
    @rpc(Integer, _returns=Customer)
    def get_customer(ctx, customer_id):
        if customer_id not in CUSTOMERS:
            raise ValueError(f"Customer {customer_id} not found")
        return CUSTOMERS[customer_id]
    
    @rpc(Integer, Integer, _returns=Unicode)
    def check_credit(ctx, customer_id, amount):
        if customer_id not in CUSTOMERS:
            return "CUSTOMER_NOT_FOUND"
        if amount > CUSTOMERS[customer_id].credit_limit:
            return "CREDIT_EXCEEDED"
        return "APPROVED"

application = Application(
    [CustomerService],
    tns='http://example.com/customer',
    in_protocol=Soap11(validator='lxml'),
    out_protocol=Soap11()
)
wsgi_app = WsgiApplication(application)

if __name__ == '__main__':
    print("Customer SOAP Service on http://localhost:8003")
    server = make_server('0.0.0.0', 8003, wsgi_app)
    server.serve_forever()
```

---

## 5. 📞 SOAP Client — Direct Service Consumption

### Client (`clients/soap_client.py`)

```python
"""
SOAP Client - calling services DIRECTLY (without ESB).
This demonstrates the "tight coupling" problem SOA tried to solve via ESB.
"""
from zeep import Client

# ─────────────────────────────────────────────────────────────
# Connect to services via their WSDL
# ─────────────────────────────────────────────────────────────
billing_client = Client('http://localhost:8001/?wsdl')
inventory_client = Client('http://localhost:8002/?wsdl')
customer_client = Client('http://localhost:8003/?wsdl')

def demo():
    print("=" * 60)
    print("DIRECT SOAP CLIENT DEMO")
    print("=" * 60)
    
    # 1. Get customer details
    print("\n1. Fetching customer 1...")
    customer = customer_client.service.get_customer(1)
    print(f"   Customer: {customer.name} ({customer.tier})")
    print(f"   Credit limit: ₹{customer.credit_limit/100}")
    
    # 2. Get product details
    print("\n2. Fetching product SKU-001...")
    product = inventory_client.service.get_product("SKU-001")
    print(f"   Product: {product.name}")
    print(f"   Stock: {product.stock}, Price: ₹{product.price/100}")
    
    # 3. Create invoice
    print("\n3. Creating invoice...")
    invoice = billing_client.service.create_invoice(
        customer_id=1,
        amount=product.price / 100
    )
    print(f"   Invoice: {invoice.invoice_id}")
    print(f"   Total (with tax): ₹{invoice.total}")
    
    # 4. Process payment
    print("\n4. Processing payment...")
    response = billing_client.service.process_payment({
        "invoice_id": invoice.invoice_id,
        "payment_method": "UPI",
        "amount": invoice.total
    })
    print(f"   Result: {response.message}")
    print(f"   Transaction ID: {response.transaction_id}")

if __name__ == '__main__':
    demo()
```

### Output

```bash
$ python clients/soap_client.py

============================================================
DIRECT SOAP CLIENT DEMO
============================================================

1. Fetching customer 1...
   Customer: Ashish Chaurasiya (GOLD)
   Credit limit: ₹5000.0

2. Fetching product SKU-001...
   Product: iPhone 15
   Stock: 50, Price: ₹79999.0

3. Creating invoice...
   Invoice: INV-A3B4C5D6
   Total (with tax): ₹94398.82

4. Processing payment...
   Result: Payment of 94398.82 successful
   Transaction ID: TXN-X1Y2Z3W4V5
```

---

## 6. 🚌 Building the Mini-ESB

### The Problem with Direct Communication

```
❌ Client → Service A
❌ Client → Service B
❌ Client → Service C
   (client must know all endpoints, handle all retries, audit, etc.)
```

### The ESB Solution

```
✅ Client → ESB → Service A
                → Service B
                → Service C
   (ESB handles routing, audit, security, transformation)
```

### Mini-ESB Implementation (`esb/bus.py`)

```python
"""
Mini Enterprise Service Bus
Demonstrates ESB patterns: VETRO (Validate, Enrich, Transform, Route, Operate)
"""
import logging
import json
import uuid
from datetime import datetime
from typing import Callable, Dict, Any, Optional
from zeep import Client

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] [ESB] %(message)s')
logger = logging.getLogger(__name__)


class ESB:
    """
    Enterprise Service Bus implementing the VETRO pattern.
    All service communication flows through here.
    """
    
    def __init__(self):
        self.services: Dict[str, Client] = {}
        self.routes: Dict[str, str] = {}
        self.transformers: Dict[str, Callable] = {}
        self.validators: Dict[str, Callable] = {}
        self.audit_log = []
        self.security_tokens = {"VALID_TOKEN_123", "ADMIN_TOKEN_999"}
    
    # ─────────────────────────────────────────────────────────
    # REGISTRATION
    # ─────────────────────────────────────────────────────────
    def register_service(self, name: str, wsdl_url: str):
        """Register a SOAP service with the ESB"""
        self.services[name] = Client(wsdl_url)
        logger.info(f"Registered service: {name} → {wsdl_url}")
    
    def add_route(self, message_type: str, target_service: str):
        """Content-based routing: message_type → service"""
        self.routes[message_type] = target_service
        logger.info(f"Route added: {message_type} → {target_service}")
    
    def add_transformer(self, name: str, fn: Callable):
        """Add a data transformer"""
        self.transformers[name] = fn
        logger.info(f"Transformer registered: {name}")
    
    def add_validator(self, name: str, fn: Callable):
        """Add a message validator"""
        self.validators[name] = fn
    
    # ─────────────────────────────────────────────────────────
    # VETRO PIPELINE
    # ─────────────────────────────────────────────────────────
    def send(
        self,
        message_type: str,
        operation: str,
        payload: Dict[str, Any],
        auth_token: str,
        transform: Optional[str] = None,
        validate: Optional[str] = None,
    ) -> Any:
        """
        Process a message through ESB pipeline:
        1. Security check
        2. Validate
        3. Enrich
        4. Transform
        5. Route
        6. Operate (invoke service)
        7. Audit log
        """
        trace_id = str(uuid.uuid4())[:8]
        logger.info(f"[{trace_id}] ▶ Received: {message_type}.{operation}")
        
        # ── 1. SECURITY CHECK ──
        if auth_token not in self.security_tokens:
            logger.error(f"[{trace_id}] ✗ Unauthorized")
            raise PermissionError("Invalid auth token")
        logger.info(f"[{trace_id}] ✓ Security passed")
        
        # ── 2. VALIDATE ──
        if validate and validate in self.validators:
            valid, error = self.validators[validate](payload)
            if not valid:
                logger.error(f"[{trace_id}] ✗ Validation failed: {error}")
                raise ValueError(f"Validation error: {error}")
            logger.info(f"[{trace_id}] ✓ Validation passed")
        
        # ── 3. ENRICH (add metadata) ──
        enriched_payload = {
            **payload,
            "_trace_id": trace_id,
            "_timestamp": datetime.now().isoformat(),
        }
        
        # ── 4. TRANSFORM ──
        if transform and transform in self.transformers:
            enriched_payload = self.transformers[transform](enriched_payload)
            logger.info(f"[{trace_id}] ✓ Transformed via {transform}")
        
        # ── 5. ROUTE ──
        if message_type not in self.routes:
            raise ValueError(f"No route for {message_type}")
        target_service = self.routes[message_type]
        if target_service not in self.services:
            raise ValueError(f"Service {target_service} not registered")
        logger.info(f"[{trace_id}] ▶ Routing to {target_service}")
        
        # ── 6. OPERATE (invoke service) ──
        client = self.services[target_service]
        service_method = getattr(client.service, operation)
        
        try:
            # Remove ESB metadata before calling service
            service_payload = {k: v for k, v in enriched_payload.items()
                              if not k.startswith("_")}
            result = service_method(**service_payload)
            logger.info(f"[{trace_id}] ✓ Service responded")
        except Exception as e:
            logger.error(f"[{trace_id}] ✗ Service error: {e}")
            self._audit("ERROR", trace_id, message_type, str(e))
            raise
        
        # ── 7. AUDIT LOG ──
        self._audit("SUCCESS", trace_id, message_type, "OK")
        
        return result
    
    def _audit(self, status: str, trace_id: str, msg_type: str, detail: str):
        """Centralized audit logging (one of ESB's superpowers)"""
        self.audit_log.append({
            "timestamp": datetime.now().isoformat(),
            "trace_id": trace_id,
            "status": status,
            "message_type": msg_type,
            "detail": detail,
        })
    
    # ─────────────────────────────────────────────────────────
    # ORCHESTRATION
    # ─────────────────────────────────────────────────────────
    def orchestrate(self, workflow: list, auth_token: str) -> list:
        """
        Execute a sequence of service calls (orchestration).
        Each step can use output of previous step.
        """
        logger.info(f"▶ Starting orchestration: {len(workflow)} steps")
        results = []
        context = {}
        
        for i, step in enumerate(workflow, 1):
            logger.info(f"  Step {i}: {step['message_type']}.{step['operation']}")
            
            # Resolve template variables from previous results
            payload = {}
            for key, value in step.get("payload", {}).items():
                if isinstance(value, str) and value.startswith("$"):
                    payload[key] = context.get(value[1:])
                else:
                    payload[key] = value
            
            result = self.send(
                message_type=step["message_type"],
                operation=step["operation"],
                payload=payload,
                auth_token=auth_token,
                transform=step.get("transform"),
                validate=step.get("validate"),
            )
            results.append(result)
            
            # Save result for next step
            if "save_as" in step:
                context[step["save_as"]] = result
        
        return results
    
    def print_audit_log(self):
        print("\n" + "=" * 60)
        print("ESB AUDIT LOG")
        print("=" * 60)
        for entry in self.audit_log:
            print(f"[{entry['timestamp']}] {entry['status']:8} {entry['trace_id']} {entry['message_type']}")
```

---

## 7. 🎼 Service Orchestration via ESB

### Multi-Step Workflow (`clients/orchestration_demo.py`)

```python
"""
Demonstrates SOA's killer feature: orchestrating multiple services
via the ESB to complete a business process.

Use case: "Place an Order" - involves Customer + Inventory + Billing
"""
import sys
sys.path.insert(0, '../esb')

from esb.bus import ESB

# ─────────────────────────────────────────────────────────────
# SETUP ESB
# ─────────────────────────────────────────────────────────────
esb = ESB()

# Register all services
esb.register_service("billing", "http://localhost:8001/?wsdl")
esb.register_service("inventory", "http://localhost:8002/?wsdl")
esb.register_service("customer", "http://localhost:8003/?wsdl")

# Define routes (content-based routing)
esb.add_route("CustomerLookup", "customer")
esb.add_route("ProductLookup", "inventory")
esb.add_route("StockReservation", "inventory")
esb.add_route("CreditCheck", "customer")
esb.add_route("InvoiceCreation", "billing")
esb.add_route("PaymentProcessing", "billing")

# Add validators
esb.add_validator(
    "positive_amount",
    lambda p: (True, None) if p.get("amount", 0) > 0 else (False, "Amount must be positive")
)

# Add transformers (e.g., add tax info)
def add_tax_metadata(payload):
    if "amount" in payload:
        payload["tax_rate"] = 0.18  # 18% GST
    return payload

esb.add_transformer("add_tax", add_tax_metadata)

# ─────────────────────────────────────────────────────────────
# ORCHESTRATE: "Place Order" Workflow
# ─────────────────────────────────────────────────────────────
print("=" * 60)
print("SOA ORCHESTRATION: Place Order Workflow")
print("=" * 60)

workflow = [
    # Step 1: Look up customer
    {
        "message_type": "CustomerLookup",
        "operation": "get_customer",
        "payload": {"customer_id": 1},
        "save_as": "customer",
    },
    # Step 2: Look up product
    {
        "message_type": "ProductLookup",
        "operation": "get_product",
        "payload": {"sku": "SKU-001"},
        "save_as": "product",
    },
    # Step 3: Reserve stock
    {
        "message_type": "StockReservation",
        "operation": "reserve_stock",
        "payload": {"sku": "SKU-001", "quantity": 1},
        "save_as": "reservation",
    },
    # Step 4: Credit check
    {
        "message_type": "CreditCheck",
        "operation": "check_credit",
        "payload": {"customer_id": 1, "amount": 800},
        "save_as": "credit_status",
    },
    # Step 5: Create invoice
    {
        "message_type": "InvoiceCreation",
        "operation": "create_invoice",
        "payload": {"customer_id": 1, "amount": 79999.0},
        "validate": "positive_amount",
        "transform": "add_tax",
        "save_as": "invoice",
    },
]

results = esb.orchestrate(workflow, auth_token="VALID_TOKEN_123")

print("\n" + "=" * 60)
print("WORKFLOW RESULTS")
print("=" * 60)
for i, result in enumerate(results, 1):
    print(f"\nStep {i} result:")
    print(f"   {result}")

# Show audit trail
esb.print_audit_log()
```

### Expected Output

```
============================================================
SOA ORCHESTRATION: Place Order Workflow
============================================================
[2026-05-26 10:00:00] [ESB] ▶ Starting orchestration: 5 steps
[2026-05-26 10:00:00] [ESB]   Step 1: CustomerLookup.get_customer
[2026-05-26 10:00:00] [ESB] [a1b2c3d4] ▶ Received: CustomerLookup.get_customer
[2026-05-26 10:00:00] [ESB] [a1b2c3d4] ✓ Security passed
[2026-05-26 10:00:00] [ESB] [a1b2c3d4] ▶ Routing to customer
[2026-05-26 10:00:00] [ESB] [a1b2c3d4] ✓ Service responded
[2026-05-26 10:00:00] [ESB]   Step 2: ProductLookup.get_product
... (all 5 steps)

============================================================
ESB AUDIT LOG
============================================================
[2026-05-26 10:00:00] SUCCESS  a1b2c3d4 CustomerLookup
[2026-05-26 10:00:00] SUCCESS  e5f6g7h8 ProductLookup
[2026-05-26 10:00:00] SUCCESS  i9j0k1l2 StockReservation
[2026-05-26 10:00:00] SUCCESS  m3n4o5p6 CreditCheck
[2026-05-26 10:00:00] SUCCESS  q7r8s9t0 InvoiceCreation
```

---

## 8. 🔄 SOA → REST Migration (Modernization Demo)

### The Same Service in Modern REST (FastAPI)

```python
"""
billing_rest.py - Modern REST version of BillingService
Compare with the SOAP version - same logic, much lighter!
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
import uuid

app = FastAPI(title="Billing REST Service")

# ─────────────────────────────────────────────────────────────
# Pydantic Models (much cleaner than ComplexModel)
# ─────────────────────────────────────────────────────────────
class CreateInvoiceRequest(BaseModel):
    customer_id: int
    amount: float

class Invoice(BaseModel):
    invoice_id: str
    customer_id: int
    amount: float
    tax: float
    total: float
    status: str
    created_at: str

class PaymentRequest(BaseModel):
    payment_method: str
    amount: float

class PaymentResponse(BaseModel):
    success: bool
    transaction_id: str
    message: str

# ─────────────────────────────────────────────────────────────
# Storage
# ─────────────────────────────────────────────────────────────
INVOICES = {}

# ─────────────────────────────────────────────────────────────
# REST Endpoints (vs SOAP operations)
# ─────────────────────────────────────────────────────────────

@app.post("/invoices", response_model=Invoice, status_code=201)
def create_invoice(req: CreateInvoiceRequest):
    invoice_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
    tax = req.amount * 0.18
    total = req.amount + tax
    
    invoice = Invoice(
        invoice_id=invoice_id,
        customer_id=req.customer_id,
        amount=req.amount,
        tax=tax,
        total=total,
        status="PENDING",
        created_at=datetime.now().isoformat()
    )
    INVOICES[invoice_id] = invoice
    return invoice

@app.get("/invoices/{invoice_id}", response_model=Invoice)
def get_invoice(invoice_id: str):
    if invoice_id not in INVOICES:
        raise HTTPException(404, "Invoice not found")
    return INVOICES[invoice_id]

@app.post("/invoices/{invoice_id}/payment", response_model=PaymentResponse)
def process_payment(invoice_id: str, req: PaymentRequest):
    if invoice_id not in INVOICES:
        raise HTTPException(404, "Invoice not found")
    
    invoice = INVOICES[invoice_id]
    if req.amount < invoice.total:
        return PaymentResponse(
            success=False,
            transaction_id="",
            message="Insufficient amount"
        )
    
    invoice.status = "PAID"
    return PaymentResponse(
        success=True,
        transaction_id=f"TXN-{uuid.uuid4().hex[:10].upper()}",
        message=f"Payment of ₹{req.amount} successful"
    )

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=9001)
```

### Comparison: SOAP vs REST Request

```bash
# ─── SOAP REQUEST (verbose, ~500 bytes) ───
$ curl -X POST http://localhost:8001/ \
    -H "Content-Type: text/xml" \
    -H "SOAPAction: create_invoice" \
    -d '<?xml version="1.0"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <m:create_invoice xmlns:m="http://example.com/billing">
      <m:customer_id>1</m:customer_id>
      <m:amount>79999</m:amount>
    </m:create_invoice>
  </soap:Body>
</soap:Envelope>'

# ─── REST REQUEST (concise, ~80 bytes) ───
$ curl -X POST http://localhost:9001/invoices \
    -H "Content-Type: application/json" \
    -d '{"customer_id": 1, "amount": 79999}'
```

---

## 9. 🧪 Testing the SOA System

### Test File (`tests/test_services.py`)

```python
"""Tests for SOAP services"""
import pytest
from zeep import Client

@pytest.fixture
def billing_client():
    return Client('http://localhost:8001/?wsdl')

@pytest.fixture
def inventory_client():
    return Client('http://localhost:8002/?wsdl')

def test_create_invoice(billing_client):
    invoice = billing_client.service.create_invoice(
        customer_id=1, amount=1000.0
    )
    assert invoice.invoice_id.startswith("INV-")
    assert invoice.total == 1180.0  # 1000 + 18% tax
    assert invoice.status == "PENDING"

def test_get_product(inventory_client):
    product = inventory_client.service.get_product("SKU-001")
    assert product.sku == "SKU-001"
    assert product.stock > 0

def test_stock_reservation(inventory_client):
    result = inventory_client.service.reserve_stock("SKU-001", 1)
    assert result == "RESERVED"

def test_insufficient_stock(inventory_client):
    result = inventory_client.service.reserve_stock("SKU-001", 9999)
    assert result == "INSUFFICIENT_STOCK"
```

### Test the ESB

```python
"""tests/test_esb.py"""
import pytest
from esb.bus import ESB

def test_esb_unauthorized():
    esb = ESB()
    esb.register_service("billing", "http://localhost:8001/?wsdl")
    esb.add_route("InvoiceCreation", "billing")
    
    with pytest.raises(PermissionError):
        esb.send(
            message_type="InvoiceCreation",
            operation="create_invoice",
            payload={"customer_id": 1, "amount": 100},
            auth_token="INVALID"
        )

def test_esb_validation_failure():
    esb = ESB()
    esb.add_validator(
        "positive",
        lambda p: (False, "Negative not allowed") if p.get("amount", 0) < 0 else (True, None)
    )
    esb.register_service("billing", "http://localhost:8001/?wsdl")
    esb.add_route("InvoiceCreation", "billing")
    
    with pytest.raises(ValueError, match="Negative not allowed"):
        esb.send(
            message_type="InvoiceCreation",
            operation="create_invoice",
            payload={"customer_id": 1, "amount": -100},
            auth_token="VALID_TOKEN_123",
            validate="positive"
        )
```

---

## 10. 🚀 Running Everything (Docker Compose)

### `docker-compose.yml`

```yaml
version: '3.8'

services:
  billing:
    build:
      context: ./services/billing_service
    ports:
      - "8001:8001"
    command: python service.py
  
  inventory:
    build:
      context: ./services/inventory_service
    ports:
      - "8002:8002"
    command: python service.py
  
  customer:
    build:
      context: ./services/customer_service
    ports:
      - "8003:8003"
    command: python service.py
  
  esb:
    build:
      context: ./esb
    ports:
      - "9000:9000"
    depends_on:
      - billing
      - inventory
      - customer
    environment:
      - BILLING_URL=http://billing:8001
      - INVENTORY_URL=http://inventory:8002
      - CUSTOMER_URL=http://customer:8003
```

### Run All Services

```bash
# Terminal 1
$ python services/billing_service/service.py

# Terminal 2
$ python services/inventory_service/service.py

# Terminal 3
$ python services/customer_service/service.py

# Terminal 4 - Run orchestration
$ python clients/orchestration_demo.py
```

---

## 11. Key Learnings Summary

```
✅ SOA = Architectural style, not technology
✅ SOAP services expose operations via WSDL contract
✅ ESB centralizes routing, transformation, audit
✅ Service orchestration enables complex workflows
✅ Heavyweight but powerful for enterprise integration
✅ Modern alternative: REST + API Gateway

📊 SOAP vs REST quick stats:
   SOAP message: ~500-2000 bytes (XML overhead)
   REST message: ~50-200 bytes  (JSON)
   
   SOAP parse time: ~5-10ms (lxml parsing)
   REST parse time: ~0.1-0.5ms (JSON parsing)
```

---

## 🎬 What's Next?

In **Lecture 2's practical**, we'll build a **microservices system** with FastAPI, Kafka events, distributed tracing, and resilience patterns — see how modern systems differ from SOA in practice.

> **Next lecture:** [02_Microservices_Architecture.md](02_Microservices_Architecture.md)

---

## 📚 Try It Yourself

1. Add a `RefundService` and orchestrate refund workflow
2. Add **circuit breaker** to ESB (fail fast if service down)
3. Add **caching** in ESB for frequently-asked queries
4. Add **rate limiting** per consumer
5. Migrate one service from SOAP to REST while keeping ESB
