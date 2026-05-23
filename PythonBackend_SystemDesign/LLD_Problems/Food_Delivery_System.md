# Food Delivery System (Swiggy/Zomato) LLD

## Quick Reference Card
```
Pattern Used    → State Machine (order lifecycle), Strategy (delivery partner assign), Observer (tracking)
Core Challenge  → Multi-actor coordination (Customer→Restaurant→Delivery), ETA calculation
Key Classes     → Order, MenuItem, Restaurant, DeliveryPartner, OrderService
State Machine   → PLACED → CONFIRMED → PREPARING → READY → PICKED_UP → DELIVERED
Interview Hook  → "3 actors ka coordination: restaurant accepts, kitchen prepares, partner picks up"
```

---

## PART 1: HINGLISH — Samjhne ke liye

### 1.1 Kya hai?

Swiggy/Zomato mein 3 actors hain ek order mein:
1. **Customer** — khana order karta hai
2. **Restaurant** — order accept + prepare karta hai
3. **Delivery Partner** — ready food pick up + deliver karta hai

**Tricky part:** Teen alag workflows simultaneously chal rahe hain:
- Kitchen ka timer (preparation time)
- Partner assignment (restaurant ke paas kaun sabse paas hai?)
- Customer ka order tracking (real-time status)

**Key difference from Uber:**
- Uber: Driver + Rider directly  
- Food: Restaurant → Delivery Partner → Customer (3-way coordination)
- Order ke saath cart/items bhi hain (menu, pricing, discounts)
- Preparation time unknown → ETA dynamic hai

### 1.2 Code

```python
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import threading
import uuid
import time

# ===== ENUMS =====

class OrderStatus(Enum):
    CART = "CART"               # Still adding items
    PLACED = "PLACED"           # Payment done, sent to restaurant
    CONFIRMED = "CONFIRMED"     # Restaurant ne accept kiya
    PREPARING = "PREPARING"     # Kitchen mein ban raha hai
    READY = "READY"             # Packaging done, partner ka wait
    PICKED_UP = "PICKED_UP"     # Partner ne pick kiya
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"       # Restaurant ne reject kiya

class PaymentStatus(Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    REFUNDED = "REFUNDED"
    FAILED = "FAILED"

class PartnerStatus(Enum):
    OFFLINE = "OFFLINE"
    AVAILABLE = "AVAILABLE"
    ON_DELIVERY = "ON_DELIVERY"

class CuisineType(Enum):
    INDIAN = "INDIAN"
    CHINESE = "CHINESE"
    ITALIAN = "ITALIAN"
    FAST_FOOD = "FAST_FOOD"
    DESSERTS = "DESSERTS"

# ===== LOCATION =====

@dataclass
class Location:
    latitude: float
    longitude: float
    address: str = ""
    
    def distance_to(self, other: 'Location') -> float:
        """Simplified distance in km"""
        import math
        R = 6371
        lat1, lon1 = math.radians(self.latitude), math.radians(self.longitude)
        lat2, lon2 = math.radians(other.latitude), math.radians(other.longitude)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
        return R * 2 * math.asin(math.sqrt(a))

# ===== MENU =====

@dataclass
class Category:
    category_id: str = field(default_factory=lambda: str(uuid.uuid4())[:6])
    name: str = ""             # "Starters", "Main Course", "Desserts"
    display_order: int = 0

@dataclass
class MenuItem:
    item_id: str = field(default_factory=lambda: f"I{str(uuid.uuid4())[:6].upper()}")
    name: str = ""
    description: str = ""
    price: float = 0.0
    category: str = ""
    is_veg: bool = True
    is_available: bool = True
    preparation_time_min: int = 15   # Average prep time
    calories: Optional[int] = None
    
    def __hash__(self):
        return hash(self.item_id)

@dataclass
class CartItem:
    menu_item: MenuItem
    quantity: int = 1
    special_instructions: str = ""
    
    @property
    def subtotal(self) -> float:
        return self.menu_item.price * self.quantity

# ===== RESTAURANT =====

@dataclass
class Restaurant:
    restaurant_id: str = field(default_factory=lambda: f"RST{str(uuid.uuid4())[:6].upper()}")
    name: str = ""
    cuisine_types: List[CuisineType] = field(default_factory=list)
    location: Location = None
    rating: float = 4.0
    min_order: float = 100.0
    delivery_radius_km: float = 5.0
    avg_preparation_time_min: int = 30
    is_open: bool = True
    menu: Dict[str, MenuItem] = field(default_factory=dict)
    
    def add_menu_item(self, item: MenuItem):
        self.menu[item.item_id] = item
    
    def get_item(self, item_id: str) -> Optional[MenuItem]:
        return self.menu.get(item_id)
    
    def is_within_delivery_range(self, customer_location: Location) -> bool:
        return self.location.distance_to(customer_location) <= self.delivery_radius_km

# ===== CUSTOMER =====

@dataclass
class Customer:
    customer_id: str = field(default_factory=lambda: f"C{str(uuid.uuid4())[:6].upper()}")
    name: str = ""
    phone: str = ""
    email: str = ""
    saved_addresses: List[Location] = field(default_factory=list)
    wallet_balance: float = 0.0
    
    def add_address(self, location: Location):
        self.saved_addresses.append(location)

# ===== DELIVERY PARTNER =====

@dataclass
class DeliveryPartner:
    partner_id: str = field(default_factory=lambda: f"DP{str(uuid.uuid4())[:6].upper()}")
    name: str = ""
    phone: str = ""
    rating: float = 4.5
    current_location: Location = None
    status: PartnerStatus = PartnerStatus.OFFLINE
    vehicle_type: str = "BIKE"
    total_deliveries: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False, compare=False)
    
    def go_online(self, location: Location):
        with self._lock:
            self.current_location = location
            self.status = PartnerStatus.AVAILABLE
    
    def assign_order(self) -> bool:
        """Atomic: ek hi order mila at a time"""
        with self._lock:
            if self.status != PartnerStatus.AVAILABLE:
                return False
            self.status = PartnerStatus.ON_DELIVERY
            return True
    
    def complete_delivery(self, location: Location):
        with self._lock:
            self.current_location = location
            self.status = PartnerStatus.AVAILABLE
            self.total_deliveries += 1

# ===== ORDER =====

@dataclass
class Order:
    order_id: str = field(default_factory=lambda: f"ORD{str(uuid.uuid4())[:8].upper()}")
    customer_id: str = ""
    restaurant_id: str = ""
    items: List[CartItem] = field(default_factory=list)
    delivery_address: Location = None
    status: OrderStatus = OrderStatus.PLACED
    payment_status: PaymentStatus = PaymentStatus.PENDING
    partner_id: Optional[str] = None
    
    # Pricing
    items_total: float = 0.0
    delivery_fee: float = 30.0
    platform_fee: float = 5.0
    taxes: float = 0.0
    discount: float = 0.0
    total_amount: float = 0.0
    
    # Timing
    placed_at: datetime = field(default_factory=datetime.now)
    confirmed_at: Optional[datetime] = None
    ready_at: Optional[datetime] = None
    picked_up_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    estimated_delivery_at: Optional[datetime] = None
    
    # Tracking
    customer_rating: Optional[float] = None
    partner_rating: Optional[float] = None
    
    def calculate_totals(self):
        self.items_total = sum(item.subtotal for item in self.items)
        self.taxes = round(self.items_total * 0.05, 2)  # 5% GST
        self.total_amount = (
            self.items_total + self.delivery_fee + self.platform_fee +
            self.taxes - self.discount
        )
    
    def max_prep_time(self) -> int:
        """Sabse zyada time lene wale item ka time → overall prep time"""
        if not self.items:
            return 30
        return max(item.menu_item.preparation_time_min for item in self.items)
    
    def estimated_delivery_time(self, restaurant: Restaurant, delivery_address: Location) -> int:
        """
        Total delivery time = prep time + travel time
        prep time = max of all items' prep times
        travel time = distance / avg speed (20 km/h city driving)
        """
        prep_time = self.max_prep_time()
        distance = restaurant.location.distance_to(delivery_address)
        travel_time = int(distance / 20 * 60)  # minutes
        buffer = 5  # Buffer
        return prep_time + travel_time + buffer

# ===== PRICING SERVICE =====

class PricingService:
    """
    Dynamic delivery fee calculation
    """
    
    BASE_DELIVERY_FEE = 30.0
    FREE_DELIVERY_THRESHOLD = 299.0  # Orders above ₹299 = free delivery
    RAIN_SURCHARGE = 20.0
    
    def calculate_delivery_fee(self, distance_km: float, items_total: float,
                                is_raining: bool = False) -> float:
        if items_total >= self.FREE_DELIVERY_THRESHOLD:
            return 0.0
        
        fee = self.BASE_DELIVERY_FEE
        
        # Distance surcharge (> 3km)
        if distance_km > 3:
            fee += (distance_km - 3) * 5  # ₹5 per km after 3km
        
        if is_raining:
            fee += self.RAIN_SURCHARGE
        
        return round(min(fee, 100.0), 2)  # Max ₹100 delivery fee

# ===== DISCOUNT SERVICE =====

class DiscountService:
    """
    Coupon + offer management
    
    Real Swiggy: ML-based personalized offers
    Yahan: simple rule-based
    """
    
    _coupons = {
        "FIRST50": {"type": "PERCENTAGE", "value": 50, "max_discount": 100, "min_order": 150},
        "FLAT100": {"type": "FLAT", "value": 100, "min_order": 300},
        "FREE_DELIVERY": {"type": "DELIVERY", "value": 0, "min_order": 0},
    }
    
    def apply_coupon(self, code: str, order_total: float, delivery_fee: float) -> float:
        coupon = self._coupons.get(code.upper())
        if not coupon:
            raise ValueError(f"Invalid coupon: {code}")
        
        if order_total < coupon["min_order"]:
            raise ValueError(f"Minimum order ₹{coupon['min_order']} required")
        
        if coupon["type"] == "PERCENTAGE":
            discount = order_total * coupon["value"] / 100
            return min(discount, coupon.get("max_discount", discount))
        elif coupon["type"] == "FLAT":
            return min(coupon["value"], order_total)
        elif coupon["type"] == "DELIVERY":
            return delivery_fee
        
        return 0.0

# ===== DELIVERY ASSIGNMENT SERVICE =====

class DeliveryAssignmentService:
    """
    Best delivery partner assign karo
    
    Strategy: Restaurant ke paas available partner dhundo
    Score = f(distance_from_restaurant, rating, current_load)
    """
    
    SEARCH_RADIUS_KM = 3.0
    
    def __init__(self):
        self._partners: Dict[str, DeliveryPartner] = {}
    
    def register_partner(self, partner: DeliveryPartner):
        self._partners[partner.partner_id] = partner
    
    def update_location(self, partner_id: str, location: Location):
        partner = self._partners.get(partner_id)
        if partner:
            partner.current_location = location
    
    def assign_partner(self, restaurant_location: Location) -> Optional[DeliveryPartner]:
        """
        Nearby available partner dhundo + assign karo
        """
        candidates = []
        
        for partner in self._partners.values():
            if (partner.status == PartnerStatus.AVAILABLE and
                    partner.current_location):
                distance = restaurant_location.distance_to(partner.current_location)
                if distance <= self.SEARCH_RADIUS_KM:
                    score = self._score_partner(partner, distance)
                    candidates.append((score, partner))
        
        if not candidates:
            return None
        
        # Best partner
        candidates.sort(key=lambda x: x[0], reverse=True)
        
        for score, partner in candidates:
            if partner.assign_order():  # Atomic assignment
                print(f"  [Delivery] Partner {partner.name} assigned "
                      f"(score: {score:.2f})")
                return partner
        
        return None
    
    def get_partner(self, partner_id: str) -> Optional[DeliveryPartner]:
        return self._partners.get(partner_id)
    
    def _score_partner(self, partner: DeliveryPartner, distance: float) -> float:
        distance_score = max(0, 10 - distance * 3)    # Closer = better
        rating_score = partner.rating * 2              # Higher rating = better
        return distance_score * 0.6 + rating_score * 0.4

# ===== NOTIFICATION SERVICE =====

class FoodNotificationService:
    """Order state change pe notifications"""
    
    def on_order_confirmed(self, customer: Customer, order: Order, eta_min: int):
        print(f"  [Push → {customer.name}] Order confirmed! ETA: {eta_min} min.")
    
    def on_preparing(self, customer: Customer, order: Order):
        print(f"  [Push → {customer.name}] {order.restaurant_id} is preparing your order!")
    
    def on_partner_assigned(self, customer: Customer, partner: DeliveryPartner):
        print(f"  [Push → {customer.name}] {partner.name} will deliver your order. "
              f"Phone: {partner.phone}")
    
    def on_picked_up(self, customer: Customer, order: Order):
        print(f"  [Push → {customer.name}] Your order is on the way!")
    
    def on_delivered(self, customer: Customer, order: Order):
        print(f"  [Push → {customer.name}] Delivered! Rate your experience.")
    
    def on_cancelled(self, customer: Customer, reason: str):
        print(f"  [Push → {customer.name}] Order cancelled: {reason}")
    
    def notify_restaurant(self, restaurant: Restaurant, order: Order):
        print(f"  [Restaurant Alert] New order #{order.order_id} received! "
              f"Items: {len(order.items)}")

# ===== ORDER SERVICE (Facade) =====

class OrderService:
    """
    Main service — food ordering ka pura flow
    
    Business Rules:
    - Minimum order amount check
    - Restaurant delivery radius check
    - Payment before order confirmation
    - Auto-cancel if restaurant doesn't respond in 3 min
    - Auto-refund on cancellation
    """
    
    def __init__(self):
        self._restaurants: Dict[str, Restaurant] = {}
        self._customers: Dict[str, Customer] = {}
        self._orders: Dict[str, Order] = {}
        
        self.delivery_service = DeliveryAssignmentService()
        self.pricing_service = PricingService()
        self.discount_service = DiscountService()
        self.notifier = FoodNotificationService()
        
        self._lock = threading.RLock()
    
    # ---- Setup ----
    
    def register_restaurant(self, restaurant: Restaurant) -> Restaurant:
        self._restaurants[restaurant.restaurant_id] = restaurant
        print(f"[Food] Restaurant registered: {restaurant.name}")
        return restaurant
    
    def register_customer(self, name: str, phone: str, email: str) -> Customer:
        customer = Customer(name=name, phone=phone, email=email)
        self._customers[customer.customer_id] = customer
        return customer
    
    # ---- Menu / Search ----
    
    def search_restaurants(self, customer_location: Location,
                           cuisine: Optional[CuisineType] = None,
                           min_rating: float = 3.0) -> List[Restaurant]:
        """
        Customer ke location pe delivery karne wale restaurants
        """
        results = []
        for restaurant in self._restaurants.values():
            if (restaurant.is_open and
                    restaurant.is_within_delivery_range(customer_location) and
                    restaurant.rating >= min_rating):
                if cuisine is None or cuisine in restaurant.cuisine_types:
                    results.append(restaurant)
        
        # Rating se sort karo
        results.sort(key=lambda r: r.rating, reverse=True)
        print(f"[Food] Found {len(results)} restaurants for cuisine={cuisine}")
        return results
    
    def get_menu(self, restaurant_id: str) -> List[MenuItem]:
        restaurant = self._restaurants.get(restaurant_id)
        if not restaurant:
            raise ValueError(f"Restaurant {restaurant_id} not found")
        return [item for item in restaurant.menu.values() if item.is_available]
    
    # ---- Cart + Order ----
    
    def create_order(self, customer_id: str, restaurant_id: str,
                     delivery_address: Location) -> Order:
        """Create empty order (cart)"""
        customer = self._customers.get(customer_id)
        restaurant = self._restaurants.get(restaurant_id)
        
        if not customer or not restaurant:
            raise ValueError("Invalid customer or restaurant")
        
        if not restaurant.is_within_delivery_range(delivery_address):
            raise ValueError(f"Delivery address out of range ({restaurant.delivery_radius_km}km)")
        
        order = Order(
            customer_id=customer_id,
            restaurant_id=restaurant_id,
            delivery_address=delivery_address,
            status=OrderStatus.CART
        )
        self._orders[order.order_id] = order
        return order
    
    def add_item(self, order_id: str, item_id: str, quantity: int = 1,
                 special_instructions: str = "") -> Order:
        """Cart mein item add karo"""
        order = self._orders.get(order_id)
        if not order or order.status != OrderStatus.CART:
            raise ValueError("Order not in cart state")
        
        restaurant = self._restaurants[order.restaurant_id]
        item = restaurant.get_item(item_id)
        
        if not item:
            raise ValueError(f"Item {item_id} not found")
        if not item.is_available:
            raise ValueError(f"{item.name} is currently unavailable")
        
        # Check if already in cart
        existing = next((ci for ci in order.items if ci.menu_item.item_id == item_id), None)
        if existing:
            existing.quantity += quantity
        else:
            order.items.append(CartItem(
                menu_item=item,
                quantity=quantity,
                special_instructions=special_instructions
            ))
        
        order.calculate_totals()
        return order
    
    def apply_coupon(self, order_id: str, coupon_code: str) -> Order:
        order = self._orders.get(order_id)
        if not order:
            raise ValueError(f"Order {order_id} not found")
        
        discount = self.discount_service.apply_coupon(
            coupon_code, order.items_total, order.delivery_fee
        )
        order.discount = discount
        order.calculate_totals()
        print(f"[Food] Coupon {coupon_code} applied: ₹{discount} discount")
        return order
    
    def place_order(self, order_id: str, payment_method: str = "UPI",
                    coupon_code: str = None) -> Order:
        """
        Order place karo (payment + send to restaurant)
        
        Steps:
        1. Cart validate karo (items, min order)
        2. Delivery fee calculate karo
        3. Coupon apply karo (if any)
        4. Payment process karo
        5. Restaurant ko send karo
        6. Delivery partner queue mein dalo (ready hone pe assign)
        7. ETA calculate + customer notify karo
        """
        with self._lock:
            order = self._orders.get(order_id)
            if not order:
                raise ValueError(f"Order {order_id} not found")
            if order.status != OrderStatus.CART:
                raise ValueError("Order already placed")
            
            customer = self._customers[order.customer_id]
            restaurant = self._restaurants[order.restaurant_id]
            
            # 1. Validate
            if not order.items:
                raise ValueError("Cart is empty")
            
            order.calculate_totals()
            
            if order.items_total < restaurant.min_order:
                raise ValueError(f"Minimum order ₹{restaurant.min_order} required")
            
            # 2. Delivery fee
            distance = restaurant.location.distance_to(order.delivery_address)
            order.delivery_fee = self.pricing_service.calculate_delivery_fee(
                distance, order.items_total
            )
            
            # 3. Coupon
            if coupon_code:
                try:
                    self.apply_coupon(order_id, coupon_code)
                except ValueError as e:
                    print(f"  [Food] Coupon failed: {e}")
            
            order.calculate_totals()
            
            # 4. Payment (simplified)
            print(f"  [Payment] Processing ₹{order.total_amount} via {payment_method}...")
            order.payment_status = PaymentStatus.PAID
            
            # 5. Status update
            order.status = OrderStatus.PLACED
            
            # 6. ETA
            eta_min = order.estimated_delivery_time(restaurant, order.delivery_address)
            order.estimated_delivery_at = datetime.now() + timedelta(minutes=eta_min)
            
            # 7. Notify
            self.notifier.notify_restaurant(restaurant, order)
            self.notifier.on_order_confirmed(customer, order, eta_min)
            
            print(f"\n[Food] ORDER PLACED: {order.order_id}")
            print(f"  Customer: {customer.name} | Restaurant: {restaurant.name}")
            print(f"  Items: {len(order.items)} | Total: ₹{order.total_amount}")
            print(f"  ETA: {eta_min} min")
            
            return order
    
    # ---- Restaurant Side ----
    
    def restaurant_confirm(self, order_id: str, prep_time_min: int = None) -> Order:
        """Restaurant ne order accept kiya"""
        order = self._orders[order_id]
        order.status = OrderStatus.CONFIRMED
        order.confirmed_at = datetime.now()
        
        if prep_time_min:
            order.estimated_delivery_at = datetime.now() + timedelta(minutes=prep_time_min + 15)
        
        customer = self._customers[order.customer_id]
        restaurant = self._restaurants[order.restaurant_id]
        self.notifier.on_preparing(customer, order)
        
        # Delivery partner ko queue karo
        # (assign hoga jab food ready hoga)
        print(f"[Food] {order_id}: Restaurant confirmed, kitchen started")
        return order
    
    def mark_food_ready(self, order_id: str) -> Order:
        """
        Khana ready hai, ab delivery partner assign karo
        """
        order = self._orders[order_id]
        order.status = OrderStatus.READY
        order.ready_at = datetime.now()
        
        restaurant = self._restaurants[order.restaurant_id]
        customer = self._customers[order.customer_id]
        
        print(f"[Food] {order_id}: Food ready! Finding delivery partner...")
        
        # NOW assign delivery partner
        partner = self.delivery_service.assign_partner(restaurant.location)
        
        if not partner:
            print(f"  [Food] No delivery partner available! Retrying in 60 seconds...")
            # Real: retry queue, ops alert
        else:
            order.partner_id = partner.partner_id
            self.notifier.on_partner_assigned(customer, partner)
        
        return order
    
    # ---- Delivery Side ----
    
    def partner_picked_up(self, order_id: str) -> Order:
        """Partner ne restaurant se khana uthaya"""
        order = self._orders[order_id]
        order.status = OrderStatus.PICKED_UP
        order.picked_up_at = datetime.now()
        
        customer = self._customers[order.customer_id]
        self.notifier.on_picked_up(customer, order)
        
        print(f"[Food] {order_id}: Picked up by partner, heading to customer")
        return order
    
    def mark_delivered(self, order_id: str) -> Order:
        """Delivery complete"""
        with self._lock:
            order = self._orders[order_id]
            order.status = OrderStatus.DELIVERED
            order.delivered_at = datetime.now()
            
            # Partner free karo
            partner = self.delivery_service.get_partner(order.partner_id)
            if partner:
                delivery_location = order.delivery_address
                partner.complete_delivery(delivery_location)
            
            customer = self._customers[order.customer_id]
            self.notifier.on_delivered(customer, order)
            
            # Actual delivery time vs estimated
            if order.placed_at and order.delivered_at:
                actual_min = int((order.delivered_at - order.placed_at).seconds / 60)
                print(f"[Food] {order_id}: DELIVERED in {actual_min} min")
            
            return order
    
    # ---- Cancellation ----
    
    def cancel_order(self, order_id: str, reason: str, cancelled_by: str) -> dict:
        """
        Cancellation + refund logic:
        - Before CONFIRMED → full refund
        - After CONFIRMED but before PREPARING → ₹20 cancellation fee
        - After PREPARING → no cancellation (food being made)
        """
        with self._lock:
            order = self._orders.get(order_id)
            if not order:
                raise ValueError(f"Order {order_id} not found")
            
            non_cancellable = [OrderStatus.PREPARING, OrderStatus.READY,
                               OrderStatus.PICKED_UP, OrderStatus.OUT_FOR_DELIVERY,
                               OrderStatus.DELIVERED]
            
            if order.status in non_cancellable:
                raise ValueError(f"Cannot cancel order in {order.status.value} state")
            
            # Cancellation fee calculation
            cancellation_fee = 0.0
            if order.status == OrderStatus.CONFIRMED:
                cancellation_fee = 20.0
            
            refund_amount = order.total_amount - cancellation_fee
            
            order.status = OrderStatus.CANCELLED
            order.payment_status = PaymentStatus.REFUNDED
            
            # Partner free karo agar assigned tha
            if order.partner_id:
                partner = self.delivery_service.get_partner(order.partner_id)
                if partner:
                    partner.status = PartnerStatus.AVAILABLE
            
            customer = self._customers[order.customer_id]
            self.notifier.on_cancelled(customer, reason)
            
            print(f"[Food] {order_id}: CANCELLED | "
                  f"Refund: ₹{refund_amount} | Fee: ₹{cancellation_fee}")
            
            return {
                "order_id": order_id,
                "refund_amount": refund_amount,
                "cancellation_fee": cancellation_fee
            }
    
    # ---- Rating ----
    
    def rate_order(self, order_id: str, food_rating: float,
                   delivery_rating: float, review: str = "") -> None:
        order = self._orders.get(order_id)
        if not order or order.status != OrderStatus.DELIVERED:
            raise ValueError("Can only rate delivered orders")
        
        order.customer_rating = food_rating
        order.partner_rating = delivery_rating
        
        # Update partner rating
        if order.partner_id:
            partner = self.delivery_service.get_partner(order.partner_id)
            if partner:
                partner.rating = (partner.rating * partner.total_deliveries + delivery_rating) / (partner.total_deliveries + 1)
        
        print(f"[Food] Rating saved: Food={food_rating}, Delivery={delivery_rating}")

# ===== DEMO =====

def demo():
    print("=" * 60)
    print("FOOD DELIVERY SYSTEM DEMO")
    print("=" * 60)
    
    service = OrderService()
    
    # --- Restaurant Setup ---
    print("\n--- Restaurant Setup ---")
    biryani_house = Restaurant(
        name="Biryani House",
        cuisine_types=[CuisineType.INDIAN],
        location=Location(19.0760, 72.8777, "Dadar"),
        rating=4.3,
        min_order=200.0,
        avg_preparation_time_min=25
    )
    
    # Menu items
    biryani = MenuItem(name="Chicken Biryani", price=280.0, is_veg=False,
                       preparation_time_min=25, category="Main Course")
    dal = MenuItem(name="Dal Makhani", price=180.0, is_veg=True,
                   preparation_time_min=20, category="Main Course")
    gulab = MenuItem(name="Gulab Jamun", price=80.0, is_veg=True,
                     preparation_time_min=5, category="Desserts")
    
    biryani_house.add_menu_item(biryani)
    biryani_house.add_menu_item(dal)
    biryani_house.add_menu_item(gulab)
    
    service.register_restaurant(biryani_house)
    
    # --- Delivery Partner ---
    print("\n--- Delivery Partner Setup ---")
    raju = service.delivery_service.register_partner.__func__ if False else None
    partner = DeliveryPartner(name="Raju Delivery", phone="+91-8111111111")
    partner.go_online(Location(19.0780, 72.8790, "Near Restaurant"))
    service.delivery_service.register_partner(partner)
    print(f"[Food] Partner {partner.name} is online")
    
    # --- Customer ---
    print("\n--- Customer Registration ---")
    ashish = service.register_customer("Ashish Kumar", "+91-9999999999", "ashish@email.com")
    delivery_addr = Location(19.0900, 72.8850, "Matunga East")
    
    # --- Search ---
    print("\n--- Search Restaurants ---")
    restaurants = service.search_restaurants(delivery_addr, CuisineType.INDIAN)
    for r in restaurants:
        print(f"  {r.name} | Rating: {r.rating} | Min: ₹{r.min_order}")
    
    # --- Menu ---
    print("\n--- Menu ---")
    menu = service.get_menu(biryani_house.restaurant_id)
    for item in menu:
        veg = "🥦" if item.is_veg else "🍗"
        print(f"  {veg} {item.name} — ₹{item.price} ({item.preparation_time_min} min)")
    
    # --- Create Order + Add Items ---
    print("\n--- Create Order ---")
    order = service.create_order(ashish.customer_id, biryani_house.restaurant_id, delivery_addr)
    
    service.add_item(order.order_id, biryani.item_id, quantity=1)
    service.add_item(order.order_id, gulab.item_id, quantity=2)
    
    print(f"  Cart: {[(ci.menu_item.name, ci.quantity) for ci in order.items]}")
    print(f"  Subtotal: ₹{order.items_total}")
    
    # --- Apply Coupon ---
    try:
        service.apply_coupon(order.order_id, "FLAT100")
    except ValueError as e:
        print(f"  Coupon failed: {e}")
    
    # --- Place Order ---
    print("\n--- Place Order ---")
    placed = service.place_order(order.order_id, payment_method="UPI")
    
    # --- Restaurant Confirms ---
    print("\n--- Restaurant Lifecycle ---")
    service.restaurant_confirm(order.order_id, prep_time_min=25)
    
    # Food ready
    service.mark_food_ready(order.order_id)
    
    # Partner picks up
    service.partner_picked_up(order.order_id)
    
    # Delivered!
    service.mark_delivered(order.order_id)
    
    # --- Rate ---
    print("\n--- Rating ---")
    service.rate_order(order.order_id, food_rating=4.5, delivery_rating=5.0,
                       review="Great biryani!")
    
    # --- Cancel Demo ---
    print("\n--- Cancellation Demo ---")
    order2 = service.create_order(ashish.customer_id, biryani_house.restaurant_id, delivery_addr)
    service.add_item(order2.order_id, dal.item_id, quantity=1)
    service.add_item(order2.order_id, biryani.item_id, quantity=1)
    service.place_order(order2.order_id)
    
    result = service.cancel_order(order2.order_id, "Changed my mind", "customer")
    print(f"  Cancellation result: {result}")
    
    print("\n[Demo Complete]")

if __name__ == "__main__":
    demo()
```

### 1.5 Tumhara real project mein kahan use hua

**Niroskos Package Booking ↔ Food Order:**
- Package booking ka `DRAFT → CONFIRMED → ALLOCATED` = Food ka `CART → PLACED → CONFIRMED`
- Payment pehle, phir service confirm karta hai = Dono same pattern
- Multi-party coordination (Subsidiary, Customer, Driver) = Restaurant, Customer, Partner
- ETA calculation = Niroskos departure time + buffer

---

## PART 2: ENGLISH — Interviewer ko bolne ke liye

### 2.1 Definition

> Food Delivery System coordinates three actors — Customer, Restaurant, and Delivery Partner — through a shared Order state machine. Unlike ride-hailing (direct assignment), food delivery has an intermediate preparation phase. Delivery partner assignment is deferred until food is ready (not at order placement), optimizing partner utilization.

### 2.2 Key Design: Why Assign Partner LATE?

```
Naive approach: Assign delivery partner when order is placed
Problem: Partner waits at restaurant for 25-30 min (prep time)
         Partner "blocked" — can't take other deliveries

Better approach: Assign partner when food is READY
Benefit: Partner is free for other deliveries during prep time
         Better partner utilization
         No waiting at restaurant

Implementation:
place_order() → Restaurant notified
restaurant_confirm() → Kitchen starts
mark_food_ready() → NOW find + assign partner
partner_picked_up() → Heading to customer
mark_delivered() → Partner free for next order
```

### 2.3 State Transition Diagram

```
CART ──(place_order)──→ PLACED ──(restaurant_confirm)──→ CONFIRMED
                                                              │
                                                    (kitchen starts)
                                                              ↓
                                                        PREPARING
                                                              │
                                                    (mark_food_ready)
                                                              ↓
                                                           READY ──(assign partner)
                                                              │
                                                    (partner_picked_up)
                                                              ↓
                                                         PICKED_UP
                                                              │
                                                    (mark_delivered)
                                                              ↓
                                                         DELIVERED

Any state before PREPARING → CANCELLED (with refund logic)
```

### 2.4 ETA Calculation

```python
def estimated_delivery_time(order, restaurant, delivery_address) -> int:
    prep_time = max(item.preparation_time_min for item in order.items)
    distance_km = restaurant.location.distance_to(delivery_address)
    travel_time_min = int(distance_km / 20 * 60)   # 20 km/h avg city speed
    buffer = 5
    return prep_time + travel_time_min + buffer

# Example: Biryani (25 min prep) + 3km distance (9 min travel) + 5 buffer = 39 min
# Displayed as: "35-45 min"
```

### 2.5 Real Project Answer

> "In Niroskos, the booking lifecycle is structurally identical to a food order. A booking goes DRAFT → CONFIRMED → ALLOCATED → IN_TRANSIT → DELIVERED. The 'restaurant accept' step maps to our subsidiary confirming availability. The 'delivery partner assignment' maps to our driver allocation — we also defer driver assignment until the pickup date approaches, not at booking time. The multi-actor coordination — customer waits, subsidiary prepares, driver delivers — is the same 3-party model."

### 2.6 Common Follow-up Q&A

**Q1: How do you handle restaurant rejection?**
> "Order goes to REJECTED state. Customer gets immediate notification with full refund. The system also flags the restaurant if rejection rate > 10% in a day — too many rejections hurt customer experience. Alternative: auto-suggest similar nearby restaurants in the rejection notification."

**Q2: How do you handle delivery partner going offline mid-delivery?**
> "Heartbeat timeout: if partner hasn't updated GPS for 5 minutes and order is PICKED_UP, trigger alert. Try to contact partner. If unreachable after 2 minutes, flag the order as at-risk, notify ops team. Customer gets proactive message. If partner confirmed lost, re-dispatch to new partner (rare — food quality concern). Full refund regardless."

**Q3: How would you implement live order tracking?**
> "WebSocket connection from customer app to tracking server. Partner app sends GPS every 5 seconds via REST POST. Tracking server stores in Redis (per order_id: location). WebSocket server pushes to connected customer. Architecture: Partner → REST API → Redis → WebSocket Server → Customer App. At scale: Kafka between REST and WebSocket for fan-out to multiple customers tracking same order."

**Q4: How do you handle the menu across thousands of restaurants?**
> "Database: restaurants table → menu_categories table → menu_items table. Caching: Redis cache per restaurant_id for menu (TTL 30 min). On menu update, invalidate cache. CDN for food images. Menu search uses Elasticsearch — full text on item name and description. Restaurant search uses PostGIS for geo queries — `WHERE ST_DWithin(location, customer_point, radius_meters)`."

---

## Interview Cheat Sheet

```
30-second pitch:
"Food delivery coordinates 3 actors: Customer, Restaurant, Delivery Partner.
Key insight: assign delivery partner when food is READY (not at order placement)
— this frees partners during prep time. State machine: CART → PLACED → 
CONFIRMED → PREPARING → READY → PICKED_UP → DELIVERED.
Delivery fee = base + distance surcharge - promo discount.
ETA = prep time + travel time + buffer."

Key patterns:
- State Machine (order lifecycle — 8 states)
- Strategy (pricing: standard/rain/free delivery threshold)
- Observer (customer notifications at every state change)
- Facade (OrderService hides all coordination complexity)

Scaling considerations:
- Redis for restaurant menu caching
- PostGIS for restaurant search
- WebSocket for live order tracking
- Kafka for partner location streaming
```
