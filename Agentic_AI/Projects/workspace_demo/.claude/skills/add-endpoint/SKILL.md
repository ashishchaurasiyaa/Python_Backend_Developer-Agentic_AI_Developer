---
name: Add API endpoint
description: Scaffold a new FastAPI endpoint plus a matching frontend call. Use when asked to add an API route, endpoint, or new backend feature to this project.
---

# Add an API endpoint

Follow these steps to add a new endpoint consistently with this project.

## 1. Backend (`backend/main.py`)
- Add a Pydantic request model if the endpoint takes a body:
  ```python
  class FooRequest(BaseModel):
      bar: str
  ```
- Add the route **above** the `app.mount(...)` line (the static mount must stay last):
  ```python
  @app.post("/api/foo")
  async def foo(req: FooRequest) -> dict:
      ...
      return {"result": ...}
  ```
- Put any Claude/LLM logic in `backend/llm.py`, not inline in the route.

## 2. Frontend (`frontend/app.js`)
- Call the endpoint with `fetch("/api/foo", { method: "POST", ... })`.
- Reuse the existing `addMessage(...)` helper for any UI output.

## 3. Verify
- Restart isn't needed (`--reload` is on). Test with:
  ```bash
  curl -s -X POST localhost:8000/api/foo -H 'Content-Type: application/json' -d '{"bar":"x"}'
  ```
- Then run the `api-tester` agent, or `/ship-check`, before committing.

Keep the endpoint small and typed. See [reference/conventions.md](reference/conventions.md)
for the project conventions this must follow.
