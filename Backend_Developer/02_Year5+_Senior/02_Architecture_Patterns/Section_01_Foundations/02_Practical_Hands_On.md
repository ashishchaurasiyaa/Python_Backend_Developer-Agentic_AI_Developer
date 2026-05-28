# Lecture 2 — Practical Hands-On: Food Delivery Platform (All 3 Layers)

> **Theory file:** [02_Architecture_vs_Design_vs_Code.md](02_Architecture_vs_Design_vs_Code.md)

---

## 🎯 Is Practical Mein Kya Banayenge?

Ek **mini food delivery platform** banayenge with **all 3 layers visible**:

1. **🏗 Architecture layer** — `docker-compose.yml`, infrastructure
2. **📐 Design layer** — Pattern selections (Strategy, Observer, Layered), class structures
3. **💻 Code layer** — Working Python implementations

---

## 1. Mini Food Delivery — Project Setup

### Project Structure (Reflects Architecture)

```
mini_food_delivery/
├── docker-compose.yml              # 🏗 ARCHITECTURE — infrastructure
├── README.md                       # Architecture overview
├── docs/
│   ├── architecture/
│   │   ├── context.md             # C4 Level 1
│   │   └── containers.md          # C4 Level 2
│   └── adr/
│       └── ADR-001-payment-strategy.md
│
├── services/                       # Microservices
│   ├── order-service/
│   │   ├── pyproject.toml
│   │   ├── Dockerfile
│   │   ├── src/
│   │   │   ├── main.py            # FastAPI entry
│   │   │   ├── application/       # 📐 DESIGN — services
│   │   │   ├── domain/            # 📐 DESIGN — entities
│   │   │   ├── infrastructure/    # 📐 DESIGN — repositories
│   │   │   └── presentation/      # 💻 CODE — controllers
│   │   └── tests/
│   ├── payment-service/
│   │   └── src/
│   │       └── gateways/           # 📐 Strategy pattern
│   ├── notification-service/
│   │   └── src/
│   │       └── channels/           # 📐 Observer pattern
│   └── delivery-service/
│       └── src/
│           └── eta/                # 📐 Layered pattern
│
└── shared/                         # Cross-service shared
    └── events/                     # Kafka event schemas
```

> **Insight:** Folder structure architectural decisions ko **physically reflect** karta hai.

---

## 2. 🏗 ARCHITECTURE Layer — Infrastructure

### docker-compose.yml — Full Stack

```yaml
# docker-compose.yml
# Architecture decisions visible here:
# - Microservices (4 separate services)
# - Each owns its DB (Database per Service pattern)
# - Async events via Kafka
# - Caching via Redis
# - Service-to-service via HTTP

version: '3.8'

services:
  # ─── User-facing ───
  api-gateway:
    image: kong:3.6
    environment:
      KONG_DATABASE: "off"
      KONG_DECLARATIVE_CONFIG: /usr/local/kong/declarative/kong.yml
    ports: ["8000:8000"]
    volumes:
      - ./api-gateway/kong.yml:/usr/local/kong/declarative/kong.yml

  # ─── Order Service ───
  order-service:
    build: ./services/order-service
    environment:
      DATABASE_URL: postgres://order:order@order-db:5432/orders
      REDIS_URL: redis://redis:6379/0
      PAYMENT_SERVICE_URL: http://payment-service:8000
      KAFKA_BOOTSTRAP: kafka:9092
    depends_on: [order-db, redis, kafka, payment-service]
    ports: ["8001:8000"]

  order-db:
    image: postgres:16
    environment:
      POSTGRES_USER: order
      POSTGRES_PASSWORD: order
      POSTGRES_DB: orders
    volumes:
      - order-data:/var/lib/postgresql/data

  # ─── Payment Service ───
  payment-service:
    build: ./services/payment-service
    environment:
      DATABASE_URL: postgres://payment:payment@payment-db:5432/payments
      STRIPE_SECRET_KEY: ${STRIPE_SECRET_KEY}
      RAZORPAY_KEY_ID: ${RAZORPAY_KEY_ID}
      RAZORPAY_KEY_SECRET: ${RAZORPAY_KEY_SECRET}
      KAFKA_BOOTSTRAP: kafka:9092
    depends_on: [payment-db, kafka]
    ports: ["8002:8000"]

  payment-db:
    image: postgres:16
    environment:
      POSTGRES_USER: payment
      POSTGRES_PASSWORD: payment
      POSTGRES_DB: payments
    volumes:
      - payment-data:/var/lib/postgresql/data

  # ─── Notification Service ───
  notification-service:
    build: ./services/notification-service
    environment:
      KAFKA_BOOTSTRAP: kafka:9092
      SENDGRID_API_KEY: ${SENDGRID_API_KEY}
      TWILIO_ACCOUNT_SID: ${TWILIO_ACCOUNT_SID}
      TWILIO_AUTH_TOKEN: ${TWILIO_AUTH_TOKEN}
      FCM_SERVER_KEY: ${FCM_SERVER_KEY}
    depends_on: [kafka]

  # ─── Delivery Service ───
  delivery-service:
    build: ./services/delivery-service
    environment:
      DATABASE_URL: postgres://delivery:delivery@delivery-db:5432/delivery
      REDIS_URL: redis://redis:6379/1
      KAFKA_BOOTSTRAP: kafka:9092
    depends_on: [delivery-db, redis, kafka]
    ports: ["8003:8000"]

  delivery-db:
    image: postgres:16
    environment:
      POSTGRES_USER: delivery
      POSTGRES_PASSWORD: delivery
      POSTGRES_DB: delivery
    volumes:
      - delivery-data:/var/lib/postgresql/data

  # ─── Shared infrastructure ───
  redis:
    image: redis:7
    ports: ["6379:6379"]

  kafka:
    image: confluentinc/cp-kafka:7.6.0
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:9092
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      CLUSTER_ID: MkU3OEVBNTcwNTJENDM2Qk
    ports: ["9092:9092"]

  # ─── Observability ───
  prometheus:
    image: prom/prometheus
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
    ports: ["9090:9090"]

  grafana:
    image: grafana/grafana
    ports: ["3000:3000"]

volumes:
  order-data:
  payment-data:
  delivery-data:
```

### Architecture Diagram

```mermaid
flowchart TB
    Customer((Customer App))
    Customer -->|HTTPS| Gateway[Kong API Gateway]

    Gateway --> OrderSvc[Order Service]
    Gateway --> PaymentSvc[Payment Service]
    Gateway --> DeliverySvc[Delivery Service]

    OrderSvc -->|HTTP| PaymentSvc
    OrderSvc --> OrderDB[(Order DB)]
    PaymentSvc --> PaymentDB[(Payment DB)]
    DeliverySvc --> DeliveryDB[(Delivery DB)]

    OrderSvc -.publish events.-> Kafka[Kafka]
    PaymentSvc -.publish events.-> Kafka

    Kafka -.consume.-> NotificationSvc[Notification Service]
    Kafka -.consume.-> DeliverySvc

    NotificationSvc -->|SMS| Twilio[Twilio]
    NotificationSvc -->|Email| SendGrid[SendGrid]
    NotificationSvc -->|Push| FCM[FCM]

    PaymentSvc -->|HTTPS| Stripe[Stripe]
    PaymentSvc -->|HTTPS| Razorpay[Razorpay]

    AllSvcs[All Services] --> Redis[(Redis Cache)]
```

---

## 3. 📐 DESIGN Layer — Patterns

### Pattern 1: Strategy Pattern (Payment Service)

**Design decision:** Multiple payment gateways need pluggable interface.

```python
# services/payment-service/src/gateways/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class PaymentRequest:
    amount: float
    currency: str
    customer_id: str
    idempotency_key: str
    metadata: dict


@dataclass
class PaymentResult:
    success: bool
    transaction_id: Optional[str]
    gateway: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    raw_response: Optional[dict] = None


class PaymentGateway(ABC):
    """
    Strategy Pattern interface.
    Each payment gateway implements this same interface.
    Application code doesn't care which one is used at runtime.
    """

    @abstractmethod
    async def charge(self, request: PaymentRequest) -> PaymentResult:
        """Charge the customer."""
        ...

    @abstractmethod
    async def refund(self, transaction_id: str, amount: float) -> PaymentResult:
        """Refund a transaction."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Gateway name for logging/metrics."""
        ...

    @property
    @abstractmethod
    def supported_currencies(self) -> list[str]:
        """Currencies this gateway supports."""
        ...
```

```python
# services/payment-service/src/gateways/stripe_gateway.py
import stripe
import logging
from .base import PaymentGateway, PaymentRequest, PaymentResult


class StripeGateway(PaymentGateway):
    """Stripe implementation of payment gateway."""

    def __init__(self, secret_key: str):
        stripe.api_key = secret_key
        self.logger = logging.getLogger(__name__)

    @property
    def name(self) -> str:
        return "stripe"

    @property
    def supported_currencies(self) -> list[str]:
        return ["USD", "EUR", "GBP", "INR"]

    async def charge(self, req: PaymentRequest) -> PaymentResult:
        try:
            intent = stripe.PaymentIntent.create(
                amount=int(req.amount * 100),  # Stripe expects cents
                currency=req.currency.lower(),
                customer=req.customer_id,
                idempotency_key=req.idempotency_key,
                metadata=req.metadata,
            )
            return PaymentResult(
                success=True,
                transaction_id=intent.id,
                gateway=self.name,
                raw_response=intent.to_dict(),
            )
        except stripe.error.CardError as e:
            self.logger.warning(f"Card declined: {e.user_message}")
            return PaymentResult(
                success=False,
                transaction_id=None,
                gateway=self.name,
                error_code=e.code,
                error_message=e.user_message,
            )
        except Exception as e:
            self.logger.exception(f"Stripe charge failed")
            return PaymentResult(
                success=False,
                transaction_id=None,
                gateway=self.name,
                error_code="unknown",
                error_message=str(e),
            )

    async def refund(self, transaction_id: str, amount: float) -> PaymentResult:
        try:
            refund = stripe.Refund.create(
                payment_intent=transaction_id,
                amount=int(amount * 100),
            )
            return PaymentResult(
                success=True,
                transaction_id=refund.id,
                gateway=self.name,
            )
        except Exception as e:
            return PaymentResult(
                success=False,
                transaction_id=None,
                gateway=self.name,
                error_message=str(e),
            )
```

```python
# services/payment-service/src/gateways/razorpay_gateway.py
import razorpay
from .base import PaymentGateway, PaymentRequest, PaymentResult


class RazorpayGateway(PaymentGateway):
    """Razorpay implementation."""

    def __init__(self, key_id: str, key_secret: str):
        self.client = razorpay.Client(auth=(key_id, key_secret))

    @property
    def name(self) -> str:
        return "razorpay"

    @property
    def supported_currencies(self) -> list[str]:
        return ["INR"]  # Razorpay India-focused

    async def charge(self, req: PaymentRequest) -> PaymentResult:
        try:
            order = self.client.order.create({
                "amount": int(req.amount * 100),  # paise
                "currency": req.currency,
                "receipt": req.idempotency_key,
                "notes": req.metadata,
            })
            return PaymentResult(
                success=True,
                transaction_id=order["id"],
                gateway=self.name,
                raw_response=order,
            )
        except Exception as e:
            return PaymentResult(
                success=False,
                transaction_id=None,
                gateway=self.name,
                error_message=str(e),
            )

    async def refund(self, transaction_id: str, amount: float) -> PaymentResult:
        try:
            refund = self.client.payment.refund(transaction_id, {"amount": int(amount * 100)})
            return PaymentResult(
                success=True,
                transaction_id=refund["id"],
                gateway=self.name,
            )
        except Exception as e:
            return PaymentResult(
                success=False,
                transaction_id=None,
                gateway=self.name,
                error_message=str(e),
            )
```

```python
# services/payment-service/src/gateways/upi_gateway.py
import httpx
from .base import PaymentGateway, PaymentRequest, PaymentResult


class UPIGateway(PaymentGateway):
    """UPI direct integration (NPCI)."""

    def __init__(self, merchant_id: str, npci_url: str):
        self.merchant_id = merchant_id
        self.npci_url = npci_url

    @property
    def name(self) -> str:
        return "upi"

    @property
    def supported_currencies(self) -> list[str]:
        return ["INR"]

    async def charge(self, req: PaymentRequest) -> PaymentResult:
        # ... UPI-specific NPCI integration
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.npci_url}/collect",
                json={"amount": req.amount, "vpa": req.metadata.get("vpa")},
            )
        return PaymentResult(
            success=response.status_code == 200,
            transaction_id=response.json().get("txn_id"),
            gateway=self.name,
        )

    async def refund(self, transaction_id: str, amount: float) -> PaymentResult:
        # UPI refunds
        ...
```

```python
# services/payment-service/src/gateways/registry.py
from .base import PaymentGateway
from .stripe_gateway import StripeGateway
from .razorpay_gateway import RazorpayGateway
from .upi_gateway import UPIGateway
import os


class PaymentGatewayRegistry:
    """
    Registry to select gateway at runtime.
    This is part of the Strategy pattern — pick strategy based on context.
    """

    def __init__(self):
        self._gateways: dict[str, PaymentGateway] = {}
        self._initialize()

    def _initialize(self):
        # Stripe
        if stripe_key := os.environ.get("STRIPE_SECRET_KEY"):
            self._gateways["stripe"] = StripeGateway(stripe_key)

        # Razorpay
        if razorpay_id := os.environ.get("RAZORPAY_KEY_ID"):
            self._gateways["razorpay"] = RazorpayGateway(
                razorpay_id,
                os.environ["RAZORPAY_KEY_SECRET"],
            )

        # UPI
        if upi_merchant := os.environ.get("UPI_MERCHANT_ID"):
            self._gateways["upi"] = UPIGateway(
                upi_merchant,
                os.environ["NPCI_URL"],
            )

    def get(self, gateway_name: str) -> PaymentGateway:
        gateway = self._gateways.get(gateway_name)
        if not gateway:
            raise ValueError(f"Gateway {gateway_name} not registered")
        return gateway

    def select_best(self, currency: str, country: str) -> PaymentGateway:
        """Smart routing — pick best gateway for context."""
        # India + INR → UPI preferred (cheapest)
        if country == "IN" and currency == "INR":
            return self._gateways.get("upi") or self._gateways.get("razorpay")

        # International → Stripe
        if currency in ["USD", "EUR", "GBP"]:
            return self._gateways["stripe"]

        # Default
        return self._gateways.get("stripe")
```

### Pattern 2: Observer Pattern (Notification Service)

**Design decision:** When order events happen, notify multiple channels without hardcoding.

```python
# services/notification-service/src/channels/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class NotificationEvent:
    event_type: str         # 'order_placed', 'order_shipped', etc.
    user_id: str
    payload: dict
    user_preferences: dict  # which channels to use


class NotificationChannel(ABC):
    """
    Observer Pattern interface.
    Each channel observes order events and decides if/how to notify.
    """

    @abstractmethod
    async def notify(self, event: NotificationEvent) -> bool:
        ...

    @property
    @abstractmethod
    def channel_name(self) -> str:
        ...

    def is_enabled_for(self, event: NotificationEvent) -> bool:
        """Check if user has opted into this channel."""
        return event.user_preferences.get(self.channel_name, True)
```

```python
# services/notification-service/src/channels/sms_channel.py
from twilio.rest import Client
from .base import NotificationChannel, NotificationEvent
import logging


class SMSChannel(NotificationChannel):
    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        self.client = Client(account_sid, auth_token)
        self.from_number = from_number
        self.logger = logging.getLogger(__name__)

    @property
    def channel_name(self) -> str:
        return "sms"

    async def notify(self, event: NotificationEvent) -> bool:
        if not self.is_enabled_for(event):
            return False

        phone = event.payload.get("phone")
        if not phone:
            return False

        message = self._render_message(event)

        try:
            self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=phone,
            )
            return True
        except Exception as e:
            self.logger.error(f"SMS failed: {e}")
            return False

    def _render_message(self, event: NotificationEvent) -> str:
        templates = {
            "order_placed": "Your order #{order_id} is confirmed! Total: ₹{total}",
            "order_shipped": "Order #{order_id} shipped! Track: {track_url}",
            "order_delivered": "Order #{order_id} delivered. Enjoy!",
        }
        template = templates.get(event.event_type, "Update on order #{order_id}")
        return template.format(**event.payload)
```

```python
# services/notification-service/src/channels/email_channel.py
import sendgrid
from sendgrid.helpers.mail import Mail
from .base import NotificationChannel, NotificationEvent


class EmailChannel(NotificationChannel):
    def __init__(self, api_key: str, from_email: str):
        self.client = sendgrid.SendGridAPIClient(api_key)
        self.from_email = from_email

    @property
    def channel_name(self) -> str:
        return "email"

    async def notify(self, event: NotificationEvent) -> bool:
        if not self.is_enabled_for(event):
            return False

        email = event.payload.get("email")
        if not email:
            return False

        mail = Mail(
            from_email=self.from_email,
            to_emails=email,
            subject=self._render_subject(event),
            html_content=self._render_html(event),
        )
        try:
            response = self.client.send(mail)
            return response.status_code in [200, 201, 202]
        except Exception:
            return False

    def _render_subject(self, event: NotificationEvent) -> str:
        return {
            "order_placed": "Your order is confirmed! 🎉",
            "order_shipped": "On its way 🚀",
            "order_delivered": "Hope you enjoyed it 😋",
        }.get(event.event_type, "Order update")

    def _render_html(self, event: NotificationEvent) -> str:
        # Render template based on event type
        return f"<h1>{event.event_type}</h1><pre>{event.payload}</pre>"
```

```python
# services/notification-service/src/channels/push_channel.py
import httpx
from .base import NotificationChannel, NotificationEvent


class PushChannel(NotificationChannel):
    def __init__(self, fcm_server_key: str):
        self.fcm_key = fcm_server_key

    @property
    def channel_name(self) -> str:
        return "push"

    async def notify(self, event: NotificationEvent) -> bool:
        if not self.is_enabled_for(event):
            return False

        device_token = event.payload.get("device_token")
        if not device_token:
            return False

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://fcm.googleapis.com/fcm/send",
                headers={"Authorization": f"key={self.fcm_key}"},
                json={
                    "to": device_token,
                    "notification": {
                        "title": event.event_type,
                        "body": str(event.payload),
                    },
                },
            )
        return response.status_code == 200
```

```python
# services/notification-service/src/notification_service.py
import asyncio
from .channels.base import NotificationChannel, NotificationEvent


class NotificationService:
    """
    Observer pattern subject.
    Manages list of channels (observers) and notifies them all.
    """

    def __init__(self):
        self.channels: list[NotificationChannel] = []

    def subscribe(self, channel: NotificationChannel):
        self.channels.append(channel)

    def unsubscribe(self, channel: NotificationChannel):
        self.channels.remove(channel)

    async def notify_all(self, event: NotificationEvent):
        """Fan out to all channels in parallel."""
        results = await asyncio.gather(
            *[channel.notify(event) for channel in self.channels],
            return_exceptions=True,
        )

        success_count = sum(1 for r in results if r is True)
        return {
            "total_channels": len(self.channels),
            "success_count": success_count,
            "results": dict(zip(
                [c.channel_name for c in self.channels],
                results,
            )),
        }
```

### Pattern 3: Layered Pattern (Delivery ETA)

**Design decision:** ETA estimation has multiple concerns — caching, traffic, routing.

```python
# services/delivery-service/src/eta/cache_layer.py
import redis.asyncio as aioredis
import json
import logging
from typing import Optional


class CacheLayer:
    """Layer 3 (top): Cache layer — fast lookups."""

    def __init__(self, redis_url: str, ttl_seconds: int = 60):
        self.redis = aioredis.from_url(redis_url)
        self.ttl = ttl_seconds
        self.logger = logging.getLogger(__name__)

    def _key(self, restaurant_id: int, destination: str) -> str:
        return f"eta:{restaurant_id}:{destination}"

    async def get(self, restaurant_id: int, destination: str) -> Optional[int]:
        try:
            cached = await self.redis.get(self._key(restaurant_id, destination))
            if cached:
                self.logger.info(f"Cache hit for {restaurant_id}→{destination}")
                return int(cached)
        except Exception as e:
            self.logger.error(f"Cache error: {e}")
        return None

    async def set(self, restaurant_id: int, destination: str, eta_minutes: int):
        try:
            await self.redis.setex(
                self._key(restaurant_id, destination),
                self.ttl,
                str(eta_minutes),
            )
        except Exception as e:
            self.logger.error(f"Cache set error: {e}")
```

```python
# services/delivery-service/src/eta/traffic_layer.py
import httpx
from typing import Optional


class TrafficLayer:
    """Layer 2: Get live traffic data from external API."""

    def __init__(self, google_maps_api_key: str):
        self.api_key = google_maps_api_key

    async def get_travel_time(
        self,
        origin: str,
        destination: str,
    ) -> Optional[int]:
        """Returns travel time in minutes."""
        async with httpx.AsyncClient(timeout=5) as client:
            try:
                response = await client.get(
                    "https://maps.googleapis.com/maps/api/distancematrix/json",
                    params={
                        "origins": origin,
                        "destinations": destination,
                        "departure_time": "now",
                        "traffic_model": "best_guess",
                        "key": self.api_key,
                    },
                )
                data = response.json()
                rows = data.get("rows", [])
                if rows and rows[0].get("elements"):
                    duration = rows[0]["elements"][0].get("duration_in_traffic", {})
                    return duration.get("value", 0) // 60  # seconds → minutes
            except Exception:
                return None
        return None
```

```python
# services/delivery-service/src/eta/routing_engine.py
class RoutingEngine:
    """Layer 1 (core): Routing engine — fallback computation."""

    # Average prep time per restaurant type
    PREP_TIME_MINUTES = {
        "pizza": 20,
        "burger": 10,
        "indian": 25,
        "chinese": 15,
        "sushi": 30,
    }

    async def estimate_prep_time(self, restaurant_id: int) -> int:
        # In real system, lookup from DB
        # For simplicity, return default
        return 15  # minutes

    async def estimate_travel_time(
        self,
        restaurant_id: int,
        destination: str,
    ) -> int:
        """Fallback when traffic API fails — use distance heuristics."""
        # Simplified: 15 minutes default
        return 15
```

```python
# services/delivery-service/src/eta/eta_service.py
from .cache_layer import CacheLayer
from .traffic_layer import TrafficLayer
from .routing_engine import RoutingEngine
import logging


class ETAService:
    """
    Layered architecture in action.
    Orchestrates cache → traffic → routing layers.
    """

    def __init__(
        self,
        cache: CacheLayer,
        traffic: TrafficLayer,
        routing: RoutingEngine,
    ):
        self.cache = cache
        self.traffic = traffic
        self.routing = routing
        self.logger = logging.getLogger(__name__)

    async def estimate(
        self,
        restaurant_id: int,
        destination: str,
    ) -> dict:
        """
        Layered orchestration:
        1. Try cache (fast)
        2. Try live traffic (accurate)
        3. Fallback to routing engine (always works)
        """
        # Layer 3: Cache
        cached_eta = await self.cache.get(restaurant_id, destination)
        if cached_eta is not None:
            return {
                "eta_minutes": cached_eta,
                "source": "cache",
                "confidence": "high",
            }

        # Layer 2: Traffic
        prep_time = await self.routing.estimate_prep_time(restaurant_id)
        traffic_time = await self.traffic.get_travel_time(
            origin=f"restaurant:{restaurant_id}",
            destination=destination,
        )

        if traffic_time is not None:
            total_eta = prep_time + traffic_time
            await self.cache.set(restaurant_id, destination, total_eta)
            return {
                "eta_minutes": total_eta,
                "prep_time": prep_time,
                "travel_time": traffic_time,
                "source": "live_traffic",
                "confidence": "high",
            }

        # Layer 1: Fallback
        self.logger.warning("Traffic API unavailable, using fallback")
        fallback_travel = await self.routing.estimate_travel_time(
            restaurant_id,
            destination,
        )
        total_eta = prep_time + fallback_travel
        return {
            "eta_minutes": total_eta,
            "prep_time": prep_time,
            "travel_time": fallback_travel,
            "source": "fallback",
            "confidence": "low",
        }
```

---

## 4. 💻 CODE Layer — FastAPI Implementation

### Order Service Endpoint

```python
# services/order-service/src/presentation/api/orders.py
from fastapi import APIRouter, Depends, HTTPException
from uuid import UUID, uuid4
from pydantic import BaseModel, Field
from typing import Optional
import logging

from src.application.order_service import OrderService
from src.infrastructure.kafka_producer import KafkaProducer
from src.presentation.dependencies import get_order_service, get_kafka

router = APIRouter(prefix="/orders", tags=["orders"])
logger = logging.getLogger(__name__)


class OrderItem(BaseModel):
    product_id: int
    quantity: int = Field(..., ge=1, le=100)
    price: float = Field(..., ge=0)


class CreateOrderRequest(BaseModel):
    customer_id: int
    restaurant_id: int
    items: list[OrderItem] = Field(..., min_length=1)
    delivery_address: str
    payment_method: str  # 'stripe', 'razorpay', 'upi'
    idempotency_key: Optional[str] = None


class OrderResponse(BaseModel):
    order_id: UUID
    status: str
    total_amount: float
    estimated_delivery_minutes: int


@router.post("", response_model=OrderResponse)
async def create_order(
    req: CreateOrderRequest,
    order_svc: OrderService = Depends(get_order_service),
    kafka: KafkaProducer = Depends(get_kafka),
):
    """Create a new order."""

    # 1. Application layer handles the business logic
    try:
        order = await order_svc.create_order(
            customer_id=req.customer_id,
            restaurant_id=req.restaurant_id,
            items=[item.dict() for item in req.items],
            delivery_address=req.delivery_address,
            payment_method=req.payment_method,
            idempotency_key=req.idempotency_key or str(uuid4()),
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        logger.exception("Order creation failed")
        raise HTTPException(500, "Internal server error")

    # 2. Emit event for downstream services
    await kafka.publish("order.created", {
        "order_id": str(order.id),
        "customer_id": order.customer_id,
        "restaurant_id": order.restaurant_id,
        "total_amount": order.total_amount,
        "items": [item.dict() for item in order.items],
        "delivery_address": order.delivery_address,
    })

    return OrderResponse(
        order_id=order.id,
        status=order.status,
        total_amount=order.total_amount,
        estimated_delivery_minutes=order.estimated_delivery_minutes or 30,
    )


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(
    order_id: UUID,
    order_svc: OrderService = Depends(get_order_service),
):
    order = await order_svc.get_order(order_id)
    if not order:
        raise HTTPException(404, "Order not found")

    return OrderResponse(
        order_id=order.id,
        status=order.status,
        total_amount=order.total_amount,
        estimated_delivery_minutes=order.estimated_delivery_minutes or 0,
    )
```

### Order Service Application Layer

```python
# services/order-service/src/application/order_service.py
from uuid import UUID, uuid4
from datetime import datetime
import httpx
import logging
from typing import Optional

from src.domain.entities import Order, OrderItem, OrderStatus
from src.infrastructure.order_repository import OrderRepository


class OrderService:
    """
    Application service — orchestrates business logic.
    Does NOT know about HTTP, DB, or external APIs directly.
    """

    def __init__(
        self,
        repo: OrderRepository,
        payment_service_url: str,
        delivery_service_url: str,
    ):
        self.repo = repo
        self.payment_url = payment_service_url
        self.delivery_url = delivery_service_url
        self.logger = logging.getLogger(__name__)

    async def create_order(
        self,
        customer_id: int,
        restaurant_id: int,
        items: list[dict],
        delivery_address: str,
        payment_method: str,
        idempotency_key: str,
    ) -> Order:
        # 1. Check idempotency
        existing = await self.repo.get_by_idempotency_key(idempotency_key)
        if existing:
            return existing

        # 2. Validate items + calculate total
        total = sum(item["price"] * item["quantity"] for item in items)
        if total <= 0:
            raise ValueError("Order total must be positive")

        # 3. Create order in pending state
        order = Order(
            id=uuid4(),
            customer_id=customer_id,
            restaurant_id=restaurant_id,
            items=[OrderItem(**item) for item in items],
            delivery_address=delivery_address,
            payment_method=payment_method,
            total_amount=total,
            status=OrderStatus.PENDING,
            idempotency_key=idempotency_key,
            created_at=datetime.utcnow(),
        )
        await self.repo.save(order)

        # 4. Charge payment (synchronous — must succeed)
        try:
            payment_result = await self._charge_payment(
                order_id=order.id,
                customer_id=customer_id,
                amount=total,
                payment_method=payment_method,
                idempotency_key=idempotency_key,
            )
            if not payment_result["success"]:
                order.status = OrderStatus.PAYMENT_FAILED
                await self.repo.save(order)
                raise ValueError(f"Payment failed: {payment_result.get('error_message')}")

            order.payment_transaction_id = payment_result["transaction_id"]
            order.status = OrderStatus.CONFIRMED
        except Exception as e:
            order.status = OrderStatus.PAYMENT_FAILED
            await self.repo.save(order)
            raise

        # 5. Get delivery ETA
        try:
            eta_minutes = await self._get_delivery_eta(
                restaurant_id=restaurant_id,
                destination=delivery_address,
            )
            order.estimated_delivery_minutes = eta_minutes
        except Exception as e:
            self.logger.warning(f"ETA fetch failed: {e}")
            order.estimated_delivery_minutes = 30  # default

        # 6. Save final state
        await self.repo.save(order)
        return order

    async def get_order(self, order_id: UUID) -> Optional[Order]:
        return await self.repo.get(order_id)

    async def _charge_payment(
        self,
        order_id: UUID,
        customer_id: int,
        amount: float,
        payment_method: str,
        idempotency_key: str,
    ) -> dict:
        """Call payment service."""
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                f"{self.payment_url}/payments",
                json={
                    "order_id": str(order_id),
                    "customer_id": customer_id,
                    "amount": amount,
                    "gateway": payment_method,
                    "idempotency_key": idempotency_key,
                },
            )
            response.raise_for_status()
            return response.json()

    async def _get_delivery_eta(
        self,
        restaurant_id: int,
        destination: str,
    ) -> int:
        """Call delivery service."""
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.get(
                f"{self.delivery_url}/eta",
                params={
                    "restaurant_id": restaurant_id,
                    "destination": destination,
                },
            )
            response.raise_for_status()
            return response.json()["eta_minutes"]
```

### Domain Entities (Code Level)

```python
# services/order-service/src/domain/entities.py
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from uuid import UUID
from typing import Optional


class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PAYMENT_FAILED = "payment_failed"
    PREPARING = "preparing"
    READY = "ready"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


@dataclass
class OrderItem:
    product_id: int
    quantity: int
    price: float

    def dict(self) -> dict:
        return {
            "product_id": self.product_id,
            "quantity": self.quantity,
            "price": self.price,
        }


@dataclass
class Order:
    id: UUID
    customer_id: int
    restaurant_id: int
    items: list[OrderItem]
    delivery_address: str
    payment_method: str
    total_amount: float
    status: OrderStatus
    idempotency_key: str
    created_at: datetime
    payment_transaction_id: Optional[str] = None
    estimated_delivery_minutes: Optional[int] = None
    delivered_at: Optional[datetime] = None
```

### Repository (Infrastructure Layer)

```python
# services/order-service/src/infrastructure/order_repository.py
from uuid import UUID
from typing import Optional
import asyncpg
import json

from src.domain.entities import Order, OrderItem, OrderStatus


class OrderRepository:
    """
    Infrastructure: data access.
    Decouples domain from PostgreSQL specifics.
    """

    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    async def save(self, order: Order):
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO orders (
                    id, customer_id, restaurant_id, items, delivery_address,
                    payment_method, total_amount, status, idempotency_key,
                    payment_transaction_id, estimated_delivery_minutes, created_at
                )
                VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12
                )
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    payment_transaction_id = EXCLUDED.payment_transaction_id,
                    estimated_delivery_minutes = EXCLUDED.estimated_delivery_minutes
                """,
                order.id,
                order.customer_id,
                order.restaurant_id,
                json.dumps([item.dict() for item in order.items]),
                order.delivery_address,
                order.payment_method,
                order.total_amount,
                order.status.value,
                order.idempotency_key,
                order.payment_transaction_id,
                order.estimated_delivery_minutes,
                order.created_at,
            )

    async def get(self, order_id: UUID) -> Optional[Order]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM orders WHERE id = $1",
                order_id,
            )
            if not row:
                return None
            return self._row_to_entity(row)

    async def get_by_idempotency_key(self, key: str) -> Optional[Order]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM orders WHERE idempotency_key = $1",
                key,
            )
            if not row:
                return None
            return self._row_to_entity(row)

    def _row_to_entity(self, row) -> Order:
        items = [OrderItem(**item) for item in json.loads(row["items"])]
        return Order(
            id=row["id"],
            customer_id=row["customer_id"],
            restaurant_id=row["restaurant_id"],
            items=items,
            delivery_address=row["delivery_address"],
            payment_method=row["payment_method"],
            total_amount=float(row["total_amount"]),
            status=OrderStatus(row["status"]),
            idempotency_key=row["idempotency_key"],
            payment_transaction_id=row["payment_transaction_id"],
            estimated_delivery_minutes=row["estimated_delivery_minutes"],
            created_at=row["created_at"],
            delivered_at=row.get("delivered_at"),
        )
```

---

## 5. Tests at Each Layer

### Unit Test (Code Layer)

```python
# tests/unit/test_eta_service.py
import pytest
from unittest.mock import AsyncMock

from src.eta.eta_service import ETAService
from src.eta.cache_layer import CacheLayer
from src.eta.traffic_layer import TrafficLayer
from src.eta.routing_engine import RoutingEngine


@pytest.mark.asyncio
async def test_estimate_returns_cached_eta():
    # Arrange
    cache = AsyncMock(spec=CacheLayer)
    cache.get.return_value = 25  # cached value

    traffic = AsyncMock(spec=TrafficLayer)
    routing = AsyncMock(spec=RoutingEngine)

    service = ETAService(cache, traffic, routing)

    # Act
    result = await service.estimate(restaurant_id=1, destination="address")

    # Assert
    assert result["eta_minutes"] == 25
    assert result["source"] == "cache"
    traffic.get_travel_time.assert_not_called()
    routing.estimate_travel_time.assert_not_called()


@pytest.mark.asyncio
async def test_estimate_uses_traffic_on_cache_miss():
    cache = AsyncMock(spec=CacheLayer)
    cache.get.return_value = None

    traffic = AsyncMock(spec=TrafficLayer)
    traffic.get_travel_time.return_value = 20

    routing = AsyncMock(spec=RoutingEngine)
    routing.estimate_prep_time.return_value = 15

    service = ETAService(cache, traffic, routing)

    result = await service.estimate(restaurant_id=1, destination="addr")

    assert result["eta_minutes"] == 35  # 15 prep + 20 travel
    assert result["source"] == "live_traffic"
    cache.set.assert_called_once()


@pytest.mark.asyncio
async def test_estimate_falls_back_when_traffic_fails():
    cache = AsyncMock(spec=CacheLayer)
    cache.get.return_value = None

    traffic = AsyncMock(spec=TrafficLayer)
    traffic.get_travel_time.return_value = None  # API failed

    routing = AsyncMock(spec=RoutingEngine)
    routing.estimate_prep_time.return_value = 15
    routing.estimate_travel_time.return_value = 12

    service = ETAService(cache, traffic, routing)

    result = await service.estimate(restaurant_id=1, destination="addr")

    assert result["eta_minutes"] == 27  # 15 + 12
    assert result["source"] == "fallback"
    assert result["confidence"] == "low"
```

### Strategy Pattern Test

```python
# tests/unit/test_payment_strategy.py
import pytest
from src.gateways.registry import PaymentGatewayRegistry


def test_indian_customer_inr_gets_upi():
    registry = PaymentGatewayRegistry()
    gateway = registry.select_best(currency="INR", country="IN")
    assert gateway.name in ["upi", "razorpay"]  # cheap Indian gateway


def test_us_customer_usd_gets_stripe():
    registry = PaymentGatewayRegistry()
    gateway = registry.select_best(currency="USD", country="US")
    assert gateway.name == "stripe"


def test_european_customer_eur_gets_stripe():
    registry = PaymentGatewayRegistry()
    gateway = registry.select_best(currency="EUR", country="FR")
    assert gateway.name == "stripe"
```

### Integration Test (Design Layer)

```python
# tests/integration/test_order_creation.py
import pytest
import httpx


@pytest.mark.asyncio
async def test_create_order_end_to_end():
    async with httpx.AsyncClient(base_url="http://localhost:8001") as client:
        # Create order via API
        response = await client.post("/orders", json={
            "customer_id": 1,
            "restaurant_id": 100,
            "items": [
                {"product_id": 1, "quantity": 2, "price": 250.0},
            ],
            "delivery_address": "123 Main St",
            "payment_method": "upi",
        })

        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["confirmed", "pending"]
        assert data["total_amount"] == 500.0
        order_id = data["order_id"]

        # Fetch order
        get_response = await client.get(f"/orders/{order_id}")
        assert get_response.status_code == 200
```

---

## 6. Running Everything

### Start the full stack

```bash
# Clone + setup
git clone <your-repo>
cd mini_food_delivery
cp .env.example .env  # Fill in API keys

# Build + run
docker-compose up --build -d

# Verify all services healthy
docker-compose ps

# View logs
docker-compose logs -f order-service
```

### Test the system

```bash
# 1. Create an order
curl -X POST http://localhost:8000/orders \
  -H "Content-Type: application/json" \
  -d '{
    "customer_id": 1,
    "restaurant_id": 100,
    "items": [{"product_id": 1, "quantity": 2, "price": 250.0}],
    "delivery_address": "Mumbai, MH",
    "payment_method": "upi"
  }'

# Response:
# {
#   "order_id": "abc-123",
#   "status": "confirmed",
#   "total_amount": 500.0,
#   "estimated_delivery_minutes": 35
# }

# 2. Check order status
curl http://localhost:8000/orders/abc-123

# 3. Watch Kafka events
docker exec -it mini_food_delivery_kafka_1 \
  kafka-console-consumer --topic order.created --from-beginning --bootstrap-server localhost:9092
```

---

## 7. Tracing All 3 Layers in Action

For a single order creation, trace through:

```
🏗 ARCHITECTURE:
- Request hits API Gateway (Kong)
- Gateway routes to Order Service
- Order Service is one microservice in larger system

📐 DESIGN:
- Order Service uses Layered architecture
  - Presentation layer: orders.py (router)
  - Application layer: order_service.py (use case)
  - Domain layer: entities.py (pure business logic)
  - Infrastructure layer: order_repository.py (DB)
- Calls Payment Service via HTTP (Strategy chosen at runtime)
- Publishes event to Kafka (Observer pattern downstream)

💻 CODE:
- Pydantic validates request
- OrderService.create_order() orchestrates
- Repository.save() persists to PostgreSQL
- httpx.AsyncClient calls payment service
- Kafka producer publishes event
- Returns OrderResponse to client
```

---

## 8. Summary

```
🏗 ARCHITECTURE (infrastructure decisions)
   └── docker-compose.yml, K8s manifests
      └── Decides: microservices vs monolith, sync vs async, DBs

📐 DESIGN (component organization)
   └── Pattern selections per service
      └── Decides: Strategy, Observer, Layered patterns, DI, error handling

💻 CODE (actual implementation)
   └── Python files with FastAPI, asyncio
      └── Decides: naming, formatting, tests, business logic
```

### Key Takeaways

1. **Folder structure reflects architecture** — anyone can see the pattern
2. **Patterns chosen at design level**, implemented at code level
3. **Each layer has its own tests** — unit (code), integration (design), e2e (architecture)
4. **docker-compose.yml IS architecture documentation** — runnable + clear

---

## 9. Related Resources

- [00_Year0-2_Junior/06_FastAPI/12_clean_architecture_ddd.md](../../../00_Year0-2_Junior/06_FastAPI/12_clean_architecture_ddd.md) — Clean architecture
- [02_Year5+_Senior/01_System_Design/LLD_Theory/07_Strategy_Pattern.md](../../01_System_Design/LLD_Theory/07_Strategy_Pattern.md) — Strategy deep
- [02_Year5+_Senior/01_System_Design/LLD_Theory/08_Observer_Pattern.md](../../01_System_Design/LLD_Theory/08_Observer_Pattern.md) — Observer deep
- [01_Year3-4_Mid/05_Microservices/01_microservices_patterns.md](../../../01_Year3-4_Mid/05_Microservices/01_microservices_patterns.md)
