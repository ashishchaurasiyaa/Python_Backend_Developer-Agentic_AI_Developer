# Request Body Advanced — `Body()`, Multiple Models, Nested Validation, Param Source Rules

> **Interview angle:** "Ek endpoint me do Pydantic models body me kaise loge? FastAPI kaise decide karta hai ki parameter path se aayega, query se ya body se?" — yeh questions check karte hain ki tumne FastAPI ko sirf tutorial-level use kiya hai ya uska request-parsing model samjha hai.

**One-line truth:** FastAPI har endpoint parameter ko dekh kar **infer** karta hai ki woh kahan se aayega — path > model/Body > query — aur `Body()` us inference ko override/control karne ka tool hai.

---

## 1. Parameter Source Inference — FastAPI Kaise Decide Karta Hai

Har endpoint parameter ke liye FastAPI yeh rules order me apply karta hai:

```
1. Parameter ka naam path template me hai?        → PATH param
2. Type Pydantic BaseModel hai?                    → BODY (JSON)
3. Explicit marker hai (Query/Path/Body/Header/Cookie/Form/File)? → wahi
4. Singular type hai (int, str, float, bool, list[int]...)? → QUERY param
```

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class Item(BaseModel):
    name: str
    price: float

@app.put("/items/{item_id}")
async def update_item(
    item_id: int,        # naam path me hai          → PATH
    item: Item,          # BaseModel                  → BODY
    q: str | None = None # singular, koi marker nahi  → QUERY
):
    return {"item_id": item_id, "q": q, **item.model_dump()}

# Request:
#   PUT /items/5?q=hello
#   Body: {"name": "Pen", "price": 10.5}
# Teeno sources EK request me — FastAPI ne khud route kiya
```

**Note:** "precedence" yahan **declaration-level inference** hai — koi runtime fight nahi hota ki "same naam path me bhi hai query me bhi". Path template me naam hai toh woh path param HI hai; usi naam ka query param chahiye toh alag naam + `Query(alias=...)` use karo.

```python
# ⚠️ Trap: GET/DELETE me body — technically FastAPI allow karta hai (BaseModel param GET me bhi body banega),
# lekin RFC 9110 GET body ko "no defined semantics" bolta hai; proxies/clients drop kar sakte hain. Mat karo.
```

---

## 2. `Body()` Deep — Singular Values in Body

Problem: `importance: int` likhoge toh FastAPI use **query param** samjhega (rule 4). Lekin tumhe woh JSON body me chahiye. Solution = `Body()` marker:

```python
from fastapi import Body

@app.put("/items/{item_id}")
async def update_item(
    item_id: int,
    item: Item,
    importance: int = Body(),    # ← ab yeh BODY se aayega, query se nahi
):
    return {"item_id": item_id, "importance": importance}

# Expected request body — FastAPI ne importance ko item ke SIBLING key
# ki tarah expect kiya (kyunki ab body me multiple cheezein hain):
# {
#   "item": {"name": "Pen", "price": 10.5},
#   "importance": 5
# }
```

### `Body(embed=True)` — Single Model ko Key ke Andar Wrap Karna

Default: **ek hi** body param ho toh FastAPI body ko directly model maanta hai (no wrapper key). `embed=True` se wrapper key force hoti hai:

```python
# Default (embed nahi):
@app.post("/items")
async def create(item: Item): ...
# Body: {"name": "Pen", "price": 10.5}            ← direct

# embed=True:
@app.post("/items-embedded")
async def create_embedded(item: Item = Body(embed=True)): ...
# Body: {"item": {"name": "Pen", "price": 10.5}}  ← "item" key ke andar
```

**Kab embed chahiye:** (1) API contract me wrapper key already promised hai (frontend/mobile team ke saath), (2) future me sibling body params add karne ka plan hai — abhi se embed kar do toh baad me contract nahi tootega, (3) consistency: team convention "har body envelope-keyed hogi".

**Trap:** embed bhool jaana = 422. Client `{"item": {...}}` bhej raha hai lekin endpoint me `embed=True` nahi → FastAPI direct `{"name", "price"}` expect karega → `field required` errors. (Aur ulta bhi — embed laga diya, client flat bhej raha hai.)

---

## 3. Multiple Body Params — Do Pydantic Models Ek Endpoint Me

```python
class Item(BaseModel):
    name: str
    price: float

class User(BaseModel):
    username: str
    full_name: str | None = None

@app.put("/items/{item_id}")
async def update_item(item_id: int, item: Item, user: User):
    return {"item_id": item_id, "item": item, "user": user}
```

**FastAPI kaise merge karta hai:** jaise hi endpoint me **1 se zyada** body params dikhe (multiple models, ya model + `Body()` singular), FastAPI **automatically sab ko embed** kar deta hai — har param apne **parameter NAAM** ki key ke neeche:

```jsonc
// Expected body — parameter names = top-level keys:
{
  "item": {"name": "Pen", "price": 10.5},
  "user": {"username": "ashish", "full_name": "Ashish K"}
}
// Yaani: multiple body params hote hi behavior implicitly embed=True jaisa
// ho jata hai SAB params ke liye. Single→multiple migrate karte waqt
// yahi BREAKING CHANGE hai jo log miss karte hain!
```

### Generated OpenAPI schema kya banta hai

FastAPI internally ek **synthetic wrapper model** banata hai jo OpenAPI me dikhta hai:

```jsonc
// POST /items/{item_id} ka requestBody schema (simplified):
{
  "type": "object",
  "title": "Body_update_item_items__item_id__put",   // ← auto-generated naam
  "required": ["item", "user", "importance"],
  "properties": {
    "item":       {"$ref": "#/components/schemas/Item"},
    "user":       {"$ref": "#/components/schemas/User"},
    "importance": {"type": "integer"}
  }
}
// /docs me yahi composite schema dikhega — Item aur User
// components me alag-alag $ref ke roop me reusable rehte hain.
```

**Interview line:** "Multiple body params pe FastAPI ek synthetic envelope object banata hai jisme har param uske naam ki key pe hota hai; OpenAPI me yeh `Body_<operation>` naam ka inline schema banta hai with `$ref`s to the real models."

### Kab 2 models vs kab 1 combined model

```python
# 2 alag models tab jab: logically alag entities hain (item + acting user),
# ya models REUSE ho rahe hain aur jodna pollution hoga.

# 1 combined model tab jab: yeh genuinely EK request shape hai —
class UpdateRequest(BaseModel):
    item: Item
    user: User
# Benefit: explicit naam, model-level validators laga sakte ho
# (e.g. @model_validator se cross-field check between item & user),
# aur schema ka naam "UpdateRequest" hota hai, ugly auto-naam nahi.
# Zyada production codebases isi taraf jaati hain.
```

---

## 4. `Body()` with Validation Constraints + Examples

`Body()` me wahi constraint kwargs chalte hain jo `Query()`/`Path()`/`Field()` me — sab `Param`/`FieldInfo` family se aate hain:

```python
from typing import Annotated
from fastapi import Body

@app.put("/items/{item_id}")
async def update_item(
    item_id: int,
    item: Item,
    importance: Annotated[int, Body(
        gt=0, le=10,                       # numeric constraints (>0, <=10)
        title="Importance",
        description="Priority 1-10",
        examples=[5],                      # docs me example dikhega
    )],
    note: Annotated[str | None, Body(min_length=3, max_length=100)] = None,
):
    return {"importance": importance}

# Constraint fail → 422 with location:
# {"detail": [{"loc": ["body", "importance"], "msg": "Input should be less than or equal to 10",
#              "type": "less_than_equal", "input": 99}]}

# Pura model bhi example ke saath document kar sakte ho:
@app.post("/items")
async def create(
    item: Annotated[Item, Body(
        examples=[{"name": "Pen", "price": 10.5}],   # Swagger UI me prefill
        openapi_examples={                            # named multiple examples (dropdown in /docs)
            "normal":  {"summary": "Valid item", "value": {"name": "Pen", "price": 10.5}},
            "invalid": {"summary": "Bad price",  "value": {"name": "Pen", "price": -1}},
        },
    )],
): ...
```

**Note:** `Annotated[int, Body(...)]` modern style hai (default-value style `importance: int = Body(...)` bhi valid). `examples=[...]` JSON-Schema-level hai; `openapi_examples={...}` OpenAPI-level named examples deta hai jo Swagger UI dropdown me dikhte hain — dono ka layer alag hai.

---

## 5. Nested Pydantic Models — Lists, Deep Nesting, Error Paths

```python
class Image(BaseModel):
    url: str
    name: str

class Item(BaseModel):
    name: str
    price: float
    tags: set[str] = set()            # list bheja toh dedupe ho ke set banega!
    images: list[Image] | None = None # ← list of models

class Offer(BaseModel):
    name: str
    items: list[Item]                 # ← deeply nested: Offer → Items → Images

@app.post("/offers")
async def create_offer(offer: Offer):
    return offer

# Valid body — arbitrarily deep JSON, FastAPI/Pydantic pura validate+convert karta hai:
# {
#   "name": "Diwali Sale",
#   "items": [
#     {"name": "Pen", "price": 10.5, "tags": ["a", "a", "b"],     ← set: {"a","b"} banega
#      "images": [{"url": "http://x/1.png", "name": "front"}]}
#   ]
# }
```

### Validation Error Paths — `loc` ko padhna seekho (debugging gold)

Nested structure me error aaye toh 422 response ka `loc` **exact path** batata hai — body se leke us field tak:

```jsonc
// Bheja: items[1].images[0].url missing, items[0].price string
{
  "detail": [
    {
      "loc": ["body", "items", 0, "price"],
      //      ^body   ^field  ^index ^field — Offer.items[0].price
      "msg": "Input should be a valid number, unable to parse string as a number",
      "type": "float_parsing",
      "input": "ten"
    },
    {
      "loc": ["body", "items", 1, "images", 0, "url"],
      "msg": "Field required",
      "type": "missing"
    }
  ]
}
// loc ka format: ["body", <param-name agar multiple body params>, path..., index, field]
// Multiple body params ho toh: ["body", "item", "price"] — param naam bhi path me aata hai!
```

**Production tip:** frontend ko field-level errors dikhane ke liye `loc` ko join karo (`items.0.price`) — yeh stable contract hai. Aur saare errors EK SAATH aate hain (fail-fast nahi) — Pydantic pura document validate karke sab errors collect karta hai, isliye client ek round-trip me sab fix kar sakta hai.

```python
# Bonus: list[Item] ko DIRECT body bhi le sakte ho (top-level JSON array):
@app.post("/items/bulk")
async def bulk_create(items: list[Item]):   # Body: [{...}, {...}]
    return {"count": len(items)}
# Error loc tab: ["body", 0, "price"] — index directly body ke baad
```

---

## 6. Sab Kuch Ek Saath — Path + Query + Multiple Body

```python
@app.put("/users/{user_id}/items/{item_id}")
async def full_combo(
    user_id: int,                                    # PATH (naam template me)
    item_id: int,                                    # PATH
    item: Item,                                      # BODY → key "item"
    user: User,                                      # BODY → key "user"
    importance: Annotated[int, Body(gt=0)],          # BODY → key "importance"
    q: str | None = None,                            # QUERY (singular, no marker)
    dry_run: bool = False,                           # QUERY
):
    return {"user_id": user_id, "q": q, "dry_run": dry_run,
            "item": item, "user": user, "importance": importance}

# PUT /users/7/items/5?q=test&dry_run=true
# Body:
# {
#   "item": {"name": "Pen", "price": 10.5},
#   "user": {"username": "ashish"},
#   "importance": 5
# }
```

Mental model recap: **naam path me → path; BaseModel ya Body() → body (multiple = auto-embed by param name); baaki singular → query.** Header/Cookie/Form/File explicit markers se.

---

## 7. Common Mistakes Checklist

- [ ] ❌ Singular value ko body me chahiye lekin `Body()` nahi lagaya → FastAPI query me dhundhega → 422 ya silent None
- [ ] ❌ Single body param se multiple pe migrate kiya, clients ko nahi bataya — body shape flat se enveloped ho gayi (breaking change!)
- [ ] ❌ `embed=True` ka mismatch — server embed expect kare, client flat bheje (ya ulta) → confusing `field required` 422
- [ ] ❌ GET endpoint me BaseModel param — FastAPI chalne dega, infra (proxies/CDN/clients) todegi
- [ ] ❌ Do unrelated cheezon ko ek mega-model me thoosna — alag params ya explicit wrapper model with naam, dono better
- [ ] ❌ 422 ke `loc` array ko ignore karke "validation failed" bhar dena logs me — exact nested path wahin pada hai
- [ ] ❌ `examples` (JSON Schema) aur `openapi_examples` (named, Swagger dropdown) ko same samajhna
- [ ] ❌ `set[str]` field me order pe depend karna — JSON list aayegi, dedupe+unordered ho jayegi

---

## 8. Interview Q&A

**Q1: FastAPI kaise decide karta hai ki parameter path, query ya body se aayega?**
Inference rules: (1) parameter ka naam path template me hai → path param; (2) type Pydantic BaseModel hai → body; (3) explicit marker (`Query`, `Path`, `Body`, `Header`, `Cookie`, `Form`, `File`) ho → wahi source; (4) warna singular types (int/str/bool/list) → query. Isliye `q: str` query banta hai aur `item: Item` body — bina kuch bole. Yeh runtime precedence nahi, declaration-time routing hai.

**Q2: Endpoint me ek singular int body me kaise loge? `Body(embed=True)` kya karta hai?**
`importance: Annotated[int, Body()]` — Body marker singular value ko query ke bajaye JSON body se uthata hai. `embed=True` single body param ko uske parameter-naam ki key ke andar wrap karwata hai: `{"item": {...}}` instead of direct `{...}`. Use cases: envelope-style API contract, ya future-proofing taaki sibling body params add karne pe shape na toote.

**Q3: Do Pydantic models ek endpoint me body params hain — request body kaisi dikhegi aur OpenAPI me kya generate hota hai?**
Multiple body params hote hi FastAPI sabko auto-embed kar deta hai — har param apne naam ki top-level key pe: `{"item": {...}, "user": {...}}`. OpenAPI me ek synthetic composite object schema banta hai (auto-naam jaise `Body_update_item_items__item_id__put`) jiski properties original models ke `$ref`s hoti hain. Important gotcha: single→multiple body param migration body shape badal deta hai (flat → enveloped) — clients ke liye breaking change.

**Q4: Deeply nested body (`Offer → list[Item] → list[Image]`) me validation error aaye toh client ko kaise pata chalega kahan?**
422 response ke har error me `loc` array exact path deta hai: `["body", "items", 0, "images", 1, "url"]` — body se field tak, list indices ke saath. Multiple body params me param ka naam bhi path me aata hai (`["body", "item", "price"]`). Pydantic fail-fast nahi karta — pura document validate karke SAARE errors ek saath return karta hai, toh client ek round-trip me sab fix kar sakta hai. Frontend field-mapping ke liye `loc` ko dot-join karna standard pattern hai.

**Q5: `Body()` me validation constraints aur examples kaise lagate ho?**
`Query`/`Path` jaise hi kwargs: `Body(gt=0, le=10, min_length=3, max_length=100, title=..., description=...)` — fail hone par standard 422 with `loc`. Documentation ke liye do layers: `examples=[...]` JSON-Schema-level example list hai, jabki `openapi_examples={"name": {"summary": ..., "value": ...}}` OpenAPI-level NAMED examples deta hai jo Swagger UI me dropdown ban ke dikhte hain — multiple scenarios (valid/invalid) dikhane ke liye openapi_examples better hai. Modern style `Annotated[int, Body(...)]` prefer karo taaki default value aur metadata mix na ho.

---

## Related
- [[01_routing_params]] — Path/Query basics, order matters in routes
- [[18_pydantic_v2_advanced]] — model_validator, field_validator, model_fields_set
- [[05_exception_handling_response_schema]] — 422 ko custom error format me convert karna
- [[11_forms_cookies_openapi]] — Form/File params (body ka non-JSON side)
