# Endpoint conventions (loaded on demand)

This file is **not** in the context by default. Claude reads it only when the
`add-endpoint` skill points here — that is "progressive disclosure" in action.

- All routes live under the `/api/` prefix.
- Request bodies are typed with a Pydantic `BaseModel`; responses return a dict.
- Routes are declared in `backend/main.py` **before** the `StaticFiles` mount.
- No business logic in the route body — delegate to a function in `backend/llm.py`
  or a new module under `backend/`.
- Never read `ANTHROPIC_API_KEY` in a route; the SDK reads it from the env.
- Keep handlers `async def`.
