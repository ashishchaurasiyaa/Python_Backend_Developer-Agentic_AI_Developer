# LLD — Parking Lot System
> **Interview Level:** SDE-2 | **Difficulty:** Medium | **Time:** 30-40 min
> **Patterns Used:** Singleton, Strategy (x2), Observer, Factory, State

---

## Step 1: Requirements Analysis (Interviewer ke saamne 2 min karo)

```
Functional Requirements:
  ✅ Multiple entrances and exits
  ✅ Display board — free spots count by type
  ✅ Spot types: Mini (motorbike), Compact (car), Large (truck)
  ✅ Multiple floors
  ✅ Admin: add/remove entrances & exits
  ✅ Attendant: create parking tickets
  ✅ Parking strategy: Nearest First / Farthest First
  ✅ Multiple payment methods

Clarifying Questions (interviewer se poochho):
  Q: Ek vehicle ek hi spot le sakti hai?          → Yes
  Q: Reserved spots hote hain (monthly pass)?     → Out of scope
  Q: Pricing kaise — flat rate ya hourly?         → Hourly
  Q: Spot compatibility strict hai?               → Yes (mini=bike only)
  Q: Concurrent entries handle karna hai?         → Yes (thread safety)
```

---

## Step 2: Core Entities

```
ParkingLot        → Singleton — poora system
ParkingFloor      → Ek floor
ParkingSpot       → Ek individual spot (Mini/Compact/Large)
Vehicle           → Motorbike / Car / Truck
Entrance          → Entry gate
Exit              → Exit gate
ParkingTicket     → Entry se exit tak ka record
Payment           → Cash / Card / UPI — Strategy
DisplayBoard      → Observer — free spots dikhata hai
ParkingStrategy   → NearestFirst / FarthestFirst — Strategy
ParkingAttendant  → Ticket create karta hai
Admin             → Entrances/Exits manage karta hai
```

---

## Step 3: Class Diagram (Text)

```
ParkingLot (Singleton)
 ├── floors: List[ParkingFloor]
 ├── entrances: List[Entrance]
 ├── exits: List[Exit]
 ├── display_board: DisplayBoard     ← Observer
 └── strategy: ParkingStrategy       ← Strategy

ParkingFloor
 └── spots: List[ParkingSpot]

ParkingSpot (Abstract)
 ├── MiniSpot      → accepts: Motorbike
 ├── CompactSpot   → accepts: Car
 └── LargeSpot     → accepts: Truck

Vehicle (Abstract)
 ├── Motorbike
 ├── Car
 └── Truck

ParkingTicket
 ├── vehicle: Vehicle
 ├── spot: ParkingSpot
 ├── entry_time: datetime
 └── status: TicketStatus

PaymentStrategy (Abstract)        ← Strategy Pattern
 ├── CashPayment
 ├── CardPayment
 └── UPIPayment

ParkingStrategy (Abstract)        ← Strategy Pattern
 ├── NearestFirstStrategy
 └── FarthestFirstStrategy

DisplayBoard                      ← Observer Pattern
 ├── free_mini: int
 ├── free_compact: int
 └── free_large: int
```

---

## Step 4: Enums & Constants

```python
from enum import Enum

class VehicleType(Enum):
    MOTORBIKE = "motorbike"
    CAR       = "car"
    TRUCK     = "truck"

class SpotType(Enum):
    MINI    = "mini"      # Motorbike ke liye
    COMPACT = "compact"   # Car ke liye
    LARGE   = "large"     # Truck ke liye

class SpotStatus(Enum):
    FREE        = "free"
    OCCUPIED    = "occupied"
    MAINTENANCE = "maintenance"

class TicketStatus(Enum):
    ACTIVE  = "active"
    PAID    = "paid"
    LOST    = "lost"

class PaymentMethod(Enum):
    CASH = "cash"
    CARD = "card"
    UPI  = "upi"

# Spot → Vehicle compatibility map
SPOT_VEHICLE_MAP = {
    SpotType.MINI:    VehicleType.MOTORBIKE,
    SpotType.COMPACT: VehicleType.CAR,
    SpotType.LARGE:   VehicleType.TRUCK,
}
```

---

## Step 5: Complete Implementation

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict
import threading
import uuid


# ════════════════════════════════════════════════
# ENUMS
# ════════════════════════════════════════════════

class VehicleType(Enum):
    MOTORBIKE = "motorbike"
    CAR       = "car"
    TRUCK     = "truck"

class SpotType(Enum):
    MINI    = "mini"
    COMPACT = "compact"
    LARGE   = "large"

class SpotStatus(Enum):
    FREE        = "free"
    OCCUPIED    = "occupied"
    MAINTENANCE = "maintenance"

class TicketStatus(Enum):
    ACTIVE = "active"
    PAID   = "paid"
    LOST   = "lost"

SPOT_VEHICLE_MAP = {
    SpotType.MINI:    VehicleType.MOTORBIKE,
    SpotType.COMPACT: VehicleType.CAR,
    SpotType.LARGE:   VehicleType.TRUCK,
}

HOURLY_RATE = {
    SpotType.MINI:    20,   # Rs 20/hour
    SpotType.COMPACT: 40,   # Rs 40/hour
    SpotType.LARGE:   80,   # Rs 80/hour
}


# ════════════════════════════════════════════════
# VEHICLE CLASSES
# ════════════════════════════════════════════════

class Vehicle(ABC):
    def __init__(self, license_plate: str, vehicle_type: VehicleType):
        self.license_plate = license_plate
        self.vehicle_type  = vehicle_type

    def __repr__(self):
        return f"{self.vehicle_type.value.upper()}({self.license_plate})"

class Motorbike(Vehicle):
    def __init__(self, license_plate: str):
        super().__init__(license_plate, VehicleType.MOTORBIKE)

class Car(Vehicle):
    def __init__(self, license_plate: str):
        super().__init__(license_plate, VehicleType.CAR)

class Truck(Vehicle):
    def __init__(self, license_plate: str):
        super().__init__(license_plate, VehicleType.TRUCK)


# ════════════════════════════════════════════════
# DISPLAY BOARD — Observer Pattern
# ════════════════════════════════════════════════

class DisplayBoard:
    """
    Observer — ParkingSpot state change hone pe automatically update hota hai.
    Global board — sab floors ke free spots dikhata hai.
    """
    def __init__(self):
        self._free_spots: Dict[SpotType, int] = {
            SpotType.MINI:    0,
            SpotType.COMPACT: 0,
            SpotType.LARGE:   0,
        }
        self._lock = threading.Lock()

    def update(self, spot_type: SpotType, delta: int) -> None:
        """Spot free/occupied hone pe call hota hai"""
        with self._lock:
            self._free_spots[spot_type] = max(
                0, self._free_spots[spot_type] + delta
            )

    def initialize(self, floors: List['ParkingFloor']) -> None:
        """Startup pe sab floors se count karo"""
        with self._lock:
            for spot_type in SpotType:
                self._free_spots[spot_type] = sum(
                    floor.count_free_spots(spot_type)
                    for floor in floors
                )

    def display(self) -> str:
        with self._lock:
            return (
                f"╔══════════════════════════════╗\n"
                f"║      AVAILABLE SPOTS          ║\n"
                f"╠══════════════════════════════╣\n"
                f"║  Mini    (Motorbike): {self._free_spots[SpotType.MINI]:4d}   ║\n"
                f"║  Compact (Car)      : {self._free_spots[SpotType.COMPACT]:4d}   ║\n"
                f"║  Large   (Truck)    : {self._free_spots[SpotType.LARGE]:4d}   ║\n"
                f"╚══════════════════════════════╝"
            )

    def get_free_count(self, spot_type: SpotType) -> int:
        with self._lock:
            return self._free_spots[spot_type]


# ════════════════════════════════════════════════
# PARKING SPOT — State Pattern
# ════════════════════════════════════════════════

class ParkingSpot(ABC):
    def __init__(
        self,
        spot_id:   str,
        floor_id:  int,
        spot_type: SpotType,
        display_board: DisplayBoard
    ):
        self.spot_id       = spot_id
        self.floor_id      = floor_id
        self.spot_type     = spot_type
        self._status       = SpotStatus.FREE
        self._vehicle:     Optional[Vehicle] = None
        self._display      = display_board
        self._lock         = threading.Lock()

    @property
    def status(self) -> SpotStatus:
        return self._status

    @property
    def vehicle(self) -> Optional[Vehicle]:
        return self._vehicle

    def is_available(self) -> bool:
        return self._status == SpotStatus.FREE

    def can_fit(self, vehicle: Vehicle) -> bool:
        return SPOT_VEHICLE_MAP[self.spot_type] == vehicle.vehicle_type

    def park(self, vehicle: Vehicle) -> bool:
        with self._lock:
            if not self.is_available():
                return False
            if not self.can_fit(vehicle):
                raise ValueError(
                    f"{vehicle.vehicle_type.value} cannot park in "
                    f"{self.spot_type.value} spot"
                )
            self._vehicle = vehicle
            self._status  = SpotStatus.OCCUPIED
            self._display.update(self.spot_type, -1)  # Observer notify
            return True

    def release(self) -> Optional[Vehicle]:
        with self._lock:
            if self._status != SpotStatus.OCCUPIED:
                return None
            vehicle       = self._vehicle
            self._vehicle = None
            self._status  = SpotStatus.FREE
            self._display.update(self.spot_type, +1)  # Observer notify
            return vehicle

    def set_maintenance(self) -> None:
        with self._lock:
            if self._status == SpotStatus.FREE:
                self._status = SpotStatus.MAINTENANCE
                # No display update — spot was already counted as free
                self._display.update(self.spot_type, -1)

    def __repr__(self):
        return (
            f"Spot({self.spot_id}, F{self.floor_id}, "
            f"{self.spot_type.value}, {self._status.value})"
        )


class MiniSpot(ParkingSpot):
    """For Motorbikes only"""
    def __init__(self, spot_id: str, floor_id: int, display: DisplayBoard):
        super().__init__(spot_id, floor_id, SpotType.MINI, display)

class CompactSpot(ParkingSpot):
    """For Cars only"""
    def __init__(self, spot_id: str, floor_id: int, display: DisplayBoard):
        super().__init__(spot_id, floor_id, SpotType.COMPACT, display)

class LargeSpot(ParkingSpot):
    """For Trucks only"""
    def __init__(self, spot_id: str, floor_id: int, display: DisplayBoard):
        super().__init__(spot_id, floor_id, SpotType.LARGE, display)


# ════════════════════════════════════════════════
# PARKING FLOOR
# ════════════════════════════════════════════════

class ParkingFloor:
    def __init__(self, floor_id: int):
        self.floor_id = floor_id
        self._spots:   List[ParkingSpot] = []
        self._lock     = threading.Lock()

    def add_spot(self, spot: ParkingSpot) -> None:
        with self._lock:
            self._spots.append(spot)

    def get_available_spots(self, spot_type: SpotType) -> List[ParkingSpot]:
        with self._lock:
            return [
                s for s in self._spots
                if s.spot_type == spot_type and s.is_available()
            ]

    def count_free_spots(self, spot_type: SpotType) -> int:
        with self._lock:
            return sum(
                1 for s in self._spots
                if s.spot_type == spot_type and s.is_available()
            )

    def get_spot_by_id(self, spot_id: str) -> Optional[ParkingSpot]:
        with self._lock:
            for spot in self._spots:
                if spot.spot_id == spot_id:
                    return spot
        return None

    def __repr__(self):
        return f"Floor({self.floor_id}, spots={len(self._spots)})"


# ════════════════════════════════════════════════
# PARKING STRATEGY — Strategy Pattern
# ════════════════════════════════════════════════

VEHICLE_SPOT_TYPE = {
    VehicleType.MOTORBIKE: SpotType.MINI,
    VehicleType.CAR:       SpotType.COMPACT,
    VehicleType.TRUCK:     SpotType.LARGE,
}

class ParkingStrategy(ABC):
    @abstractmethod
    def find_spot(
        self,
        floors:       List[ParkingFloor],
        vehicle_type: VehicleType
    ) -> Optional[ParkingSpot]:
        pass


class NearestFirstStrategy(ParkingStrategy):
    """
    Ground floor se start karo — pehla available spot lo.
    Floor ID aur Spot ID dono ascending.
    """
    def find_spot(self, floors, vehicle_type):
        spot_type = VEHICLE_SPOT_TYPE[vehicle_type]
        # Sort by floor_id ASC — nearest floor first
        for floor in sorted(floors, key=lambda f: f.floor_id):
            available = floor.get_available_spots(spot_type)
            if available:
                # Same floor mein — lowest spot_id first
                return sorted(available, key=lambda s: s.spot_id)[0]
        return None


class FarthestFirstStrategy(ParkingStrategy):
    """
    Top floor se start karo — last available spot lo.
    VIP ya premium parking ke liye useful.
    """
    def find_spot(self, floors, vehicle_type):
        spot_type = VEHICLE_SPOT_TYPE[vehicle_type]
        # Sort by floor_id DESC — farthest floor first
        for floor in sorted(floors, key=lambda f: f.floor_id, reverse=True):
            available = floor.get_available_spots(spot_type)
            if available:
                # Same floor mein — highest spot_id first
                return sorted(available, key=lambda s: s.spot_id, reverse=True)[0]
        return None


class RandomStrategy(ParkingStrategy):
    """Random spot assign karo — load balancing ke liye"""
    def find_spot(self, floors, vehicle_type):
        import random
        spot_type  = VEHICLE_SPOT_TYPE[vehicle_type]
        all_spots  = []
        for floor in floors:
            all_spots.extend(floor.get_available_spots(spot_type))
        return random.choice(all_spots) if all_spots else None


# ════════════════════════════════════════════════
# PARKING TICKET
# ════════════════════════════════════════════════

class ParkingTicket:
    def __init__(self, vehicle: Vehicle, spot: ParkingSpot):
        self.ticket_id  = f"TKT-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        self.vehicle    = vehicle
        self.spot       = spot
        self.entry_time = datetime.now()
        self.exit_time: Optional[datetime] = None
        self.status     = TicketStatus.ACTIVE
        self.amount:    float = 0.0

    def calculate_amount(self) -> float:
        if not self.exit_time:
            self.exit_time = datetime.now()

        duration_hours = (
            self.exit_time - self.entry_time
        ).total_seconds() / 3600

        # Minimum 1 hour
        billable_hours = max(1.0, duration_hours)
        rate           = HOURLY_RATE[self.spot.spot_type]
        self.amount    = round(billable_hours * rate, 2)
        return self.amount

    def mark_paid(self) -> None:
        self.status = TicketStatus.PAID

    def mark_lost(self) -> None:
        self.status     = TicketStatus.LOST
        self.amount     = 500.0  # Lost ticket penalty
        self.exit_time  = datetime.now()

    def __repr__(self):
        return (
            f"Ticket({self.ticket_id}, {self.vehicle}, "
            f"{self.spot}, {self.status.value})"
        )


# ════════════════════════════════════════════════
# PAYMENT — Strategy Pattern
# ════════════════════════════════════════════════

class PaymentStrategy(ABC):
    @abstractmethod
    def pay(self, amount: float) -> dict:
        pass

class CashPayment(PaymentStrategy):
    def pay(self, amount: float) -> dict:
        print(f"[CASH] Rs {amount} received in cash")
        return {"method": "cash", "amount": amount, "status": "success"}

class CardPayment(PaymentStrategy):
    def __init__(self, card_last4: str):
        self.card_last4 = card_last4

    def pay(self, amount: float) -> dict:
        print(f"[CARD] Rs {amount} charged to card ****{self.card_last4}")
        return {"method": "card", "amount": amount, "status": "success"}

class UPIPayment(PaymentStrategy):
    def __init__(self, upi_id: str):
        self.upi_id = upi_id

    def pay(self, amount: float) -> dict:
        print(f"[UPI] Rs {amount} paid via {self.upi_id}")
        return {"method": "upi", "amount": amount, "status": "success"}


class PaymentFactory:
    @staticmethod
    def create(method: str, **kwargs) -> PaymentStrategy:
        if method == 'cash':
            return CashPayment()
        elif method == 'card':
            return CardPayment(kwargs.get('card_last4', '0000'))
        elif method == 'upi':
            return UPIPayment(kwargs.get('upi_id', 'user@upi'))
        raise ValueError(f"Unknown payment method: {method}")


# ════════════════════════════════════════════════
# ENTRANCE & EXIT
# ════════════════════════════════════════════════

class Entrance:
    def __init__(self, entrance_id: str, floor_id: int = 0):
        self.entrance_id = entrance_id
        self.floor_id    = floor_id
        self.is_active   = True
        self._lock       = threading.Lock()

    def issue_ticket(
        self,
        vehicle:  Vehicle,
        spot:     ParkingSpot,
    ) -> Optional[ParkingTicket]:
        with self._lock:
            if not self.is_active:
                print(f"Entrance {self.entrance_id} is inactive")
                return None

            success = spot.park(vehicle)
            if not success:
                print(f"Could not park {vehicle} at {spot}")
                return None

            ticket = ParkingTicket(vehicle, spot)
            print(f"[ENTRY] {vehicle} parked at {spot} → {ticket.ticket_id}")
            return ticket

    def deactivate(self): self.is_active = False
    def activate(self):   self.is_active = True
    def __repr__(self): return f"Entrance({self.entrance_id})"


class Exit:
    def __init__(self, exit_id: str, floor_id: int = 0):
        self.exit_id   = exit_id
        self.floor_id  = floor_id
        self.is_active = True
        self._lock     = threading.Lock()

    def process_exit(
        self,
        ticket:   ParkingTicket,
        payment:  PaymentStrategy,
    ) -> Optional[dict]:
        with self._lock:
            if not self.is_active:
                print(f"Exit {self.exit_id} is inactive")
                return None

            if ticket.status != TicketStatus.ACTIVE:
                print(f"Ticket {ticket.ticket_id} is {ticket.status.value}")
                return None

            # Calculate amount
            amount  = ticket.calculate_amount()

            # Process payment
            receipt = payment.pay(amount)

            if receipt['status'] == 'success':
                # Release spot
                ticket.spot.release()
                ticket.mark_paid()
                print(
                    f"[EXIT] {ticket.vehicle} exited | "
                    f"Duration: {ticket.exit_time - ticket.entry_time} | "
                    f"Amount: Rs {amount}"
                )
                return {
                    "ticket_id": ticket.ticket_id,
                    "amount":    amount,
                    "receipt":   receipt
                }
            return None

    def deactivate(self): self.is_active = False
    def activate(self):   self.is_active = True
    def __repr__(self): return f"Exit({self.exit_id})"


# ════════════════════════════════════════════════
# PARKING ATTENDANT
# ════════════════════════════════════════════════

class ParkingAttendant:
    """
    Attendant entrance pe hota hai — ticket create karta hai.
    Strategy use karke spot assign karta hai.
    """
    def __init__(self, attendant_id: str, entrance: Entrance):
        self.attendant_id = attendant_id
        self.entrance     = entrance

    def process_entry(
        self,
        vehicle:       Vehicle,
        parking_lot:   'ParkingLot',
    ) -> Optional[ParkingTicket]:
        # Strategy se spot find karo
        spot = parking_lot.find_spot(vehicle)

        if not spot:
            print(f"No available spot for {vehicle.vehicle_type.value}")
            return None

        # Entrance se ticket issue karo
        return self.entrance.issue_ticket(vehicle, spot)

    def process_exit_with_ticket(
        self,
        ticket:        ParkingTicket,
        payment_method: str,
        exit_gate:     Exit,
        **payment_kwargs
    ) -> Optional[dict]:
        payment = PaymentFactory.create(payment_method, **payment_kwargs)
        return exit_gate.process_exit(ticket, payment)

    def __repr__(self): return f"Attendant({self.attendant_id})"


# ════════════════════════════════════════════════
# ADMIN
# ════════════════════════════════════════════════

class Admin:
    """
    Admin — entrances/exits manage karta hai.
    Strategy bhi change kar sakta hai.
    """
    def __init__(self, admin_id: str):
        self.admin_id = admin_id

    def add_entrance(self, parking_lot: 'ParkingLot', entrance: Entrance) -> None:
        parking_lot.add_entrance(entrance)
        print(f"[ADMIN] {entrance} added by {self.admin_id}")

    def remove_entrance(self, parking_lot: 'ParkingLot', entrance_id: str) -> bool:
        result = parking_lot.remove_entrance(entrance_id)
        status = "removed" if result else "not found"
        print(f"[ADMIN] Entrance {entrance_id} {status}")
        return result

    def add_exit(self, parking_lot: 'ParkingLot', exit_gate: Exit) -> None:
        parking_lot.add_exit(exit_gate)
        print(f"[ADMIN] {exit_gate} added by {self.admin_id}")

    def remove_exit(self, parking_lot: 'ParkingLot', exit_id: str) -> bool:
        result = parking_lot.remove_exit(exit_id)
        status = "removed" if result else "not found"
        print(f"[ADMIN] Exit {exit_id} {status}")
        return result

    def set_strategy(
        self,
        parking_lot: 'ParkingLot',
        strategy:    ParkingStrategy
    ) -> None:
        parking_lot.set_strategy(strategy)
        print(f"[ADMIN] Strategy changed to {strategy.__class__.__name__}")

    def __repr__(self): return f"Admin({self.admin_id})"


# ════════════════════════════════════════════════
# PARKING LOT — Singleton + Facade
# ════════════════════════════════════════════════

class ParkingLot:
    """
    Singleton — ek hi ParkingLot instance
    Facade — complex subsystems ko simple interface
    """
    _instance = None
    _lock      = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        name:     str,
        strategy: ParkingStrategy = None
    ):
        # Guard against re-initialization
        if hasattr(self, '_initialized'):
            return

        self.name           = name
        self._floors:      List[ParkingFloor] = []
        self._entrances:   List[Entrance]     = []
        self._exits:       List[Exit]         = []
        self._display      = DisplayBoard()
        self._strategy     = strategy or NearestFirstStrategy()
        self._tickets:     Dict[str, ParkingTicket] = {}
        self._lock         = threading.Lock()
        self._initialized  = True

    # ── Floor management ──
    def add_floor(self, floor: ParkingFloor) -> None:
        with self._lock:
            self._floors.append(floor)
        self._display.initialize(self._floors)

    def get_floors(self) -> List[ParkingFloor]:
        with self._lock:
            return list(self._floors)

    # ── Entrance/Exit management ──
    def add_entrance(self, entrance: Entrance) -> None:
        with self._lock:
            self._entrances.append(entrance)

    def remove_entrance(self, entrance_id: str) -> bool:
        with self._lock:
            for e in self._entrances:
                if e.entrance_id == entrance_id:
                    e.deactivate()
                    self._entrances.remove(e)
                    return True
        return False

    def add_exit(self, exit_gate: Exit) -> None:
        with self._lock:
            self._exits.append(exit_gate)

    def remove_exit(self, exit_id: str) -> bool:
        with self._lock:
            for e in self._exits:
                if e.exit_id == exit_id:
                    e.deactivate()
                    self._exits.remove(e)
                    return True
        return False

    # ── Strategy ──
    def set_strategy(self, strategy: ParkingStrategy) -> None:
        with self._lock:
            self._strategy = strategy

    # ── Spot finding ──
    def find_spot(self, vehicle: Vehicle) -> Optional[ParkingSpot]:
        with self._lock:
            return self._strategy.find_spot(self._floors, vehicle.vehicle_type)

    def is_full(self, vehicle_type: VehicleType) -> bool:
        spot_type = VEHICLE_SPOT_TYPE[vehicle_type]
        return self._display.get_free_count(spot_type) == 0

    # ── Ticket tracking ──
    def register_ticket(self, ticket: ParkingTicket) -> None:
        with self._lock:
            self._tickets[ticket.ticket_id] = ticket

    def get_ticket(self, ticket_id: str) -> Optional[ParkingTicket]:
        with self._lock:
            return self._tickets.get(ticket_id)

    # ── Display ──
    def show_display(self) -> None:
        print(self._display.display())

    def __repr__(self):
        return f"ParkingLot({self.name}, floors={len(self._floors)})"
```

---

## Step 6: Setup — Full System Initialize karo

```python
def setup_parking_lot() -> ParkingLot:
    """
    5 floors, 3 types of spots each
    2 entrances, 2 exits
    """
    # ── ParkingLot create karo ──
    lot = ParkingLot("Central Parking", strategy=NearestFirstStrategy())
    display = lot._display

    # ── Floors + Spots ──
    for floor_num in range(1, 6):  # 5 floors
        floor = ParkingFloor(floor_num)

        # Mini spots (Motorbike) — 10 per floor
        for i in range(1, 11):
            spot_id = f"M-{floor_num}-{i:02d}"
            floor.add_spot(MiniSpot(spot_id, floor_num, display))

        # Compact spots (Car) — 20 per floor
        for i in range(1, 21):
            spot_id = f"C-{floor_num}-{i:02d}"
            floor.add_spot(CompactSpot(spot_id, floor_num, display))

        # Large spots (Truck) — 5 per floor
        for i in range(1, 6):
            spot_id = f"L-{floor_num}-{i:02d}"
            floor.add_spot(LargeSpot(spot_id, floor_num, display))

        lot.add_floor(floor)

    # ── Entrances ──
    entrance_A = Entrance("ENT-A", floor_id=1)
    entrance_B = Entrance("ENT-B", floor_id=1)
    lot.add_entrance(entrance_A)
    lot.add_entrance(entrance_B)

    # ── Exits ──
    exit_A = Exit("EXT-A", floor_id=1)
    exit_B = Exit("EXT-B", floor_id=1)
    lot.add_exit(exit_A)
    lot.add_exit(exit_B)

    return lot


# ── Usage ──
lot = setup_parking_lot()
lot.show_display()

# Mini: 50, Compact: 100, Large: 25 (5 floors × each type)
```

---

## Step 7: Complete Flow — Entry to Exit

```python
def demo_full_flow():
    lot = setup_parking_lot()
    entrance_A = lot._entrances[0]
    exit_A     = lot._exits[0]

    # Create staff
    attendant = ParkingAttendant("ATT-001", entrance_A)
    admin     = Admin("ADMIN-001")

    print("\n═══ INITIAL DISPLAY ═══")
    lot.show_display()

    # ── 1. Car enters ──
    car = Car("DL-01-AB-1234")
    ticket1 = attendant.process_entry(car, lot)
    lot.register_ticket(ticket1)

    # ── 2. Motorbike enters ──
    bike = Motorbike("DL-02-CD-5678")
    ticket2 = attendant.process_entry(bike, lot)
    lot.register_ticket(ticket2)

    # ── 3. Truck enters ──
    truck = Truck("HR-26-EF-9012")
    ticket3 = attendant.process_entry(truck, lot)
    lot.register_ticket(ticket3)

    print("\n═══ AFTER 3 VEHICLES ═══")
    lot.show_display()

    # ── 4. Car exits — Cash payment ──
    print("\n─── Car Exit (Cash) ───")
    attendant.process_exit_with_ticket(
        ticket    = ticket1,
        payment_method = 'cash',
        exit_gate = exit_A
    )

    # ── 5. Bike exits — UPI payment ──
    print("\n─── Bike Exit (UPI) ───")
    attendant.process_exit_with_ticket(
        ticket         = ticket2,
        payment_method = 'upi',
        exit_gate      = exit_A,
        upi_id         = 'rahul@paytm'
    )

    # ── 6. Admin changes strategy ──
    print("\n─── Admin changes strategy ───")
    admin.set_strategy(lot, FarthestFirstStrategy())

    # ── 7. New car enters — Farthest floor first ──
    car2 = Car("MH-01-GH-3456")
    ticket4 = attendant.process_entry(car2, lot)
    print(f"New car parked at: {ticket4.spot}")  # Should be floor 5!

    # ── 8. Admin removes entrance ──
    print("\n─── Admin removes ENT-B ───")
    admin.remove_entrance(lot, "ENT-B")

    print("\n═══ FINAL DISPLAY ═══")
    lot.show_display()
```

---

## Step 8: Design Patterns Summary

```
Pattern Used         Where                           Why
─────────────────────────────────────────────────────────────────
Singleton           ParkingLot                       Ek hi lot — same state everywhere
Strategy (x2)       ParkingStrategy                  Nearest/Farthest runtime swap
                    PaymentStrategy                  Cash/Card/UPI interchangeable
Observer            DisplayBoard                     Spot change → board auto-update
Factory             PaymentFactory                   Payment method object creation
State               ParkingSpot (FREE/OCCUPIED/MAINT) Spot behavior changes with state
Facade              ParkingLot                       Complex subsystem → simple API
Template Method     Vehicle type check               Spot.can_fit() → subclass logic
```

---

## Step 9: Concurrency — Thread Safety

```python
# Problem: 2 cars simultaneously find same last available spot
# Solution: spot.park() mein lock hai

def spot.park(self, vehicle):
    with self._lock:           # ← Lock acquire
        if not self.is_available():  # ← Double check
            return False       # ← Second car ko False milega
        self._vehicle = vehicle
        self._status  = SpotStatus.OCCUPIED
        return True
    # Lock release

# Thread 1 (Car A): lock liya → available check → park kiya → lock release
# Thread 2 (Car B): lock wait → lock liya → available False → return False
# Car B ko dobara spot dhundhna padega — koi data corruption nahi
```

---

## Step 10: Interview Questions & Answers

---

**Q1: "How does the display board stay updated?"**
> "Observer pattern. `DisplayBoard` maintains counts by spot type. Whenever `ParkingSpot.park()` is called, it calls `display_board.update(spot_type, -1)`. When `release()` is called, it calls `update(spot_type, +1)`. The board is always in sync — no polling, no manual updates. Thread safety via `threading.Lock()` in both DisplayBoard and ParkingSpot."

---

**Q2: "How do you add a new parking strategy?"**
> "Create a class that extends `ParkingStrategy` and implements `find_spot(floors, vehicle_type) -> ParkingSpot`. Register nothing — just instantiate and call `admin.set_strategy(lot, NewStrategy())`. Open/Closed Principle — existing code untouched."

---

**Q3: "How do you handle concurrent vehicles at the same spot?"**
> "Every `ParkingSpot` has a `threading.Lock()`. The `park()` method acquires the lock, checks availability, and parks atomically. Even if two threads find the same spot as available simultaneously, only one can acquire the lock — the other gets `False` and triggers a new spot search."

---

**Q4: "How is payment extensible?"**
> "Strategy pattern + Factory. `PaymentStrategy` ABC defines `pay(amount) -> dict`. New method? Create `ApplePayPayment(PaymentStrategy)`, add to `PaymentFactory`. Zero changes to `Exit.process_exit()` — it only calls `payment.pay(amount)`."

---

**Q5: "Singleton — how is it thread-safe?"**
> "Double-checked locking with `threading.Lock()`. `__new__` is overridden — first check without lock (fast path), then acquire lock and check again (safe path). `_initialized` flag prevents `__init__` from running twice even if `__new__` is called again."

---

**Q6: "How does Admin add/remove gates at runtime?"**
> "`Entrance` and `Exit` objects are stored in lists in `ParkingLot`. Admin calls `lot.add_entrance(entrance)` or `lot.remove_entrance(entrance_id)` — the removal also calls `entrance.deactivate()` so any in-flight operation on that gate gracefully refuses new tickets. All list operations are guarded by `ParkingLot._lock`."

---

## Class Relationship Summary

```
ParkingLot (Singleton)
    │
    ├── has many → ParkingFloor
    │                  │
    │                  └── has many → ParkingSpot (Mini/Compact/Large)
    │                                      │
    │                                      └── notifies → DisplayBoard
    │
    ├── has many → Entrance
    │                  └── issues → ParkingTicket
    │                                  ├── has one → Vehicle
    │                                  └── has one → ParkingSpot
    │
    ├── has many → Exit
    │                  └── processes → Payment (Cash/Card/UPI)
    │
    ├── uses one → ParkingStrategy (Nearest/Farthest)
    │
    └── has one → DisplayBoard (Observer)

ParkingAttendant
    ├── uses → Entrance (for entry)
    └── uses → Exit (for exit)

Admin
    └── manages → ParkingLot (add/remove entrances, exits, strategy)
```

---

*Last Updated: April 2026 | SDE-2 LLD Interview — Interview Kickstart*
