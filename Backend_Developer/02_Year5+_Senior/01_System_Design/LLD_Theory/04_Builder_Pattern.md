# Builder Pattern
> **Category:** Creational | **Difficulty:** Medium | **Interview Frequency:** ★★★★☆

---

## Quick Reference Card
```
Kya karta hai : Complex object ko step-by-step banao — ek saath nahi
Kab use karo  : Bahut saare optional fields, complex nested object, fluent API
Key mechanism : Builder class mein setter methods → build() se final object
Real project  : Youngman → EwayBillPayloadBuilder | Niroskos → BookingDraftBuilder
Pattern type  : Creational
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Kya hai?

Builder pattern mein **ek complex object ko chhote chhote steps mein banate hain** — ek baar mein nahi.

Socho ek constructor mein 10 parameters honge — kaun sa kya hai yaad rakhna mushkil.
Builder mein har cheez clearly set hoti hai.

**Simple analogy:**
```
Subway sandwich banane jaate ho:
Step 1: Bread chuno (wheat/white)
Step 2: Filling chuno (chicken/veg)
Step 3: Vegetables chuno (tomato, onion, capsicum)
Step 4: Sauce chuno (mayo, mustard)
Step 5: Toast karo ya nahi

Sab optional, sab step-by-step, final sandwich = build()

Ek baar mein "sandwich banao" bolna → kya dalega? Confusing.
Builder mein clearly har step choose karo.
```

---

### 1.2 Kab use karo?

```
✅ Object mein bahut saare optional fields hain
✅ Same type ke objects different configurations mein chahiye
✅ Complex nested JSON/payload banana hai (API ke liye)
✅ Fluent API chahiye — method chaining (builder.set_a().set_b().build())
✅ Test data banana ho — TestBookingBuilder().with_package().with_date()
✅ Constructor mein 5+ parameters ho — readability kharab hoti hai
```

---

### 1.3 Kab mat use karo?

```
❌ Object simple hai — 2-3 fields — direct constructor better
❌ Fields mandatory hain, optional nahi — simple class enough
❌ Object ek baar banane ke baad change nahi hota — direct instantiation
```

---

### 1.4 Code — Hinglish Comments ke saath

```python
from dataclasses import dataclass, field
from datetime import date
from typing import Optional, List


# ─── Product — yeh complex object ban raha hai ───
@dataclass
class EwayBillPayload:
    # Supply info
    supply_type:      str
    transaction_type: int

    # Consignor (sender)
    gstin_of_consignor:    str
    name_of_consignor:     str
    address_of_consignor:  str
    pincode_of_consignor:  int
    state_of_consignor:    int

    # Consignee (receiver)
    gstin_of_consignee:    str
    name_of_consignee:     str
    address_of_consignee:  str
    pincode_of_consignee:  int
    state_of_consignee:    int

    # Vehicle info
    vehicle_number:        Optional[str] = None
    transport_mode:        str = 'Road'
    distance:              Optional[int] = None

    # Items
    item_list:             List[dict] = field(default_factory=list)
    total_value:           float = 0.0
    cgst_value:            float = 0.0
    sgst_value:            float = 0.0
    igst_value:            float = 0.0


# ─── Abstract Builder — kya kya steps hone chahiye ───
from abc import ABC, abstractmethod

class BaseEwayBillBuilder(ABC):
    def __init__(self, challan, params):
        self.challan  = challan
        self.params   = params
        self._payload = {}  # Step by step yahan fill hoga

    # Template Method — yeh steps sab builders mein same
    def build(self) -> dict:
        self._payload.update(self._get_supply_type())       # Step 1
        self._payload.update(self._get_consignor_details()) # Step 2
        self._payload.update(self._get_consignee_details()) # Step 3
        self._payload.update(self._get_transport_details()) # Step 4
        self._payload['item_list']     = self._get_items()  # Step 5
        self._payload['amount_details'] = self._get_amounts() # Step 6
        return self._payload

    # Yeh steps subclass implement karega — different for Delivery/Pickup
    @abstractmethod
    def _get_supply_type(self) -> dict:
        pass

    @abstractmethod
    def _get_consignor_details(self) -> dict:
        pass

    @abstractmethod
    def _get_consignee_details(self) -> dict:
        pass

    # Common steps — sab builders ke liye same
    def _get_transport_details(self) -> dict:
        return {
            "transporter_id":   self.params.get('transporter_id', ''),
            "transport_mode":   self.params.get('mode', 'Road'),
            "vehicle_number":   self.params.get('vehicle_no', ''),
            "distance":         self.params.get('distance', 0),
        }

    def _get_items(self) -> list:
        return [
            {
                "product_name": item.name,
                "hsn_code":     item.hsn_code,
                "quantity":     item.quantity,
                "unit":         item.unit,
                "taxable_amount": item.amount,
            }
            for item in self.challan.items.all()
        ]

    def _get_amounts(self) -> dict:
        total = sum(i.amount for i in self.challan.items.all())
        is_intra_state = self._is_intra_state()
        return {
            "total_value": total,
            "cgst_value":  total * 0.09 if is_intra_state else 0,
            "sgst_value":  total * 0.09 if is_intra_state else 0,
            "igst_value":  total * 0.18 if not is_intra_state else 0,
        }

    def _is_intra_state(self) -> bool:
        return self.challan.godown.state_code == self.challan.order.customer.state_code


# ─── Concrete Builders — alag alag types ───
class DeliveryEwayBillBuilder(BaseEwayBillBuilder):
    """Company → Customer delivery"""

    def _get_supply_type(self):
        # Delivery = Outward supply, type 2
        return {"supply_type": "Outward", "transaction_type": 2}

    def _get_consignor_details(self):
        # Company godown se bheja ja raha hai → consignor = company
        godown = self.challan.godown
        return {
            "gstin_of_consignor":   godown.gstin,
            "name_of_consignor":    "Y Equipment Services PVT. LTD.",
            "address_of_consignor": godown.address,
            "pincode_of_consignor": int(godown.pincode),
            "state_of_consignor":   int(godown.state_code),
        }

    def _get_consignee_details(self):
        # Customer receive kar raha hai → consignee = customer
        customer = self.challan.order.customer
        return {
            "gstin_of_consignee":   customer.gstin or "URP",
            "name_of_consignee":    customer.company,
            "address_of_consignee": customer.address,
            "pincode_of_consignee": int(customer.pincode),
            "state_of_consignee":   int(customer.state_code),
        }


class PickupEwayBillBuilder(BaseEwayBillBuilder):
    """Customer → Company pickup"""

    def _get_supply_type(self):
        # Pickup = Inward supply, type 3
        return {"supply_type": "Inward", "transaction_type": 3}

    def _get_consignor_details(self):
        # Customer bhej raha hai → consignor = customer
        customer = self.challan.order.customer
        return {
            "gstin_of_consignor":   customer.gstin or "URP",
            "name_of_consignor":    customer.company,
            "address_of_consignor": customer.address,
            "pincode_of_consignor": int(customer.pincode),
            "state_of_consignor":   int(customer.state_code),
        }

    def _get_consignee_details(self):
        # Company receive kar raha hai → consignee = company godown
        godown = self.challan.godown
        return {
            "gstin_of_consignee":   godown.gstin,
            "name_of_consignee":    "Y Equipment Services PVT. LTD.",
            "address_of_consignee": godown.address,
            "pincode_of_consignee": int(godown.pincode),
            "state_of_consignee":   int(godown.state_code),
        }


# ─── Fluent Builder — Niroskos Booking ke liye ───
class BookingDraftBuilder:
    """
    Fluent interface — method chaining se step by step booking banao.
    Test data banana ho ya complex booking create karna ho — clean syntax.
    """

    def __init__(self):
        self._package     = None
        self._travel_date = None
        self._guests      = 1
        self._pickup      = None
        self._language    = 'en'
        self._special_req = None

    def with_package(self, package):
        self._package = package
        return self  # Method chaining ke liye self return karo

    def on_date(self, travel_date: date):
        self._travel_date = travel_date
        return self

    def for_guests(self, count: int):
        self._guests = count
        return self

    def with_pickup(self, location: str, time: str):
        self._pickup = {"location": location, "time": time}
        return self

    def in_language(self, lang: str):
        self._language = lang
        return self

    def with_special_request(self, request: str):
        self._special_req = request
        return self

    def build(self):
        # Validation — mandatory fields check karo
        if not self._package:
            raise ValueError("Package is required")
        if not self._travel_date:
            raise ValueError("Travel date is required")

        return {
            "package":          self._package,
            "travel_date":      self._travel_date,
            "guests":           self._guests,
            "pickup":           self._pickup,
            "language":         self._language,
            "special_request":  self._special_req,
        }


# Usage — method chaining — bahut readable!
booking = (
    BookingDraftBuilder()
    .with_package("Masai Mara Safari")
    .on_date(date(2024, 6, 15))
    .for_guests(4)
    .with_pickup("Nairobi Airport", "06:00 AM")
    .in_language("en")
    .with_special_request("Vegetarian meals please")
    .build()
)
print(booking)
```

---

### 1.5 Tumhara Real Project Mein Kahan Use Hua

```
Project 1 — Youngman Django Backend:
  → EwayBillPayloadBuilder (tumhara existing code)
    BaseEwayBillBuilder.build() — Template Method + Builder combo
    DeliveryEwayBillBuilder aur PickupEwayBillBuilder alag steps
    Complex government API payload step-by-step banaya

Project 2 — Niroskos Safari Platform:
  → BookingDraft model — 12+ mixins compose karta hai
    ContactInfoMixin + PricingMixin + PickupMixin + etc.
    Builder jaisi feel — har mixin ek "step" add karta hai

Project 3 — SAP HANA Connector (4858 lines):
  → Invoice payload builder
    Header → LineItems → TaxDetails → PaymentTerms
    Har section step-by-step build hota tha
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definition

> **Builder is a creational pattern that constructs complex objects step-by-step. It separates the construction process from the representation, allowing the same construction process to create different representations.**

---

### 2.2 Problem It Solves

```python
# WITHOUT Builder — constructor hell
payload = EwayBillPayload(
    "Outward", 2, "27AABCY1234A1ZP",
    "Y Equipment Services", "123, MG Road",
    400001, 27, "27AABCX5678A1ZP",
    "Tata Steel Ltd", "456, Bandra", 400051, 27,
    "MH01AB1234", "Road", 150, items, 100000, 9000, 9000, 0
)
# 20 positional args — which is which? Impossible to read!

# WITH Builder — readable, step-by-step
payload = (
    DeliveryEwayBillBuilder(challan, params)
    .build()
)
# OR fluent
booking = BookingDraftBuilder().with_package(pkg).on_date(d).for_guests(2).build()
```

---

### 2.3 Key Components

| Component | Role | Example |
|-----------|------|---------|
| **Product** | Complex object being built | `EwayBillPayload`, `BookingDraft` |
| **Abstract Builder** | Defines construction steps | `BaseEwayBillBuilder(ABC)` |
| **Concrete Builder** | Implements steps differently | `DeliveryBuilder`, `PickupBuilder` |
| **Director** (optional) | Orchestrates build steps | `EwayBillFactory.create_builder()` |
| **build()** | Returns final constructed object | `.build()` → payload dict |

---

### 2.4 Clean Code Example

```python
from abc import ABC, abstractmethod

class QueryBuilder:
    """Fluent SQL query builder — real use case"""

    def __init__(self, table: str):
        self._table      = table
        self._conditions = []
        self._fields     = ['*']
        self._limit      = None
        self._order_by   = None

    def select(self, *fields):
        self._fields = list(fields)
        return self

    def where(self, condition: str):
        self._conditions.append(condition)
        return self

    def order_by(self, field: str, direction: str = 'ASC'):
        self._order_by = f"{field} {direction}"
        return self

    def limit(self, count: int):
        self._limit = count
        return self

    def build(self) -> str:
        query = f"SELECT {', '.join(self._fields)} FROM {self._table}"
        if self._conditions:
            query += f" WHERE {' AND '.join(self._conditions)}"
        if self._order_by:
            query += f" ORDER BY {self._order_by}"
        if self._limit:
            query += f" LIMIT {self._limit}"
        return query


# Clean, readable query construction
query = (
    QueryBuilder('invoices')
    .select('id', 'customer_id', 'amount', 'status')
    .where("status = 'OVERDUE'")
    .where("amount > 10000")
    .order_by('created_at', 'DESC')
    .limit(50)
    .build()
)
# SELECT id, customer_id, amount, status FROM invoices
# WHERE status = 'OVERDUE' AND amount > 10000
# ORDER BY created_at DESC LIMIT 50
```

---

### 2.5 Real Project Answer

**"Explain Builder pattern with your project"**

> "In Youngman's E-way bill system, generating a government API payload was complex — it had consignor details, consignee details, transport info, item list, and GST amounts. The structure differed for Delivery challan (Company → Customer) and Pickup challan (Customer → Company).
>
> I implemented `BaseEwayBillBuilder` as an abstract builder with a `build()` template method that calls `_get_supply_type()`, `_get_consignor_details()`, `_get_consignee_details()`, `_get_transport_details()`, `_get_items()`, and `_get_amounts()` in sequence. `DeliveryEwayBillBuilder` and `PickupEwayBillBuilder` override only the supply type and consignor/consignee details — everything else is inherited.
>
> This combined Builder with Template Method. The `EwayBillFactory` acted as the Director — it chose the right builder based on `challan.challan_type` and called `build()`. The view code was just: `factory.create_builder(challan, params).build()`."

---

### 2.6 Follow-up Q&A

**Q: "Builder vs Factory — when to choose?"**
> "Factory is about WHICH object to create — you pass a type string, get an object back. Builder is about HOW to create a complex object — you set properties step by step. If object construction is complex with many optional parts — Builder. If you need to choose between variants of a single type — Factory."

**Q: "What is a Director in Builder pattern?"**
> "Director is an optional component that orchestrates the builder steps. It knows the correct sequence to call builder methods. In my E-way bill system, `EwayBillFactory` acted as the Director — it selected the right builder and called `build()`. The client didn't need to know the construction sequence."

**Q: "What's the benefit of fluent interface in Builder?"**
> "Readability — method chaining makes the intent clear. `BookingDraftBuilder().with_package(p).on_date(d).for_guests(4).build()` reads like English. It also makes optional parameters natural — you only call the methods you need. Compare to a constructor with 10 positional parameters where you have to pass `None` for unused ones."

---

*Last Updated: April 2026 | SDE-2 Interview Prep*
