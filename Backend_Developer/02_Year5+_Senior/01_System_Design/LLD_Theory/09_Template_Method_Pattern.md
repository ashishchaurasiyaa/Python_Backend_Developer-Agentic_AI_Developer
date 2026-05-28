# Template Method Pattern
> **Category:** Behavioral | **Difficulty:** Easy-Medium | **Interview Frequency:** ★★★★☆

---

## Quick Reference Card
```
Kya karta hai : Algorithm ka skeleton define karo — specific steps subclass implement kare
Kab use karo  : Same overall flow, alag alag step implementations
Key mechanism : Base class mein template method (final steps sequence) + abstract steps
Real project  : Youngman → EwayBillBuilder.build() | Niroskos → BookingDraft → Booking flow
Pattern type  : Behavioral
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Kya hai?

Template Method mein **base class ek overall algorithm define karta hai (steps ka sequence)**, aur specific steps subclass implement karta hai.

Parent class bolta hai "pehle yeh karo, phir yeh, phir yeh" — lekin "yeh karo" ka actual kaam child ke paas hai.

**Simple analogy:**
```
Recipe template:
  Step 1: Pani garam karo      (same sab ke liye)
  Step 2: Ingredient dalao     ← TEA: chai patti | COFFEE: coffee powder
  Step 3: Stir karo            (same sab ke liye)
  Step 4: Serve karo           ← TEA: cup mein | COFFEE: mug mein

Template = Recipe (steps ka order fixed hai)
Child     = Tea recipe / Coffee recipe (specific steps alag)
```

---

### 1.2 Kab use karo?

```
✅ Multiple classes mein same overall flow hai lekin steps alag hain
✅ Code duplication avoid karna hai — common steps ek jagah
✅ Algorithm ka structure protect karna hai — sequence change nahi hona chahiye
✅ "Hook methods" — optional steps provide karne ho child ko
✅ Report generation — header + data + footer (structure same, content alag)
✅ Data processing pipelines — validate → transform → save (steps alag)
```

---

### 1.3 Kab mat use karo?

```
❌ Subclasses bahut alag hain — common template ka koi faida nahi
❌ Algorithm ka order frequently change hota hai — Strategy better hai
❌ Deep inheritance hierarchy ban raha hai — composition prefer karo
❌ Subclass template method override kare — design violation
```

---

### 1.4 Code — Hinglish Comments ke saath

```python
from abc import ABC, abstractmethod
from datetime import datetime


# ─── Abstract Base Class — Template ───
class BaseEwayBillBuilder(ABC):
    """
    EwayBill banana ka algorithm fixed hai:
    1. Supply type
    2. Consignor details
    3. Consignee details
    4. Transport details
    5. Item list
    6. Amount details

    Sequence kabhi nahi badlega.
    Lekin Delivery aur Pickup mein consignor/consignee alag hota hai.
    """

    COMPANY_NAME = "Y Equipment Services PVT. LTD."

    def __init__(self, challan, params):
        self.challan  = challan
        self.params   = params
        self._payload = {}

    # ─── TEMPLATE METHOD — yahi main method hai, final hai ───
    def build(self) -> dict:
        """
        Algorithm ka skeleton — yeh sequence kabhi nahi badlega.
        Subclass sirf individual steps implement kare.
        """
        # Step 1: Supply type (Delivery=Outward, Pickup=Inward)
        self._payload.update(self._get_supply_type())

        # Step 2: Consignor details (sender)
        self._payload.update(self._get_consignor_details())

        # Step 3: Consignee details (receiver)
        self._payload.update(self._get_consignee_details())

        # Step 4: Transport details (common — both types ke liye same)
        self._payload.update(self._get_transport_details())

        # Step 5: Items (common)
        self._payload['item_list'] = self._get_item_list()

        # Step 6: Amount details (common — GST calculation)
        self._payload['amount_details'] = self._get_amount_details()

        # Optional hook — subclass override kar sakta hai ya nahi
        self._post_build_hook()

        return self._payload

    # ─── Abstract steps — subclass MUST implement ───
    @abstractmethod
    def _get_supply_type(self) -> dict:
        """Delivery=Outward/type2, Pickup=Inward/type3"""
        pass

    @abstractmethod
    def _get_consignor_details(self) -> dict:
        """Sender ki details — Delivery mein Company, Pickup mein Customer"""
        pass

    @abstractmethod
    def _get_consignee_details(self) -> dict:
        """Receiver ki details — Delivery mein Customer, Pickup mein Company"""
        pass

    # ─── Concrete steps — subclass change nahi karega ───
    def _get_transport_details(self) -> dict:
        """Common — dono types ke liye same"""
        return {
            "transporter_id":  self.params.get('transporter_id', ''),
            "transport_mode":  self.params.get('mode', 'Road'),
            "vehicle_number":  self.params.get('vehicle_no', ''),
            "distance":        self.params.get('distance', 0),
        }

    def _get_item_list(self) -> list:
        """Common — items list banana"""
        return [
            {
                "product_name":    item.name,
                "hsn_code":        item.hsn_code,
                "quantity":        item.quantity,
                "unit":            item.unit,
                "taxable_amount":  float(item.amount),
            }
            for item in self.challan.items.all()
        ]

    def _get_amount_details(self) -> dict:
        """Common — GST calculation"""
        total         = sum(float(i.amount) for i in self.challan.items.all())
        is_intra      = self._is_intra_state()
        return {
            "total_value": total,
            "cgst_value":  round(total * 0.09, 2) if is_intra else 0,
            "sgst_value":  round(total * 0.09, 2) if is_intra else 0,
            "igst_value":  round(total * 0.18, 2) if not is_intra else 0,
        }

    def _is_intra_state(self) -> bool:
        return self.challan.godown.state_code == self.challan.order.customer.state_code

    # ─── Hook method — optional, subclass override kar sakta hai ───
    def _post_build_hook(self) -> None:
        """Default: kuch nahi. Override karo agar extra processing chahiye."""
        pass


# ─── Concrete Classes — sirf alag steps implement karo ───

class DeliveryEwayBillBuilder(BaseEwayBillBuilder):
    """Delivery: Company → Customer (Outward supply)"""

    def _get_supply_type(self):
        return {"supply_type": "Outward", "transaction_type": 2}

    def _get_consignor_details(self):
        # Delivery mein company bhejti hai → consignor = company
        g = self.challan.godown
        return {
            "gstin_of_consignor":   g.gstin,
            "name_of_consignor":    self.COMPANY_NAME,
            "address_of_consignor": g.address,
            "pincode_of_consignor": int(g.pincode),
            "state_of_consignor":   int(g.state_code),
        }

    def _get_consignee_details(self):
        # Delivery mein customer receive karta hai → consignee = customer
        c = self.challan.order.customer
        return {
            "gstin_of_consignee":   c.gstin or "URP",
            "name_of_consignee":    c.company,
            "address_of_consignee": c.address,
            "pincode_of_consignee": int(c.pincode),
            "state_of_consignee":   int(c.state_code),
        }


class PickupEwayBillBuilder(BaseEwayBillBuilder):
    """Pickup: Customer → Company (Inward supply)"""

    def _get_supply_type(self):
        return {"supply_type": "Inward", "transaction_type": 3}

    def _get_consignor_details(self):
        # Pickup mein customer bhejta hai → consignor = customer
        c = self.challan.order.customer
        return {
            "gstin_of_consignor":   c.gstin or "URP",
            "name_of_consignor":    c.company,
            "address_of_consignor": c.address,
            "pincode_of_consignor": int(c.pincode),
            "state_of_consignor":   int(c.state_code),
        }

    def _get_consignee_details(self):
        # Pickup mein company receive karti hai → consignee = company
        g = self.challan.godown
        return {
            "gstin_of_consignee":   g.gstin,
            "name_of_consignee":    self.COMPANY_NAME,
            "address_of_consignee": g.address,
            "pincode_of_consignee": int(g.pincode),
            "state_of_consignee":   int(g.state_code),
        }

    def _post_build_hook(self):
        # Hook override — pickup mein extra validation
        if not self.challan.order.customer.gstin:
            print("[WARN] Customer GSTIN missing — using URP")


# ─── Real Example 2: Data Report Generator ───

class BaseReportGenerator(ABC):
    """
    Report banana ka template:
    1. Header
    2. Data fetch
    3. Data format
    4. Calculations
    5. Footer
    """

    def generate(self, filters: dict) -> str:
        """Template method — yeh sequence fixed hai"""
        report  = self._generate_header(filters)  # Step 1
        data    = self._fetch_data(filters)        # Step 2
        rows    = self._format_rows(data)          # Step 3
        summary = self._calculate_summary(data)    # Step 4
        footer  = self._generate_footer(summary)   # Step 5
        return report + rows + footer

    def _generate_header(self, filters: dict) -> str:
        """Common header — sab reports ke liye same"""
        return f"Report Date: {datetime.now().strftime('%d/%m/%Y')}\n"

    @abstractmethod
    def _fetch_data(self, filters: dict) -> list:
        pass

    @abstractmethod
    def _format_rows(self, data: list) -> str:
        pass

    @abstractmethod
    def _calculate_summary(self, data: list) -> dict:
        pass

    def _generate_footer(self, summary: dict) -> str:
        """Common footer"""
        return f"\nGenerated by Y Equipment Services\n"


class InvoiceReport(BaseReportGenerator):
    def _fetch_data(self, filters):
        # DB se invoices fetch karo
        return [
            {"invoice_no": "INV-001", "customer": "Tata Steel", "amount": 50000},
            {"invoice_no": "INV-002", "customer": "L&T",        "amount": 75000},
        ]

    def _format_rows(self, data):
        rows = ""
        for inv in data:
            rows += f"{inv['invoice_no']} | {inv['customer']} | {inv['amount']}\n"
        return rows

    def _calculate_summary(self, data):
        return {"total": sum(d["amount"] for d in data), "count": len(data)}

    def _generate_footer(self, summary):
        # Override footer — custom summary
        return f"\nTotal: Rs {summary['total']} | {summary['count']} invoices\n"


class ARAgingReport(BaseReportGenerator):
    def _fetch_data(self, filters):
        return [
            {"customer": "Tata Steel", "overdue_days": 15, "amount": 25000},
            {"customer": "L&T",        "overdue_days": 45, "amount": 60000},
        ]

    def _format_rows(self, data):
        rows = ""
        for row in data:
            flag = "⚠️" if row["overdue_days"] > 30 else "  "
            rows += f"{flag} {row['customer']} | {row['overdue_days']} days | Rs {row['amount']}\n"
        return rows

    def _calculate_summary(self, data):
        critical = [d for d in data if d["overdue_days"] > 30]
        return {"total": sum(d["amount"] for d in data), "critical": len(critical)}


# Usage — same generate() call, alag alag reports
invoice_report = InvoiceReport()
ar_report      = ARAgingReport()

print(invoice_report.generate({"month": "April 2024"}))
print(ar_report.generate({"days_overdue": 15}))
```

---

### 1.5 Tumhara Real Project Mein Kahan Use Hua

```
Project 1 — Youngman Django Backend (ACTUAL CODE):
  → BaseEwayBillBuilder.build() — yahi Template Method hai
    Steps: supply_type → consignor → consignee → transport → items → amounts
    DeliveryEwayBillBuilder: Outward supply, Company as consignor
    PickupEwayBillBuilder:   Inward supply, Customer as consignor
    Common steps (transport, items, amounts) — ek baar likhe, dono use karte hain

Project 2 — Niroskos Safari Platform:
  → BookingDraft → Booking conversion
    Steps: validate draft → create order → create order items →
           create booking → link to draft → send confirmation
    Process same hai — details alag (package type, group vs individual)

Project 3 — Youngman ERP (Reports):
  → Invoice Report, AR Aging Report, Collections Report
    Sab ke header/footer same — data fetch aur format alag
    BaseReportGenerator mein template, subclass mein data logic
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definition

> **Template Method is a behavioral pattern that defines the skeleton of an algorithm in a base class, deferring some steps to subclasses. It lets subclasses redefine certain steps of an algorithm without changing the algorithm's overall structure.**

---

### 2.2 Problem It Solves

```
Without Template Method — code duplication:
  class DeliveryEwayBill:
      def build(self):
          payload = {}
          payload.update(get_outward_supply())     # Unique
          payload.update(get_company_consignor())  # Unique
          payload.update(get_customer_consignee()) # Unique
          payload.update(get_transport())          # DUPLICATE ←
          payload['items']   = get_items()         # DUPLICATE ←
          payload['amounts'] = get_amounts()       # DUPLICATE ←
          return payload

  class PickupEwayBill:
      def build(self):
          payload = {}
          payload.update(get_inward_supply())      # Unique
          payload.update(get_customer_consignor()) # Unique
          payload.update(get_company_consignee())  # Unique
          payload.update(get_transport())          # DUPLICATE ←
          payload['items']   = get_items()         # DUPLICATE ←
          payload['amounts'] = get_amounts()       # DUPLICATE ←
          return payload
  # Transport, items, amounts — exact copy in both!

With Template Method:
  BaseEwayBillBuilder.build() has full sequence
  Only _get_supply_type, _get_consignor, _get_consignee are abstract
  Transport, items, amounts are concrete in base — no duplication
```

---

### 2.3 Key Components

| Component | Role | Example |
|-----------|------|---------|
| **Abstract Base Class** | Defines template method + abstract steps | `BaseEwayBillBuilder` |
| **Template Method** | Algorithm skeleton — calls steps in order | `build()` |
| **Abstract Steps** | Must be implemented by subclasses | `_get_supply_type()`, `_get_consignor_details()` |
| **Concrete Steps** | Common implementation in base | `_get_transport_details()`, `_get_item_list()` |
| **Hook Methods** | Optional override points | `_post_build_hook()` |
| **Concrete Subclasses** | Implement only variable steps | `DeliveryEwayBillBuilder`, `PickupEwayBillBuilder` |

---

### 2.4 Clean Code Example

```python
from abc import ABC, abstractmethod

class DataProcessor(ABC):

    def process(self, raw_data: list) -> list:
        """Template method — fixed algorithm"""
        validated = self._validate(raw_data)    # Step 1
        cleaned   = self._clean(validated)      # Step 2
        enriched  = self._enrich(cleaned)       # Step 3
        return self._save(enriched)             # Step 4

    @abstractmethod
    def _validate(self, data: list) -> list: pass

    @abstractmethod
    def _enrich(self, data: list) -> list: pass

    def _clean(self, data: list) -> list:
        """Common — remove nulls and duplicates"""
        return [d for d in data if d is not None]

    def _save(self, data: list) -> list:
        """Common — return processed data"""
        print(f"Saving {len(data)} records")
        return data


class CustomerDataProcessor(DataProcessor):
    def _validate(self, data):
        return [d for d in data if 'gstin' in d and len(d['gstin']) == 15]

    def _enrich(self, data):
        for record in data:
            record['gstin_verified'] = True
        return data


class InvoiceDataProcessor(DataProcessor):
    def _validate(self, data):
        return [d for d in data if d.get('amount', 0) > 0]

    def _enrich(self, data):
        for record in data:
            record['gst_amount'] = record['amount'] * 0.18
        return data


# Same process() call — different validation and enrichment
cust_proc = CustomerDataProcessor()
inv_proc  = InvoiceDataProcessor()

cust_proc.process([{'gstin': '27AABCY1234A1ZP', 'name': 'Tata'}])
inv_proc.process([{'invoice_no': 'INV-001', 'amount': 50000}])
```

---

### 2.5 Real Project Answer

**"Explain Template Method from your work"**

> "My most direct use of Template Method is the E-way bill builder in Youngman Django backend — which is actually in my existing code files.
>
> The government e-way bill API requires a JSON payload with 6 sections: supply type, consignor details, consignee details, transport details, item list, and amount details. For Delivery challan (Company→Customer) and Pickup challan (Customer→Company), the supply type and consignor/consignee are reversed, but transport, items, and amounts are calculated identically.
>
> `BaseEwayBillBuilder.build()` is the template method — it calls all 6 steps in fixed sequence. Supply type, consignor, and consignee are abstract methods — each subclass implements them differently. Transport, items, and amounts are concrete methods in base — written once, inherited by both.
>
> The result: `DeliveryEwayBillBuilder` and `PickupEwayBillBuilder` each implement only 3 methods. Zero duplicate code for the common 3 sections. The `EwayBillFactory` acts as the director — picks the right builder and calls `build()`."

---

### 2.6 Follow-up Q&A

**Q: "Template Method vs Strategy — key difference?"**
> "Template Method uses inheritance — base class defines the skeleton, subclass fills in steps. Structure is fixed at compile time. Strategy uses composition — algorithm is injected at runtime, completely replaceable. Use Template Method when overall structure is fixed but steps vary. Use Strategy when you need to swap the entire algorithm at runtime."

**Q: "What are Hook Methods?"**
> "Hooks are optional override points in the template. Base class provides an empty default implementation. Subclasses can override if they need additional behavior at that point. In my E-way bill builder, `_post_build_hook()` defaults to no-op. `PickupEwayBillBuilder` overrides it to log a warning when GSTIN is missing. Delivery builder doesn't override it — hook is skipped."

**Q: "Hollywood Principle — what is it?"**
> "Don't call us, we'll call you. In Template Method, the base class calls the subclass methods — not the other way around. Subclass implements steps but doesn't control when they're called. The template method controls the sequence. This inversion of control prevents subclasses from breaking the algorithm structure."

---

## Template Method vs Strategy vs Builder

| | Template Method | Strategy | Builder |
|---|----------------|---------|---------|
| **Mechanism** | Inheritance | Composition | Composition |
| **Fixed** | Algorithm structure | Context class | Construction process |
| **Variable** | Specific steps | Entire algorithm | Step implementations |
| **Change time** | Compile time | Runtime | Compile time |
| **Real example** | `EwayBillBuilder.build()` | `PaymentStrategy.initiate()` | `BookingDraftBuilder.build()` |

---

*Last Updated: April 2026 | SDE-2 Interview Prep*
