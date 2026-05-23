# Ride Booking System (Uber/Ola) LLD

## Quick Reference Card
```
Pattern Used    → Strategy (pricing), State Machine (ride lifecycle), Observer (notifications)
Core Challenge  → Real-time driver matching, Dynamic pricing, Concurrent ride requests
Key Classes     → Rider, Driver, Ride, PricingStrategy, MatchingService, RideService
State Machine   → REQUESTED → ACCEPTED → DRIVER_ARRIVING → IN_PROGRESS → COMPLETED/CANCELLED
Interview Hook  → "Geohash grid mein nearby drivers dhundna — O(1) lookup"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Kya hai?

Uber-type system mein 3 main actors hain:
- **Rider** — ride book karna chahta hai
- **Driver** — ride accept karna chahta hai, paise kamana chahta hai
- **Ride** — ek transaction jisme rider + driver + route + fare sab hai

**Core challenge:** 
> "Millions of drivers real-time GPS update kar rahe hain, millions of riders request kar rahe hain — correct match karo O(1) time mein"

**Geohash trick:** Location ko ek string mein convert karo (e.g., `"ttnn8p"`). Same prefix = same area. Nearby drivers = same geohash cell mein search karo. Database index pe O(1) lookup!

### 1.2 Kab use karo?

- On-demand service matching (ride, delivery, doctor)
- Real-time location tracking
- Dynamic pricing (supply-demand based)
- Rating/review systems

### 1.3 Code — Hinglish comments ke saath

```python
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Tuple
from datetime import datetime
import threading
import math
import uuid
import time

# ===== ENUMS =====

class RideStatus(Enum):
    REQUESTED = "REQUESTED"       # Rider ne request ki
    SEARCHING = "SEARCHING"       # Driver dhund rahe hain
    ACCEPTED = "ACCEPTED"         # Driver ne accept kiya
    DRIVER_ARRIVING = "DRIVER_ARRIVING"  # Driver aa raha hai
    IN_PROGRESS = "IN_PROGRESS"   # Ride chal rahi hai
    COMPLETED = "COMPLETED"       # Ride khatam
    CANCELLED = "CANCELLED"       # Cancel ho gayi
    NO_DRIVER_FOUND = "NO_DRIVER_FOUND"  # Koi driver nahi mila

class DriverStatus(Enum):
    OFFLINE = "OFFLINE"           # App off
    AVAILABLE = "AVAILABLE"       # Ready for ride
    ON_TRIP = "ON_TRIP"           # Abhi ride pe hai
    RETURNING = "RETURNING"       # Ride complete, return kar raha hai

class VehicleType(Enum):
    BIKE = "BIKE"                 # 2-wheeler
    AUTO = "AUTO"                 # 3-wheeler
    MINI = "MINI"                 # Hatchback
    SEDAN = "SEDAN"               # Sedan
    SUV = "SUV"                   # SUV/XL

class CancellationReason(Enum):
    RIDER_CANCELLED = "RIDER_CANCELLED"
    DRIVER_CANCELLED = "DRIVER_CANCELLED"
    NO_DRIVER_FOUND = "NO_DRIVER_FOUND"
    PAYMENT_FAILED = "PAYMENT_FAILED"

# ===== LOCATION =====

@dataclass
class Location:
    """GPS coordinates"""
    latitude: float
    longitude: float
    address: str = ""
    
    def distance_to(self, other: 'Location') -> float:
        """
        Haversine formula — Earth ki surface pe distance calculate karo
        Returns: distance in kilometers
        
        Real mein Google Maps Distance Matrix API use karte hain
        (traffic, road conditions consider karta hai)
        Yahan: straight line distance for demo
        """
        R = 6371  # Earth radius in km
        
        lat1, lon1 = math.radians(self.latitude), math.radians(self.longitude)
        lat2, lon2 = math.radians(other.latitude), math.radians(other.longitude)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c
    
    def geohash(self, precision: int = 6) -> str:
        """
        Location ko geohash string mein convert karo
        Precision 6 ≈ 1.2km x 0.6km grid cell
        
        Real implementation: python-geohash library
        Yahan: simplified version
        """
        # Simplified: lat/lon ko grid cell mein convert karo
        lat_grid = int((self.latitude + 90) / 180 * (10 ** precision))
        lon_grid = int((self.longitude + 180) / 360 * (10 ** precision))
        return f"{lat_grid:0{precision}}_{lon_grid:0{precision}}"

# ===== VEHICLE =====

@dataclass
class Vehicle:
    vehicle_id: str = field(default_factory=lambda: f"V{str(uuid.uuid4())[:6].upper()}")
    registration: str = ""    # "MH12AB1234"
    vehicle_type: VehicleType = VehicleType.MINI
    model: str = ""            # "Swift Dzire"
    color: str = ""
    year: int = 2020
    capacity: int = 4

# ===== DRIVER =====

@dataclass
class Driver:
    driver_id: str = field(default_factory=lambda: f"D{str(uuid.uuid4())[:6].upper()}")
    name: str = ""
    phone: str = ""
    rating: float = 4.5        # 1-5 stars
    total_rides: int = 0
    vehicle: Vehicle = None
    current_location: Location = None
    status: DriverStatus = DriverStatus.OFFLINE
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)
    
    def go_online(self, location: Location):
        with self._lock:
            self.current_location = location
            self.status = DriverStatus.AVAILABLE
    
    def go_offline(self):
        with self._lock:
            self.status = DriverStatus.OFFLINE
    
    def accept_ride(self) -> bool:
        """Ride accept karo — atomic status change"""
        with self._lock:
            if self.status != DriverStatus.AVAILABLE:
                return False  # Already on trip
            self.status = DriverStatus.ON_TRIP
            return True
    
    def complete_ride(self, location: Location):
        with self._lock:
            self.current_location = location
            self.status = DriverStatus.AVAILABLE
            self.total_rides += 1

# ===== RIDER =====

@dataclass
class Rider:
    rider_id: str = field(default_factory=lambda: f"R{str(uuid.uuid4())[:6].upper()}")
    name: str = ""
    phone: str = ""
    email: str = ""
    rating: float = 4.8        # Driver ko rider ki rating dikhta hai
    total_rides: int = 0
    wallet_balance: float = 0.0
    preferred_payment: str = "UPI"

# ===== FARE ESTIMATE =====

@dataclass
class FareEstimate:
    base_fare: float = 0.0
    distance_charge: float = 0.0
    time_charge: float = 0.0
    surge_multiplier: float = 1.0
    taxes: float = 0.0
    total_fare: float = 0.0
    currency: str = "INR"
    
    def breakdown(self) -> str:
        return (f"Base: ₹{self.base_fare} + Distance: ₹{self.distance_charge:.1f} + "
                f"Time: ₹{self.time_charge:.1f} | Surge: {self.surge_multiplier}x | "
                f"Tax: ₹{self.taxes:.1f} = Total: ₹{self.total_fare:.1f}")

# ===== RIDE =====

@dataclass
class Ride:
    ride_id: str = field(default_factory=lambda: f"RD{str(uuid.uuid4())[:8].upper()}")
    rider_id: str = ""
    driver_id: Optional[str] = None
    vehicle_type: VehicleType = VehicleType.MINI
    pickup: Location = None
    dropoff: Location = None
    status: RideStatus = RideStatus.REQUESTED
    fare_estimate: Optional[FareEstimate] = None
    actual_fare: float = 0.0
    distance_km: float = 0.0
    duration_minutes: float = 0.0
    rider_rating: Optional[float] = None   # Driver ne rider ko diya
    driver_rating: Optional[float] = None  # Rider ne driver ko diya
    requested_at: datetime = field(default_factory=datetime.now)
    accepted_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancellation_reason: Optional[CancellationReason] = None

# ===== PRICING STRATEGY =====

class PricingStrategy:
    """Base class — alag alag pricing models"""
    
    def calculate_fare(self, distance_km: float, duration_min: float,
                       vehicle_type: VehicleType, surge: float) -> FareEstimate:
        raise NotImplementedError

class StandardPricingStrategy(PricingStrategy):
    """
    Normal pricing — distance + time based
    Rates vary by vehicle type
    """
    
    RATES = {
        VehicleType.BIKE:  {"base": 20, "per_km": 8,  "per_min": 1.0},
        VehicleType.AUTO:  {"base": 25, "per_km": 12, "per_min": 1.5},
        VehicleType.MINI:  {"base": 40, "per_km": 14, "per_min": 2.0},
        VehicleType.SEDAN: {"base": 60, "per_km": 18, "per_min": 2.5},
        VehicleType.SUV:   {"base": 80, "per_km": 22, "per_min": 3.0},
    }
    TAX_RATE = 0.05  # 5% GST
    
    def calculate_fare(self, distance_km, duration_min, vehicle_type, surge=1.0):
        rates = self.RATES[vehicle_type]
        
        base = rates["base"]
        distance_charge = distance_km * rates["per_km"]
        time_charge = duration_min * rates["per_min"]
        
        subtotal = (base + distance_charge + time_charge) * surge
        taxes = subtotal * self.TAX_RATE
        total = round(subtotal + taxes, 2)
        
        return FareEstimate(
            base_fare=base,
            distance_charge=round(distance_charge, 2),
            time_charge=round(time_charge, 2),
            surge_multiplier=surge,
            taxes=round(taxes, 2),
            total_fare=total
        )

class AirportPricingStrategy(PricingStrategy):
    """Airport pick/drop — flat rate + extras"""
    
    AIRPORT_FLAT_RATE = {
        VehicleType.MINI: 500,
        VehicleType.SEDAN: 700,
        VehicleType.SUV: 1000,
    }
    TOLL_CHARGE = 100
    
    def calculate_fare(self, distance_km, duration_min, vehicle_type, surge=1.0):
        base = self.AIRPORT_FLAT_RATE.get(vehicle_type, 600)
        total = (base + self.TOLL_CHARGE) * surge
        
        return FareEstimate(
            base_fare=base,
            distance_charge=self.TOLL_CHARGE,
            time_charge=0,
            surge_multiplier=surge,
            taxes=round(total * 0.05, 2),
            total_fare=round(total * 1.05, 2)
        )

# ===== SURGE CALCULATOR =====

class SurgeCalculator:
    """
    Supply-demand based surge pricing
    
    Demand >> Supply → surge multiplier badhta hai
    Real Uber: ML model, historical data, events, weather
    Yahan: ratio-based simple model
    """
    
    SURGE_THRESHOLDS = [
        (0.5, 1.0),   # demand/supply < 0.5 → 1x (normal)
        (1.0, 1.2),   # 0.5-1.0 → 1.2x
        (1.5, 1.5),   # 1.0-1.5 → 1.5x
        (2.0, 1.8),   # 1.5-2.0 → 1.8x
        (float('inf'), 2.0),  # > 2.0 → 2x (cap)
    ]
    
    def calculate_surge(self, active_requests: int, available_drivers: int) -> float:
        """
        Surge = f(demand, supply)
        available_drivers = 0 hoga to ZeroDivisionError → handle karo
        """
        if available_drivers == 0:
            return 2.0  # Max surge
        
        ratio = active_requests / available_drivers
        
        for threshold, multiplier in self.SURGE_THRESHOLDS:
            if ratio <= threshold:
                return multiplier
        
        return 2.0

# ===== DRIVER POOL (Location Index) =====

class DriverPool:
    """
    Available drivers ka real-time index
    
    Geohash-based: drivers ko unaके geohash grid mein store karo
    Query: "5 km ke andar available drivers dhundo"
    
    Real system: Redis Geospatial commands
    - GEOADD driver:{id} longitude latitude
    - GEORADIUS <key> <longitude> <latitude> <radius> km
    """
    
    def __init__(self):
        # geohash → set of driver_ids
        self._grid: Dict[str, set] = {}
        # driver_id → Driver
        self._drivers: Dict[str, Driver] = {}
        self._lock = threading.RLock()
    
    def register_driver(self, driver: Driver):
        with self._lock:
            self._drivers[driver.driver_id] = driver
    
    def update_location(self, driver_id: str, location: Location):
        """Driver ne location update ki (every 5-10 seconds)"""
        with self._lock:
            driver = self._drivers.get(driver_id)
            if not driver:
                return
            
            # Old geohash se remove karo
            if driver.current_location:
                old_hash = driver.current_location.geohash()
                if old_hash in self._grid:
                    self._grid[old_hash].discard(driver_id)
            
            # New geohash mein add karo
            driver.current_location = location
            new_hash = location.geohash()
            if new_hash not in self._grid:
                self._grid[new_hash] = set()
            self._grid[new_hash].add(driver_id)
    
    def find_nearby_drivers(
        self, location: Location, radius_km: float,
        vehicle_type: VehicleType, limit: int = 5
    ) -> List[Driver]:
        """
        Nearby available drivers dhundo
        
        Simple approach: geohash grid check + distance filter
        Real: Redis GEORADIUS ya Elasticsearch geo_distance query
        """
        with self._lock:
            candidates = []
            
            # Grid-based search — expand gradually
            target_hash = location.geohash(precision=4)  # Larger cell for initial search
            
            for driver_id, driver in self._drivers.items():
                if (driver.status == DriverStatus.AVAILABLE and
                        driver.vehicle and
                        driver.vehicle.vehicle_type == vehicle_type and
                        driver.current_location):
                    
                    distance = location.distance_to(driver.current_location)
                    if distance <= radius_km:
                        candidates.append((distance, driver))
            
            # Sort by distance
            candidates.sort(key=lambda x: x[0])
            return [driver for _, driver in candidates[:limit]]
    
    def get_driver(self, driver_id: str) -> Optional[Driver]:
        return self._drivers.get(driver_id)
    
    def get_available_count_in_area(self, location: Location, radius_km: float) -> int:
        with self._lock:
            return sum(
                1 for driver in self._drivers.values()
                if (driver.status == DriverStatus.AVAILABLE and
                    driver.current_location and
                    location.distance_to(driver.current_location) <= radius_km)
            )

# ===== MATCHING SERVICE =====

class MatchingService:
    """
    Rider + Driver ko match karo
    
    Algorithm:
    1. Nearby available drivers dhundo (radius = 5km)
    2. Score calculate karo per driver:
       - Distance (closer = better)
       - Rating (higher = better)
       - Acceptance rate (historically accepts = better)
    3. Top driver ko request bhejo
    4. Agar accept nahi kiya (60 sec timeout) → next driver try karo
    5. Max 3 attempts → NO_DRIVER_FOUND
    """
    
    MAX_SEARCH_RADIUS_KM = 5.0
    DRIVER_RESPONSE_TIMEOUT_SEC = 30
    MAX_ATTEMPTS = 3
    
    def __init__(self, driver_pool: DriverPool):
        self.driver_pool = driver_pool
    
    def find_best_driver(
        self, pickup: Location, vehicle_type: VehicleType,
        rider_rating: float = 4.0
    ) -> Optional[Driver]:
        """
        Best driver dhundo aur assign karo
        """
        candidates = self.driver_pool.find_nearby_drivers(
            pickup, self.MAX_SEARCH_RADIUS_KM, vehicle_type, limit=10
        )
        
        if not candidates:
            return None
        
        # Score based matching
        scored = []
        for driver in candidates:
            dist = pickup.distance_to(driver.current_location)
            score = self._score_driver(driver, dist, rider_rating)
            scored.append((score, driver))
        
        # Highest score pehle
        scored.sort(key=lambda x: x[0], reverse=True)
        
        # Try to assign in order
        for score, driver in scored:
            if driver.accept_ride():  # Atomic — driver available hai to accept
                print(f"  [Match] Driver {driver.name} assigned (score: {score:.2f}, "
                      f"dist: {pickup.distance_to(driver.current_location):.2f}km)")
                return driver
        
        return None
    
    def _score_driver(self, driver: Driver, distance_km: float, rider_rating: float) -> float:
        """
        Lower distance = higher score
        Higher driver rating = higher score
        Rider rating also matters (drivers prefer high-rated riders)
        """
        distance_score = max(0, 10 - distance_km * 2)  # 0-10, closer is better
        rating_score = driver.rating * 2                # 0-10
        rider_factor = rider_rating / 5.0               # 0-1 multiplier
        
        return (distance_score * 0.5 + rating_score * 0.3) * rider_factor

# ===== NOTIFICATION SERVICE =====

class RideNotificationService:
    """Observer — ride events pe notifications"""
    
    def notify_driver_assigned(self, rider: Rider, driver: Driver, ride: Ride):
        eta_min = int(ride.pickup.distance_to(driver.current_location) / 0.5)  # Assume 30 km/h
        print(f"  [SMS → {rider.phone}] Driver {driver.name} is on the way! "
              f"ETA: {eta_min} min | {driver.vehicle.registration}")
    
    def notify_driver_arrived(self, rider: Rider, driver: Driver):
        print(f"  [Push → {rider.name}] Your driver has arrived!")
    
    def notify_ride_started(self, rider: Rider):
        print(f"  [Push → {rider.name}] Ride started. Have a safe journey!")
    
    def notify_ride_completed(self, rider: Rider, fare: float):
        print(f"  [Push → {rider.name}] Ride complete! Fare: ₹{fare}. Rate your trip.")
    
    def notify_cancellation(self, rider: Rider, reason: CancellationReason):
        print(f"  [SMS → {rider.phone}] Ride cancelled: {reason.value}")

# ===== RIDE SERVICE (Facade) =====

class RideService:
    """
    Main service — sab kuch yahan se
    
    Business Rules:
    - Rider ek time pe ek active ride
    - Driver rating < 3.5 → deactivated
    - Surge 2x se zyada nahi
    - Cancellation by rider after 3 min → cancellation fee ₹50
    - No driver in 5 min → auto-cancel
    """
    
    def __init__(self):
        self.driver_pool = DriverPool()
        self.matching_service = MatchingService(self.driver_pool)
        self.surge_calculator = SurgeCalculator()
        self.notifier = RideNotificationService()
        
        self._riders: Dict[str, Rider] = {}
        self._rides: Dict[str, Ride] = {}
        self._active_rider_rides: Dict[str, str] = {}  # rider_id → ride_id
        
        self._lock = threading.RLock()
    
    # ---- Setup ----
    
    def register_rider(self, name: str, phone: str, email: str) -> Rider:
        rider = Rider(name=name, phone=phone, email=email)
        self._riders[rider.rider_id] = rider
        return rider
    
    def register_driver(self, name: str, phone: str, vehicle: Vehicle) -> Driver:
        driver = Driver(name=name, phone=phone, vehicle=vehicle)
        self.driver_pool.register_driver(driver)
        return driver
    
    def driver_go_online(self, driver_id: str, lat: float, lon: float):
        driver = self.driver_pool.get_driver(driver_id)
        if driver:
            location = Location(lat, lon)
            driver.go_online(location)
            self.driver_pool.update_location(driver_id, location)
            print(f"[Ride] Driver {driver.name} is ONLINE at ({lat:.4f}, {lon:.4f})")
    
    # ---- Fare Estimate ----
    
    def get_fare_estimate(self, pickup: Location, dropoff: Location,
                          vehicle_type: VehicleType) -> FareEstimate:
        """
        Ride book karne se pehle estimate dikhao
        Rider ko pata ho kitna lagega
        """
        distance = pickup.distance_to(dropoff)
        duration = distance / 0.5  # Approx 30 km/h average
        
        # Surge calculate karo
        available_drivers = self.driver_pool.get_available_count_in_area(pickup, radius_km=5)
        active_requests = len([r for r in self._rides.values()
                               if r.status == RideStatus.SEARCHING])
        surge = self.surge_calculator.calculate_surge(active_requests, available_drivers)
        
        strategy = StandardPricingStrategy()
        estimate = strategy.calculate_fare(distance, duration, vehicle_type, surge)
        estimate.total_fare = estimate.total_fare  # Already calculated
        
        print(f"[Ride] Fare estimate: {estimate.breakdown()}")
        return estimate
    
    # ---- Book Ride ----
    
    def book_ride(self, rider_id: str, pickup: Location, dropoff: Location,
                  vehicle_type: VehicleType) -> Ride:
        """
        Ride book karo
        
        Steps:
        1. Rider check karo
        2. Already active ride? → reject
        3. Fare estimate calculate karo
        4. Ride create karo (SEARCHING state)
        5. Driver dhundo
        6. Assign karo ya NO_DRIVER_FOUND
        """
        with self._lock:
            # 1. Rider valid?
            rider = self._riders.get(rider_id)
            if not rider:
                raise ValueError(f"Rider {rider_id} not found")
            
            # 2. Active ride check
            if rider_id in self._active_rider_rides:
                existing = self._rides[self._active_rider_rides[rider_id]]
                raise ValueError(f"Active ride exists: {existing.ride_id} ({existing.status.value})")
            
            # 3. Fare estimate
            estimate = self.get_fare_estimate(pickup, dropoff, vehicle_type)
            
            # 4. Create ride
            ride = Ride(
                rider_id=rider_id,
                vehicle_type=vehicle_type,
                pickup=pickup,
                dropoff=dropoff,
                status=RideStatus.SEARCHING,
                fare_estimate=estimate,
                distance_km=pickup.distance_to(dropoff)
            )
            self._rides[ride.ride_id] = ride
            self._active_rider_rides[rider_id] = ride.ride_id
            
            print(f"\n[Ride] NEW RIDE: {ride.ride_id}")
            print(f"  Rider: {rider.name} | Vehicle: {vehicle_type.value}")
            print(f"  Pickup: {pickup.address} → Dropoff: {dropoff.address}")
            print(f"  Estimated fare: ₹{estimate.total_fare}")
            
            # 5. Driver dhundo
            driver = self.matching_service.find_best_driver(
                pickup, vehicle_type, rider.rating
            )
            
            if not driver:
                ride.status = RideStatus.NO_DRIVER_FOUND
                del self._active_rider_rides[rider_id]
                self.notifier.notify_cancellation(rider, CancellationReason.NO_DRIVER_FOUND)
                raise ValueError("No drivers available nearby. Try again in a few minutes.")
            
            # 6. Assign driver
            ride.driver_id = driver.driver_id
            ride.status = RideStatus.ACCEPTED
            ride.accepted_at = datetime.now()
            
            self.notifier.notify_driver_assigned(rider, driver, ride)
            
            return ride
    
    # ---- Ride Lifecycle ----
    
    def driver_arrived(self, ride_id: str) -> Ride:
        """Driver pickup pe pahunch gaya"""
        ride = self._get_active_ride(ride_id)
        ride.status = RideStatus.DRIVER_ARRIVING
        
        rider = self._riders[ride.rider_id]
        driver = self.driver_pool.get_driver(ride.driver_id)
        self.notifier.notify_driver_arrived(rider, driver)
        
        print(f"[Ride] {ride_id}: Driver arrived at pickup")
        return ride
    
    def start_ride(self, ride_id: str) -> Ride:
        """Rider baith gaya, ride shuru"""
        ride = self._get_active_ride(ride_id)
        ride.status = RideStatus.IN_PROGRESS
        ride.started_at = datetime.now()
        
        rider = self._riders[ride.rider_id]
        self.notifier.notify_ride_started(rider)
        
        print(f"[Ride] {ride_id}: Ride started!")
        return ride
    
    def complete_ride(self, ride_id: str, actual_distance_km: float = None) -> Ride:
        """
        Ride complete karo
        Actual distance pe final fare calculate karo
        """
        with self._lock:
            ride = self._get_active_ride(ride_id)
            ride.status = RideStatus.COMPLETED
            ride.completed_at = datetime.now()
            
            if actual_distance_km:
                ride.distance_km = actual_distance_km
            
            # Final fare calculate
            duration_min = (
                (ride.completed_at - ride.started_at).seconds / 60
                if ride.started_at else ride.distance_km / 0.5
            )
            
            strategy = StandardPricingStrategy()
            final_estimate = strategy.calculate_fare(
                ride.distance_km, duration_min,
                ride.vehicle_type,
                ride.fare_estimate.surge_multiplier
            )
            ride.actual_fare = final_estimate.total_fare
            
            # Driver status update
            driver = self.driver_pool.get_driver(ride.driver_id)
            driver.complete_ride(ride.dropoff)
            
            # Clean up active ride
            del self._active_rider_rides[ride.rider_id]
            
            rider = self._riders[ride.rider_id]
            self.notifier.notify_ride_completed(rider, ride.actual_fare)
            
            print(f"[Ride] {ride_id}: COMPLETED | "
                  f"Distance: {ride.distance_km:.2f}km | "
                  f"Fare: ₹{ride.actual_fare}")
            return ride
    
    def cancel_ride(self, ride_id: str, cancelled_by: str,
                    reason: CancellationReason) -> dict:
        """
        Ride cancel karo
        Cancellation fee logic:
        - Rider cancels after 3 min = ₹50 fee
        - Driver cancels = no fee + driver penalty
        """
        with self._lock:
            ride = self._get_active_ride(ride_id)
            ride.status = RideStatus.CANCELLED
            ride.cancellation_reason = reason
            
            cancellation_fee = 0.0
            
            if reason == CancellationReason.RIDER_CANCELLED:
                time_since_request = (datetime.now() - ride.requested_at).seconds
                if time_since_request > 180 and ride.driver_id:  # 3 min = 180 sec
                    cancellation_fee = 50.0
                    print(f"  [Ride] Cancellation fee: ₹{cancellation_fee}")
            
            # Driver free karo
            if ride.driver_id:
                driver = self.driver_pool.get_driver(ride.driver_id)
                if driver:
                    driver.status = DriverStatus.AVAILABLE
            
            # Active ride remove karo
            if ride.rider_id in self._active_rider_rides:
                del self._active_rider_rides[ride.rider_id]
            
            rider = self._riders[ride.rider_id]
            self.notifier.notify_cancellation(rider, reason)
            
            print(f"[Ride] {ride_id}: CANCELLED by {cancelled_by}")
            return {
                "ride_id": ride_id,
                "cancellation_fee": cancellation_fee,
                "reason": reason.value
            }
    
    # ---- Rating ----
    
    def rate_driver(self, ride_id: str, rating: float):
        """Rider ne driver ko rate kiya"""
        if not (1.0 <= rating <= 5.0):
            raise ValueError("Rating must be 1-5")
        
        ride = self._rides.get(ride_id)
        if not ride or ride.status != RideStatus.COMPLETED:
            raise ValueError("Can only rate completed rides")
        
        ride.driver_rating = rating
        driver = self.driver_pool.get_driver(ride.driver_id)
        
        # Moving average update
        driver.rating = (driver.rating * driver.total_rides + rating) / (driver.total_rides + 1)
        driver.rating = round(driver.rating, 2)
        
        # Auto-deactivate low-rated drivers
        if driver.rating < 3.5 and driver.total_rides > 50:
            driver.go_offline()
            print(f"  [Warning] Driver {driver.name} deactivated: rating {driver.rating}")
        
        print(f"[Ride] Driver {driver.name} rated {rating} stars. New avg: {driver.rating}")
    
    def get_ride_history(self, rider_id: str) -> List[Ride]:
        return [r for r in self._rides.values() if r.rider_id == rider_id]
    
    def _get_active_ride(self, ride_id: str) -> Ride:
        ride = self._rides.get(ride_id)
        if not ride:
            raise ValueError(f"Ride {ride_id} not found")
        if ride.status in [RideStatus.COMPLETED, RideStatus.CANCELLED]:
            raise ValueError(f"Ride {ride_id} is already {ride.status.value}")
        return ride

# ===== DEMO =====

def demo():
    print("=" * 60)
    print("RIDE BOOKING SYSTEM (UBER/OLA) DEMO")
    print("=" * 60)
    
    service = RideService()
    
    # --- Setup Drivers ---
    print("\n--- Driver Registration ---")
    swift = Vehicle(registration="MH12AB1234", vehicle_type=VehicleType.MINI,
                    model="Swift Dzire", color="White")
    honda = Vehicle(registration="MH01CD5678", vehicle_type=VehicleType.SEDAN,
                    model="Honda City", color="Silver")
    
    ramu = service.register_driver("Ramu Kumar", "+91-9111111111", swift)
    shyam = service.register_driver("Shyam Singh", "+91-9222222222", honda)
    
    # Drivers online ho gaye
    service.driver_go_online(ramu.driver_id, 19.0760, 72.8777)   # Mumbai central
    service.driver_go_online(shyam.driver_id, 19.0820, 72.8850)  # Nearby
    
    # --- Register Rider ---
    print("\n--- Rider Registration ---")
    ashish = service.register_rider("Ashish Kumar", "+91-9999999999", "ashish@email.com")
    
    # --- Fare Estimate ---
    print("\n--- Fare Estimate ---")
    pickup = Location(19.0760, 72.8777, "Dadar Station")
    dropoff = Location(19.1175, 72.9060, "Andheri East")
    
    estimate = service.get_fare_estimate(pickup, dropoff, VehicleType.MINI)
    
    # --- Book Ride ---
    print("\n--- Book Ride ---")
    try:
        ride = service.book_ride(ashish.rider_id, pickup, dropoff, VehicleType.MINI)
        
        # --- Ride Lifecycle ---
        print("\n--- Ride Lifecycle ---")
        time.sleep(0.1)
        service.driver_arrived(ride.ride_id)
        
        time.sleep(0.1)
        service.start_ride(ride.ride_id)
        
        time.sleep(0.1)
        completed_ride = service.complete_ride(ride.ride_id, actual_distance_km=12.5)
        
        # --- Rating ---
        print("\n--- Rating ---")
        service.rate_driver(ride.ride_id, rating=4.5)
        
        # --- Ride History ---
        print("\n--- Ride History ---")
        history = service.get_ride_history(ashish.rider_id)
        for r in history:
            print(f"  Ride: {r.ride_id} | Status: {r.status.value} | "
                  f"Fare: ₹{r.actual_fare} | Distance: {r.distance_km:.2f}km")
    
    except ValueError as e:
        print(f"Error: {e}")
    
    # --- Surge Pricing Demo ---
    print("\n--- Surge Pricing Demo ---")
    surge_calc = SurgeCalculator()
    for requests, drivers in [(5, 10), (10, 8), (15, 7), (20, 5)]:
        surge = surge_calc.calculate_surge(requests, drivers)
        print(f"  {requests} requests, {drivers} drivers → {surge}x surge")
    
    print("\n[Demo Complete]")

if __name__ == "__main__":
    demo()
```

### 1.5 Tumhara real project mein kahan use hua

**State Machine → Niroskos Booking:**
```python
# Booking lifecycle bilkul ride lifecycle jaisa
DRAFT → CONFIRMED → ALLOCATED → IN_TRANSIT → DELIVERED
# DRAFT = Ride REQUESTED
# CONFIRMED = Ride ACCEPTED  
# IN_TRANSIT = Ride IN_PROGRESS
# DELIVERED = Ride COMPLETED
```

**Pricing Strategy → Niroskos Package Pricing:**
```python
# Alag alag pricing strategies
class RegionalPricingStrategy:    # India vs Kenya
class SeasonalPricingStrategy:    # Peak season surcharge
class B2BPricingStrategy:         # Corporate discount
```

**Driver Location → GPS tracking:**
- Niroskos mein vehicle tracking tha — driver ka GPS update Redis mein store karte the (GEOADD)
- Nearby vehicle dhundna = GEORADIUS command

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definition

> Ride Booking System is a real-time matching platform connecting riders with available drivers using location-based search, dynamic pricing, and a state machine for ride lifecycle management. The core challenges are sub-second driver matching at scale, surge pricing based on real-time supply-demand, and concurrent request handling without double-assignment.

### 2.2 Key Design Decisions

| Decision | Option A | Option B (Chosen) | Why |
|----------|----------|-------------------|-----|
| Driver lookup | Full table scan | Geohash grid + Redis GEORADIUS | O(N) vs O(1) |
| Fare calculation | Fixed rates | Strategy pattern | Pluggable for airport/surge/promo |
| Driver assignment | Round robin | Min-cost scoring | Distance + rating + rider preference |
| Concurrency | DB optimistic lock | In-memory driver.accept_ride() lock | Lower latency |
| Surge calculation | Manual rule | Ratio-based (demand/supply) | Auto-adjusts to conditions |

### 2.3 Geohash-based Driver Matching

```
Geohash converts (lat, lon) to a string: 19.0760, 72.8777 → "te7uvw"
Adjacent cells share prefix: "te7uvx", "te7uvv" are neighbors

Lookup strategy:
1. Get rider's geohash (precision=6, ~1km cell)
2. Search rider's cell + 8 adjacent cells
3. Filter by: status=AVAILABLE, vehicle_type matches
4. Sort by actual distance
5. Return top 5

Why geohash over lat/lon range query?
- Range query: WHERE lat BETWEEN x AND y AND lon BETWEEN a AND b
  Problem: rectangular, not circular; needs compound index; doesn't work at poles
- Geohash: string prefix match on indexed column; portable; works globally
```

### 2.4 Concurrent Driver Assignment (Race Condition Fix)

```python
# Problem: Two rides request same driver simultaneously
# Thread A: find_best_driver() → returns driver D1 (AVAILABLE)
# Thread B: find_best_driver() → returns driver D1 (AVAILABLE) 
# Both assign D1 → driver gets two rides!

# Solution: driver.accept_ride() is atomic with a Lock
def accept_ride(self) -> bool:
    with self._lock:
        if self.status != DriverStatus.AVAILABLE:
            return False   # Already taken by another request
        self.status = DriverStatus.ON_TRIP
        return True

# In MatchingService:
for driver in scored_candidates:
    if driver.accept_ride():   # Only ONE thread succeeds
        return driver           # Stop searching
    # If False: continue to next candidate
```

### 2.5 Scoring Function

```
score = (distance_score × 0.5 + rating_score × 0.3) × rider_rating_factor

Components:
- distance_score = max(0, 10 - distance_km × 2)  → 0-10, closer = higher
- rating_score = driver.rating × 2               → 0-10 
- rider_rating_factor = rider.rating / 5.0       → 0-1 multiplier
  (drivers get lower score for low-rated riders → they're less likely to be matched)

Example:
Driver A: 1.5km away, rating 4.8 → distance=7, rating=9.6 → (7×0.5 + 9.6×0.3) × 0.96 = 6.1
Driver B: 0.8km away, rating 4.2 → distance=8.4, rating=8.4 → (8.4×0.5 + 8.4×0.3) × 0.96 = 6.5
→ Driver B wins (closer distance outweighs slight rating difference)
```

### 2.6 Real Project Answer

> "In my Niroskos project, we had a similar state machine for booking lifecycle — DRAFT through DELIVERED — with the same atomic state transition pattern. For location-based features, we stored driver GPS updates in Redis using GEOADD and used GEORADIUS for nearby queries, which is exactly the geohash concept. Our pricing strategy pattern handled multi-region pricing — Kenya pricing vs India pricing — by swapping strategy classes at runtime based on the tenant's region, very similar to how AirportPricingStrategy works here."

### 2.7 Common Follow-up Q&A

**Q1: How do you scale driver location updates (millions of drivers)?**
> "Redis Geospatial is the answer — O(log N) for GEOADD updates, O(log N + M) for GEORADIUS queries. At Uber's scale, they partition by city — each city has its own Redis instance. Drivers publish location every 4 seconds via WebSocket. A Kafka stream ingests location events and updates Redis. The dispatch service reads from Redis, not Kafka, for low-latency lookups."

**Q2: How do you handle driver cancellation mid-ride?**
> "Ride goes back to SEARCHING state, rider is notified, and immediate re-matching begins. The cancelled driver gets a strike. Three strikes in a day → driver suspended. The replacement driver gets priority scoring (rider already waited). If no driver found in 60 seconds → full refund + ₹50 compensation credit."

**Q3: How does surge pricing prevent abuse?**
> "Two protections: (1) Fare estimate is locked at booking time — rider accepts the surge price shown upfront. (2) Max surge cap at 2x prevents price gouging. In emergencies (natural disasters), Uber manually disables surge. We'd implement this as a feature flag: surge_enabled=False overrides the calculator to return 1.0."

**Q4: How would you implement ride splitting (shared rides)?**
> "SharedRide has multiple RiderSlots. Each slot has a pickup/dropoff. Route optimization (TSP variant) finds the optimal pickup order. Fare is split proportionally by distance traveled by each rider. The key change: MatchingService allows capacity > 1 drivers (SUV/van) and schedules multiple pickups as stops on a route."

---

## Interview Cheat Sheet

```
30-second pitch:
"Uber-type system: Rider books ride → MatchingService finds nearby drivers
using Geohash grid (O(1) lookup) → score by distance + rating → 
driver.accept_ride() is atomic (prevents double-assignment) →
State machine: REQUESTED → ACCEPTED → IN_PROGRESS → COMPLETED.
Pricing uses Strategy pattern: Standard vs Airport vs Surge.
Surge = demand/supply ratio → up to 2x multiplier."

Key patterns:
- State Machine (ride lifecycle transitions)
- Strategy (pricing: standard/airport/surge)
- Observer (notifications at each state change)
- Facade (RideService hides matching, pricing, notification)

Scaling considerations (mention these):
- Redis GEORADIUS for driver lookup
- Kafka for location event ingestion
- City-level Redis partitioning
- WebSocket for real-time driver tracking
```
