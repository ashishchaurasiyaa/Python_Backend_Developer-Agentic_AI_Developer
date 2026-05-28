# LLD — Booking System (Hotel / Travel / Movie)
> **Interview Level:** SDE-2 | **Difficulty:** Medium-Hard | **Time:** 35-45 min
> **Patterns:** State Machine, Strategy, Observer, Factory, Template Method, Command
> **Real Project:** Niroskos Safari Platform — BookingDraft → Booking flow

---

## Step 1: Requirements Analysis (2 min — interviewer ke saamne)

```
Functional Requirements:
  ✅ Resource booking (Room / Safari Package / Movie Seat)
  ✅ Availability check before booking
  ✅ Booking lifecycle: Draft → Confirmed → Paid → Cancelled → Rescheduled
  ✅ Payment integration (multiple methods)
  ✅ Cancellation with refund policy
  ✅ Amendment/reschedule with deadline
  ✅ Notifications (email, SMS on state change)
  ✅ Concurrent booking — same resource sirf ek ko mile

Clarifying Questions (poochho interviewer se):
  Q: Ek resource ek time slot mein ek hi booking?    → Yes
  Q: Partial payment allow hai?                      → Yes (deposit + balance)
  Q: Cancellation refund policy flexible hai?        → Yes, time-based
  Q: Guest checkout ya login required?               → Both supported
  Q: Overbooking allowed? (airlines jaisa)           → No, strict availability
```

---

## Step 2: State Machine — Core of Booking System

```
                   ┌─────────────────────────────────────────┐
                   │           BOOKING STATE MACHINE          │
                   └─────────────────────────────────────────┘

  [DRAFT]  ──── (payment initiated) ────► [CONFIRMED]
     │                                        │
     │ (40 min expire)                        │ (payment completed)
     ▼                                        ▼
  [EXPIRED]                               [PAID]
                                              │
                              ┌───────────────┼───────────────┐
                              │               │               │
                   (cancel)   ▼   (reschedule)▼   (amend)     ▼
                         [CANCELLED]    [RESCHEDULED]    [AMENDED]
                              │
                              ▼
                         [REFUND_PENDING]
                              │
                              ▼
                         [REFUNDED]

VALID TRANSITIONS:
  DRAFT        → CONFIRMED, EXPIRED, ABANDONED
  CONFIRMED    → PAID, CANCELLED, EXPIRED
  PAID         → CANCELLED, RESCHEDULED, AMENDED, COMPLETED
  CANCELLED    → REFUND_PENDING
  REFUND_PENDING → REFUNDED
  RESCHEDULED  → PAID (after rescheduling fee payment)
```

---

## Step 3: Class Diagram

```
BookingDraft  ──────────────────► Booking (1:1 after confirmation)
    │                                 │
    ├── package: Package              ├── status: BookingStatus (State Machine)
    ├── travel_date: date             ├── amendment_deadline: datetime
    ├── guests: int                   ├── amount_paid: Decimal (cached)
    ├── expires_at: datetime (+40min) ├── balance_due: Decimal (cached)
    └── status: DraftStatus          └── is_locked(): bool

Package ──────► Option (pricing variants)
    │               └── base_price, start_date, end_date
    └── Itinerary
           └── ItineraryStop[]

Payment ──► PaymentStrategy (Card / Crypto / MPesa / Bank)
    │
    └── PaymentAllocation ──► OrderItem ──► Booking (GenericFK)

NotificationObserver
    ├── EmailObserver
    └── SMSObserver

CancellationPolicy (Strategy)
    ├── FreeCancellationPolicy   (>7 days: 100% refund)
    ├── PartialRefundPolicy      (3-7 days: 50% refund)
    └── NoRefundPolicy           (<3 days: 0% refund)

PricingStrategy
    ├── StandardPricing
    ├── GroupDiscountPricing
    ├── SeasonalPricing
    └── EarlyBirdPricing
```

---

## Step 4: Complete Implementation

```python
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from enum import Enum
from typing import Optional, List, Dict, Callable
import threading
import uuid


# ════════════════════════════════════════════════
# ENUMS
# ════════════════════════════════════════════════

class BookingStatus(Enum):
    DRAFT          = "DRAFT"
    CONFIRMED      = "CONFIRMED"
    PAID           = "PAID"
    CANCELLED      = "CANCELLED"
    RESCHEDULED    = "RESCHEDULED"
    AMENDED        = "AMENDED"
    COMPLETED      = "COMPLETED"
    EXPIRED        = "EXPIRED"
    REFUND_PENDING = "REFUND_PENDING"
    REFUNDED       = "REFUNDED"

class PaymentStatus(Enum):
    PENDING   = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED    = "FAILED"
    REFUNDED  = "REFUNDED"

class ResourceType(Enum):
    HOTEL_ROOM     = "hotel_room"
    SAFARI_PACKAGE = "safari_package"
    MOVIE_SEAT     = "movie_seat"


# ════════════════════════════════════════════════
# STATE MACHINE
# ════════════════════════════════════════════════

class BookingStateMachine:
    """
    Niroskos ka actual pattern — valid transitions enforce karo.
    Invalid transition pe exception throw karo.
    """

    VALID_TRANSITIONS: Dict[BookingStatus, List[BookingStatus]] = {
        BookingStatus.DRAFT:          [BookingStatus.CONFIRMED,
                                       BookingStatus.EXPIRED,
                                       BookingStatus.CANCELLED],
        BookingStatus.CONFIRMED:      [BookingStatus.PAID,
                                       BookingStatus.CANCELLED,
                                       BookingStatus.EXPIRED],
        BookingStatus.PAID:           [BookingStatus.CANCELLED,
                                       BookingStatus.RESCHEDULED,
                                       BookingStatus.AMENDED,
                                       BookingStatus.COMPLETED],
        BookingStatus.CANCELLED:      [BookingStatus.REFUND_PENDING],
        BookingStatus.REFUND_PENDING: [BookingStatus.REFUNDED],
        BookingStatus.RESCHEDULED:    [BookingStatus.PAID,
                                       BookingStatus.CANCELLED],
        BookingStatus.AMENDED:        [BookingStatus.PAID,
                                       BookingStatus.CANCELLED],
        BookingStatus.COMPLETED:      [],
        BookingStatus.EXPIRED:        [],
        BookingStatus.REFUNDED:       [],
    }

    @classmethod
    def can_transition(
        cls,
        current: BookingStatus,
        target:  BookingStatus
    ) -> bool:
        return target in cls.VALID_TRANSITIONS.get(current, [])

    @classmethod
    def transition(
        cls,
        booking: 'Booking',
        target:  BookingStatus,
        reason:  str = ""
    ) -> None:
        if not cls.can_transition(booking.status, target):
            raise InvalidTransitionError(
                f"Cannot transition: {booking.status.value} → {target.value}"
                f" (Booking: {booking.ref_code})"
            )
        old_status      = booking.status
        booking.status  = target
        booking.updated_at = datetime.now()

        # Audit log
        booking.add_history_entry(old_status, target, reason)
        print(f"[STATE] {booking.ref_code}: {old_status.value} → {target.value}")


class InvalidTransitionError(Exception):
    pass

class BookingLockedError(Exception):
    pass


# ════════════════════════════════════════════════
# RESOURCE (Hotel Room / Safari Package / Movie Seat)
# ════════════════════════════════════════════════

class Resource(ABC):
    def __init__(self, resource_id: str, name: str, resource_type: ResourceType):
        self.resource_id   = resource_id
        self.name          = name
        self.resource_type = resource_type
        self._lock         = threading.Lock()

    @abstractmethod
    def is_available(self, date_from: date, date_to: date) -> bool:
        pass

    @abstractmethod
    def get_price(self, date_from: date, date_to: date, guests: int) -> float:
        pass

    @abstractmethod
    def hold(self, booking_ref: str, date_from: date, date_to: date) -> bool:
        """
        Temporary hold — concurrency ke liye critical.
        Sirf ek booking ko hold milega.
        """
        pass

    @abstractmethod
    def release_hold(self, booking_ref: str) -> None:
        pass

    @abstractmethod
    def confirm_booking(self, booking_ref: str) -> bool:
        pass


class HotelRoom(Resource):
    """Hotel room — date range booking"""

    def __init__(self, room_id: str, room_type: str, price_per_night: float):
        super().__init__(room_id, f"Room {room_id}", ResourceType.HOTEL_ROOM)
        self.room_type       = room_type
        self.price_per_night = price_per_night
        self._bookings:      Dict[str, tuple] = {}  # ref → (from, to)
        self._holds:         Dict[str, tuple] = {}  # ref → (from, to, held_at)

    def is_available(self, date_from: date, date_to: date) -> bool:
        with self._lock:
            return (
                not self._has_conflict(self._bookings, date_from, date_to) and
                not self._has_conflict(self._holds,    date_from, date_to)
            )

    def _has_conflict(self, entries: dict, date_from: date, date_to: date) -> bool:
        for _, booking_range in entries.items():
            booked_from, booked_to = booking_range[0], booking_range[1]
            # Overlap check
            if not (date_to <= booked_from or date_from >= booked_to):
                return True
        return False

    def hold(self, booking_ref: str, date_from: date, date_to: date) -> bool:
        with self._lock:
            if self._has_conflict(self._bookings, date_from, date_to):
                return False
            if self._has_conflict(self._holds, date_from, date_to):
                return False
            self._holds[booking_ref] = (date_from, date_to, datetime.now())
            return True

    def release_hold(self, booking_ref: str) -> None:
        with self._lock:
            self._holds.pop(booking_ref, None)

    def confirm_booking(self, booking_ref: str) -> bool:
        with self._lock:
            if booking_ref not in self._holds:
                return False
            hold           = self._holds.pop(booking_ref)
            self._bookings[booking_ref] = (hold[0], hold[1])
            return True

    def get_price(self, date_from: date, date_to: date, guests: int) -> float:
        nights = (date_to - date_from).days
        return self.price_per_night * max(1, nights)


class SafariPackage(Resource):
    """
    Niroskos ka actual Package model — date-specific capacity
    """

    def __init__(
        self,
        package_id:   str,
        name:         str,
        base_price:   float,
        capacity:     int,       # Max guests per day
        duration_days: int
    ):
        super().__init__(package_id, name, ResourceType.SAFARI_PACKAGE)
        self.base_price    = base_price
        self.capacity      = capacity
        self.duration_days = duration_days
        # date → list of booking_refs
        self._date_bookings: Dict[date, List[str]] = {}
        self._date_holds:    Dict[date, Dict[str, int]] = {}  # date → {ref: guests}

    def _get_booked_count(self, travel_date: date) -> int:
        return len(self._date_bookings.get(travel_date, []))

    def _get_held_count(self, travel_date: date) -> int:
        holds = self._date_holds.get(travel_date, {})
        return sum(holds.values())

    def is_available(self, date_from: date, date_to: date = None) -> bool:
        with self._lock:
            travel_date  = date_from
            booked_count = self._get_booked_count(travel_date)
            held_count   = self._get_held_count(travel_date)
            return (booked_count + held_count) < self.capacity

    def get_available_slots(self, travel_date: date) -> int:
        with self._lock:
            used = (
                self._get_booked_count(travel_date) +
                self._get_held_count(travel_date)
            )
            return max(0, self.capacity - used)

    def hold(self, booking_ref: str, date_from: date, date_to: date = None,
             guests: int = 1) -> bool:
        with self._lock:
            travel_date = date_from
            if (self._get_booked_count(travel_date) +
                    self._get_held_count(travel_date) + guests) > self.capacity:
                return False

            if travel_date not in self._date_holds:
                self._date_holds[travel_date] = {}
            self._date_holds[travel_date][booking_ref] = guests
            return True

    def release_hold(self, booking_ref: str) -> None:
        with self._lock:
            for date_holds in self._date_holds.values():
                date_holds.pop(booking_ref, None)

    def confirm_booking(self, booking_ref: str) -> bool:
        with self._lock:
            for travel_date, holds in self._date_holds.items():
                if booking_ref in holds:
                    holds.pop(booking_ref)
                    if travel_date not in self._date_bookings:
                        self._date_bookings[travel_date] = []
                    self._date_bookings[travel_date].append(booking_ref)
                    return True
            return False

    def get_price(self, date_from: date, date_to: date = None,
                  guests: int = 1) -> float:
        return self.base_price * guests


class MovieSeat(Resource):
    """Movie seat — show-specific booking"""

    def __init__(self, seat_id: str, show_id: str, price: float):
        super().__init__(seat_id, f"Seat {seat_id}", ResourceType.MOVIE_SEAT)
        self.show_id  = show_id
        self.price    = price
        self._booked  = False
        self._held_by = None

    def is_available(self, date_from: date = None, date_to: date = None) -> bool:
        with self._lock:
            return not self._booked and self._held_by is None

    def hold(self, booking_ref: str, date_from: date = None,
             date_to: date = None) -> bool:
        with self._lock:
            if self._booked or self._held_by:
                return False
            self._held_by = booking_ref
            return True

    def release_hold(self, booking_ref: str) -> None:
        with self._lock:
            if self._held_by == booking_ref:
                self._held_by = None

    def confirm_booking(self, booking_ref: str) -> bool:
        with self._lock:
            if self._held_by != booking_ref:
                return False
            self._booked  = True
            self._held_by = None
            return True

    def get_price(self, date_from=None, date_to=None, guests: int = 1) -> float:
        return self.price


# ════════════════════════════════════════════════
# PRICING STRATEGY — Strategy Pattern
# ════════════════════════════════════════════════

class PricingStrategy(ABC):
    @abstractmethod
    def calculate(self, base_price: float, guests: int, travel_date: date) -> float:
        pass

    @abstractmethod
    def description(self) -> str:
        pass

class StandardPricing(PricingStrategy):
    def calculate(self, base_price, guests, travel_date):
        return base_price * guests

    def description(self): return "Standard rate"

class GroupDiscountPricing(PricingStrategy):
    """5+ guests: 10% off, 10+ guests: 15% off"""
    def calculate(self, base_price, guests, travel_date):
        total    = base_price * guests
        discount = 0.15 if guests >= 10 else (0.10 if guests >= 5 else 0)
        return round(total * (1 - discount), 2)

    def description(self): return "Group discount"

class SeasonalPricing(PricingStrategy):
    """Peak season mein 50% premium"""
    PEAK_MONTHS = [6, 7, 8, 12]  # June, July, Aug, Dec

    def calculate(self, base_price, guests, travel_date):
        multiplier = 1.5 if travel_date.month in self.PEAK_MONTHS else 1.0
        return round(base_price * guests * multiplier, 2)

    def description(self): return "Seasonal rate"

class EarlyBirdPricing(PricingStrategy):
    """30+ days advance booking: 15% off"""
    def calculate(self, base_price, guests, travel_date):
        days_ahead = (travel_date - date.today()).days
        discount   = 0.15 if days_ahead >= 30 else 0
        return round(base_price * guests * (1 - discount), 2)

    def description(self): return "Early bird discount"


# ════════════════════════════════════════════════
# CANCELLATION POLICY — Strategy Pattern
# ════════════════════════════════════════════════

class CancellationPolicy(ABC):
    @abstractmethod
    def calculate_refund(self, booking: 'Booking') -> float:
        pass

    @abstractmethod
    def description(self) -> str:
        pass

class FreeCancellationPolicy(CancellationPolicy):
    """7+ days before: 100% refund"""
    def calculate_refund(self, booking):
        days_to_travel = (booking.travel_date - date.today()).days
        if days_to_travel >= 7:
            return booking.amount_paid
        elif days_to_travel >= 3:
            return booking.amount_paid * 0.5
        return 0.0

    def description(self): return "Free cancellation (7+ days)"

class StrictCancellationPolicy(CancellationPolicy):
    """No refund after confirmation"""
    def calculate_refund(self, booking):
        return 0.0

    def description(self): return "No refund policy"

class PartialRefundPolicy(CancellationPolicy):
    def __init__(self, refund_percentage: float):
        self.refund_percentage = refund_percentage

    def calculate_refund(self, booking):
        return round(booking.amount_paid * self.refund_percentage, 2)

    def description(self): return f"{int(self.refund_percentage*100)}% refund"


# ════════════════════════════════════════════════
# NOTIFICATION — Observer Pattern
# ════════════════════════════════════════════════

class BookingObserver(ABC):
    @abstractmethod
    def on_booking_event(self, event: str, booking: 'Booking') -> None:
        pass

class EmailNotificationObserver(BookingObserver):
    def on_booking_event(self, event, booking):
        templates = {
            'CONFIRMED':   f"Booking {booking.ref_code} confirmed! Travel: {booking.travel_date}",
            'PAID':        f"Payment received for {booking.ref_code}. You're all set! 🎉",
            'CANCELLED':   f"Booking {booking.ref_code} cancelled. Refund in 5-7 days.",
            'RESCHEDULED': f"Booking {booking.ref_code} rescheduled to {booking.travel_date}",
        }
        msg = templates.get(event, f"Booking update: {event}")
        print(f"[EMAIL] → {booking.customer_email}: {msg}")

class SMSNotificationObserver(BookingObserver):
    def on_booking_event(self, event, booking):
        if event in ('CONFIRMED', 'PAID', 'CANCELLED'):
            print(f"[SMS] → {booking.customer_phone}: {booking.ref_code} {event}")

class AuditLogObserver(BookingObserver):
    def on_booking_event(self, event, booking):
        print(f"[AUDIT] {datetime.now().isoformat()} | {event} | {booking.ref_code}")


# ════════════════════════════════════════════════
# BOOKING HISTORY ENTRY
# ════════════════════════════════════════════════

@dataclass
class BookingHistoryEntry:
    from_status: BookingStatus
    to_status:   BookingStatus
    reason:      str
    timestamp:   datetime = field(default_factory=datetime.now)

    def __repr__(self):
        return (
            f"{self.timestamp.strftime('%Y-%m-%d %H:%M')} | "
            f"{self.from_status.value} → {self.to_status.value}"
            f"{' | ' + self.reason if self.reason else ''}"
        )


# ════════════════════════════════════════════════
# BOOKING DRAFT — Temporary Checkout (Niroskos pattern)
# ════════════════════════════════════════════════

class BookingDraft:
    """
    Niroskos ka actual BookingDraft:
    - Temporary checkout session
    - 40-minute expiry
    - Resource hold during checkout
    - Converts to Booking on payment initiation
    """
    EXPIRY_MINUTES = 40

    def __init__(
        self,
        resource:       Resource,
        customer_email: str,
        customer_phone: str,
        travel_date:    date,
        guests:         int          = 1,
        pricing_strategy: PricingStrategy = None,
    ):
        self.draft_id         = f"DFT-{uuid.uuid4().hex[:8].upper()}"
        self.resource         = resource
        self.customer_email   = customer_email
        self.customer_phone   = customer_phone
        self.travel_date      = travel_date
        self.guests           = guests
        self.pricing_strategy = pricing_strategy or StandardPricing()
        self.created_at       = datetime.now()
        self.expires_at       = self.created_at + timedelta(minutes=self.EXPIRY_MINUTES)
        self.status           = "ACTIVE"
        self._resource_held   = False

    def is_expired(self) -> bool:
        return datetime.now() > self.expires_at

    def hold_resource(self) -> bool:
        """
        Resource ko hold karo — doosra booking nahi le sake.
        Concurrency critical: resource.hold() mein lock hai.
        """
        if self.is_expired():
            self.status = "EXPIRED"
            return False

        success = self.resource.hold(
            booking_ref = self.draft_id,
            date_from   = self.travel_date,
            date_to     = self.travel_date,
            guests      = self.guests
        )
        self._resource_held = success
        return success

    def release_resource(self) -> None:
        if self._resource_held:
            self.resource.release_hold(self.draft_id)
            self._resource_held = False

    def calculate_total(self) -> float:
        base_price = self.resource.get_price(self.travel_date, self.travel_date, self.guests)
        return self.pricing_strategy.calculate(base_price, self.guests, self.travel_date)

    def to_booking(self, cancellation_policy: CancellationPolicy = None) -> 'Booking':
        """Draft → Booking conversion"""
        if self.is_expired():
            raise ValueError(f"Draft {self.draft_id} has expired")
        if not self._resource_held:
            raise ValueError(f"Resource not held for draft {self.draft_id}")

        return Booking(
            resource             = self.resource,
            customer_email       = self.customer_email,
            customer_phone       = self.customer_phone,
            travel_date          = self.travel_date,
            guests               = self.guests,
            total_amount         = self.calculate_total(),
            pricing_strategy     = self.pricing_strategy,
            cancellation_policy  = cancellation_policy or FreeCancellationPolicy(),
            draft_ref            = self.draft_id,
        )


# ════════════════════════════════════════════════
# BOOKING — Main Entity with State Machine
# ════════════════════════════════════════════════

class Booking:
    """
    Niroskos Booking model — exact pattern.

    Key features:
    1. State machine — valid transitions only
    2. Amendment deadline — is_locked() check
    3. Cached payment fields — amount_paid, balance_due
    4. Observer notifications on state change
    5. Audit history for every transition
    """

    def __init__(
        self,
        resource:            Resource,
        customer_email:      str,
        customer_phone:      str,
        travel_date:         date,
        guests:              int,
        total_amount:        float,
        pricing_strategy:    PricingStrategy     = None,
        cancellation_policy: CancellationPolicy  = None,
        draft_ref:           str                 = None,
    ):
        self.ref_code            = f"BKG-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        self.resource            = resource
        self.customer_email      = customer_email
        self.customer_phone      = customer_phone
        self.travel_date         = travel_date
        self.guests              = guests
        self.total_amount        = total_amount
        self.amount_paid         = 0.0    # Cached — signal se update
        self.balance_due         = total_amount
        self.status              = BookingStatus.DRAFT
        self.pricing_strategy    = pricing_strategy or StandardPricing()
        self.cancellation_policy = cancellation_policy or FreeCancellationPolicy()
        self.draft_ref           = draft_ref
        self.created_at          = datetime.now()
        self.updated_at          = datetime.now()
        self.cancelled_at:       Optional[datetime] = None
        self.cancel_reason:      Optional[str]      = None
        self.refund_amount:      float              = 0.0
        self.special_request:    Optional[str]      = None
        self.staff_notes:        Optional[str]      = None

        # Amendment deadline — Niroskos exact pattern
        # 3+ day tour: travel_date - 3 days | Day trip: travel_date - 1 day
        days_before = 3  # Can be set based on resource type
        self.amendment_deadline = datetime.combine(
            travel_date - timedelta(days=days_before),
            datetime.min.time()
        )

        # History + Observers
        self._history:   List[BookingHistoryEntry] = []
        self._observers: List[BookingObserver]     = []
        self._lock       = threading.Lock()

    # ── Properties ──────────────────────────────

    def is_locked(self) -> bool:
        """
        Niroskos exact method — amendment deadline ke baad locked.
        Locked booking: cancel/reschedule needs backoffice override.
        """
        return datetime.now() > self.amendment_deadline

    @property
    def is_fully_paid(self) -> bool:
        return self.amount_paid >= self.total_amount

    @property
    def net_paid(self) -> float:
        return self.amount_paid

    # ── Observer management ──────────────────────

    def subscribe(self, observer: BookingObserver) -> None:
        self._observers.append(observer)

    def _notify_observers(self, event: str) -> None:
        for observer in self._observers:
            try:
                observer.on_booking_event(event, self)
            except Exception as e:
                print(f"[WARN] Observer {observer.__class__.__name__} failed: {e}")

    # ── History ──────────────────────────────────

    def add_history_entry(
        self,
        from_status: BookingStatus,
        to_status:   BookingStatus,
        reason:      str = ""
    ) -> None:
        self._history.append(
            BookingHistoryEntry(from_status, to_status, reason)
        )

    def get_history(self) -> List[BookingHistoryEntry]:
        return list(self._history)

    # ── State Transitions ────────────────────────

    def confirm(self) -> None:
        """Draft → Confirmed (payment initiated)"""
        with self._lock:
            BookingStateMachine.transition(self, BookingStatus.CONFIRMED)
            # Resource hold → confirmed booking
            if not self.resource.confirm_booking(self.draft_ref or self.ref_code):
                # Rollback
                self.status = BookingStatus.DRAFT
                raise RuntimeError("Resource confirmation failed")
            self._notify_observers('CONFIRMED')

    def mark_paid(self, amount: float) -> None:
        """Confirmed → Paid (payment completed)"""
        with self._lock:
            self.amount_paid += amount
            self.balance_due  = max(0, self.total_amount - self.amount_paid)

            if self.is_fully_paid:
                BookingStateMachine.transition(self, BookingStatus.PAID)
                self._notify_observers('PAID')
            else:
                # Partial payment — still CONFIRMED
                print(f"[BOOKING] Partial payment: {self.amount_paid}/{self.total_amount}")

    def cancel(self, reason: str = "", force: bool = False) -> float:
        """
        Cancel booking — refund calculate karo.
        Locked booking: force=True (backoffice override) required.
        """
        with self._lock:
            if self.is_locked() and not force:
                raise BookingLockedError(
                    f"Booking {self.ref_code} is locked. "
                    f"Amendment deadline: {self.amendment_deadline}. "
                    f"Use force=True for backoffice override."
                )

            BookingStateMachine.transition(self, BookingStatus.CANCELLED, reason)
            self.cancelled_at = datetime.now()
            self.cancel_reason = reason

            # Calculate refund
            self.refund_amount = self.cancellation_policy.calculate_refund(self)

            # Release resource
            self.resource.release_hold(self.ref_code)

            self._notify_observers('CANCELLED')
            print(f"[CANCEL] {self.ref_code}: Refund = Rs {self.refund_amount}")
            return self.refund_amount

    def reschedule(self, new_date: date, reason: str = "") -> None:
        """Paid → Rescheduled"""
        with self._lock:
            if self.is_locked():
                raise BookingLockedError(
                    f"Booking {self.ref_code} is locked for amendments."
                )

            # Check availability on new date
            if not self.resource.is_available(new_date, new_date):
                raise ValueError(
                    f"Resource not available on {new_date}"
                )

            old_date         = self.travel_date
            self.travel_date = new_date

            # Recalculate amendment deadline
            self.amendment_deadline = datetime.combine(
                new_date - timedelta(days=3),
                datetime.min.time()
            )

            BookingStateMachine.transition(self, BookingStatus.RESCHEDULED, reason)
            self._notify_observers('RESCHEDULED')
            print(f"[RESCHEDULE] {self.ref_code}: {old_date} → {new_date}")

    def mark_expired(self) -> None:
        """40 min draft expiry"""
        with self._lock:
            if self.status in (BookingStatus.DRAFT, BookingStatus.CONFIRMED):
                BookingStateMachine.transition(self, BookingStatus.EXPIRED)
                self.resource.release_hold(self.ref_code)

    def complete(self) -> None:
        """Paid → Completed (after travel date)"""
        with self._lock:
            BookingStateMachine.transition(self, BookingStatus.COMPLETED)

    def refresh_payment_cache(self, payments: List[dict]) -> None:
        """
        Niroskos ka exact pattern — Django Signal se trigger hota tha.
        PaymentAllocation save pe → booking cache refresh.
        N+1 avoid karne ke liye cached fields.
        """
        with self._lock:
            self.amount_paid = sum(p['amount'] for p in payments if p['status'] == 'COMPLETED')
            self.balance_due = max(0.0, self.total_amount - self.amount_paid)

    def __repr__(self):
        return (
            f"Booking({self.ref_code}, {self.status.value}, "
            f"{self.travel_date}, guests={self.guests}, "
            f"paid={self.amount_paid}/{self.total_amount})"
        )


# ════════════════════════════════════════════════
# BOOKING SERVICE — Facade + Template Method
# ════════════════════════════════════════════════

class BookingService:
    """
    Facade — complex booking flow ko simple API.
    Template Method — booking flow ke steps fixed hain.
    """

    def __init__(self, observers: List[BookingObserver] = None):
        self._observers     = observers or [
            EmailNotificationObserver(),
            SMSNotificationObserver(),
            AuditLogObserver(),
        ]
        self._active_drafts: Dict[str, BookingDraft] = {}
        self._bookings:      Dict[str, Booking]      = {}
        self._lock           = threading.Lock()

    # ── Step 1: Availability Check ──

    def check_availability(
        self,
        resource:    Resource,
        travel_date: date,
        guests:      int = 1
    ) -> dict:
        available = resource.is_available(travel_date, travel_date)
        result    = {
            "available": available,
            "date":      travel_date,
            "guests":    guests,
        }

        if isinstance(resource, SafariPackage):
            result["slots_left"] = resource.get_available_slots(travel_date)

        if not available:
            result["message"] = "No availability on this date"

        return result

    # ── Step 2: Create Draft (Resource Hold) ──

    def initiate_booking(
        self,
        resource:        Resource,
        customer_email:  str,
        customer_phone:  str,
        travel_date:     date,
        guests:          int               = 1,
        pricing_strategy: PricingStrategy  = None,
        special_request: str               = None,
    ) -> BookingDraft:
        """
        Booking shuru karo — resource hold karo 40 min ke liye.
        CONCURRENCY: resource.hold() mein lock hai — sirf ek baar success hoga.
        """
        draft = BookingDraft(
            resource         = resource,
            customer_email   = customer_email,
            customer_phone   = customer_phone,
            travel_date      = travel_date,
            guests           = guests,
            pricing_strategy = pricing_strategy or self._select_pricing(guests, travel_date),
        )

        # Critical section — resource hold karo
        if not draft.hold_resource():
            raise ResourceNotAvailableError(
                f"Resource {resource.name} not available for {travel_date}. "
                f"Another booking may have just been made."
            )

        with self._lock:
            self._active_drafts[draft.draft_id] = draft

        print(f"[DRAFT] Created: {draft.draft_id} | Expires: {draft.expires_at.strftime('%H:%M:%S')}")
        print(f"[DRAFT] Total: Rs {draft.calculate_total()}")
        return draft

    # ── Step 3: Confirm Booking ──

    def confirm_booking(
        self,
        draft_id:            str,
        cancellation_policy: CancellationPolicy = None,
    ) -> Booking:
        """Draft → Confirmed Booking"""
        draft = self._active_drafts.get(draft_id)

        if not draft:
            raise ValueError(f"Draft {draft_id} not found")

        if draft.is_expired():
            draft.release_resource()
            del self._active_drafts[draft_id]
            raise ValueError(f"Draft {draft_id} expired. Please start again.")

        # Create booking from draft
        booking = draft.to_booking(cancellation_policy)

        # Wire up observers
        for observer in self._observers:
            booking.subscribe(observer)

        # Confirm transition
        booking.confirm()

        with self._lock:
            self._bookings[booking.ref_code] = booking
            del self._active_drafts[draft_id]

        return booking

    # ── Step 4: Process Payment ──

    def process_payment(
        self,
        ref_code:       str,
        amount:         float,
        payment_method: str,
        **payment_kwargs
    ) -> dict:
        booking = self._get_booking(ref_code)
        payment = PaymentFactory.create(payment_method, **payment_kwargs)
        receipt = payment.pay(amount)

        if receipt['status'] == 'success':
            booking.mark_paid(amount)
            return {
                "ref_code":    ref_code,
                "amount_paid": booking.amount_paid,
                "balance_due": booking.balance_due,
                "status":      booking.status.value,
            }
        raise PaymentFailedError(f"Payment failed for {ref_code}")

    # ── Step 5: Cancel Booking ──

    def cancel_booking(
        self,
        ref_code:  str,
        reason:    str  = "",
        force:     bool = False,
    ) -> dict:
        booking      = self._get_booking(ref_code)
        refund_amount = booking.cancel(reason, force=force)
        return {
            "ref_code":     ref_code,
            "status":       booking.status.value,
            "refund_amount": refund_amount,
            "policy":       booking.cancellation_policy.description(),
        }

    # ── Step 6: Reschedule ──

    def reschedule_booking(
        self,
        ref_code:  str,
        new_date:  date,
        reason:    str = "",
    ) -> Booking:
        booking = self._get_booking(ref_code)
        booking.reschedule(new_date, reason)
        return booking

    # ── Helpers ──

    def _get_booking(self, ref_code: str) -> Booking:
        booking = self._bookings.get(ref_code)
        if not booking:
            raise ValueError(f"Booking {ref_code} not found")
        return booking

    def _select_pricing(self, guests: int, travel_date: date) -> PricingStrategy:
        """Auto-select best pricing strategy"""
        if guests >= 5:
            return GroupDiscountPricing()
        days_ahead = (travel_date - date.today()).days
        if days_ahead >= 30:
            return EarlyBirdPricing()
        if travel_date.month in [6, 7, 8, 12]:
            return SeasonalPricing()
        return StandardPricing()

    def get_booking(self, ref_code: str) -> Booking:
        return self._get_booking(ref_code)


# ════════════════════════════════════════════════
# PAYMENT — Strategy Pattern
# ════════════════════════════════════════════════

class PaymentStrategy(ABC):
    @abstractmethod
    def pay(self, amount: float) -> dict: pass

class CashPayment(PaymentStrategy):
    def pay(self, amount):
        return {"method": "cash", "amount": amount, "status": "success"}

class CardPayment(PaymentStrategy):
    def __init__(self, card_last4: str = "0000"):
        self.card_last4 = card_last4

    def pay(self, amount):
        print(f"[CARD] Rs {amount} charged to ****{self.card_last4}")
        return {"method": "card", "amount": amount, "status": "success"}

class UPIPayment(PaymentStrategy):
    def __init__(self, upi_id: str = ""):
        self.upi_id = upi_id

    def pay(self, amount):
        print(f"[UPI] Rs {amount} via {self.upi_id}")
        return {"method": "upi", "amount": amount, "status": "success"}

class CryptoPayment(PaymentStrategy):
    """Niroskos ka Web3/USDT payment"""
    def pay(self, amount):
        print(f"[CRYPTO] {amount} USDT — blockchain confirmation pending")
        return {"method": "crypto", "amount": amount, "status": "success"}

class PaymentFactory:
    _map = {
        'cash':   CashPayment,
        'card':   CardPayment,
        'upi':    UPIPayment,
        'crypto': CryptoPayment,
    }

    @classmethod
    def create(cls, method: str, **kwargs) -> PaymentStrategy:
        klass = cls._map.get(method)
        if not klass:
            raise ValueError(f"Unknown payment method: {method}")
        return klass(**{k: v for k, v in kwargs.items()
                       if k in ['card_last4', 'upi_id']})


# ════════════════════════════════════════════════
# EXCEPTIONS
# ════════════════════════════════════════════════

class ResourceNotAvailableError(Exception): pass
class PaymentFailedError(Exception):        pass
```

---

## Step 5: Complete Demo — End to End Flow

```python
def demo_safari_booking():
    print("\n" + "═"*60)
    print("   NIROSKOS SAFARI BOOKING — COMPLETE FLOW")
    print("═"*60)

    # ── Setup ──
    safari = SafariPackage(
        package_id    = "PKG-MASAI-001",
        name          = "Masai Mara Safari",
        base_price    = 50000,
        capacity      = 10,
        duration_days = 5
    )

    service = BookingService()

    # ── 1. Check Availability ──
    travel = date(2024, 7, 15)
    avail  = service.check_availability(safari, travel, guests=4)
    print(f"\n[1] Availability: {avail}")

    # ── 2. Initiate Booking (Resource Hold) ──
    print("\n[2] Creating booking draft...")
    draft = service.initiate_booking(
        resource       = safari,
        customer_email = "rahul@gmail.com",
        customer_phone = "+919876543210",
        travel_date    = travel,
        guests         = 4,
    )
    print(f"    Draft ID: {draft.draft_id}")
    print(f"    Total: Rs {draft.calculate_total()}")
    print(f"    Expires: {draft.expires_at.strftime('%H:%M:%S')}")

    # ── 3. Confirm Booking ──
    print("\n[3] Confirming booking...")
    booking = service.confirm_booking(
        draft_id            = draft.draft_id,
        cancellation_policy = FreeCancellationPolicy(),
    )
    print(f"    Booking: {booking.ref_code}")
    print(f"    Status:  {booking.status.value}")
    print(f"    Locked:  {booking.is_locked()}")

    # ── 4. Process Partial Payment ──
    print("\n[4] Processing deposit (50%)...")
    result = service.process_payment(
        ref_code       = booking.ref_code,
        amount         = 100000,   # 50% deposit (4 guests × 50000 × 50%)
        payment_method = 'card',
        card_last4     = '4242'
    )
    print(f"    Paid: Rs {result['amount_paid']} / Due: Rs {result['balance_due']}")

    # ── 5. Process Balance ──
    print("\n[5] Processing balance...")
    result = service.process_payment(
        ref_code       = booking.ref_code,
        amount         = 100000,   # Remaining 50%
        payment_method = 'upi',
        upi_id         = 'rahul@paytm'
    )
    print(f"    Status: {result['status']} | Balance: Rs {result['balance_due']}")

    # ── 6. View Booking History ──
    print("\n[6] Booking History:")
    for entry in booking.get_history():
        print(f"    {entry}")

    # ── 7. Attempt Reschedule ──
    print("\n[7] Reschedule to Aug 2024...")
    try:
        service.reschedule_booking(
            ref_code = booking.ref_code,
            new_date = date(2024, 8, 20),
            reason   = "Client request"
        )
    except BookingLockedError as e:
        print(f"    LOCKED: {e}")

    return booking


def demo_concurrency():
    """
    Race condition test — 2 users same last spot book karne ki koshish
    """
    print("\n" + "═"*60)
    print("   CONCURRENCY TEST — 2 Users, 1 Spot Left")
    print("═"*60)

    # Safari with capacity = 1
    safari  = SafariPackage("PKG-001", "Gorilla Trek", 75000, capacity=1, duration_days=3)
    service = BookingService()
    travel  = date(2024, 9, 1)
    results = []

    def book_user(user_name: str, email: str):
        try:
            draft = service.initiate_booking(
                resource       = safari,
                customer_email = email,
                customer_phone = "+91-0000000000",
                travel_date    = travel,
                guests         = 1,
            )
            results.append(f"✅ {user_name}: Got draft {draft.draft_id}")
        except ResourceNotAvailableError as e:
            results.append(f"❌ {user_name}: {e}")

    # Both users try simultaneously
    import threading
    t1 = threading.Thread(target=book_user, args=("Rahul", "rahul@gmail.com"))
    t2 = threading.Thread(target=book_user, args=("Priya", "priya@gmail.com"))

    t1.start(); t2.start()
    t1.join();  t2.join()

    for r in results:
        print(f"  {r}")
    # Only ONE will succeed — Lock ensures this


def demo_hotel_booking():
    print("\n" + "═"*60)
    print("   HOTEL BOOKING FLOW")
    print("═"*60)

    room    = HotelRoom("101", "Deluxe", price_per_night=3000)
    service = BookingService()

    checkin  = date(2024, 8, 15)
    checkout = date(2024, 8, 18)  # 3 nights = Rs 9000

    draft = service.initiate_booking(
        resource       = room,
        customer_email = "guest@hotel.com",
        customer_phone = "+91-9999999999",
        travel_date    = checkin,
        guests         = 2,
    )
    print(f"Hotel booking draft: Rs {draft.calculate_total()}")

    booking = service.confirm_booking(draft.draft_id)
    result  = service.process_payment(booking.ref_code, 9000, 'cash')
    print(f"Hotel booking confirmed: {booking.ref_code} | {result['status']}")

    # Cancel — should get refund (>7 days away)
    cancel_result = service.cancel_booking(booking.ref_code, "Change of plans")
    print(f"Cancelled: Refund = Rs {cancel_result['refund_amount']}")


# Run all demos
if __name__ == "__main__":
    demo_safari_booking()
    demo_concurrency()
    demo_hotel_booking()
```

---

## Step 6: Design Patterns Summary

```
Pattern            Where Used                          Why
──────────────────────────────────────────────────────────────────
State Machine      BookingStateMachine                 Valid transitions enforce karo
                   BookingStatus enum                  Invalid state = exception

Strategy (×3)      PricingStrategy                     Standard/Group/Early Bird
                   CancellationPolicy                  Free/Strict/Partial refund
                   PaymentStrategy                     Cash/Card/UPI/Crypto

Observer           BookingObserver                     State change → auto notify
                   EmailObserver, SMSObserver          Decoupled notifications

Factory            PaymentFactory                      String → Payment object
                   _select_pricing()                   Auto pricing selection

Template Method    BookingService flow                 initiate→confirm→pay→cancel
                   build() steps

Facade             BookingService                      Complex flow → simple API
                   check_availability → initiate →
                   confirm → pay → cancel

Command            (Implicit in service methods)       Operations as methods
                   cancel(), reschedule()              Undoable operations
```

---

## Step 7: Concurrency Deep Dive

```python
# Problem: 2 users book karne ki koshish karein same time pe

# User A                          User B
# check_availability() → True     check_availability() → True
# initiate_booking()              initiate_booking()
#   resource.hold()               resource.hold()  ← RACE CONDITION!

# Solution: Resource.hold() mein threading.Lock()

def hold(self, booking_ref, date_from, ...):
    with self._lock:                          # ← Critical section start
        if self._has_conflict(...):           # ← Check again inside lock
            return False                      # ← User B ko False milega
        self._holds[booking_ref] = (...)      # ← User A ne hold liya
        return True                           # ← Lock release

# Guarantee:
# User A: lock liya → conflict nahi → hold add kiya → True return → Lock release
# User B: lock wait → lock mila → conflict hai (A ka hold) → False → Lock release
# Result: Only ONE user gets the booking. NO double booking.

# Same pattern: select_for_update() in Django ORM
# with transaction.atomic():
#     spot = ParkingSpot.objects.select_for_update().get(id=spot_id)
#     if spot.is_available():
#         spot.status = 'OCCUPIED'
#         spot.save()
```

---

## Step 8: Niroskos Real-World Mapping

```
LLD Class               Niroskos Actual Code
──────────────────────────────────────────────────────
BookingDraft            apps/booking/models/draft.py
Booking                 apps/booking/models/booking.py
BookingStateMachine     Booking.VALID_TRANSITIONS dict + _transition_to()
is_locked()             booking.is_locked() → now() > amendment_deadline
amendment_deadline      travel_date - timedelta(days=3) for 3+ day tours
SafariPackage           apps/products/models/package.py
Resource.hold()         select_for_update() in BookingService
refresh_payment_cache() Signal: PaymentAllocation → booking.refresh_payment_cache()
BookingObserver         Django Signals: post_save → email/SMS task
PaymentFactory          PaymentMethod choices + factory pattern
CancellationPolicy      Booking.calculate_refund() with date logic
```

---

## Step 9: Interview Questions & Answers

---

**Q1: "How does the state machine prevent invalid transitions?"**
> "I have a `BookingStateMachine` class with a `VALID_TRANSITIONS` dict — each status maps to its allowed next states. The `transition()` method checks `can_transition()` before changing state. If invalid, it raises `InvalidTransitionError`. No code path can put a booking in an invalid state. In Niroskos, I used a property setter with this validation — `booking.status = 'PAID'` directly was blocked; only `BookingStateMachine.transition()` could change it."

---

**Q2: "How do you handle concurrent bookings for the same slot?"**
> "Two layers of protection. First: `Resource.hold()` uses `threading.Lock()`. Even if two requests pass the availability check simultaneously, only one can acquire the lock and add the hold. The second one finds a conflict and gets `False` — immediately shown 'no availability'. Second layer: the hold expires if payment isn't completed in 40 minutes — same as Niroskos's `BookingDraft.expires_at`. This prevents ghost holds from blocking inventory permanently."

---

**Q3: "Explain the BookingDraft → Booking conversion"**
> "This is directly from Niroskos. When a user starts checkout, a `BookingDraft` is created — resource is held immediately (40-min TTL). The draft is a temporary, uncommitted state. If user completes payment initiation within 40 minutes, `draft.to_booking()` creates a confirmed `Booking` and the resource hold converts to a confirmed booking. If 40 minutes pass without action, the draft expires and the resource is released back to inventory. This prevents a user from holding a slot indefinitely without paying."

---

**Q4: "How does the amendment deadline work?"**
> "In Niroskos: `amendment_deadline = travel_date - 3 days` for multi-day tours, `travel_date - 1 day` for day trips. `is_locked()` returns `True` if current time is past this deadline. Locked bookings cannot be cancelled or rescheduled through normal flow — it raises `BookingLockedError`. Only backoffice with `force=True` can override. This protects the business from last-minute cancellations after resources are committed."

---

**Q5: "How are notifications decoupled from booking logic?"**
> "Observer pattern — `Booking` maintains a list of `BookingObserver` objects. Every state transition calls `_notify_observers(event)`. `EmailNotificationObserver`, `SMSNotificationObserver`, `AuditLogObserver` are wired up in `BookingService`. In production Niroskos code, I used Django Signals — `post_save` on `Booking` model triggered Celery tasks for email and SMS. The booking model had zero knowledge of email/SMS logic."

---

**Q6: "How is pricing extensible?"**
> "Strategy pattern — `PricingStrategy` ABC with `calculate(base_price, guests, travel_date)`. Four strategies: Standard, Group Discount (5+ guests), Seasonal (peak months), Early Bird (30+ days). `BookingService._select_pricing()` auto-selects based on context. New pricing rule? Add one class. Zero changes to Booking or BookingService. In Niroskos, pricing options were per-package — each `Option` model had its own base price and date range."

---

## Class Relationship Summary

```
BookingService (Facade)
    │
    ├── creates ──► BookingDraft (40-min temp hold)
    │                   │
    │                   └── converts to ──► Booking (State Machine)
    │                                           │
    │                                           ├── uses ─► PricingStrategy
    │                                           ├── uses ─► CancellationPolicy
    │                                           ├── has ──► BookingHistory[]
    │                                           └── notifies ─► BookingObserver[]
    │
    ├── checks ──► Resource.is_available()
    │               ├── HotelRoom     (date range overlap)
    │               ├── SafariPackage (capacity per date)
    │               └── MovieSeat     (show-specific)
    │
    └── processes ──► PaymentFactory ──► PaymentStrategy
                                          ├── Cash
                                          ├── Card
                                          ├── UPI
                                          └── Crypto
```

---

*Last Updated: April 2026 | SDE-2 LLD Interview — Interview Kickstart*
