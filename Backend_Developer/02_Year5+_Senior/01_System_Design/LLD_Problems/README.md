# 🧩 LLD Problems — 20 machine-coding problems

> **Machine-coding round** ka practice set. 4–6 saal experience pe India ke product companies
> (Flipkart, Swiggy, CRED, Zeta, Navi, PhonePe) me yeh **alag round** hota hai — HLD se alag.
>
> **Format:** 45–60 min me class design + working code. Interviewer dekhta hai:
> requirements clarify kiye? classes/responsibilities saaf hain? extensible hai? edge cases?

---

## ⚠️ Padho mat — pehle KHUD likho

Har problem ka model answer diya hai. Model answer **pehle padh liya to practice barbaad**.
Sahi tarika: 45 min timer → khud design karo → phir file kholo → jo miss hua wahi note karo.

---

## 🟢 Level 1 — pehle yeh 4 (foundation)

| Problem | Kya sikhata hai |
|---|---|
| [LRU_Cache](LRU_Cache.md) 🔴 | HashMap + doubly-linked list; sabse zyada poocha jane wala |
| [Parking_Lot_System](Parking_Lot_System.md) 🔴 | Classic OOD — inheritance vs composition, pricing strategy |
| [Vending_Machine](Vending_Machine.md) | **State pattern** ka clean example |
| [Tic_Tac_Toe_Chess](Tic_Tac_Toe_Chess.md) | Board games — clean abstraction |

## 🟡 Level 2 — real-world services

| Problem | Kya sikhata hai |
|---|---|
| [Splitwise](Splitwise.md) 🔴 | Expense splitting, balance settlement — India interviews me favourite |
| [Rate_Limiter](Rate_Limiter.md) 🔴 | Token/leaky bucket, sliding window |
| [Notification_System](Notification_System.md) | Multi-channel fan-out, Strategy + Observer |
| [Elevator_System](Elevator_System.md) | Scheduling + state machine, concurrency |
| [ATM_System](ATM_System.md) | State pattern, transaction integrity |
| [Login_System](Login_System.md) | Auth flows, session/token design |
| [Online_Shopping_Cart](Online_Shopping_Cart.md) | Cart/pricing/discount rules |
| [Library_Management_System](Library_Management_System.md) | CRUD-heavy OOD, borrowing rules |

## 🔴 Level 3 — complex domains

| Problem | Kya sikhata hai |
|---|---|
| [Payment_System](Payment_System.md) 🔴 | Payment state machine, wallet, idempotency *(HLD-scale version: [Design_Payment_Gateway](../HLD_Problems/Design_Payment_Gateway.md))* |
| [Booking_System](Booking_System.md) | Seat locking, concurrency, double-booking rokna |
| [Food_Delivery_System](Food_Delivery_System.md) | Multi-actor (user/restaurant/rider), matching |
| [Ride_Booking_System](Ride_Booking_System.md) | Driver matching, pricing, trip lifecycle |
| [Stock_Trading_System](Stock_Trading_System.md) | Order matching engine, order types |
| [Task_Queue_Job_Scheduler](Task_Queue_Job_Scheduler.md) | Scheduling, retries, priority |
| [File_Storage_System](File_Storage_System.md) | Chunking, metadata, versioning |
| [Zoom_Video_Call](Zoom_Video_Call.md) | Session/participant management |

---

## 🎯 Interview se pehle ka plan

| Din | Kya |
|---|---|
| 1 | LRU_Cache + Parking_Lot (timer laga ke) |
| 2 | Splitwise + Rate_Limiter |
| 3 | Vending_Machine (State) + Payment_System |
| 4 | Booking_System (concurrency — double booking ka jawab taiyar rakho) |
| 5 | Koi ek naya problem, bina model answer ke |

**Base kamzor lage to:** [`../LLD_Theory/`](../LLD_Theory/README.md) — SOLID + patterns pehle.
**Timed drill format:** [`../PRACTICE_DRILLS.md`](../PRACTICE_DRILLS.md)
**Patterns chala ke dekhne hain:** [`../Design_Patterns_Code/`](../Design_Patterns_Code/)
