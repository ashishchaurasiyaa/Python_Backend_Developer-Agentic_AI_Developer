"""
============================================================
MEDIATOR PATTERN — Practical Implementation
============================================================
Run:  python mediator.py
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from collections import defaultdict


# ============================================================
# 1. MEDIATOR BASE
# ============================================================
class Mediator(ABC):
    @abstractmethod
    def notify(self, sender: Any, event: str, data: Any = None) -> None:
        ...


# ============================================================
# 2. EXAMPLE 1: CHAT ROOM
# ============================================================
class ChatRoom(Mediator):
    def __init__(self, name: str):
        self.name = name
        self.users: dict[str, "ChatUser"] = {}

    def register(self, user: "ChatUser"):
        self.users[user.name] = user
        user.mediator = self
        self._broadcast_system(f"{user.name} joined {self.name}")

    def unregister(self, user: "ChatUser"):
        if user.name in self.users:
            del self.users[user.name]
            self._broadcast_system(f"{user.name} left")

    def notify(self, sender, event, data=None):
        if event == "message":
            for name, user in self.users.items():
                if name != sender.name:
                    user.receive(sender.name, data)
        elif event == "private":
            target, msg = data
            if target in self.users:
                self.users[target].receive(sender.name, msg, private=True)

    def _broadcast_system(self, msg):
        print(f"  [SYSTEM] {msg}")


class ChatUser:
    def __init__(self, name: str):
        self.name = name
        self.mediator: Mediator | None = None

    def send(self, msg: str):
        self.mediator.notify(self, "message", msg)

    def whisper(self, to: str, msg: str):
        self.mediator.notify(self, "private", (to, msg))

    def receive(self, sender: str, msg: str, private: bool = False):
        tag = "(WHISPER) " if private else ""
        print(f"  [{self.name}] {tag}<{sender}> {msg}")


def demo_chat():
    print("=" * 60)
    print("DEMO 1: Chat Room Mediator")
    print("=" * 60)
    room = ChatRoom("general")
    alice = ChatUser("Alice")
    bob = ChatUser("Bob")
    carol = ChatUser("Carol")
    room.register(alice)
    room.register(bob)
    room.register(carol)

    alice.send("Hi everyone!")
    bob.send("Hello Alice")
    carol.whisper("Alice", "Psst, want to grab coffee?")
    room.unregister(bob)
    carol.send("Where did Bob go?")


# ============================================================
# 3. EXAMPLE 2: FORM VALIDATION MEDIATOR
# ============================================================
@dataclass
class FormField:
    name: str
    value: str = ""
    enabled: bool = True
    options: list = field(default_factory=list)
    mediator: Mediator | None = None

    def set_value(self, value: str):
        self.value = value
        if self.mediator:
            self.mediator.notify(self, "field_changed")


class FormMediator(Mediator):
    """Coordinates field interactions:
    - Country change → repopulate state dropdown
    - Password change → enable/disable submit
    """
    def __init__(self):
        self.fields: dict[str, FormField] = {}
        self._country_states = {
            "India": ["Delhi", "Maharashtra", "Karnataka"],
            "USA": ["California", "Texas", "New York"],
        }

    def add(self, field_: FormField):
        self.fields[field_.name] = field_
        field_.mediator = self

    def notify(self, sender: FormField, event, data=None):
        if event != "field_changed":
            return
        if sender.name == "country":
            states = self._country_states.get(sender.value, [])
            self.fields["state"].options = states
            self.fields["state"].value = ""    # reset
            print(f"  → State options updated: {states}")
        elif sender.name == "password":
            strong = len(sender.value) >= 8
            self.fields["submit"].enabled = strong
            print(f"  → Submit enabled: {strong}")


def demo_form():
    print("\n" + "=" * 60)
    print("DEMO 2: Form Validation Mediator")
    print("=" * 60)
    form = FormMediator()
    form.add(FormField("country"))
    form.add(FormField("state"))
    form.add(FormField("password"))
    form.add(FormField("submit", enabled=False))

    form.fields["country"].set_value("India")
    form.fields["password"].set_value("short")
    form.fields["password"].set_value("longenough123")
    form.fields["country"].set_value("USA")


# ============================================================
# 4. EXAMPLE 3: AIR TRAFFIC CONTROL
# ============================================================
class AirTrafficControl(Mediator):
    def __init__(self):
        self.aircraft: list["Aircraft"] = []
        self.runway_busy = False

    def register(self, plane: "Aircraft"):
        self.aircraft.append(plane)
        plane.atc = self

    def notify(self, sender: "Aircraft", event, data=None):
        if event == "request_landing":
            if self.runway_busy:
                print(f"  [ATC → {sender.id}] HOLD — runway busy")
                # Tell others to wait too
            else:
                self.runway_busy = True
                print(f"  [ATC → {sender.id}] CLEARED for landing")
                sender.land()
        elif event == "landed":
            self.runway_busy = False
            print(f"  [ATC] Runway clear after {sender.id}")


class Aircraft:
    def __init__(self, plane_id: str):
        self.id = plane_id
        self.atc: Mediator | None = None

    def request_landing(self):
        print(f"  [{self.id}] Requesting landing")
        self.atc.notify(self, "request_landing")

    def land(self):
        print(f"  [{self.id}] Touchdown!")
        self.atc.notify(self, "landed")


def demo_atc():
    print("\n" + "=" * 60)
    print("DEMO 3: Air Traffic Control")
    print("=" * 60)
    atc = AirTrafficControl()
    a1 = Aircraft("AI-101")
    a2 = Aircraft("UA-202")
    a3 = Aircraft("LH-303")
    for a in (a1, a2, a3):
        atc.register(a)

    a1.request_landing()
    a2.request_landing()    # will be told to hold
    a3.request_landing()


# ============================================================
# 5. EXAMPLE 4: SAGA ORCHESTRATOR (microservices)
# ============================================================
class OrderSagaMediator(Mediator):
    """Coordinates order placement across services with compensation."""
    def __init__(self):
        self.services = {}
        self.state = "INIT"
        self.compensations = []

    def register(self, name, service):
        self.services[name] = service
        service.mediator = self

    def notify(self, sender, event, data=None):
        # Sender publishes events; mediator decides what's next
        print(f"  [SAGA] {sender.__class__.__name__}: {event}")
        if event == "payment_charged":
            self.compensations.append(("refund", data))
            self.services["inventory"].reserve(data["items"])
        elif event == "inventory_reserved":
            self.compensations.append(("release_inventory", data))
            self.services["shipping"].create_shipment(data)
        elif event == "shipping_created":
            self.state = "SUCCESS"
            print("  [SAGA] ✅ Order completed")
        elif event == "FAIL":
            self.state = "FAILED"
            self._compensate()

    def _compensate(self):
        print("  [SAGA] ⚠️  Running compensations:")
        for action, data in reversed(self.compensations):
            print(f"    - {action}({data})")


class PaymentService:
    def __init__(self): self.mediator = None
    def charge(self, items, amount):
        print(f"  [Payment] Charging ${amount}")
        self.mediator.notify(self, "payment_charged", {"items": items, "amount": amount})


class InventoryService:
    def __init__(self): self.mediator = None
    def reserve(self, items):
        if "out-of-stock" in items:
            print("  [Inventory] Failed!")
            self.mediator.notify(self, "FAIL", None)
        else:
            print(f"  [Inventory] Reserved {items}")
            self.mediator.notify(self, "inventory_reserved", {"items": items})


class ShippingService:
    def __init__(self): self.mediator = None
    def create_shipment(self, data):
        print(f"  [Shipping] Created for {data['items']}")
        self.mediator.notify(self, "shipping_created", data)


def demo_saga():
    print("\n" + "=" * 60)
    print("DEMO 4: Saga Orchestrator Mediator")
    print("=" * 60)
    saga = OrderSagaMediator()
    saga.register("payment", PaymentService())
    saga.register("inventory", InventoryService())
    saga.register("shipping", ShippingService())

    print("--- Happy path ---")
    saga.services["payment"].charge(["item-A", "item-B"], 250)

    print("\n--- Failure with compensation ---")
    saga2 = OrderSagaMediator()
    saga2.register("payment", PaymentService())
    saga2.register("inventory", InventoryService())
    saga2.register("shipping", ShippingService())
    saga2.services["payment"].charge(["out-of-stock"], 100)


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    demo_chat()
    demo_form()
    demo_atc()
    demo_saga()

    print("\n" + "=" * 60)
    print("KEY TAKEAWAYS")
    print("=" * 60)
    print("""
1. Mediator centralizes N-to-N coupling into N-to-1
2. Components only know mediator, not each other
3. Real uses: chat, forms, ATC, saga orchestrator, workflow
4. Don't let mediator become God Class — split by domain
5. Use registration for flexibility, dependency injection for testing
6. Different from Observer (one→many) and Facade (one-way)
""")
