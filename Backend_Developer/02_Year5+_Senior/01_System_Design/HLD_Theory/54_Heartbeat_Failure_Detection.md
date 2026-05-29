# Heartbeat & Failure Detection — "Kaun zinda hai?"

## WHAT

In a distributed system there are many nodes. Koi node **crash** ho jaaye, ya network se **cut** ho jaaye — baaki system ko jaldi pata chalna chahiye, warna requests ek dead node pe jaati rahengi.

**Heartbeat** = har node periodically ek chhota "main zinda hoon" signal bhejta hai. Agar signal aana band → node ko **dead/suspected** maan lo.

| | Heartbeat ke bina | Heartbeat ke saath |
|---|---|---|
| Dead node detect | Request fail hone ke baad pata chalta hai (slow) | Proactively, seconds me |
| Traffic to dead node | Jaata rehta hai (errors) | Turant rok do |
| Used by | — | LB health checks, leader election, cluster membership |

---

## HOW IT WORKS

### Push vs Pull model
```
PUSH:  Node A  --"alive"-->  Monitor      (A khud bhejta hai every T sec)
PULL:  Monitor --"alive?"--> Node A       (Monitor poochta hai, A reply karta hai)
```
- **Push** = gossip / cluster membership (Cassandra, Akka). Node خود bolta hai.
- **Pull** = load balancer health check (LB har 5s `GET /health` maarta hai).

### 3 tuning knobs
```
interval   = kitni der me ek heartbeat   (e.g. har 1s)
timeout    = kitna wait karein           (e.g. 3s)
threshold  = kitne missed beats = dead   (e.g. 3 missed → dead)
```

### Detection-time vs false-positive trade-off (yeh hai asli interview point)
- **Chhota interval/timeout** → fast detection, par **false positives** zyada (GC pause ya 200ms network blip pe healthy node ko "dead" maan loge).
- **Bada interval/timeout** → safe (kam false alarms), par dead node ko detect karne me der.

### Phi-Accrual Failure Detector (production-grade)
Binary "alive/dead" ke bajaye ek **suspicion score (φ)** deta hai. Recent heartbeat arrival times ka distribution dekh ke "yeh node dead hone ki kitni probability hai" calculate karta hai. Cassandra & Akka isi ko use karte hain — network conditions ke hisaab se khud adapt karta hai.

---

## REAL LIFE ANALOGY

**ICU ka pulse monitor.** Patient ka dil har second "beep" karta hai. Beep aana band → alarm baj jaata hai, nurse daudti hai. Beep = heartbeat. Ek beep miss hona (interval) vs flatline declare karna (threshold) — dono alag cheez hai. Doctor 1 missed beep pe death declare nahi karta (false positive se bachne ke liye).

---

## WHEN / WHERE USED

| Jagah | Heartbeat ka kaam |
|---|---|
| Load Balancer | Unhealthy backend ko rotation se hata do |
| Leader Election (Raft/ZooKeeper) | Leader ka heartbeat ruka → naya election |
| DB Replication | Primary down → replica promote karo |
| Cluster Membership (gossip) | Kaun-kaun node alive hai, sabko pata |
| Kubernetes | `livenessProbe` / `readinessProbe` = heartbeat hi hai |

---

## Illustrative Code (concept)

```python
import time

class HeartbeatMonitor:
    def __init__(self, timeout=3.0, max_missed=3):
        self.last_seen = {}          # node_id -> timestamp
        self.timeout = timeout
        self.max_missed = max_missed

    def beat(self, node_id):
        # node ne "main zinda hoon" bola
        self.last_seen[node_id] = time.time()

    def dead_nodes(self):
        now = time.time()
        return [
            n for n, ts in self.last_seen.items()
            if now - ts > self.timeout * self.max_missed
        ]
# Note: production me phi-accrual use hota hai, fixed threshold nahi.
```

---

## GOTCHAS (interview me bolne layak)

- **GC pause = false death.** Ek 2-second Java GC pause heartbeat rok deta hai → healthy node "dead" mark. Isliye threshold > 1.
- **Network partition ≠ node dead.** Node zinda hai par cut-off hai. "Suspected" state better hai "dead" se.
- **Heartbeat ka apna overhead.** 10,000 nodes har second beat bhejein → monitor pe load. Solution: **gossip** (nodes aapas me info phailate hain, central monitor nahi).

---

## Connection to Other Topics

- **Leader Election** (SD_Theory/09) — leader ka heartbeat ruke toh election trigger.
- **Service Discovery** (HLD_Theory/35) — registry heartbeat se hi "live instances" track karti hai.
- **Load Balancer** (HLD_Theory/12) — health check = heartbeat ka pull-model.

---

## Interview Q&A

**Q: Heartbeat interval kaise choose karein?**
A: Detection-speed vs false-positive ka trade-off. Typical: interval 1s, dead after 3 missed (~3s). Latency-sensitive systems chhota rakhte hain par phi-accrual jaisa adaptive detector use karte hain.

**Q: Healthy node ko galti se "dead" mark karne ka kya nuksaan?**
A: Unnecessary failover/re-election, data re-replication, ya split-brain (do leader ban jaayein). Isliye threshold aur "suspected" state important hai.

**Q: Push vs pull heartbeat — kab kya?**
A: Pull (LB → backend) jab central component ko fresh status chahiye. Push/gossip jab nodes bahut zyada hain aur central monitor bottleneck ban jaayega.

**Q: Kubernetes me heartbeat kahan hai?**
A: `livenessProbe` (container zinda hai? nahi → restart) aur `readinessProbe` (traffic lene ko ready hai? nahi → service se hata do) — dono periodic heartbeat checks hain.
