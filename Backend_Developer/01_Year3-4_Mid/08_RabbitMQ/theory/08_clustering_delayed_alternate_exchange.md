# RabbitMQ — Clustering Topology, Delayed Exchange, Alternate Exchange

## Why It Matters

Marked ⚪ skim-priority in the study plan — RabbitMQ is your secondary queue
system (Kafka is primary for interviews). This file exists to close 3 small,
genuinely niche gaps so nothing is a blank if a JD specifically calls out
RabbitMQ: cluster topology beyond the quorum-queue basics already covered,
and two less-common exchange types that occasionally come up in "how would
you implement X" design questions.

---

## 1. Clustering Topology (beyond the 3-node HA setup already covered)

`05_quorum_queues_ha.md` already covers the 3-node cluster + Erlang cookie
setup. The gap is the **topology decisions** on top of that basic setup:

```
Cluster node roles:
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│  Disc Node    │  │  Disc Node    │  │  RAM Node     │
│  (persists    │  │  (persists    │  │  (metadata    │
│   metadata    │  │   metadata    │  │   in memory   │
│   to disk)    │  │   to disk)    │  │   only —      │
│               │  │               │  │   faster,     │
│               │  │               │  │   riskier)    │
└──────────────┘  └──────────────┘  └──────────────┘
```

- **Disc nodes** persist queue/exchange/binding metadata to disk — survive a
  full cluster restart. Need at least ONE, in practice at least TWO for HA.
- **RAM nodes** keep metadata in memory only — faster for metadata-heavy
  operations (many queue declares/deletes), but lose all metadata if they
  restart while being the only node up. Rarely worth the risk in production;
  most real clusters run all-disc-node.

```bash
# Joining a node to an existing cluster
rabbitmqctl stop_app
rabbitmqctl join_cluster rabbit@node1
rabbitmqctl start_app

# Check cluster status
rabbitmqctl cluster_status
```

### Network partition handling — the actual interview depth

```
Cluster split into two halves during a network partition:
Partition A: [node1, node2]   Partition B: [node3]

RabbitMQ's `cluster_partition_handling` setting decides what happens:
- "ignore"        → both halves keep accepting writes independently (risky — split-brain)
- "autoheal"      → on reconnect, pick a winning partition, restart losing side's queues
- "pause_minority"→ minority side (node3) pauses itself, refuses connections
                    until it can rejoin — RECOMMENDED for production
```

```ini
# rabbitmq.conf
cluster_partition_handling = pause_minority
```

`pause_minority` is the production-safe default to recommend in an interview
— it sacrifices availability on the minority side rather than risk two
halves of the cluster diverging (split-brain), which quorum queues (Raft
consensus, already covered) also inherently protect against at the queue level.

### Federation vs Clustering (a distinction worth stating explicitly)

Already have a `06_federation_shovel.md` file — the key clarification: **a
cluster** is tightly-coupled nodes sharing all state (same LAN, low latency
required); **federation** is for loosely-coupled links between independent
clusters (different data centers/regions, higher latency tolerated). Don't
cluster across regions — federate instead.

---

## 2. Delayed Message Exchange

**The problem it solves:** RabbitMQ has no native "deliver this message in 30
minutes" feature. The standard workaround before this plugin existed was the
**TTL + Dead Letter Exchange trick** (already covered in
`02_dlx_ttl_priority_confirms.md`) — set a per-message TTL, let it expire
into a DLX that routes to the real queue. That works, but only supports one
fixed delay per queue and adds indirection.

The **delayed message exchange plugin** solves this directly:

```bash
# Install (community plugin, not built-in)
rabbitmq-plugins enable rabbitmq_delayed_message_exchange
```

```python
import pika

connection = pika.BlockingConnection(pika.ConnectionParameters("localhost"))
channel = connection.channel()

channel.exchange_declare(
    exchange="delayed_orders",
    exchange_type="x-delayed-message",
    arguments={"x-delayed-type": "direct"},   # underlying routing behavior
)
channel.queue_declare(queue="order_reminders")
channel.queue_bind(exchange="delayed_orders", queue="order_reminders", routing_key="reminder")

channel.basic_publish(
    exchange="delayed_orders",
    routing_key="reminder",
    body="Send cart-abandonment reminder",
    properties=pika.BasicProperties(
        headers={"x-delay": 1800000}   # delay in ms — 30 minutes, PER MESSAGE
    ),
)
```

**Key advantage over the TTL+DLX trick:** per-message delay (any value, set
at publish time) versus TTL+DLX's fixed-per-queue delay. Tradeoff: it's a
community plugin, not part of RabbitMQ core — adds an operational dependency
to track/upgrade separately.

**When to just use Celery/a task queue instead:** if delayed execution is a
core application feature (scheduled reminders, cart-abandonment emails at
scale), a dedicated scheduler (Celery `countdown`/`eta`, or a database-backed
job scheduler) is usually a better fit than routing it through message-broker
plugins — reach for delayed exchange for occasional/infrastructure-level
delays, not as your primary scheduling mechanism.

---

## 3. Alternate Exchange

**The problem it solves:** by default, a message published with a routing
key that matches NO binding on its exchange is **silently dropped** — no
error, no dead-letter, it just vanishes. This is a real production
gotcha (a typo'd routing key loses messages with zero visibility).

```
Normal exchange with no matching binding:
  Publish → Exchange → [no binding matches routing key] → message DISCARDED, silently

With an alternate exchange configured:
  Publish → Exchange → [no binding matches] → routed to ALTERNATE exchange
                                                  → caught by a catch-all queue
```

```python
# Declare the "catch-all" alternate exchange + queue first
channel.exchange_declare(exchange="unrouted_messages", exchange_type="fanout")
channel.queue_declare(queue="unrouted_queue")
channel.queue_bind(exchange="unrouted_messages", queue="unrouted_queue")

# Declare the MAIN exchange, pointing its "ae" argument at the alternate
channel.exchange_declare(
    exchange="orders",
    exchange_type="direct",
    arguments={"alternate-exchange": "unrouted_messages"},
)

# Now: any message published to "orders" with an unmatched routing key
# lands in "unrouted_queue" instead of silently vanishing.
```

**Interview-correct framing:** this is essentially the exchange-level
equivalent of a **dead letter exchange for routing failures** specifically
(vs DLX which handles TTL-expiry/rejection/queue-length-limit failures) —
same "never let a message vanish silently" philosophy, different failure mode.

---

## Interview Q&A

**Q: What's `pause_minority` and why is it the recommended partition-handling mode?**
A: On a network split, the minority-side nodes pause and refuse connections
until they can rejoin the majority, rather than both halves continuing to
accept writes independently (which would cause divergent, unreconcilable
state — split-brain). Sacrificing minority-side availability is safer than
risking data divergence.

**Q: How would you delay a message by a variable amount, decided per message at publish time?**
A: The `x-delayed-message` exchange type (community plugin) supports a
per-message `x-delay` header in milliseconds — unlike the TTL+DLX trick,
which only supports one fixed delay per queue.

**Q: A message with a typo'd routing key just disappears — how do you prevent this happening silently in the future?**
A: Configure an alternate exchange on the main exchange — any message that
matches no binding gets routed there instead of being silently discarded,
giving you visibility (a queue to inspect / alert on) instead of silent data loss.

---

Related: `02_dlx_ttl_priority_confirms.md` (the TTL+DLX delay workaround this
compares against), `05_quorum_queues_ha.md` (cluster basics this topology
section extends), `06_federation_shovel.md` (federation vs clustering distinction).
