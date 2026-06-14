# RabbitMQ — Hand-written `pika` Exercises

Raw practice scripts (moved out of the repo root). These are the "learn-by-doing"
versions; the curated, numbered reference scripts live in [`../practical/`](../practical/)
and the notes in [`../theory/`](../theory/) (PDFs under [`../theory/pdfs/`](../theory/pdfs/)).

Each script is standalone — start RabbitMQ locally, then run a consumer and a publisher
in separate terminals.

| Folder | Exchange type | What it shows | Files |
|---|---|---|---|
| `01_fanout/` | `fanout` | Broadcast to all queues | `publisher.py`, `subscriber.py` |
| `02_rpc/` | `direct` (reply-to) | Request/reply RPC (factorial) | `client.py`, `server.py` |
| `03_direct_routing/` | `direct` | Route by severity (Error/Warning/Info) | `publisher.py`, `alarmraiser.py`, `fiewriter.py`, `screenprinter.py` |
| `04_topic_routing/` | `topic` | Wildcard routing keys (`#`, `*`) | `publisher.py`, `A3actiontaker.py`, `allwarningsfromC2.py`, `errorhandlingsub.py` |
| `05_durability_confirms/` | `direct` (durable) | Durable queues, persistent msgs, publisher confirms, work queue | `publisher.py`, `subscriber.py` |
