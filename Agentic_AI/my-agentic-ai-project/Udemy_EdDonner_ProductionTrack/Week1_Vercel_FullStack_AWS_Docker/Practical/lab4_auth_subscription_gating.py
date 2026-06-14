"""
LAB 4 — Auth + Subscription Gating (BACKEND side)
=================================================
Title: Backend par session token verify karna + subscription plan se feature gating.

Lecture mapping: Ed Donner "AI Engineer Production Track", Week 1 Day 3,
                 L15-L18 (User Authentication with Clerk + Subscription Billing).
                 Course mein FRONTEND part Clerk (Next.js: <ClerkProvider>,
                 <SignedIn>/<SignedOut>, fastapi-clerk-auth) se hota hai. Yeh
                 Python lab us kahani ka BACKEND half teach karta hai — bilkul
                 wahi pattern jo `Depends(clerk_auth)` karta hai, par fully
                 offline + zero external deps, taaki concept haath se samajh aaye.

KYA SEEKHENGE (what concepts):
- JWT (JSON Web Token) ko ZERO dependency mein khud banana + verify karna
  (HS256 = HMAC-SHA256), sirf standard library se: hmac, hashlib, base64, json, time.
- Signature verify karna kyun zaroori hai: client jo bhi bheje wo trust NAHI karte;
  hum sirf apne SECRET se signed token par bharosa karte hain (tamper-proof).
- exp (expiry) claim check karna — purana/expired token reject ho.
- FastAPI dependency injection se do auth gates:
    * require_user  -> AUTHENTICATION (kaun ho? valid logged-in user?)  -> warna 401
    * require_pro   -> AUTHORIZATION  (kya kar sakte ho? paid plan hai?) -> warna 403
- Subscription billing ka MENTAL MODEL: paisa -> plan="pro" claim token mein ->
  backend us claim ko verify karke premium feature unlock karta hai (entitlement check).
- Authentication (401) vs Authorization (403) ka clean fark.

KAISE CHALANA (how to run):
    # 1) Self-demo (DEFAULT, no args): apni hi routes ko TestClient se call karke
    #    results print karta hai, phir exit 0. Koi API key / internet NAHI chahiye.
    uv run Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/lab4_auth_subscription_gating.py

    # 2) Real server (browser/curl se test karna ho):
    uv run Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/lab4_auth_subscription_gating.py --serve
    #   -> http://127.0.0.1:8000  (curl examples niche RUNBOOK section mein)

COST (yeh DEPLOYMENT course hai, isliye paisa-baat zaroori):
- YEH LAB LOCALLY 100% FREE hai. Koi LLM call nahi (auth/gating mein LLM lagta hi
  nahi), koi API key nahi, koi network call nahi. Bas Python stdlib + FastAPI.
- Production CLOUD deploy (runbook wala asli flow) ka cost:
    * Clerk: free tier kaafi udaar hai (~10k MAU tak free), uske baad MAU-based pricing.
    * Clerk Billing / Stripe: payment processing fee (~2.9% + 30c per charge Stripe);
      Clerk billing test payments FREE hote hain (course mein $100/mo PLAN sirf test hai,
      asli paisa nahi katta).
    * Vercel/AWS hosting: chhoti app ke liye free/hobby tier par chal jaati hai.
  => Concept seekhne ka cost ZERO; asli SaaS monetize karoge tabhi payment fees lagti hain.

NOTE — REAL CLERK vs IS LAB KA DIFFERENCE (zaroor padho):
  Asli Clerk RS256 (asymmetric) use karta hai: Clerk apni PRIVATE key se token sign
  karta hai, tumhara backend Clerk ke PUBLIC keys (JWKS endpoint:
  https://<app>.clerk.accounts.dev/.well-known/jwks.json) se signature verify karta hai.
  Iska fayda: backend ke paas signing secret rakhne ki zaroorat NAHI (sirf public key).
  HUM yahan HS256 (symmetric / shared-secret) use kar rahe hain — issuer aur verifier
  dono ek hi SECRET share karte hain — kyunki yeh offline padhana aasaan hai aur ZERO
  deps mein ban jaata hai. CONCEPT (sign -> verify -> claims se gate) bilkul same hai.
"""

import sys
import time
import json
import hmac
import hashlib
import base64

# NOTE: yeh lab LLM use NAHI karta (auth/gating pure backend logic hai). Convention
# ke according get_client helper neeche diya gaya hai TAAKI agar tum is route mein
# baad mein koi premium LLM feature add karo to ready-to-use ho. Self-demo isko
# call nahi karta, isliye API key na ho to bhi sab kuch chalta hai (graceful).
import os
try:
    from dotenv import load_dotenv
    load_dotenv(override=True)
except Exception:
    # dotenv optional hai — agar nahi mila to bhi lab chalta rahe (no crash).
    pass


def get_client(provider: str = "groq"):
    """(client, model) return karta hai. Default groq => zero cost, fast, OpenAI-compatible.

    IMPORTANT: yeh sirf tab use karna jab tum premium route mein asli LLM feature
    add karo. Self-demo isko NAHI chhoota hai, isliye key missing ho to bhi exit 0.
    """
    from openai import OpenAI  # lazy import: openai na ho to bhi baaki lab chale.
    if provider == "groq":
        return OpenAI(base_url="https://api.groq.com/openai/v1",
                      api_key=os.getenv("GROQ_API_KEY") or "placeholder"), "llama-3.3-70b-versatile"
    if provider == "gemini":
        return OpenAI(base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                      api_key=os.getenv("GOOGLE_API_KEY") or "placeholder"), "gemini-2.5-flash"
    raise ValueError(f"Unknown provider: {provider}")


# ===========================================================================
# PART 1 — Minimal HS256 JWT, ONLY standard library
# ===========================================================================
# JWT ek dot-separated string hoti hai:  header.payload.signature
#   - header  : {"alg":"HS256","typ":"JWT"}   <- konsa algo use hua
#   - payload : claims (sub=user id, plan, exp, ...)  <- ye DATA hai
#   - signature: HMAC-SHA256(secret, header + "." + payload)  <- TAMPER-PROOF seal
#
# KEY INSIGHT (poore lesson ka dil):
#   header aur payload bas base64url-ENCODED hain — ye ENCRYPTION nahi hai!
#   koi bhi unhe decode karke padh sakta hai. Toh phir security kahan se aati hai?
#   => SIGNATURE se. Sirf wahi banda valid signature bana sakta hai jiske paas
#      SECRET hai. Agar koi payload mein "plan":"pro" likh ke chhed-chhaad kare,
#      to signature match nahi karegi => verify_token reject kar dega.
#   ISILIYE: hum client se aaye plan/role par KABHI trust nahi karte — hum
#   signed token verify karte hain, jo prove karta hai ki claims hamare trusted
#   issuer (server) ne hi banaye the.

def _b64url_encode(raw: bytes) -> str:
    """bytes -> base64url string, BINA padding ('=') ke (JWT spec aisa maangti hai)."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    """base64url string -> bytes. Padding wapas add karte hain (warna decode fail)."""
    # base64 ko length % 4 == 0 chahiye; missing '=' padding manually add karo.
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign(signing_input: bytes, secret: str) -> str:
    """HMAC-SHA256 signature banao aur base64url string lautao.

    hmac.new(key, msg, digestmod) -> ek keyed hash. Sirf 'secret' jaanne wala
    hi same signature reproduce kar sakta hai. Yahi 'shared secret' ka jaadu hai.
    """
    sig = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return _b64url_encode(sig)


def make_token(payload: dict, secret: str, expires_in: int = 3600) -> str:
    """Ek signed JWT (HS256) banao.

    payload    : claims dict (e.g. {"sub": "user_123", "plan": "pro"}).
    secret     : shared signing secret (REAL clerk mein yeh private key hoti hai).
    expires_in : kitne second baad token expire ho (default 1 ghanta).

    Hum payload mein 'exp' (absolute unix epoch seconds) daal dete hain taaki
    verify_token isay enforce kar sake. (Agar caller ne khud exp diya hai to
    use overwrite nahi karte.)
    """
    header = {"alg": "HS256", "typ": "JWT"}

    # exp claim: agar payload mein pehle se nahi hai, to abhi-se expires_in seconds.
    body = dict(payload)  # caller ka dict mutate na karein — copy bana lo.
    body.setdefault("iat", int(time.time()))          # issued-at (jab bana)
    body.setdefault("exp", int(time.time()) + expires_in)  # expiry timestamp

    # JSON ko compact (no spaces) + deterministic banane ke liye separators fix.
    h_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    p_b64 = _b64url_encode(json.dumps(body, separators=(",", ":")).encode("utf-8"))

    signing_input = f"{h_b64}.{p_b64}".encode("ascii")
    sig_b64 = _sign(signing_input, secret)
    return f"{h_b64}.{p_b64}.{sig_b64}"


class TokenError(Exception):
    """verify_token fail hone par raise hoti hai (invalid/tampered/expired)."""


def verify_token(token: str, secret: str) -> dict:
    """Token verify karo aur claims (payload dict) return karo.

    FAIL kab hota hai (har case par TokenError raise):
      - structurally galat (3 parts nahi).
      - signature MISMATCH (tamper hua ya galat secret) -> sabse important check.
      - 'exp' nikal chuka (expired).

    Return: verified claims dict. Yahi 'trusted' data hai jis par hum gate lagayenge.
    """
    # 1) structure check: header.payload.signature
    parts = token.split(".")
    if len(parts) != 3:
        raise TokenError("Malformed token (expected 3 dot-separated parts)")
    h_b64, p_b64, sig_b64 = parts

    # 2) SIGNATURE VERIFY — sabse crucial step.
    #    Hum khud secret se EXPECTED signature dobara compute karte hain aur
    #    incoming signature se compare karte hain. hmac.compare_digest use kar
    #    rahe hain (NOT '==') taaki TIMING ATTACK na ho — constant-time compare.
    expected_sig = _sign(f"{h_b64}.{p_b64}".encode("ascii"), secret)
    if not hmac.compare_digest(expected_sig, sig_b64):
        # signature match nahi hui => ya secret galat, ya kisi ne payload chheda.
        # dono case mein token par BHAROSA NAHI -> reject.
        raise TokenError("Bad signature (token tampered or wrong secret)")

    # 3) ab signature valid hai => payload safely decode kar sakte hain.
    try:
        claims = json.loads(_b64url_decode(p_b64))
    except Exception as e:
        raise TokenError(f"Cannot decode payload: {e}")

    # 4) expiry check: 'exp' (unix seconds) ab se peeche to expired.
    exp = claims.get("exp")
    if exp is not None and int(time.time()) >= int(exp):
        raise TokenError("Token expired")

    return claims


# ===========================================================================
# PART 2 — FastAPI app: auth + subscription gating dependencies
# ===========================================================================
from fastapi import FastAPI, Depends, HTTPException, Header, Query
from fastapi.responses import JSONResponse

app = FastAPI(title="Lab4 Auth + Subscription Gating (backend)")

# DEMO secret. PRODUCTION mein yeh kabhi code mein hardcode NAHI karte — env var /
# secret manager se aata hai (AWS Secrets Manager, Vercel env, etc.). Real Clerk
# mein to backend ke paas signing secret hota hi nahi (RS256 + public JWKS).
JWT_SECRET = os.getenv("JWT_SECRET", "dev-only-shared-secret-change-me")


# --- DEPENDENCY 1: require_user (AUTHENTICATION) ---------------------------
# FastAPI 'Depends' pattern: yeh function har protected route ke aage chalta hai.
# Authorization header se "Bearer <jwt>" nikaalta hai, verify karta hai. Fail =>
# 401 Unauthorized (matlab: tum logged-in/identified hi nahi ho).
#
# Header(None) => agar header missing hai to None milega (crash nahi). Hum khud
# friendly 401 raise karte hain.
def require_user(authorization: str | None = Header(default=None)) -> dict:
    """Valid Bearer JWT hona chahiye. Verified claims return karta hai, warna 401.

    Yahi exactly wo kaam hai jo course ka `Depends(clerk_auth)` karta tha —
    bas hum haath se likh rahe hain taaki andar ka mechanism dikh jaye.
    """
    if not authorization:
        # koi token bheja hi nahi.
        raise HTTPException(status_code=401, detail="Missing Authorization header")

    # Header format: "Bearer eyJ...". Scheme aur token alag karo.
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Expected 'Bearer <token>'")

    try:
        claims = verify_token(token, JWT_SECRET)
    except TokenError as e:
        # invalid / tampered / expired — sab 401 (authentication fail).
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")

    return claims  # downstream route ko verified claims mil jaate hain.


# --- DEPENDENCY 2: require_pro (AUTHORIZATION / entitlement) ----------------
# Yeh require_user ke UPAR build hota hai (dependency chaining): pehle user valid
# hona chahiye (401 warna), AUR plan == "pro" hona chahiye (403 warna).
#
# 401 vs 403 ka FARK (interview-favourite):
#   401 Unauthorized  = "main tumhe pehchanta hi nahi" (auth missing/invalid).
#   403 Forbidden     = "main tumhe pehchanta hoon, par yeh tumhare liye allowed nahi"
#                       (authenticated but not entitled — yahan: free plan, pro chahiye).
#
# SUBSCRIPTION BILLING MAPPING:
#   user paisa deta hai -> Clerk/Stripe subscription "active" -> Clerk token mein
#   ek plan/feature claim daal deta hai -> backend us VERIFIED claim ko check karke
#   premium feature unlock karta hai. "plan" ek ENTITLEMENT hai. Hum DB mein har
#   request par check nahi karte (stateless) — signed token hi proof carry karta hai.
def require_pro(claims: dict = Depends(require_user)) -> dict:
    """Pehle valid user (require_user), phir plan=='pro' enforce. Warna 403."""
    plan = claims.get("plan")
    if plan != "pro":
        # CRITICAL: client kabhi bhi apna plan "badal" ke nahi bhej sakta, kyunki
        # plan ek SIGNED claim hai — chhedne par signature toot jaati (verify_token
        # 401 de deta). Isliye yahan trust kar sakte hain. NEVER trust an UNsigned
        # client-sent plan/role header.
        raise HTTPException(
            status_code=403,
            detail=f"Subscription required: plan='{plan}' but 'pro' needed",
        )
    return claims


# ===========================================================================
# PART 3 — Routes
# ===========================================================================

@app.get("/health")
def health():
    """Liveness probe. Auth ke bina accessible (load balancer / k8s isay ping karta)."""
    return {"status": "ok"}


@app.post("/token")
def issue_token(plan: str = Query(default="free")):
    """DEMO HELPER: ek token mint karke deta hai (?plan=free | ?plan=pro).

    YEH SIRF PADHAI/DEMO KE LIYE HAI. Asli zindagi mein token CLERK banata hai
    sign-in ke baad — tumhara backend kabhi token issue nahi karta (sirf verify).
    Hum yahan apni demo ke liye 'issuer' ban rahe hain taaki verify dikha sakein.
    """
    # sub = subject = unique user id (Clerk ka user id is claim mein hota hai).
    payload = {"sub": "user_demo_001", "plan": plan, "email": "demo@example.com"}
    token = make_token(payload, JWT_SECRET, expires_in=3600)
    return {"access_token": token, "token_type": "bearer", "plan": plan}


@app.get("/me")
def me(claims: dict = Depends(require_user)):
    """AUTHENTICATED route: valid token chahiye (warna 401). User ke claims lautata hai.

    Free aur pro DONO yahan aa sakte hain — yeh sirf "logged-in?" check karta hai,
    plan ki parwah nahi. (Auth, not authz.)
    """
    return {"user": claims}


@app.get("/premium")
def premium(claims: dict = Depends(require_pro)):
    """PAID route: plan=='pro' chahiye (warna 403). Yahi 'subscription gating' hai.

    Imagine: yahan asli premium AI feature hota (e.g. get_client() se ek fancy
    model call). Free user ko yeh kabhi nahi milega — entitlement backend par
    enforce hota hai, frontend par sirf 'hide' (security frontend par nahi hoti).
    """
    return {
        "message": "premium AI feature unlocked",
        "user": claims.get("sub"),
        "plan": claims.get("plan"),
    }


# ===========================================================================
# PART 4 — Self-demo (DEFAULT run) : apni hi routes ko TestClient se call karo
# ===========================================================================
# TestClient FastAPI app ko IN-PROCESS chalata hai (koi real server/port nahi,
# koi network nahi) — isliye yeh fast hai aur kabhi hang nahi karta. Perfect for
# CI / "uv run <file>" wala self-check.
def run_self_demo() -> int:
    from fastapi.testclient import TestClient

    print("\n" + "#" * 72)
    print("#  LAB 4 — Auth + Subscription Gating (backend) : SELF-DEMO")
    print("#  (no API key, no network — pure stdlib JWT + FastAPI TestClient)")
    print("#" * 72 + "\n")

    client = TestClient(app)

    # --- Step A: do tokens MINT karo (ek free, ek pro) ----------------------
    print("=" * 72)
    print("STEP A — Mint tokens (issuer = hamari demo /token route)")
    print("=" * 72)
    free_token = make_token({"sub": "u_free", "plan": "free"}, JWT_SECRET)
    pro_token = make_token({"sub": "u_pro", "plan": "pro"}, JWT_SECRET)
    print(f"free token (first 40 chars): {free_token[:40]}...")
    print(f"pro  token (first 40 chars): {pro_token[:40]}...")
    # Quick sanity: verify karke dikhao ki claims wapas wahi nikalte hain.
    print(f"verify(free).plan = {verify_token(free_token, JWT_SECRET)['plan']!r}")
    print(f"verify(pro ).plan = {verify_token(pro_token, JWT_SECRET)['plan']!r}")
    print()

    free_hdr = {"Authorization": f"Bearer {free_token}"}
    pro_hdr = {"Authorization": f"Bearer {pro_token}"}

    # --- Step B: gating matrix — expected status codes verify karo -----------
    print("=" * 72)
    print("STEP B — Hit routes & assert gating behaviour")
    print("=" * 72)

    checks = []  # (label, actual_status, expected_status)

    # /premium WITHOUT token => 401 (no auth at all).
    r = client.get("/premium")
    print(f"GET /premium  (no token)   -> {r.status_code}  expect 401  | {r.json()}")
    checks.append(("no-token /premium", r.status_code, 401))

    # /premium WITH FREE token => 403 (authenticated but not entitled).
    r = client.get("/premium", headers=free_hdr)
    print(f"GET /premium  (free token) -> {r.status_code}  expect 403  | {r.json()}")
    checks.append(("free /premium", r.status_code, 403))

    # /premium WITH PRO token => 200 (entitled).
    r = client.get("/premium", headers=pro_hdr)
    print(f"GET /premium  (pro token)  -> {r.status_code}  expect 200  | {r.json()}")
    checks.append(("pro /premium", r.status_code, 200))

    # /me WITH FREE token => 200 (auth only, plan irrelevant).
    r = client.get("/me", headers=free_hdr)
    print(f"GET /me       (free token) -> {r.status_code}  expect 200  | {r.json()}")
    checks.append(("free /me", r.status_code, 200))

    # Bonus: tampered token => 401 (signature check ka demo).
    tampered = pro_token[:-3] + ("aaa" if not pro_token.endswith("aaa") else "bbb")
    r = client.get("/premium", headers={"Authorization": f"Bearer {tampered}"})
    print(f"GET /premium  (tampered)   -> {r.status_code}  expect 401  | {r.json()}")
    checks.append(("tampered /premium", r.status_code, 401))

    # Bonus: expired token => 401 (exp check ka demo). expires_in negative => already expired.
    expired = make_token({"sub": "u_exp", "plan": "pro"}, JWT_SECRET, expires_in=-1)
    r = client.get("/me", headers={"Authorization": f"Bearer {expired}"})
    print(f"GET /me       (expired)    -> {r.status_code}  expect 401  | {r.json()}")
    checks.append(("expired /me", r.status_code, 401))

    print()

    # --- Step C: summary + exit code ----------------------------------------
    print("=" * 72)
    print("STEP C — Summary")
    print("=" * 72)
    all_ok = True
    for label, actual, expected in checks:
        ok = (actual == expected)
        all_ok = all_ok and ok
        mark = "PASS" if ok else "FAIL"
        print(f"  [{mark}] {label:24s} got {actual}, expected {expected}")
    print()

    if all_ok:
        print(">>> AHA MOMENT: client NEVER trusted. plan ek SIGNED claim hai —")
        print("    backend signature verify karta hai, phir plan se feature gate karta")
        print("    hai. 401 = pehchaan nahi; 403 = pehchaan hai par subscription nahi.")
        print(">>> Yahi backend half hai us Clerk + Billing flow ka jo course mein dikha.")
    else:
        print(">>> Kuch check fail hua — upar dekho.")

    print("\n" + "#" * 72)
    print("#  LAB 4 self-demo complete.")
    print("#" * 72 + "\n")

    # CI-friendly exit code: sab pass => 0, warna 1. (Prompt: self-demo exit 0.)
    return 0 if all_ok else 1


# ---------------------------------------------------------------------------
# RUNBOOK — asli Clerk frontend + webhook flow (production reference)
# ---------------------------------------------------------------------------
# Yeh comment hi runbook hai (course ka asli flow, backend dev ke liye):
#
# 1) FRONTEND (Next.js, course L15-L16):
#    - App ko <ClerkProvider> mein wrap karo. <SignedIn>/<SignedOut> se UI gate.
#    - User sign-in karta hai -> Clerk ek SHORT-LIVED session JWT (RS256) deta hai.
#    - Frontend us JWT ko backend request ke Authorization: Bearer header mein bhejta hai.
#
# 2) BACKEND (FastAPI, course L16 + YEH LAB):
#    - Clerk ke JWKS URL (.well-known/jwks.json) se PUBLIC keys fetch (cache) karo.
#    - Har request par JWT verify karo (signature + exp). Course mein
#      `Depends(clerk_auth)` yahi karta tha; humne require_user mein haath se kiya.
#    - claims["sub"] = user id; claims mein plan/feature entitlement bhi aata hai.
#
# 3) BILLING / SUBSCRIPTION (course L17-L18):
#    - Clerk Billing (ya Stripe) mein plan banao: key e.g. `premium_subscription`
#      (underscore, hyphen nahi). User subscribe/pay karta hai.
#    - Subscription active hote hi Clerk token mein plan/feature claim inject karta hai.
#    - WEBHOOK: jab subscription create/cancel/payment-fail ho, Clerk tumhare backend
#      ko webhook event bhejta hai (HMAC-signed — webhook signature bhi verify karni
#      hai, bilkul JWT jaisa!). Tum apne DB mein entitlement sync/update kar sakte ho,
#      aur token refresh hone par naya plan claim aa jaata hai.
#    - Backend route premium feature ko plan claim se gate karta hai (yahan require_pro).
#
# 4) GOLDEN RULE: client kabhi trust nahi. Frontend UI sirf "hide" karta hai;
#    asli security backend par signed-token verify + claim check se hoti hai.
#
# --serve mode mein curl examples:
#   PRO=$(curl -s -X POST 'http://127.0.0.1:8000/token?plan=pro' | python -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')
#   curl -s http://127.0.0.1:8000/premium                              # 401 (no token)
#   curl -s -H "Authorization: Bearer $PRO" http://127.0.0.1:8000/premium  # 200
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    # Default (no args) => self-demo (TestClient), exit code se result.
    # `--serve` => asli uvicorn server (browser/curl ke liye).
    if "--serve" in sys.argv:
        import uvicorn
        print("Serving on http://127.0.0.1:8000  (Ctrl+C to stop)")
        print("Try:  curl -X POST 'http://127.0.0.1:8000/token?plan=pro'")
        uvicorn.run(app, host="127.0.0.1", port=8000)
    else:
        raise SystemExit(run_self_demo())
