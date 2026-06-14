# PUT vs PATCH + Method Semantics — Idempotency, Safety, URI Nesting (Pakka Interview Question)

> **Interview angle:** "PUT aur PATCH me kya farak hai?" — yeh REST ka SABSE common question hai. 90% log bolte hain "PUT = update, PATCH = partial update" aur wahin atak jaate hain. Senior answer me 3 cheezein aani chahiye: **full replacement semantics (missing fields ka kya hota hai)**, **idempotency guarantee ka difference (aur PATCH idempotent kyun NAHI guaranteed)**, aur **RFC 7396 vs 6902 awareness**.

**One-line truth:** PUT bolta hai "resource ko ISSE replace kar do" — PATCH bolta hai "resource pe YEH operations apply kar do". Replace vs apply — yahi saara farak hai.

---

## 1. PUT — Full Replacement (The Part Everyone Forgets)

RFC 9110 (pehle 7231): PUT ka matlab hai **"request body = resource ki NAYI complete state"**. Jo fields body me nahi hain, woh resource me bhi nahi rehne chahiye.

```python
# Resource ki current state:
# { "id": 1, "name": "Ashish", "email": "a@x.com", "phone": "9999999999" }

# Client bhejta hai:
# PUT /users/1
# { "name": "Ashish Kumar", "email": "a@x.com" }

# ✅ CORRECT PUT semantics ke hisaab se result:
# { "id": 1, "name": "Ashish Kumar", "email": "a@x.com", "phone": null }
#                                                         ^^^^^^^^^^^^
#                            phone GAYA! Body me nahi tha = resource se hata
```

**Yahi trap hai:** PUT me missing fields **null/default ho jaate hain** (ya defaults pe reset). Client ko PUT karne se pehle **poora resource GET karna chahiye**, modify karna chahiye, phir poora wapas bhejna chahiye — "read-modify-write" cycle.

### Production me PUT ka classic bug

```python
# Frontend Team A ne form banaya jo sirf name+email bhejta hai PUT pe
# Backend Team B ne PUT ko "merge" ki tarah implement kiya (galat, lekin chal raha tha)
# 6 mahine baad Backend ne PUT ko spec-correct (full replace) kar diya
# → har profile update pe users ke phone numbers NULL hone lage
# → kisi ne method semantics document nahi kiye the

# Lesson: PUT implement karo toh FULL REPLACE karo, aur API docs me likho.
# Merge chahiye toh PATCH banao. Half-PUT-half-PATCH = future bug.
```

### PUT idempotent kyun hai (mathematically)

PUT = assignment operation. `resource = body`. Assignment ko 1 baar karo ya 100 baar — final state SAME.

```
PUT /users/1 {"name": "A"}   → state: {"name": "A"}
PUT /users/1 {"name": "A"}   → state: {"name": "A"}   (repeat = no change)
PUT /users/1 {"name": "A"}   → state: {"name": "A"}   (kitni baar bhi)
```

**Idempotency ki definition (RFC 9110):** same request ko N baar bhejne ka **server-side effect** = 1 baar bhejne jaisa. Response codes alag ho sakte hain — effect same hona chahiye. (Yeh nuance neeche DELETE wale section me kaam aayegi.)

### Bonus: PUT se CREATE bhi hota hai

PUT upsert-capable hai — client URI decide karta hai:

```
PUT /users/1 on non-existent resource:
  → server chahe toh CREATE kar sakta hai (201 Created return karo)
  → ya 404 de sakta hai (agar client-chosen IDs allow nahi)

POST /users:
  → SERVER URI decide karta hai (auto-increment id, UUID)
  → isliye POST create ke liye common hai — PUT create tab jab
    client ke paas natural key ho (e.g. PUT /configs/feature-x)
```

---

## 2. PATCH — Partial Update (Aur Idempotency Guarantee Kyun NAHI Hai)

RFC 5789: PATCH body me **"set of changes"** hota hai — instructions, not state. Server unhe apply karta hai.

```python
# PATCH /users/1
# { "name": "Ashish Kumar" }
#
# Result: sirf name change hua, email/phone UNTOUCHED
# { "id": 1, "name": "Ashish Kumar", "email": "a@x.com", "phone": "9999999999" }
```

### PATCH "not guaranteed idempotent" — KYUN? (Yahi senior-level answer hai)

PATCH ki body **operations** hai, state nahi. Operations idempotent ho bhi sakte hain, nahi bhi:

```jsonc
// Case A: IDEMPOTENT patch (set operation)
// {"name": "Ashish"} — 100 baar apply karo, name "Ashish" hi rahega ✅

// Case B: NON-idempotent patch (relative operation)
// JSON Patch (RFC 6902) style:
[
  {"op": "add", "path": "/tags/-", "value": "vip"}
]
// Har apply pe array me EK AUR "vip" append hota hai!
// 3 baar bhejo → tags: ["vip", "vip", "vip"] ❌ NOT idempotent

// Ya socho: {"op": "increment", "path": "/credits", "value": 10}
// (custom patch format) — har retry pe +10. Retry storm = paisa barbaad.
```

**Isliye spec bolta hai:** PATCH idempotent **ho sakta hai**, lekin method-level **guarantee nahi hai**. Practical implication: HTTP clients/proxies PATCH ko automatically retry NAHI kar sakte (PUT/DELETE kar sakte hain). Tumhare ZYADATAR JSON-merge-style PATCHes idempotent hi honge — lekin interview me bolo "the METHOD doesn't guarantee it, the payload decides".

### PATCH ke 2 standard formats — RFC 7396 vs RFC 6902

| | JSON Merge Patch (RFC 7396) | JSON Patch (RFC 6902) |
|---|---|---|
| Content-Type | `application/merge-patch+json` | `application/json-patch+json` |
| Body | Partial document (jo bhejo woh merge) | Operations ki array |
| Field delete kaise | `{"phone": null}` → phone removed | `{"op": "remove", "path": "/phone"}` |
| **Trap** | `null` set NAHI kar sakte — null = delete! | Verbose, paths galat = 400 |
| Array update | Poori array replace hoti hai (element-level merge NAHI) | Element-level: add/remove/replace at index |
| Conditional ops | ❌ | ✅ `{"op": "test", ...}` — fail toh poora patch abort |
| Idempotent? | Practically haan (set semantics) | Depends on ops (`add` on array = NO) |
| Use kab | 95% CRUD APIs — simple, intuitive | Precise array surgery, optimistic checks chahiye |

```jsonc
// JSON Merge Patch (RFC 7396) — "jaisa bhejo waisa merge"
// PATCH /users/1   Content-Type: application/merge-patch+json
{
  "name": "Ashish Kumar",
  "phone": null          // ← phone DELETE ho jayega (null = remove!)
}

// JSON Patch (RFC 6902) — operations ki list
// PATCH /users/1   Content-Type: application/json-patch+json
[
  {"op": "replace", "path": "/name", "value": "Ashish Kumar"},
  {"op": "remove",  "path": "/phone"},
  {"op": "test",    "path": "/version", "value": 7},  // version match nahi → 409, kuch apply nahi hota
  {"op": "add",     "path": "/tags/0", "value": "vip"}
]
```

**Merge Patch ka famous limitation:** "field ko explicitly null SET karna" impossible hai, kyunki null ka matlab delete define kiya gaya hai. Agar tumhare domain me `null` valid value hai (e.g. `discount: null` vs `discount` absent), Merge Patch kaam nahi karega — JSON Patch ya custom format chahiye.

---

## 3. Framework Reality — DRF `partial=True` aur FastAPI `exclude_unset`

Dono frameworks PATCH ke liye **same problem** solve karte hain: "client ne field BHEJI NAHI" vs "client ne field me null/default BHEJA" — in dono me farak kaise karein?

### DRF — `partial=True`

```python
# Django REST Framework — ViewSet me PATCH automatically partial hota hai
class UserViewSet(viewsets.ModelViewSet):
    serializer_class = UserSerializer
    # PATCH → self.partial_update() → serializer ko partial=True milta hai

# Manually:
def patch(self, request, pk):
    user = User.objects.get(pk=pk)
    serializer = UserSerializer(user, data=request.data, partial=True)
    #                                                    ^^^^^^^^^^^^
    # partial=True → required fields ka validation SKIP for missing fields
    # sirf bheji hui fields validate + update hoti hain
    serializer.is_valid(raise_exception=True)
    serializer.save()

# PUT me partial=False (default) → missing required field = 400 validation error
# Yahi DRF ka PUT-as-full-replacement enforcement hai
```

### FastAPI — `exclude_unset=True`

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI()

class UserPatch(BaseModel):
    # PATCH model: SAB fields Optional with None default
    name: str | None = None
    email: str | None = None
    phone: str | None = None

@app.patch("/users/{user_id}")
async def patch_user(user_id: int, patch: UserPatch):
    user = await get_user_or_404(user_id)

    # ❌ GALAT: patch.model_dump() — unsent fields bhi None ban ke aayengi
    #    → user.phone ko None se overwrite kar doge (accidental PUT!)

    # ✅ SAHI: exclude_unset=True — sirf woh fields jo client ne ACTUALLY bheji
    updates = patch.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(user, field, value)
    await user.save()
    return user

# Pydantic v2 internally har model pe `model_fields_set` track karta hai —
# "kaunsi fields constructor/JSON me explicitly aayi thi". exclude_unset usi se filter karta hai.
# Isliye {"phone": null} bhejne par phone None SET hoga (field set hui thi),
# lekin phone bhejna hi nahi = untouched. Merge-Patch jaisa "null=delete" yahan default NAHI hai.
```

**Connection samjho:** `partial=True` (DRF) aur `exclude_unset=True` (FastAPI/Pydantic) — dono "sent vs unsent" distinction implement karte hain, jo PATCH semantics ka core hai. PUT me yeh distinction matter nahi karta — full body required, full replace.

---

## 4. THE TABLE — Safety & Idempotency Per Method (Ratta Maar Lo)

**Safe** = server state change NAHI hoti (read-only). **Idempotent** = N baar = 1 baar (effect-wise). Safe ⊂ Idempotent — har safe method idempotent bhi hai.

| Method | Safe? | Idempotent? | Cacheable? | Kyun / Notes |
|---|---|---|---|---|
| GET | ✅ | ✅ | ✅ | Pure read. Side effects rakhna spec violation (analytics logging chalega — "essentially read-only") |
| HEAD | ✅ | ✅ | ✅ | GET minus body — headers/metadata check |
| OPTIONS | ✅ | ✅ | ❌ | Capabilities discovery; CORS preflight yahi use karta hai |
| PUT | ❌ | ✅ | ❌ | Replace = assignment → repeat-safe. Retry karna SAFE hai |
| DELETE | ❌ | ✅ | ❌ | "Ensure absent" → repeat-safe (neeche 404 wala point) |
| POST | ❌ | ❌ | ❌* | "Process this" — repeat = duplicate order/payment. Retry ke liye Idempotency-Key chahiye |
| PATCH | ❌ | ❌** | ❌ | Method-level guarantee nahi — payload decide karta hai (Section 2) |

\* POST responses technically cacheable ho sakte hain explicit freshness headers ke saath — practically koi nahi karta.
\*\* "Not guaranteed idempotent" — not "guaranteed not idempotent". Farak bolo interview me.

### Classic follow-up: "DELETE twice — doosri baar 404 aata hai, toh idempotent kaise?"

```
DELETE /users/1   → 204 No Content   (user delete hua)
DELETE /users/1   → 404 Not Found    (user already gone)

Status code ALAG hai — phir bhi idempotent. KYUN?
```

**Kyunki idempotency SERVER STATE ke baare me hai, response code ke baare me nahi.** Dono calls ke baad server ki state identical hai: "user 1 exist nahi karta". Pehli call ne state change ki, doosri ne nahi — effect of N calls = effect of 1 call. RFC 9110 explicitly yahi bolta hai: idempotency "intended effect on the server" se define hoti hai, response se nahi.

(Kuch APIs second DELETE pe bhi 204 dete hain — "tombstone" pattern — taaki retry karne wale clients confuse na hon. Dono valid hain.)

### Yeh table production me kyun matter karti hai

- **Retry logic:** Network timeout pe PUT/DELETE blind retry kar sakte ho. POST/PATCH NAHI — duplicate risk. POST retry chahiye toh `Idempotency-Key` header (Stripe pattern) implement karo.
- **Browsers/proxies:** GET prefetch/cache kar sakte hain. Agar tumne `GET /users/1/delete` jaisa endpoint banaya (safe method pe side effect), crawler/prefetcher tumhara data uda dega. (Yeh real incident hai — Google Web Accelerator 2005 ne GET-delete links wali apps ka data delete kar diya tha.)
- **Load balancers:** idempotent methods ko dusre backend pe re-dispatch kar sakte hain failure pe.

---

## 5. URI Nesting — `/users/1/orders` vs `/orders?user=1`

### Decision framework

```
Nested (sub-resource):  /users/1/orders
  Use jab: child ka parent ke BINA koi matlab nahi (composition)
  - order hamesha kisi user ka hota hai, "ownership" express karni hai
  - access control parent se flow karta hai

Flat + filter:          /orders?user_id=1
  Use jab: resource INDEPENDENT hai, user_id bas EK filter hai
  - orders ko date/status/amount se bhi filter karna hai
  - admin ko SAB orders dekhne hain (nested me yeh awkward: /users/*/orders ??)
  - cross-parent queries chahiye
```

### 2-Level Max Rule

```
✅ /users/1/orders                    (collection under resource — fine)
✅ /users/1/orders/99                 (specific child — fine, 2 levels)
❌ /users/1/orders/99/items/3/product/specs
   ^^^ URL archaeology — har segment pe DB lookup + permission check,
       clients ko 4 IDs yaad rakhne padte hain, aur product ka
       canonical URL kya hai? /products/7 ya yeh? (duplicate identity!)

Better: deep child ka APNA top-level address do:
✅ /orders/99          (order id globally unique hai toh user prefix kyun?)
✅ /order-items/3
✅ /products/7
```

**Rule of thumb:** nesting MAX 2 levels (`/collection/{id}/sub-collection/{id}` tak). Uske aage = child resource ko promote karo top-level pe.

### Subtle points jo senior log bolte hain

```python
# 1. Nested CREATE natural hai, nested deep-GET nahi:
#    POST /users/1/orders        ✅ "user 1 ke liye order banao" — parent context zaroori
#    GET  /orders/99             ✅ order fetch karne ke liye user id kyun chahiye?
#    Dono COEXIST kar sakte hain — create nested, read flat. Valid pattern.

# 2. Nested URL me parent VERIFY karo (common security bug):
@app.get("/users/{user_id}/orders/{order_id}")
async def get_order(user_id: int, order_id: int):
    order = await db.get(Order, order_id)
    if order is None or order.user_id != user_id:   # ⚠️ yeh check bhoolna = IDOR/BOLA
        raise HTTPException(404)                     # (OWASP API #1 vulnerability)
    return order
# Sirf order_id se fetch karke return kar diya = koi bhi user kisi ka bhi
# order dekh lega URL me apna user_id daal ke.

# 3. Filter approach me unknown-parent ka behavior soch lo:
#    GET /users/999/orders   → 404 (user hi nahi hai) — nested me natural
#    GET /orders?user_id=999 → 200 [] (empty list) — filter me natural
#    Dono theek hain, bas CONSISTENT raho aur document karo.
```

| Criteria | Nested `/users/1/orders` | Flat `/orders?user_id=1` |
|---|---|---|
| Relationship | Composition/ownership express hoti hai | Sirf ek filter dimension |
| Multi-filter (`status`, `date` bhi) | Awkward — `/users/1/orders?status=paid` chalega lekin growing | ✅ Natural |
| Admin "saare orders" view | ❌ Alag endpoint chahiye | ✅ Same endpoint, filter hata do |
| Child globally addressable | ❌ Parent id hamesha chahiye | ✅ `/orders/99` direct |
| Access control | Parent pe check natural | Query-param pe authorize karna padta hai |
| Verdict | Strong ownership + create flows | Independent resource + rich querying |

---

## 6. Common Mistakes Checklist

- [ ] ❌ PUT ko merge ki tarah implement karna — "PUT jo bheja wahi update karega, baaki chhod dega" = yeh PATCH hai, PUT nahi
- [ ] ❌ PATCH endpoint me `model_dump()` without `exclude_unset=True` — unsent Optional fields None ban ke data uda dengi
- [ ] ❌ "PATCH is not idempotent" flat bolna — sahi statement: "not GUARANTEED idempotent; payload decides"
- [ ] ❌ DELETE pe 404 dekh ke "idempotency toot gayi" sochna — idempotency = server effect, not response code
- [ ] ❌ POST retry without Idempotency-Key — duplicate payments/orders
- [ ] ❌ GET pe state change (`GET /orders/1/cancel`) — prefetchers/crawlers tumhara data process kar denge
- [ ] ❌ 3+ level nesting (`/a/1/b/2/c/3`) — 2-level max, deep children ko promote karo
- [ ] ❌ Nested route me parent-child relationship verify na karna — IDOR/BOLA vulnerability
- [ ] ❌ Merge Patch use karte hue `null` ko valid value maan lena — RFC 7396 me null = DELETE field

---

## 7. Interview Q&A

**Q1: PUT vs PATCH — real difference kya hai?**
PUT = **full replacement**: body resource ki complete nayi state hai; jo fields body me missing hain woh resource se remove/null ho jaani chahiye (RFC 9110). PATCH = **partial update**: body changes ka set hai, sirf mentioned fields touch hoti hain (RFC 5789). Dusra axis: PUT method-level **idempotent guaranteed** hai (replace = assignment), PATCH ki idempotency **payload pe depend** karti hai. Teesra: PUT upsert kar sakta hai client-chosen URI pe; PATCH existing resource pe hi operate karta hai.

**Q2: PATCH idempotent kyun guaranteed nahi hai? Example do.**
Kyunki PATCH body operations hai, state nahi. `{"name": "X"}` jaisa set-style patch idempotent hai. Lekin JSON Patch ka `{"op": "add", "path": "/tags/-", "value": "vip"}` har apply pe array me append karta hai — 3 retries = 3 duplicate tags. Isi liye HTTP infrastructure (proxies, clients) PATCH ko auto-retry nahi kar sakta jabki PUT/DELETE kar sakta hai. Production me PATCH retry chahiye toh Idempotency-Key ya conditional request (`If-Match` + ETag) lagao.

**Q3: JSON Merge Patch vs JSON Patch?**
Merge Patch (RFC 7396, `application/merge-patch+json`): partial document bhejo, server merge karta hai; `null` = field delete — isliye null as VALUE express nahi kar sakte; arrays poori replace hoti hain. JSON Patch (RFC 6902, `application/json-patch+json`): operations ki array (`add/remove/replace/move/copy/test`); verbose lekin precise — array element surgery aur `test` op se conditional/atomic apply milta hai. Simple CRUD = Merge Patch; array manipulation ya optimistic-check = JSON Patch.

**Q4: DELETE do baar bheja, doosri baar 404 aaya — kya DELETE ab bhi idempotent hai?**
Haan. Idempotency **server state ke effect** se define hoti hai, response code se nahi (RFC 9110). Dono calls ke baad state same hai: resource absent. N calls ka cumulative effect = 1 call ka effect — definition satisfy hoti hai. 404 sirf information hai ki "ab nahi mila". Kuch APIs doosri baar bhi 204 return karti hain retry-friendly hone ke liye — woh bhi valid design hai.

**Q5: DRF me PATCH kaise handle hota hai? FastAPI me equivalent kya hai?**
DRF: `serializer(instance, data=..., partial=True)` — `partial=True` missing required fields ka validation skip karta hai, sirf sent fields validate+update hoti hain; ModelViewSet ka `partial_update` PATCH pe yahi karta hai, PUT pe `partial=False`. FastAPI: all-Optional patch model + `patch.model_dump(exclude_unset=True)` — Pydantic `model_fields_set` se track karta hai kaunsi fields request me actually aayi thi, toh "field not sent" vs "field sent as null" distinguish hota hai. Dono ka core idea same: PATCH ko sent-fields-only pe operate karana.

**Q6: Kab `/users/1/orders` banaoge aur kab `/orders?user_id=1`? Kitna deep nest karoge?**
Nested jab strong ownership/composition ho aur create-context chahiye (`POST /users/1/orders` natural hai); flat+filter jab resource independent ho, multi-dimension filtering chahiye (status, date), ya admin/cross-user listing chahiye. Hybrid valid hai: create nested, read/list flat (`GET /orders/99`). Max **2 levels** nesting — `/users/1/orders/99` tak; uske aage deep children (items, products) ko apna top-level URI do, warna har URL pe multiple lookups + clients ko ID-chains yaad rakhni padti hain. Aur nested route me parent-child match VERIFY karna mat bhoolo — warna IDOR.

---

## Related
- [[01_rest_best_practices]] — status codes, versioning, response envelope
- [[18_conditional_requests_deep]] — ETag + If-Match se PATCH ko race-safe banana
- [[10_bulk_operations_design]] — bulk PATCH semantics
- [[08_api_security_hardening]] — IDOR/BOLA, object-level authorization
