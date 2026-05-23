# Elevator System LLD

## Quick Reference Card
```
Pattern Used    → State Machine + Strategy (scheduling) + Observer
Core Challenge  → Direction optimization, request batching, starvation prevention
Key Classes     → Elevator, ElevatorController, RequestDispatcher, Door, Display
Scheduling      → SCAN (like disk scheduling) / LOOK algorithm
State Machine   → IDLE → MOVING_UP / MOVING_DOWN → DOOR_OPEN → IDLE
Interview Hook  → "LOOK algorithm jaisa disk scheduling — current direction maintain karo"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Kya hai?

Elevator system ek classic LLD problem hai jisme:
- Multiple elevators hain building mein
- Passengers floor pe button dabaate hain (external request)
- Andar se bhi button dabaate hain (internal request)
- Controller decide karta hai kaun si elevator kahan jaaye

**Real-world analogy:** Socho ek taxi dispatcher hai — multiple taxis (elevators) hain, requests aa rahi hain, dispatcher decide karta hai kaunsi taxi closest + same direction mein hai.

**SCAN Algorithm (Disk Scheduling se ana):**
- Elevator ek direction mein chalti rahti hai jab tak requests hain us direction mein
- Phir reverse karti hai
- Jaise lift ek manzil se ooper jaate jaate sabke buttons serve karti hai, neeche aa ke phir serve karti hai
- Isse "LOOK" kehte hain — actually look karo ki koi request hai ya nahi, phir reverse karo

### 1.2 Kab use karo?

- **Multi-elevator buildings** (> 3 elevators)
- **High-traffic scenarios** (office buildings peak hours)
- **Priority zones** (VIP floors, hospital emergency)
- Jab **starvation prevent** karni ho (koi floor wait hi karta rahe)

### 1.3 Kab mat use karo?

- Single elevator → simple FIFO queue kaafi hai
- 2-floor building → state machine overkill hai
- Emergency-only elevator → different logic (manual override)

### 1.4 State Machine — Hinglish comments ke saath

```python
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set
import threading
import heapq
import time

# ===== ENUMS =====

class Direction(Enum):
    UP = "UP"
    DOWN = "DOWN"
    IDLE = "IDLE"

class ElevatorState(Enum):
    # Elevator kuch nahi kar rahi
    IDLE = "IDLE"
    # Upar ja rahi hai
    MOVING_UP = "MOVING_UP"
    # Neeche ja rahi hai
    MOVING_DOWN = "MOVING_DOWN"
    # Door khula hai (3 sec ke liye)
    DOOR_OPEN = "DOOR_OPEN"
    # Maintenance mein hai, use mat karo
    OUT_OF_SERVICE = "OUT_OF_SERVICE"

class RequestType(Enum):
    # Bahar se button daba — "mujhe upar/neeche jaana hai"
    EXTERNAL = "EXTERNAL"
    # Andar se button daba — "mujhe floor X jaana hai"
    INTERNAL = "INTERNAL"

# ===== DATA CLASSES =====

@dataclass
class ElevatorRequest:
    floor: int
    direction: Optional[Direction]   # External ke liye (UP/DOWN button)
    request_type: RequestType
    timestamp: float = field(default_factory=time.time)
    
    # Priority queue ke liye comparison
    def __lt__(self, other):
        return self.timestamp < other.timestamp

@dataclass
class ElevatorStatus:
    elevator_id: int
    current_floor: int
    state: ElevatorState
    direction: Direction
    pending_stops: List[int]

# ===== DOOR =====

class Door:
    """
    Door ki state manage karta hai
    Real mein sensor hota hai — yahan simulate kar rahe hain
    """
    
    OPEN_DURATION = 3.0  # seconds
    
    def __init__(self, elevator_id: int):
        self.elevator_id = elevator_id
        self._is_open = False
        self._lock = threading.Lock()
    
    def open(self):
        with self._lock:
            if not self._is_open:
                self._is_open = True
                print(f"  [Door {self.elevator_id}] OPEN")
                # Real mein: motor command + sensor wait
    
    def close(self) -> bool:
        """Returns False agar koi beech mein hai (sensor blocked)"""
        with self._lock:
            if self._is_open:
                self._is_open = False
                print(f"  [Door {self.elevator_id}] CLOSED")
                return True
            return True
    
    @property
    def is_open(self):
        return self._is_open

# ===== DISPLAY =====

class Display:
    """Floor indicator aur direction arrow"""
    
    def __init__(self, elevator_id: int):
        self.elevator_id = elevator_id
    
    def update(self, floor: int, direction: Direction, state: ElevatorState):
        arrow = "↑" if direction == Direction.UP else "↓" if direction == Direction.DOWN else "—"
        print(f"  [Display E{self.elevator_id}] Floor: {floor} {arrow} [{state.value}]")

# ===== ELEVATOR =====

class Elevator:
    """
    Single elevator ki state + movement manage karta hai
    
    LOOK Algorithm:
    - Ek direction mein jao
    - Us direction mein jo bhi stops hain, serve karo
    - Jab koi stop nahi us direction mein, reverse karo
    - Agar dono taraf kuch nahi, IDLE ho jao
    """
    
    def __init__(self, elevator_id: int, total_floors: int):
        self.elevator_id = elevator_id
        self.total_floors = total_floors
        self.current_floor = 1          # Ground floor se shuru
        self.state = ElevatorState.IDLE
        self.direction = Direction.IDLE
        
        # Min-heap for UP stops, max-heap for DOWN stops
        # UP: [2, 5, 8] → 2 pehle serve karein
        # DOWN: [-8, -5, -2] → negate karke max-heap banate hain
        self._up_stops: List[int] = []    # heapq (min-heap)
        self._down_stops: List[int] = []  # heapq (max-heap, negated)
        
        self.door = Door(elevator_id)
        self.display = Display(elevator_id)
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        
        # Thread jo continuously move karta rehta hai
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name=f"Elevator-{elevator_id}"
        )
    
    def start(self):
        self._thread.start()
    
    def stop(self):
        self._stop_event.set()
    
    # ---- Request Add Karna ----
    
    def add_stop(self, floor: int, direction: Optional[Direction] = None):
        """
        Floor add karo stops mein
        
        LOOK logic:
        - Agar elevator UP ja rahi hai aur floor current se upar → up_stops
        - Agar elevator DOWN ja rahi hai aur floor current se neeche → down_stops
        - Warna opposite queue mein daalo (serve karenge jab direction reverse hogi)
        """
        with self._lock:
            if floor == self.current_floor and self.state == ElevatorState.DOOR_OPEN:
                return  # Already yahaan hain, door khula hai
            
            # Determine karo kahan add karein
            if self.direction == Direction.UP or self.direction == Direction.IDLE:
                if floor >= self.current_floor:
                    # Up queue mein daalo
                    if floor not in self._up_stops:
                        heapq.heappush(self._up_stops, floor)
                else:
                    # Neeche hai, down queue mein daalo (negate karke)
                    if floor not in self._down_stops:
                        heapq.heappush(self._down_stops, -floor)
            else:  # Going DOWN
                if floor <= self.current_floor:
                    # Down queue mein daalo
                    if floor not in self._down_stops:
                        heapq.heappush(self._down_stops, -floor)
                else:
                    # Upar hai, up queue mein daalo
                    if floor not in self._up_stops:
                        heapq.heappush(self._up_stops, floor)
            
            print(f"  [E{self.elevator_id}] Stop added: Floor {floor} | "
                  f"UP: {sorted(self._up_stops)} | "
                  f"DOWN: {sorted([-x for x in self._down_stops])}")
    
    # ---- Main Loop ----
    
    def _run_loop(self):
        """
        Continuously check karo aur move karo
        Real mein: event-driven hota (sensor signals)
        Yahan: polling with sleep
        """
        while not self._stop_event.is_set():
            self._process_next_stop()
            time.sleep(0.1)  # Polling interval
    
    def _process_next_stop(self):
        with self._lock:
            next_floor = self._get_next_stop()
            
            if next_floor is None:
                if self.state != ElevatorState.IDLE:
                    self.state = ElevatorState.IDLE
                    self.direction = Direction.IDLE
                    self.display.update(self.current_floor, self.direction, self.state)
                return
            
            # Move karo
            self._move_to(next_floor)
    
    def _get_next_stop(self) -> Optional[int]:
        """
        LOOK Algorithm:
        1. Current direction mein next stop dhundo
        2. Agar nahi mila, direction switch karo
        3. Agar wahan bhi nahi, IDLE
        """
        if self.direction == Direction.UP or self.direction == Direction.IDLE:
            # Pehle UP mein dekho
            if self._up_stops:
                return heapq.heappop(self._up_stops)   # Smallest floor upar
            elif self._down_stops:
                # UP mein kuch nahi, DOWN mein dekho
                return -heapq.heappop(self._down_stops)  # Largest floor neeche
        else:  # Direction.DOWN
            if self._down_stops:
                return -heapq.heappop(self._down_stops)  # Largest floor neeche
            elif self._up_stops:
                return heapq.heappop(self._up_stops)
        
        return None  # Koi stop nahi
    
    def _move_to(self, target_floor: int):
        """Floor-by-floor movement simulate karta hai"""
        if target_floor > self.current_floor:
            self.direction = Direction.UP
            self.state = ElevatorState.MOVING_UP
        elif target_floor < self.current_floor:
            self.direction = Direction.DOWN
            self.state = ElevatorState.MOVING_DOWN
        
        self.display.update(self.current_floor, self.direction, self.state)
        
        # Floor-by-floor move
        while self.current_floor != target_floor:
            time.sleep(0.5)  # 1 floor = 0.5 sec (real mein ~3 sec)
            if self.direction == Direction.UP:
                self.current_floor += 1
            else:
                self.current_floor -= 1
            self.display.update(self.current_floor, self.direction, self.state)
        
        # Arrived! Door kholo
        self._arrive_at_floor()
    
    def _arrive_at_floor(self):
        """Floor pe pahunch gaye"""
        self.state = ElevatorState.DOOR_OPEN
        self.door.open()
        self.display.update(self.current_floor, self.direction, self.state)
        
        time.sleep(Door.OPEN_DURATION)  # Log in/out hone do
        
        self.door.close()
        self.state = ElevatorState.IDLE  # Next stop check hoga loop mein
    
    # ---- Status ----
    
    def get_status(self) -> ElevatorStatus:
        with self._lock:
            all_stops = (
                sorted(self._up_stops) +
                sorted([-x for x in self._down_stops])
            )
            return ElevatorStatus(
                elevator_id=self.elevator_id,
                current_floor=self.current_floor,
                state=self.state,
                direction=self.direction,
                pending_stops=all_stops
            )
    
    def estimated_cost(self, target_floor: int, direction: Direction) -> float:
        """
        Dispatcher ke liye — yeh elevator kitna cost karega yeh request serve karne mein?
        
        Cost factors:
        1. Distance from current floor
        2. Number of pending stops (already busy?)
        3. Same direction bonus (if going towards target anyway)
        """
        with self._lock:
            if self.state == ElevatorState.OUT_OF_SERVICE:
                return float('inf')
            
            distance = abs(self.current_floor - target_floor)
            pending_penalty = len(self._up_stops) + len(self._down_stops)
            
            # Same direction bonus
            direction_bonus = 0
            if (self.direction == Direction.UP and direction == Direction.UP and
                    target_floor > self.current_floor):
                direction_bonus = -2  # Bonus: same direction, same way
            elif (self.direction == Direction.DOWN and direction == Direction.DOWN and
                    target_floor < self.current_floor):
                direction_bonus = -2
            
            return distance + pending_penalty * 0.5 + direction_bonus

# ===== DISPATCHER (Controller) =====

class RequestDispatcher:
    """
    Decides which elevator should handle which request
    
    Strategy: Minimum Cost Selection
    - Distance se calculate karo
    - Pending stops ka penalty
    - Same direction bonus
    """
    
    def __init__(self, elevators: List[Elevator]):
        self.elevators = elevators
    
    def dispatch(self, request: ElevatorRequest) -> Optional[Elevator]:
        """Best elevator choose karo"""
        best_elevator = None
        best_cost = float('inf')
        
        for elevator in self.elevators:
            cost = elevator.estimated_cost(request.floor, request.direction or Direction.UP)
            print(f"  [Dispatcher] E{elevator.elevator_id} cost for floor {request.floor}: {cost:.2f}")
            
            if cost < best_cost:
                best_cost = cost
                best_elevator = elevator
        
        if best_elevator:
            print(f"  [Dispatcher] → Assigned to E{best_elevator.elevator_id}")
            best_elevator.add_stop(request.floor, request.direction)
        
        return best_elevator

# ===== BUILDING CONTROLLER =====

class ElevatorController:
    """
    Main facade — building ke sabhi elevators manage karta hai
    
    Real building mein yeh:
    - Separate hardware controller hota hai (Otis, Schindler)
    - Building management system se connected hota hai
    - Yahan: software simulation
    """
    
    def __init__(self, num_elevators: int, total_floors: int):
        self.total_floors = total_floors
        self.elevators = [
            Elevator(elevator_id=i+1, total_floors=total_floors)
            for i in range(num_elevators)
        ]
        self.dispatcher = RequestDispatcher(self.elevators)
        self._running = False
    
    def start(self):
        """Sabhi elevators start karo"""
        self._running = True
        for elevator in self.elevators:
            elevator.start()
        print(f"[Controller] {len(self.elevators)} elevators started, {self.total_floors} floors")
    
    def stop(self):
        """Graceful shutdown"""
        for elevator in self.elevators:
            elevator.stop()
        self._running = False
    
    # ---- External Requests (Floor buttons) ----
    
    def request_elevator(self, floor: int, direction: Direction):
        """
        Koi floor pe button dabata hai
        E.g.: Floor 5 pe koi "UP" button dabata hai
        """
        if not (1 <= floor <= self.total_floors):
            raise ValueError(f"Invalid floor: {floor}")
        
        print(f"\n[Controller] External request: Floor {floor}, Direction {direction.value}")
        
        request = ElevatorRequest(
            floor=floor,
            direction=direction,
            request_type=RequestType.EXTERNAL
        )
        self.dispatcher.dispatch(request)
    
    # ---- Internal Requests (Inside elevator) ----
    
    def select_floor(self, elevator_id: int, floor: int):
        """
        Andar se button daba — "mujhe floor X jaana hai"
        """
        if not (1 <= floor <= self.total_floors):
            raise ValueError(f"Invalid floor: {floor}")
        if not (1 <= elevator_id <= len(self.elevators)):
            raise ValueError(f"Invalid elevator: {elevator_id}")
        
        elevator = self.elevators[elevator_id - 1]
        print(f"\n[Controller] Internal request: E{elevator_id} → Floor {floor}")
        
        request = ElevatorRequest(
            floor=floor,
            direction=None,  # Internal: direction matter nahi
            request_type=RequestType.INTERNAL
        )
        elevator.add_stop(floor)
    
    # ---- Status ----
    
    def get_all_status(self) -> List[ElevatorStatus]:
        return [e.get_status() for e in self.elevators]
    
    def print_status(self):
        print("\n=== ELEVATOR STATUS ===")
        for status in self.get_all_status():
            arrow = "↑" if status.direction == Direction.UP else "↓" if status.direction == Direction.DOWN else "—"
            print(f"E{status.elevator_id}: Floor {status.current_floor} {arrow} [{status.state.value}] "
                  f"| Pending: {status.pending_stops}")
        print("=" * 23)
    
    # ---- Emergency ----
    
    def emergency_stop_all(self):
        """Emergency button — sabhi ruko"""
        print("\n[EMERGENCY] All elevators stopping at nearest floor!")
        for elevator in self.elevators:
            elevator.state = ElevatorState.OUT_OF_SERVICE
            elevator.door.open()  # Safety: door kholo

# ===== DEMO =====

def demo():
    print("=" * 60)
    print("ELEVATOR SYSTEM — LOOK ALGORITHM DEMO")
    print("=" * 60)
    
    # 2 elevators, 10 floors
    controller = ElevatorController(num_elevators=2, total_floors=10)
    controller.start()
    
    time.sleep(0.5)  # Elevators initialize hone do
    
    # Scenario 1: Morning rush — sab upar jaana chahte hain
    print("\n--- SCENARIO 1: Morning Rush (Ground → Upper floors) ---")
    controller.request_elevator(floor=1, direction=Direction.UP)
    time.sleep(0.2)
    controller.request_elevator(floor=2, direction=Direction.UP)
    time.sleep(0.2)
    controller.request_elevator(floor=3, direction=Direction.UP)
    
    time.sleep(1.0)
    
    # Scenario 2: Andar se floor select karna
    print("\n--- SCENARIO 2: Passengers inside selecting floors ---")
    controller.select_floor(elevator_id=1, floor=7)
    controller.select_floor(elevator_id=1, floor=5)  # Pehle 5 serve hoga (LOOK)
    controller.select_floor(elevator_id=2, floor=8)
    
    time.sleep(1.0)
    controller.print_status()
    
    # Scenario 3: Evening rush — sab neeche aana chahte hain
    print("\n--- SCENARIO 3: Evening Rush (Upper → Ground) ---")
    controller.request_elevator(floor=9, direction=Direction.DOWN)
    controller.request_elevator(floor=7, direction=Direction.DOWN)
    controller.request_elevator(floor=5, direction=Direction.DOWN)
    
    time.sleep(2.0)
    controller.print_status()
    
    controller.stop()
    print("\n[Demo Complete]")

if __name__ == "__main__":
    demo()
```

### 1.5 Tumhara real project mein kahan use hua

Directly elevator nahi, but same concepts:

**State Machine → Niroskos Booking State:**
- `DRAFT → CONFIRMED → ALLOCATED → IN_TRANSIT → DELIVERED`
- Jaise elevator: `IDLE → MOVING → DOOR_OPEN → IDLE`
- Invalid transitions ko reject karna (`can_transition()` method)

**SCAN-like Scheduling → Blockchain Scanner:**
```python
# Blocks ko scan karta tha — same direction mein jab tak koi transaction nahi
# Phir "reverse" — yahan naya start block
class BlockchainScanner:
    def scan_blocks(self, start_block, end_block):
        current = start_block
        while current <= end_block:
            txns = self.fetch_transactions(current)
            if txns:
                self.process_transactions(txns)
            current += 1  # SCAN: linear direction maintain karo
```

**Priority Queue → Celery Task Priorities:**
- CRITICAL (payment webhook) = priority 1
- HIGH (booking confirmed email) = priority 2  
- NORMAL (weekly report) = priority 9

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definition

> The Elevator System is a multi-elevator scheduling problem combining **State Machine** (per-elevator lifecycle), **LOOK Disk Scheduling Algorithm** (request batching by direction), and a **Dispatcher** (minimum-cost assignment across elevators). The core challenge is serving requests efficiently while preventing starvation and ensuring safety constraints like door sensors.

### 2.2 Problem it Solves

| Problem | Naive Approach | Our Solution |
|---------|---------------|--------------|
| Serving all requests | FCFS (First Come First Serve) | LOOK: batch by direction |
| Which elevator? | Random assignment | Min-cost dispatcher |
| Starvation | None | Direction-based queues — both sides served |
| Concurrent requests | Single queue | Per-elevator up/down heaps |
| State safety | None | Explicit state machine + lock |

### 2.3 Key Components

| Component | Responsibility | Design Pattern |
|-----------|---------------|----------------|
| `Elevator` | Single elevator: state, movement, LOOK algorithm | State Machine |
| `Door` | Open/close lifecycle, sensor simulation | N/A |
| `Display` | Floor indicator (real: 7-segment display driver) | Observer (display updates) |
| `RequestDispatcher` | Assign request to best elevator | Strategy Pattern |
| `ElevatorController` | Facade: external/internal requests, emergency | Facade Pattern |

### 2.4 LOOK Algorithm — The Core

```
LOOK (improved SCAN):
1. Move in current direction
2. Serve all stops in that direction
3. When no more stops ahead in current direction → reverse
4. If no stops in either direction → IDLE

Why LOOK over SCAN?
- SCAN goes all the way to end floor even if no stops there
- LOOK only goes as far as the last stop — more efficient
- Real elevators use LOOK (or variants like C-LOOK)
```

```
Example: Elevator at floor 4, going UP
Pending stops: [1, 3, 6, 8, 9]
UP stops (≥ 4): [6, 8, 9]   → serve 6 → 8 → 9
DOWN stops (< 4): [3, 1]    → reverse → serve 3 → 1
Result: 5 stops served in optimal order
FCFS would have been: 1 → 3 → 6 → 8 → 9 (many direction changes)
```

### 2.5 Data Structures

```python
# UP stops: Min-heap (serve lowest first when going up)
self._up_stops: List[int] = []    # heapq

# DOWN stops: Max-heap using negation (serve highest first when going down)
self._down_stops: List[int] = []  # heapq with -floor values

# Add stop going UP at floor 7:
heapq.heappush(self._up_stops, 7)

# Next stop going UP:
next_floor = heapq.heappop(self._up_stops)  # O(log n)

# Next stop going DOWN (negate to simulate max-heap):
next_floor = -heapq.heappop(self._down_stops)  # O(log n)
```

### 2.6 Dispatcher Cost Function

```python
def estimated_cost(self, target_floor: int, direction: Direction) -> float:
    distance = abs(self.current_floor - target_floor)
    
    # Penalty for each pending stop (elevator is already busy)
    pending_penalty = len(self._up_stops) + len(self._down_stops)
    
    # Bonus if elevator is already going same direction toward target
    direction_bonus = -2 if same_direction_and_towards_target else 0
    
    return distance + pending_penalty * 0.5 + direction_bonus

# Result: Idle elevator nearby > Busy elevator nearby > Distant elevator
```

### 2.7 State Transition Diagram

```
         add_stop()
IDLE ──────────────→ MOVING_UP ──→ DOOR_OPEN
  ↑                      |              |
  |                      ↓         (3 sec wait)
  |                 MOVING_DOWN         |
  |                      |              |
  └──────────────────────┴──────────────┘
           no more stops              close()

OUT_OF_SERVICE (maintenance mode — no transitions in/out except manual)
```

### 2.8 Thread Safety

```python
class Elevator:
    def __init__(self):
        self._lock = threading.Lock()       # Protects state + queues
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
    
    def add_stop(self, floor):
        with self._lock:          # Multiple external callers → one at a time
            heapq.heappush(...)
    
    def _get_next_stop(self):
        # Called from _run_loop (single thread) but state read by others
        # Already inside _lock when called from _process_next_stop
        ...
```

**Why daemon=True?**  
Elevator threads are daemon threads — they die when main thread dies. No zombie threads on shutdown.

### 2.9 Real Project Answer

> "In my Niroskos project, I used a similar state machine for booking lifecycle — DRAFT, CONFIRMED, ALLOCATED, IN_TRANSIT, DELIVERED. The elevator's LOOK algorithm is analogous to how our Celery task queue batches similar jobs — instead of reversing direction, we use task priority levels. The dispatcher cost function is similar to how we chose which Celery worker queue to route a task to based on current queue depth."

> "For the elevator's thread-per-elevator model, I'd say in production I'd use async/await with asyncio.Queue instead of threading, because elevator events are I/O-bound (waiting for door sensors, floor sensors) — perfect for asyncio's event loop model."

### 2.10 Common Follow-up Q&A

**Q1: How do you prevent starvation?**
> "With LOOK algorithm, both UP and DOWN queues are maintained separately. When an elevator finishes all UP requests, it immediately switches to serve DOWN requests. No floor is skipped. For edge cases where a very busy building keeps adding UP requests, I'd implement a MAX_PASSES_IN_ONE_DIRECTION limit — after N passes, force direction switch even if UP queue has items."

**Q2: What if an elevator breaks down mid-journey?**
> "The elevator transitions to OUT_OF_SERVICE state (circuit breaker pattern). The ElevatorController detects this via a heartbeat timeout — each elevator publishes its last_heartbeat timestamp. On failure detection: (1) door safety open if between floors, (2) redistribute pending stops from broken elevator to others via dispatcher, (3) alert maintenance system. This is the same pattern as our Celery worker failure — task_acks_late=True ensures tasks get re-queued if worker dies."

**Q3: How would you scale this to a 100-floor skyscraper?**
> "Zone-based scheduling: floors 1-25 = Elevators 1-4, floors 26-50 = Elevators 5-8, with 2 'express' elevators serving ground + sky lobbies. This is exactly how real high-rises work (Burj Khalifa model). Sky lobby transfers reduce average travel time from O(floors) to O(floors/zones). I'd model this as an ElevatorGroup per zone with a ZoneController above them."

**Q4: How is LOOK different from Round Robin assignment?**
> "Round Robin ignores elevator state — it might send a floor 1 request to an elevator currently at floor 10 going up. LOOK + Cost Dispatcher always picks the most contextually appropriate elevator. Round Robin gives equal load but not optimal response time. LOOK gives optimal response time at the cost of slightly unequal load — acceptable trade-off for passenger experience."

**Q5: Why min-heap for UP stops, max-heap for DOWN stops?**
> "When going UP, you want to serve the next floor above you first — smallest floor number wins → min-heap is natural. When going DOWN, you want to serve the next floor below you first — largest floor number wins → max-heap. Python's heapq is min-heap only, so we negate values for DOWN: push(-floor), pop gives most negative = largest floor."

---

## Comparison: Scheduling Algorithms

| Algorithm | How it Works | Pros | Cons | Use Case |
|-----------|-------------|------|------|----------|
| FCFS | Serve in request order | Simple | Many direction changes | Single elevator, low traffic |
| SCAN | Go end-to-end, serve all in between | No starvation | Wasteful at ends | Old elevators |
| LOOK | Go until last stop in direction, reverse | Efficient, no waste | Slightly complex | Most modern elevators |
| C-LOOK | Only go in one direction (circular) | Very uniform | Higher avg wait | High-rise express zones |
| Shortest Seek Time First (SSTF) | Serve nearest request | Low avg distance | Starvation possible | Not used in elevators |

---

## Production Considerations

```python
# 1. Persistence: Elevator state survives restart
class ElevatorStatePersistence:
    def save(self, elevator_id, floor, direction):
        redis.set(f"elevator:{elevator_id}:floor", floor)
        redis.set(f"elevator:{elevator_id}:direction", direction.value)

# 2. Metrics: Prometheus counters
elevator_wait_time = Histogram('elevator_wait_seconds', 'Time from request to arrival')
elevator_trips_total = Counter('elevator_trips_total', 'Total trips', ['elevator_id'])

# 3. Predictive: ML-based peak hour pre-positioning
# Morning 9am: send all elevators to floors 1-3 proactively
# Evening 6pm: send elevators to upper floors

# 4. Energy: Park idle elevators at ground or mid floor
# Industry standard: park at most-used floor during off-peak

# 5. VIP floors: Priority in dispatcher cost function
VIP_FLOORS = {10, 20}  # Executive floors
if target_floor in VIP_FLOORS:
    cost *= 0.5  # Halve cost → preferred elevator gets chosen
```

---

## Interview Cheat Sheet

```
30-second pitch:
"Elevator system uses LOOK algorithm — elevator maintains two heaps,
one for UP stops (min-heap) and one for DOWN stops (max-heap via negation).
Dispatcher uses a cost function: distance + pending_stops_penalty - direction_bonus.
State machine: IDLE → MOVING_UP/DOWN → DOOR_OPEN → IDLE.
Thread-per-elevator with Lock protecting heap modifications."

Key numbers to mention:
- DOOR_OPEN_DURATION = 3 seconds (real: ~3-5s with sensors)
- Floor travel time = ~3 seconds/floor (real)
- Cost function weights: distance=1, pending=0.5/stop, direction_bonus=-2

Patterns used:
- State Machine (Elevator lifecycle)
- Strategy (Dispatcher can swap to Round Robin, Zone-based, etc.)
- Facade (ElevatorController hides complexity)
- Observer (Display updates on every state change)
```
