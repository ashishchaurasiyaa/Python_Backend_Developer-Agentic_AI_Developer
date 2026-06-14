# Real-Time AI Chat App (ChatGPT-style) — Starter

Spec: [../09_Realtime_AI_Chat_App.md](../09_Realtime_AI_Chat_App.md)

## What to build

Real-time multi-user AI chat: WebSocket streaming with stop/regenerate, multi-device sync via Redis pub/sub, branching conversation model (edit + alternate timelines), multi-model LLM routing (Claude/GPT/Gemini), and Anthropic prompt caching for cost reduction.  Target: 50K concurrent WS connections, TTFT < 1s P95.

## How to run

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Infrastructure
docker run -d --name pg -e POSTGRES_PASSWORD=dev -p 5432:5432 postgres:16
docker run -d --name redis -p 6379:6379 redis:7

export ANTHROPIC_API_KEY=sk-ant-...
export OPENAI_API_KEY=sk-...
export DATABASE_URL=postgresql+asyncpg://postgres:dev@localhost/chatdb
export REDIS_URL=redis://localhost:6379/0

uvicorn main:app --reload
```

Connect via WebSocket at `ws://localhost:8000/ws/chat?token=<jwt>`.

## Milestones (from spec)

- **Phase 1** — FastAPI skeleton, JWT auth, Postgres schema, basic REST conversation endpoints, non-streaming LLM call
- **Phase 2** — WebSocket endpoint, Redis pub/sub fan-out for multi-device, Anthropic streaming, stop-generation via asyncio.Event
- **Phase 3** — Conversation history, edit + branch (`parent_message_id`), regenerate, auto-title via Haiku, multi-model routing
- **Phase 4** — Conversation sharing (public links), multi-user collaboration, presence + typing indicators
- **Phase 5** — Horizontal scaling (sticky sessions), tier-based rate limiting, Stripe Pro tier, Datadog / Sentry
- **Phase 6** — PWA, React Native mobile, push notifications, file uploads (S3 presigned URLs)

## Key patterns to implement

1. Multi-device sync: `_broadcast_to_user()` sends to all local WS connections, then publishes to Redis `user:{user_id}` channel for other pods.
2. Stop-generation: `asyncio.Event` per active stream; client sends `{"type": "stop", "message_id": "..."}` → event is set → streaming loop breaks.
3. Branching: messages have `parent_message_id` FK and `is_active_branch` flag; regenerate = new message with same parent, toggle active.
4. LLM cost: `tokens_in * input_price + tokens_out * output_price` stored per message; daily cap checked via Redis.
5. Anthropic prompt caching: prefix system prompt + conversation history with `cache_control: {"type": "ephemeral"}` to reduce cost 65%.
