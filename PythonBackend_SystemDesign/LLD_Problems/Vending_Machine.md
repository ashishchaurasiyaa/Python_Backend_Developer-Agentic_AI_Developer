# Vending Machine LLD

## Quick Reference Card
```
Pattern Used    → State Machine + Strategy (payment)
Core Challenge  → State transitions, Money handling, Inventory
Key States      → IDLE → ITEM_SELECTED → PAYMENT → DISPENSING → CHANGE → IDLE
Interview Hook  → "State Pattern — har state apna behavior define karta hai"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Kya hai?

Vending Machine ek classic **State Machine** problem hai:
- Idle hoti hai pehle
- Item select karo
- Paisa daalo
- Item milta hai + change milta hai

**State Pattern vs Simple State Machine:**
- Simple: ek class mein sabhi states + if-else chains
- State Pattern: har state apni class hai, apna behavior khud handle karta hai
- Result: open/closed principle — naya state add karo without existing code change

### 1.2 Code

```python
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Optional
import threading

# ===== PRODUCT =====

@dataclass
class Product:
    code: str           # "A1", "B2" etc
    name: str
    price: float
    quantity: int = 0
    
    def is_available(self) -> bool:
        return self.quantity > 0

# ===== STATE (Abstract) =====

class VendingMachineState:
    """Har state apna behavior define karta hai"""
    
    def select_item(self, machine: 'VendingMachine', code: str) -> str:
        return "Action not allowed in current state"
    
    def insert_money(self, machine: 'VendingMachine', amount: float) -> str:
        return "Action not allowed in current state"
    
    def dispense(self, machine: 'VendingMachine') -> str:
        return "Action not allowed in current state"
    
    def cancel(self, machine: 'VendingMachine') -> str:
        return "Action not allowed in current state"
    
    def __repr__(self):
        return self.__class__.__name__

# ===== CONCRETE STATES =====

class IdleState(VendingMachineState):
    """Machine ready hai, koi action nahi hua"""
    
    def select_item(self, machine, code):
        product = machine.get_product(code)
        
        if not product:
            return f"Product {code} not found"
        
        if not product.is_available():
            return f"Sorry, {product.name} is out of stock"
        
        machine.selected_product = product
        machine.transition_to(machine.item_selected_state)
        return f"Selected: {product.name} (₹{product.price}). Please insert money."
    
    def cancel(self, machine):
        return "Nothing to cancel"

class ItemSelectedState(VendingMachineState):
    """Item select ho gaya, paisa daalna hai"""
    
    def insert_money(self, machine, amount):
        if amount <= 0:
            return "Invalid amount"
        
        machine.inserted_amount += amount
        remaining = machine.selected_product.price - machine.inserted_amount
        
        if machine.inserted_amount >= machine.selected_product.price:
            machine.transition_to(machine.payment_done_state)
            return (f"₹{amount} accepted. Total: ₹{machine.inserted_amount}. "
                    f"Press dispense!")
        else:
            return f"₹{amount} accepted. Please insert ₹{remaining:.2f} more."
    
    def cancel(self, machine):
        refund = machine.inserted_amount
        machine.inserted_amount = 0
        machine.selected_product = None
        machine.transition_to(machine.idle_state)
        return f"Cancelled. Refund: ₹{refund}"

class PaymentDoneState(VendingMachineState):
    """Paisa kaafi hai, dispense karna hai"""
    
    def insert_money(self, machine, amount):
        machine.inserted_amount += amount
        return f"₹{amount} accepted. Total: ₹{machine.inserted_amount}. Press dispense!"
    
    def dispense(self, machine):
        product = machine.selected_product
        change = machine.inserted_amount - product.price
        
        # Dispense product
        product.quantity -= 1
        
        machine.inserted_amount = 0
        machine.selected_product = None
        machine.transition_to(machine.idle_state)
        
        if change > 0:
            return f"Dispensing {product.name}! Change: ₹{change:.2f}. Thank you!"
        else:
            return f"Dispensing {product.name}! Thank you!"
    
    def cancel(self, machine):
        refund = machine.inserted_amount
        machine.inserted_amount = 0
        machine.selected_product = None
        machine.transition_to(machine.idle_state)
        return f"Cancelled. Refund: ₹{refund}"

class OutOfStockState(VendingMachineState):
    """Item select kiya but tab tak stock khatam ho gaya"""
    
    def cancel(self, machine):
        refund = machine.inserted_amount
        machine.inserted_amount = 0
        machine.selected_product = None
        machine.transition_to(machine.idle_state)
        return f"Out of stock! Refund: ₹{refund}"

# ===== VENDING MACHINE =====

class VendingMachine:
    """
    State machine — state object hi decide karta hai behavior
    """
    
    def __init__(self):
        # State instances (shared, stateless)
        self.idle_state = IdleState()
        self.item_selected_state = ItemSelectedState()
        self.payment_done_state = PaymentDoneState()
        self.out_of_stock_state = OutOfStockState()
        
        self._current_state: VendingMachineState = self.idle_state
        self._products: Dict[str, Product] = {}
        self.selected_product: Optional[Product] = None
        self.inserted_amount: float = 0.0
        self._lock = threading.Lock()
    
    def transition_to(self, state: VendingMachineState):
        print(f"  [State] {self._current_state} → {state}")
        self._current_state = state
    
    def add_product(self, code: str, name: str, price: float, quantity: int):
        self._products[code] = Product(code, name, price, quantity)
        print(f"[VM] Added: {code} - {name} ₹{price} x{quantity}")
    
    def restock(self, code: str, quantity: int):
        if code in self._products:
            self._products[code].quantity += quantity
            print(f"[VM] Restocked: {code} +{quantity} = {self._products[code].quantity}")
    
    def get_product(self, code: str) -> Optional[Product]:
        return self._products.get(code)
    
    # Public interface — delegates to current state
    
    def select_item(self, code: str) -> str:
        with self._lock:
            result = self._current_state.select_item(self, code)
            print(f"[VM] select_item({code}): {result}")
            return result
    
    def insert_money(self, amount: float) -> str:
        with self._lock:
            result = self._current_state.insert_money(self, amount)
            print(f"[VM] insert_money(₹{amount}): {result}")
            return result
    
    def dispense(self) -> str:
        with self._lock:
            result = self._current_state.dispense(self)
            print(f"[VM] dispense(): {result}")
            return result
    
    def cancel(self) -> str:
        with self._lock:
            result = self._current_state.cancel(self)
            print(f"[VM] cancel(): {result}")
            return result
    
    def show_inventory(self):
        print("\n[VM] === INVENTORY ===")
        for code, product in self._products.items():
            status = "IN STOCK" if product.is_available() else "OUT OF STOCK"
            print(f"  {code}: {product.name} ₹{product.price} x{product.quantity} [{status}]")
        print(f"  Current state: {self._current_state}")
        print(f"  Inserted: ₹{self.inserted_amount}")

# ===== DEMO =====

def demo():
    print("=" * 50)
    print("VENDING MACHINE DEMO")
    print("=" * 50)
    
    vm = VendingMachine()
    
    # Stock karo
    vm.add_product("A1", "Coke", 25.0, 3)
    vm.add_product("A2", "Pepsi", 25.0, 2)
    vm.add_product("B1", "Chips", 20.0, 1)
    
    vm.show_inventory()
    
    # Normal flow
    print("\n--- Normal Purchase ---")
    vm.select_item("A1")
    vm.insert_money(20)
    vm.insert_money(10)
    vm.dispense()
    
    # Exact change
    print("\n--- Exact Change ---")
    vm.select_item("B1")
    vm.insert_money(20)
    vm.dispense()
    
    # Cancel mid-way
    print("\n--- Cancel ---")
    vm.select_item("A2")
    vm.insert_money(15)
    vm.cancel()
    
    # Invalid state test
    print("\n--- Invalid State Test ---")
    vm.dispense()  # Nothing selected — state machine rejects
    
    vm.show_inventory()
    print("\n[Demo Complete]")

if __name__ == "__main__":
    demo()
```

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definition

> Vending Machine implements the **State Pattern** — each state is a class that encapsulates its own behavior. The machine delegates all operations to its current state object. Invalid transitions are silently ignored (safe default). This eliminates if-else chains and makes adding new states (e.g., MaintenanceState) a zero-change operation on existing code.

### 2.2 State Transition Diagram

```
IDLE ──(select valid item)──→ ITEM_SELECTED ──(enough money)──→ PAYMENT_DONE
  ↑                               │                                    │
  │                        (cancel/refund)                      (dispense)
  └───────────────────────────────┘                                    │
  ↑                                                                     │
  └─────────────────────────────────────────────────────────────────────┘

OUT_OF_STOCK: (item selected but stock just ran out) → cancel → IDLE
```

### 2.3 Why State Pattern over if-else?

```python
# Bad (if-else):
def insert_money(self, amount):
    if self.state == "IDLE":
        return "Select item first"
    elif self.state == "ITEM_SELECTED":
        self.inserted += amount
        ...
    elif self.state == "PAYMENT_DONE":
        ...
    # Adding new state = modify this function + every other function

# Good (State Pattern):
def insert_money(self, amount):
    return self._current_state.insert_money(self, amount)
    # Each state handles it. New state = new class only.
```

### 2.4 Thread Safety

```python
# Machine has single Lock — all state transitions protected
def select_item(self, code):
    with self._lock:                     # Serializes all operations
        return self._current_state.select_item(self, code)

# State objects themselves are STATELESS (shared across machine instances)
# Machine context (inserted_amount, selected_product) lives in VendingMachine
# This allows state singletons — no new object per transition
```

### 2.5 Common Follow-up Q&A

**Q1: How do you handle the machine running out of change?**
> "Add a ChangeAvailableState check before PaymentDoneState transitions to Dispense. The machine tracks denomination counts (coins: 1, 2, 5, 10; notes: 20, 50, 100). Greedy algorithm: largest denomination first. If change can't be made exactly, offer rounded amount or reject payment with 'exact change only' message."

**Q2: How would you add a maintenance mode?**
> "New MaintenanceState class — all public methods return 'Machine under maintenance'. Add transition: VendingMachine.set_maintenance(True) → transition_to(maintenance_state). Admin interface bypasses state for restocking. This is zero changes to existing states — pure Open/Closed principle."

**Q3: How do you persist state across power failures?**
> "State + context serialized to persistent storage (file/DB) on every transition. On restart: load last state + inserted_amount. If inserted_amount > 0 on restart → refund_pending flag → dispense change on next user interaction."

---

## Interview Cheat Sheet

```
30-second pitch:
"Vending machine uses State Pattern. 4 states: IDLE, ITEM_SELECTED,
PAYMENT_DONE, OUT_OF_STOCK. Each state class handles its own method calls
and returns safe defaults for invalid actions. Machine delegates all calls
to current state object. Thread safety via single Lock."

Patterns: State, Strategy (payment methods), Observer (low-stock alert)
```
