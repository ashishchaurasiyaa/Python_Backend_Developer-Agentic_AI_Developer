# Stateful vs Stateless Architecture — Server yaad rakhta hai ya nahi?

## WHAT

Sawaal yeh hai: **do consecutive requests ke beech, server client ke baare me kuch yaad rakhta hai kya?**

- **Stateless** = har request **self-contained**. Server ko pichhli request yaad nahi. Request me hi saari zaroori info aati hai.
- **Stateful** = server **session/context** apne paas rakhta hai. Agli request pichhli pe depend karti hai.

| | Stateless | Stateful |
|---|---|---|
| Server memory | Kuch store nahi (per-client) | Session/context stored |
| Koi bhi node handle kare? | Haan (any node) | Nahi (wahi node jisne state rakhi) |
| Horizontal scaling | Easy | Hard |
| Crash pe state loss | Nahi (state bahar hai) | Haan (jab tak externalize na ho) |
| Examples | REST API + JWT, HTTP | WebSocket chat, online game, video call |

---

## WHY IT MATTERS — Scaling

Yeh poora khel **scaling** ka hai.

```
STATELESS:
  Request --> [LB] --> kisi bhi server pe       (server1/2/3 — koi bhi)
  Naya server add karo → turant traffic le lega
  Server mar gaya → request doosre pe chali jaayegi, user ko pata bhi nahi

STATEFUL (server me session):
  User ki session server-2 ki RAM me hai
  → Agli request bhi server-2 pe hi jaani chahiye (sticky session)
  → server-2 mara → session gayi → user dobara login
```

**Isliye modern backend stateless banaye jaate hain** — state ko server se nikaal ke ek **external store** (Redis / DB) me daal dete hain. Server khud "dumb" rehta hai, scale karna trivial ho jaata hai.

---

## HOW — State ko kahan rakhein?

### Stateless banane ka tareeka: state externalize karo
```
Session data   → Redis (fast, shared by all servers)
User identity  → JWT token (client ke paas, har request me aata hai)
Files/uploads  → S3 (local disk pe mat rakho)
```

### JWT (stateless) vs Server Session (stateful)
```
SERVER SESSION (stateful):
  Login → server session banata hai → session_id cookie
  Har request: server ko session_id se apni memory/Redis me lookup karna padta hai

JWT (stateless):
  Login → server signed token deta hai (user_id + expiry, signature ke saath)
  Har request: server bas signature verify karta hai — koi lookup nahi, kuch store nahi
```

### Sticky Sessions (stateful ka jugaad)
Agar state server me hai hi, toh LB ko bolo "is user ko hamesha wahi server bhej" (cookie/IP hash se). Kaam chalta hai par **scaling aur failover dono kharab** — woh server mara toh state gayi.

---

## REAL LIFE ANALOGY

**Stateless = McDonald's counter.** Har order independent. Jo bhi cashier free hai, order le lega. Cashier ko tumhari pichhli visit yaad rakhne ki zaroorat nahi. Naya counter khol do → instantly orders le lega.

**Stateful = family doctor.** Woh tumhari poori history yaad rakhta hai. Tum kisi naye doctor ke paas jaoge toh use sab dobara batana padega. Convenient, par "scale" nahi hota — har doctor sabki history nahi rakh sakta.

---

## WHEN TO USE WHAT

| Scenario | Choice | Why |
|---|---|---|
| REST API / microservices | Stateless | Horizontal scale, easy failover |
| Web app auth | Stateless (JWT) ya external session | Koi bhi node serve kare |
| Real-time chat / WebSocket | Stateful (connection) | Persistent connection ek node se bandhа |
| Online multiplayer game | Stateful | Low-latency game state in memory |
| Video call (Zoom) | Stateful | Media session ek server pe |
| Batch/REST data fetch | Stateless | Simplicity + scale |

**Pro tip:** WebSocket stateful hai, par usse bhi scale karte waqt connection-state ko Redis pub/sub se share karte hain taaki ek node ka load doosra le sake.

---

## Illustrative Code (concept)

```python
# STATELESS — JWT: server kuch store nahi karta
import jwt
SECRET = "..."

def login(user_id):
    # token client ko de do; server me kuch save nahi
    return jwt.encode({"uid": user_id, "exp": ...}, SECRET, algorithm="HS256")

def handle_request(token):
    payload = jwt.decode(token, SECRET, algorithms=["HS256"])  # bas verify
    return payload["uid"]      # koi DB/session lookup nahi

# STATEFUL — server session: memory me rakha (scale karna mushkil)
sessions = {}                  # is server ki RAM — doosre server ko nahi pata
def login_stateful(user_id):
    sid = make_id()
    sessions[sid] = {"uid": user_id}
    return sid
def handle_stateful(sid):
    return sessions[sid]["uid"]   # sirf isi server pe milega
```

---

## Connection to Other Topics

- **Load Balancing** (HLD_Theory/12) — stateless = round-robin freely; stateful = sticky sessions needed.
- **Horizontal Scaling** (HLD_Theory/10) — statelessness hi easy horizontal scaling enable karti hai.
- **Token-Based Auth** (HLD_Theory/26) — JWT = stateless auth ka core.
- **Caching** (HLD_Theory/13) — externalized session Redis me = stateless server + shared state.

---

## Interview Q&A

**Q: REST ko "stateless" kyun kehte hain?**
A: HTTP/REST principle — har request me poori info honi chahiye (auth token, params). Server do requests ke beech client context nahi rakhta. Isliye koi bhi server koi bhi request handle kar sakta hai.

**Q: Stateful service ko kaise scale karein?**
A: (1) State externalize karo (Redis/DB) → effectively stateless ban jaata hai. (2) Sticky sessions (kamजोर option). (3) Consistent hashing se state partition karo. (4) WebSocket ke liye Redis pub/sub se nodes ke beech messages share karo.

**Q: JWT ka downside?**
A: Stateless hone ki wajah se token **revoke** karna mushkil — expiry tak valid rehta hai. Logout/ban ke liye short expiry + refresh token, ya ek blocklist (jo thodi state wapas le aati hai).

**Q: Sticky session aur stateless me kya behtar?**
A: Stateless almost hamesha better — failover clean, scaling easy. Sticky session tab hi jab state externalize karna mehnga/impossible ho.
