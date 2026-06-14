# Real-Time Collaborative Whiteboard / Editor — Starter

Spec: [../02_FastAPI_RealTime_Whiteboard.md](../02_FastAPI_RealTime_Whiteboard.md)

## What to build

Google Docs / Figma-style collaborative editor backend.  Multiple users edit the same document simultaneously with sub-100ms sync via Y.js CRDT and Redis pub/sub cross-server fan-out.  Target: 100K concurrent users, 1M documents.

## How to run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Infrastructure
docker run -d --name pg -e POSTGRES_PASSWORD=dev -p 5432:5432 postgres:16
docker run -d --name redis -p 6379:6379 redis:7

uvicorn main:app --reload
```

Connect a Y.js client (e.g. y-websocket demo) to `ws://localhost:8000/ws/doc/<doc_id>`.

## Milestones (from spec)

- **Week 1** — FastAPI scaffold, document CRUD, single-server WebSocket sync (no auth yet)
- **Week 2** — Persist CRDT updates to Postgres, Redis pub/sub for multi-server, JWT auth, presence + cursors
- **Week 3** — Sharing (links, collaborators), comments, version history, anonymous users
- **Week 4** — Backpressure, graceful shutdown, sticky sessions via ALB / Cloudflare, load test 10K WS

## Key patterns to implement

1. Server is a dumb CRDT broker: receive binary update, persist, publish to Redis, broadcast to other connected clients.
2. Late-joining client: send snapshot (from S3) + incremental updates since last snapshot.
3. Snapshot strategy: every 500 updates or 5 min activity — merge all updates via `y_py`, upload to S3, GC old update rows.
4. Presence stored in Redis hash `presence:doc:{doc_id}` with TTL 300s; broadcast at 5 Hz throttle.
5. Bounded per-connection send queue (asyncio.Queue) to handle slow clients without OOM.
