"""
FastAPI Request Body Advanced — Body(), Multiple Models, Nested Validation, Param Source Rules

Covers every concept from 40_request_body_advanced_gaps.md:
  1. Parameter source inference (path > model/Body() > query)
  2. Body() — forcing singular values into the JSON body
  3. Body(embed=True) — wrapping a single model under its param-name key
  4. Multiple Pydantic models in one endpoint (auto-embed by param name)
  5. Body() validation constraints + examples / openapi_examples
  6. Nested models (Offer → list[Item] → list[Image]), set deduplication
  7. Top-level list body (bulk create)
  8. Full combo endpoint: path + query + multiple body params
  9. 422 error loc path — how to read nested validation errors
 10. Production design choice: two models vs one explicit wrapper model

Run:
    pip install fastapi uvicorn
    uvicorn 40_request_body_advanced_gaps:app --reload
    # Explore: http://127.0.0.1:8000/docs
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Body, FastAPI
from pydantic import BaseModel, field_validator, model_validator

# ==========================================================================
# APP INSTANCE
# ==========================================================================

app = FastAPI(
    title="Request Body Advanced",
    description="Body(), multiple models, nested validation, param source inference.",
    version="1.0.0",
)


# ==========================================================================
# 1. DOMAIN MODELS
# ==========================================================================

class Image(BaseModel):
    """A product image with a URL and display name."""

    url: str
    name: str


class Item(BaseModel):
    """
    A product item.

    Production notes:
    - tags is set[str]: duplicate values in JSON array are silently deduplicated;
      order is NOT preserved.  Never depend on tag ordering client-side.
    - images is list[Image] | None: FastAPI/Pydantic recursively validates each
      element; an error in images[1].url shows up as loc [..., "images", 1, "url"].
    """

    name: str
    price: float
    tags: set[str] = set()
    images: list[Image] | None = None


class User(BaseModel):
    """The acting user submitting a request."""

    username: str
    full_name: str | None = None


class Offer(BaseModel):
    """
    A promotional offer containing multiple items — demonstrates deep nesting:
    Offer → list[Item] → list[Image].

    FastAPI/Pydantic validates the entire tree before responding, collecting ALL
    errors in one pass (not fail-fast), so the client can fix everything in a
    single round-trip.
    """

    name: str
    description: str | None = None
    items: list[Item]


# ==========================================================================
# 2. PARAMETER SOURCE INFERENCE — PATH / QUERY / BODY
# ==========================================================================
# FastAPI applies these rules at declaration time (not runtime):
#   1. Param name appears in the path template?           → PATH param
#   2. Type is a Pydantic BaseModel?                      → BODY (JSON)
#   3. Explicit marker (Query/Path/Body/Header/...)?      → that source
#   4. Singular scalar (int/str/float/bool/list[int]...)?  → QUERY param

@app.put(
    "/items/{item_id}",
    summary="Inference demo: path + body + query in one endpoint",
    tags=["01 - Source Inference"],
)
async def update_item_inference(
    item_id: int,          # rule 1 — name is in path template    → PATH
    item: Item,            # rule 2 — BaseModel                   → BODY
    q: str | None = None,  # rule 4 — singular, no marker         → QUERY
):
    """
    Single model body + path param + query param.

    Request:
        PUT /items/5?q=hello
        Body: {"name": "Pen", "price": 10.5}

    FastAPI routes all three from a single request without any extra decoration.
    """
    return {"item_id": item_id, "q": q, **item.model_dump()}


# ==========================================================================
# 3. Body() — SINGULAR VALUE INTO THE JSON BODY
# ==========================================================================
# Without Body(), FastAPI treats a scalar param as a query param (rule 4).
# Body() overrides that inference and pulls the value from the JSON body.
#
# When there is more than one body parameter (model + Body() scalar),
# FastAPI automatically embeds ALL of them under their parameter names:
#   { "item": {...}, "importance": 5 }

@app.put(
    "/items/{item_id}/importance",
    summary="Body() forces a scalar into the JSON body",
    tags=["02 - Body() Scalar"],
)
async def update_item_with_importance(
    item_id: int,
    item: Item,
    importance: int = Body(),  # without Body() this would be a query param
):
    """
    Expected JSON body:
        {
          "item": {"name": "Pen", "price": 10.5},
          "importance": 5
        }

    FastAPI auto-embeds both params under their names because there are now
    multiple body sources.
    """
    return {"item_id": item_id, "importance": importance, "item": item}


# ==========================================================================
# 4. Body(embed=True) — WRAP A SINGLE MODEL UNDER ITS PARAM-NAME KEY
# ==========================================================================
# Default (single body model, no embed):
#   Body: {"name": "Pen", "price": 10.5}        ← direct, no wrapper key
#
# With embed=True:
#   Body: {"item": {"name": "Pen", "price": 10.5}}   ← wrapped under "item"
#
# Use embed=True when:
#   (a) The API contract already promises a wrapper key to clients.
#   (b) You plan to add sibling body params later — embedding now avoids a
#       breaking shape change when that migration happens.
#   (c) Team convention: every body is envelope-keyed for consistency.

@app.post(
    "/items/direct",
    summary="Default: single model body is flat (no wrapper key)",
    tags=["03 - embed=True"],
)
async def create_item_direct(item: Item):
    """Body: {"name": "Pen", "price": 10.5}"""
    return item


@app.post(
    "/items/embedded",
    summary="embed=True: single model wrapped under its param name",
    tags=["03 - embed=True"],
)
async def create_item_embedded(item: Item = Body(embed=True)):
    """
    Body: {"item": {"name": "Pen", "price": 10.5}}

    Common trap: server has embed=True but client sends flat JSON (or vice versa)
    → confusing 422 "field required" errors.  Align contract with all clients
    before deploying.
    """
    return item


# ==========================================================================
# 5. MULTIPLE BODY MODELS — AUTO-EMBED BY PARAMETER NAME
# ==========================================================================
# As soon as an endpoint has more than one body param, FastAPI automatically
# embeds ALL of them under their respective parameter names.
#
# Migration gotcha: adding a second body param to an endpoint that previously
# had one changes the body shape from flat to enveloped — a BREAKING CHANGE for
# existing clients.  Coordinate with clients before shipping.

@app.put(
    "/items/{item_id}/full",
    summary="Two Pydantic models as body params — auto-embed by param name",
    tags=["04 - Multiple Body Models"],
)
async def update_item_with_user(item_id: int, item: Item, user: User):
    """
    Expected JSON body:
        {
          "item": {"name": "Pen", "price": 10.5},
          "user": {"username": "ashish", "full_name": "Ashish K"}
        }

    OpenAPI generates a synthetic composite schema
    (e.g. Body_update_item_with_user_items__item_id__full_put)
    whose properties are $refs to Item and User.
    """
    return {"item_id": item_id, "item": item, "user": user}


# ==========================================================================
# 6. EXPLICIT WRAPPER MODEL (PRODUCTION-PREFERRED ALTERNATIVE)
# ==========================================================================
# Merging multiple body models into one explicit wrapper model:
#   + Schema has a meaningful name ("ItemUserUpdateRequest") instead of the
#     ugly auto-generated "Body_update_item_..." name.
#   + Enables model-level cross-field validators (@model_validator).
#   + Reusable and importable as a standalone type.
#   Use two separate models when the entities are logically distinct and
#   independently reusable across endpoints.

class ItemUserUpdateRequest(BaseModel):
    """
    Explicit wrapper — production-preferred when the two models appear together
    in exactly this shape and cross-field validation is needed.
    """

    item: Item
    user: User

    @model_validator(mode="after")
    def item_name_not_username(self) -> ItemUserUpdateRequest:
        """Example cross-field rule: item name must differ from the username."""
        if self.item.name.lower() == self.user.username.lower():
            raise ValueError("item.name must not equal user.username")
        return self


@app.put(
    "/items/{item_id}/explicit-wrapper",
    summary="Explicit wrapper model — cleaner schema + model_validator support",
    tags=["04 - Multiple Body Models"],
)
async def update_item_explicit_wrapper(item_id: int, body: ItemUserUpdateRequest):
    """
    Body: {"item": {"name": "Pen", "price": 10.5}, "user": {"username": "ashish"}}

    The body shape is identical to the auto-embed endpoint above, but the
    OpenAPI schema name is now "ItemUserUpdateRequest" and cross-field
    validation is available.
    """
    return {"item_id": item_id, **body.model_dump()}


# ==========================================================================
# 7. Body() WITH VALIDATION CONSTRAINTS AND EXAMPLES
# ==========================================================================
# Body() accepts the same constraint kwargs as Query()/Path()/Field():
#   gt, ge, lt, le — numeric bounds
#   min_length, max_length — string bounds
#   title, description — OpenAPI metadata
#   examples — JSON-Schema-level example list
#   openapi_examples — named examples that appear as a dropdown in Swagger UI

@app.put(
    "/items/{item_id}/constrained",
    summary="Body() with validation constraints and Swagger UI examples",
    tags=["05 - Body() Constraints & Examples"],
)
async def update_item_constrained(
    item_id: int,
    item: Annotated[
        Item,
        Body(
            openapi_examples={
                "normal": {
                    "summary": "Valid item",
                    "value": {"name": "Pen", "price": 10.5, "tags": ["office", "writing"]},
                },
                "invalid_price": {
                    "summary": "Negative price (will fail validation)",
                    "value": {"name": "Pen", "price": -1},
                },
            },
        ),
    ],
    importance: Annotated[
        int,
        Body(
            gt=0,
            le=10,
            title="Importance",
            description="Priority level for this update, 1 (low) to 10 (critical).",
            examples=[5],
        ),
    ],
    note: Annotated[str | None, Body(min_length=3, max_length=200)] = None,
):
    """
    Constraint failure returns 422 with exact location, e.g.:
        {"detail": [{"loc": ["body", "importance"], "msg": "Input should be less than or equal to 10",
                     "type": "less_than_equal", "input": 99}]}

    Two example layers:
      - examples=[5] is JSON-Schema-level (rendered inline in /docs).
      - openapi_examples={...} is OpenAPI-level; Swagger UI shows them as a
        named dropdown — useful for valid/invalid scenario walkthroughs.
    """
    return {"item_id": item_id, "importance": importance, "note": note, "item": item}


# ==========================================================================
# 8. NESTED MODELS — Offer → list[Item] → list[Image]
# ==========================================================================
# FastAPI/Pydantic recursively validates arbitrarily deep JSON structures.
# Important: set[str] fields deduplicate and lose insertion order —
# never rely on tag ordering after the round-trip.

@app.post(
    "/offers",
    summary="Deep nesting: Offer → list[Item] → list[Image]",
    tags=["06 - Nested Models"],
)
async def create_offer(offer: Offer):
    """
    Valid body example:
        {
          "name": "Diwali Sale",
          "items": [
            {
              "name": "Pen",
              "price": 10.5,
              "tags": ["office", "office", "writing"],
              "images": [{"url": "http://example.com/1.png", "name": "front"}]
            }
          ]
        }

    Note: tags ["office", "office", "writing"] → set → {"office", "writing"}
    (order not preserved).

    If items[1].images[0].url is missing, the 422 loc path is:
        ["body", "items", 1, "images", 0, "url"]
    Pydantic collects ALL errors before responding — not fail-fast.
    """
    return offer


# ==========================================================================
# 9. TOP-LEVEL LIST BODY — BULK CREATE
# ==========================================================================
# A top-level JSON array maps to list[SomeModel] directly.
# Error loc omits the param-name segment:
#   ["body", 0, "price"] — index directly after "body"

@app.post(
    "/items/bulk",
    summary="Accept a top-level JSON array (bulk create)",
    tags=["06 - Nested Models"],
)
async def bulk_create_items(items: list[Item]):
    """
    Body: [{"name": "Pen", "price": 10.5}, {"name": "Ruler", "price": 5.0}]

    Validation error loc for a bad field in element 0:
        ["body", 0, "price"]
    """
    return {"created": len(items), "items": items}


# ==========================================================================
# 10. FULL COMBO — PATH + QUERY + MULTIPLE BODY PARAMS
# ==========================================================================
# Demonstrates all three sources working together in a single endpoint.

@app.put(
    "/users/{user_id}/items/{item_id}",
    summary="Full combo: path + query + multiple body params",
    tags=["07 - Full Combo"],
)
async def full_combo(
    user_id: int,                                # PATH  (name in template)
    item_id: int,                                # PATH  (name in template)
    item: Item,                                  # BODY  → key "item"
    user: User,                                  # BODY  → key "user"
    importance: Annotated[int, Body(gt=0)],      # BODY  → key "importance"
    q: str | None = None,                        # QUERY (singular, no marker)
    dry_run: bool = False,                       # QUERY (singular, no marker)
):
    """
    Call:
        PUT /users/7/items/5?q=test&dry_run=true
        Body:
          {
            "item": {"name": "Pen", "price": 10.5},
            "user": {"username": "ashish"},
            "importance": 5
          }

    Mental model recap:
      name in path template → PATH
      BaseModel or Body() → BODY (multiple = auto-embed by param name)
      remaining scalars → QUERY
      Header/Cookie/Form/File need explicit markers
    """
    return {
        "user_id": user_id,
        "item_id": item_id,
        "q": q,
        "dry_run": dry_run,
        "item": item,
        "user": user,
        "importance": importance,
    }


# ==========================================================================
# 11. 422 ERROR LOC — REFERENCE SHAPES (documentary constants, not routes)
# ==========================================================================
# These constants document how to read the loc array from a 422 response.
# They are not endpoints — they serve as inline reference for code reviewers
# and study purposes.

LOC_SINGLE_BODY_SCALAR = ["body", "importance"]
# → Body param "importance" failed; single body param, no wrapper level.

LOC_MULTIPLE_BODY_PARAM = ["body", "item", "price"]
# → Endpoint has multiple body params; "item" is the param name key; "price" failed.

LOC_NESTED_LIST = ["body", "items", 1, "images", 0, "url"]
# → Offer body → items[1] → images[0] → url field missing.

LOC_TOP_LEVEL_LIST = ["body", 0, "price"]
# → Bulk create endpoint; element 0 → price field failed.

# Production tip: join loc segments with "." for frontend field mapping:
#   ".".join(str(s) for s in LOC_NESTED_LIST)
#   → "body.items.1.images.0.url"


# ==========================================================================
# 12. COMMON MISTAKES — QUICK REFERENCE
# ==========================================================================

COMMON_MISTAKES = """
COMMON MISTAKES WITH REQUEST BODY ADVANCED PATTERNS
=====================================================

1.  Singular value in body without Body()
    → FastAPI reads it as a query param → 422 "field required" from body,
      or silently None if the param has a default.

2.  Single → multiple body param migration without notifying clients
    → Body shape changes from flat to enveloped (BREAKING CHANGE).
      Always version the endpoint or coordinate with clients first.

3.  embed=True mismatch
    → Server expects {"item": {...}}, client sends {"name": ...} (or vice versa)
      → confusing "field required" 422 that does not mention embed.

4.  GET endpoint with a BaseModel param
    → FastAPI parses it fine, but RFC 9110 gives GET body "no defined semantics".
      Proxies, CDNs, and HTTP clients may silently drop it.  Use POST/PUT.

5.  Merging unrelated entities into one mega-model
    → Use two separate params or an explicit named wrapper model so schemas
      stay clean and reusable.

6.  Ignoring loc in 422 responses
    → Logging only "validation failed" discards the exact nested path.
      Log the full detail array; map loc to dot-notation for frontend errors.

7.  Conflating examples and openapi_examples
    → examples=[...] → JSON-Schema level, inline in /docs.
    → openapi_examples={...} → OpenAPI level, named dropdown in Swagger UI.
      Use openapi_examples when you need multiple labelled scenarios.

8.  Depending on set[str] field ordering
    → JSON array → Python set → ordering lost, duplicates removed.
      Never sort or index tags after the round-trip.
"""


# ==========================================================================
# STARTUP LOG
# ==========================================================================

@app.on_event("startup")
async def startup() -> None:
    print("Request Body Advanced app started — visit http://127.0.0.1:8000/docs")
