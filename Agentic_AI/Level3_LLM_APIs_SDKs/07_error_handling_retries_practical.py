"""
Level3 Doc07 — Error Handling & Retries (Production) — PRACTICAL LAB
======================================================================
KYA SEEKHENGE (What we learn):
  1. Common LLM errors — RateLimitError, APITimeoutError, ConnectionError, etc.
  2. Basic try-except pattern — har error ko alag handle karna
  3. Tenacity se production-grade retry logic — exponential backoff
  4. Jitter add karna — thundering herd problem se bachna
  5. Error-specific strategy — kya retry karna, kya nahi
  6. Retry-after header respect karna — 429 pe smart sleep
  7. Timeout configuration — global aur per-call
  8. Circuit Breaker pattern — repeatedly failing API ko rest dena
  9. Fallback models — primary fail ho toh backup use karna
 10. Graceful degradation — user ko hamesha kuch na kuch milna chahiye
 11. Structured error logging — debugging ke liye context save karna

KAISE CHALANA (How to run):
  # No API key chahiye — self-demo offline chalega, EXIT 0 guaranteed
  uv run /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/Level3_LLM_APIs_SDKs/07_error_handling_retries_practical.py

  # Live Groq calls ke liye:
  GROQ_API_KEY=gsk_xxx uv run ...

NOTE: Sab sections offline bhi run hote hain — mock data se gracefully degrade karte hain.
"""

import os
import sys
import time
import random
import logging
import asyncio
from typing import Optional, List, Dict, Any

# ─── Logging setup — structured context ke saath ────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("error_handling_lab")

# ─── GROQ_API_KEY check — placeholder se OpenAI() crash nahi karega ─────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY") or "placeholder"
LIVE_MODE = os.getenv("GROQ_API_KEY") is not None  # True sirf jab real key ho

# ─── OpenAI client factory — Groq OpenAI-compatible endpoint use karta hai ──
from openai import (
    OpenAI,
    RateLimitError,
    APITimeoutError,
    APIConnectionError,
    AuthenticationError,
    BadRequestError,
    NotFoundError,
    InternalServerError,
)

def get_client() -> OpenAI:
    """
    Groq ka OpenAI-compatible client return karo.
    api_key=placeholder se object banta hai — actual call pe fail karega.
    Isse import/construction time pe crash nahi hoga.
    """
    return OpenAI(
        api_key=GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1",
        timeout=30.0,  # global timeout — theory section 7
    )


# ─── Tenacity import — production retry library ──────────────────────────────
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    wait_random_exponential,
    retry_if_exception_type,
    retry_any,
    before_sleep_log,
    RetryError,
)

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Common LLM Errors ka DEMO
# Theory ref: Doc07 Section 1 — error table
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 65)
print("ERROR HANDLING & RETRIES — PRACTICAL LAB (Level3 Doc07)")
print("=" * 65)

print("""
SECTION 1: Common LLM Errors
------------------------------
Ye errors production mein sabse zyada milte hain:

  RateLimitError (429)      — bahut zyada requests, slow down karo
  APITimeoutError           — response aaya nahi time pe
  APIConnectionError        — network issue, connection hi nahi bana
  InternalServerError (500) — provider ka server side problem
  BadRequestError (400)     — hamari request galat thi (fix karo, retry mat)
  AuthenticationError (401) — API key galat hai (retry nahi karega)
  NotFoundError (404)       — model exist nahi karta (retry nahi karega)

Production mein sabse common: 429 aur 500.
Retry karo: 429, 500, timeout, connection.
Retry MAT karo: 400, 401, 403, 404, 422.
""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Basic try-except pattern
# Theory ref: Doc07 Section 2
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 65)
print("SECTION 2: Basic try-except — Har error alag handle karo")
print("=" * 65)

def safe_llm_call(messages: List[Dict], model: str = "llama-3.1-8b-instant") -> Optional[str]:
    """
    Basic try-except wala safe call.
    Theory Doc07 S2 — yahi sabse pehle banana chahiye.

    Har error type alag handle hota hai:
    - RateLimitError  -> retry-after header se wait ka time pta chalega
    - APITimeoutError -> network slow tha, dubara try kar sakte hain
    - APIConnectionError -> internet ya DNS issue
    - Exception       -> unknown — log karo aur None return karo
    """
    if not LIVE_MODE:
        # OFFLINE MODE — placeholder se actual call crash karega, fake return
        logger.info("safe_llm_call: OFFLINE mode — mock response return ho raha hai")
        return "[MOCK] Yeh offline mock response hai. Real Groq call ke liye GROQ_API_KEY set karo."

    client = get_client()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            timeout=15,  # per-call timeout — theory S7
        )
        return response.choices[0].message.content

    except RateLimitError as e:
        # 429 — retry-after header se pata chalega kitna wait karna hai
        retry_after = float(
            getattr(getattr(e, "response", None), "headers", {}).get("retry-after", 60)
        )
        logger.warning(
            "Rate limit hit (429). Retry after: %.1fs", retry_after,
            extra={"error_type": "RateLimitError"}
        )
        return None

    except APITimeoutError:
        # Network slow tha — transient error, dobara try kar sakte hain
        logger.warning("Timeout hua. Dobara try karo.", extra={"error_type": "APITimeoutError"})
        return None

    except APIConnectionError as e:
        # Network issue — internet down ya DNS fail
        logger.warning("Connection error: %s", str(e)[:80], extra={"error_type": "APIConnectionError"})
        return None

    except AuthenticationError:
        # API key galat — retry se kuch nahi hoga
        logger.error("Authentication fail! GROQ_API_KEY check karo.", extra={"error_type": "AuthenticationError"})
        return None

    except BadRequestError as e:
        # Hamari galti — request fix karo
        logger.error("Bad request (400): %s", str(e)[:120], extra={"error_type": "BadRequestError"})
        return None

    except Exception as e:
        # Kuch bhi unexpected
        logger.error(
            "Unknown error: %s — %s", type(e).__name__, str(e)[:100],
            extra={"error_type": type(e).__name__}
        )
        return None


result = safe_llm_call([{"role": "user", "content": "Hello, kya tum theek ho?"}])
print(f"  safe_llm_call result: {result}")
print()

# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Tenacity se Retry with Exponential Backoff
# Theory ref: Doc07 Section 3
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 65)
print("SECTION 3: Tenacity — Production-grade Retry Logic")
print("=" * 65)

print("""
Tenacity kya karta hai:
  @retry decorator lagao — automatic retry milega.
  stop_after_attempt(5)  — max 5 baar try karega.
  wait_exponential       — har retry pe double wait: 2s, 4s, 8s, 16s, 32s (max 60s).
  retry_if_exception_type — sirf in errors pe retry: RateLimitError, Timeout, Connection.
  reraise=True           — agar sab try khatam, original error uthao.
  before_sleep_log       — har retry pe log karo (debugging ke liye).
""")

# Retry karne layak errors — theory S5
RETRYABLE_ERRORS = (RateLimitError, APITimeoutError, APIConnectionError, InternalServerError)


@retry(
    retry=retry_if_exception_type(RETRYABLE_ERRORS),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    reraise=True,
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def robust_llm_call(messages: List[Dict], model: str = "llama-3.1-8b-instant") -> str:
    """
    Tenacity wala robust call — transient errors pe auto retry.
    Theory Doc07 Section 3 — yahi production standard hai.

    Retry schedule (approximate):
      Attempt 1 — immediate
      Attempt 2 — 2s wait
      Attempt 3 — 4s wait
      Attempt 4 — 8s wait
      Attempt 5 — 16s wait (max 60s)
    """
    if not LIVE_MODE:
        # Offline mein fake success — retry mechanism demo karo alag se
        return "[MOCK] robust_llm_call offline mock response."

    client = get_client()
    return client.chat.completions.create(
        model=model,
        messages=messages,
        timeout=30,
    ).choices[0].message.content


# Retry mechanism ka offline demo — actual sleep nahi karega
def demo_retry_mechanism():
    """
    Retry ke concept ko simulate karte hain bina actual wait ke.
    Theory S3 — exponential backoff schedule dikhana.
    """
    print("  Exponential backoff schedule (theory S3):")
    multiplier, min_wait, max_wait = 1, 2, 60
    for attempt in range(1, 6):
        wait = min(multiplier * (2 ** (attempt - 1)) * min_wait, max_wait)
        actual = min(wait, max_wait)
        print(f"    Attempt {attempt}: wait = {actual:.0f}s (agar fail ho)")
    print()


demo_retry_mechanism()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Jitter — Thundering Herd Problem se Bachna
# Theory ref: Doc07 Section 4
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 65)
print("SECTION 4: Jitter — Thundering Herd Problem")
print("=" * 65)

print("""
Problem:
  Agar 100 clients saath mein fail ho jaayein, aur sab ek saath retry karein,
  server dobara overwhelm ho jaata hai. Yahi hai "thundering herd".

Solution — Jitter:
  Har retry mein thoda random wait add karo.
  wait_exponential + wait_random_exponential(min=0, max=2)
  Isse sab alag-alag time pe retry karte hain.
""")


def simulate_jitter_demo():
    """
    Jitter ke saath aur bina jitter ke wait times dikhao.
    Theory S4 — visual comparison.
    """
    print("  Without jitter (sab ek saath retry — bad!):")
    for client_id in range(1, 4):
        wait = 4  # Attempt 2: sab ka same 4s
        print(f"    Client {client_id}: wait = {wait:.2f}s  <- sab saath aate hain!")

    print()
    print("  With jitter (alag-alag time pe retry — good!):")
    random.seed(42)
    for client_id in range(1, 4):
        base_wait = 4
        jitter = random.uniform(0, 2)
        total = base_wait + jitter
        print(f"    Client {client_id}: base={base_wait}s + jitter={jitter:.2f}s = {total:.2f}s")

    print()


simulate_jitter_demo()


@retry(
    retry=retry_if_exception_type(RETRYABLE_ERRORS),
    stop=stop_after_attempt(5),
    # wait_exponential + random jitter — theory S4
    wait=wait_exponential(multiplier=1, min=2, max=60) + wait_random_exponential(min=0, max=2),
    reraise=True,
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
def robust_llm_call_with_jitter(messages: List[Dict], model: str = "llama-3.1-8b-instant") -> str:
    """
    Jitter ke saath robust call — thundering herd se protected.
    Yahi production mein use karo.
    """
    if not LIVE_MODE:
        return "[MOCK] robust_llm_call_with_jitter — offline mock."

    client = get_client()
    return client.chat.completions.create(
        model=model,
        messages=messages,
        timeout=30,
    ).choices[0].message.content


print("  robust_llm_call_with_jitter function ready hai (jab GROQ_API_KEY set ho tab chalega).")
print()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Error-Specific Strategies
# Theory ref: Doc07 Section 5
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 65)
print("SECTION 5: Error-Specific Strategies")
print("=" * 65)

print("""
Har error pe alag strategy chahiye:

  RETRY karo (transient hain):
    - RateLimitError (429)       — slow ho jao, phir try karo
    - APITimeoutError            — dubara try karo
    - APIConnectionError         — network recover hoga shayad
    - InternalServerError (500)  — server side issue, thodi der baad theek hoga

  RETRY MAT karo (hamari ya permanent galti):
    - BadRequestError (400)      — request fix karo pehle
    - AuthenticationError (401)  — API key set karo
    - PermissionDeniedError (403)— account issue, code fix nahi karega
    - NotFoundError (404)        — model name galat hai
    - UnprocessableEntityError (422) — content issue
""")


# retry_any se multiple error types specify karo — theory S5
@retry(
    retry=retry_any(
        retry_if_exception_type(RateLimitError),
        retry_if_exception_type(APITimeoutError),
        retry_if_exception_type(APIConnectionError),
        retry_if_exception_type(InternalServerError),
    ),
    stop=stop_after_attempt(4),
    wait=wait_exponential(min=2, max=30),
    reraise=True,
)
def strategy_aware_call(messages: List[Dict], model: str = "llama-3.1-8b-instant") -> str:
    """
    Error-specific retry strategy.
    BadRequestError / AuthenticationError pe retry nahi karega kyunki
    unhe @retry decorator ke bahar rakh diya hai — wo errors uthenge aur
    seedha caller tak jaayenge.
    """
    if not LIVE_MODE:
        return "[MOCK] strategy_aware_call offline."

    client = get_client()
    return client.chat.completions.create(
        model=model,
        messages=messages,
        timeout=30,
    ).choices[0].message.content


# Demo: different error types simulate karo
class MockRateLimitError(Exception):
    pass


def classify_error_strategy():
    """Har error type ke liye retry decision dikhao."""
    errors = [
        ("RateLimitError (429)", True, "Server ne slow down karne ko kaha — retry karein"),
        ("APITimeoutError", True, "Network slow tha — ek baar aur try karein"),
        ("APIConnectionError", True, "Network drop hua — dobara connect karo"),
        ("InternalServerError (500)", True, "Server side issue — thodi der baad retry"),
        ("BadRequestError (400)", False, "Hamari request galat thi — code fix karo"),
        ("AuthenticationError (401)", False, "API key check karo — retry useless hai"),
        ("NotFoundError (404)", False, "Model exist nahi karta — name fix karo"),
    ]
    print("  Error          | Retry? | Reason")
    print("  " + "-" * 60)
    for name, should_retry, reason in errors:
        icon = "YES" if should_retry else "NO "
        print(f"  {name:<30} | {icon}   | {reason[:35]}")
    print()


classify_error_strategy()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Retry-After Header Respect Karna
# Theory ref: Doc07 Section 6
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 65)
print("SECTION 6: Retry-After Header — 429 pe Smart Sleep")
print("=" * 65)

print("""
Jab 429 aaye, OpenAI/Groq response mein header deta hai:
  retry-after: 23        <- itne seconds baad try karo

Agar hum random sleep karte hain, kabhi zyada kabhi kam.
Header read karo aur theek utna wait karo + thoda jitter.

x-ratelimit-remaining-requests: 0    <- limit khatam
x-ratelimit-reset-requests: 1m23s   <- kab reset hoga
""")


def smart_retry_on_429(messages: List[Dict], model: str = "llama-3.1-8b-instant",
                       max_retries: int = 3) -> Optional[str]:
    """
    429 pe header se retry-after read karo — theory S6.
    Yahi sabse respectful aur effective approach hai.
    """
    if not LIVE_MODE:
        logger.info("smart_retry_on_429: OFFLINE — mock return")
        return "[MOCK] smart retry offline."

    client = get_client()
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                timeout=30,
            )
            return response.choices[0].message.content

        except RateLimitError as e:
            # Header se exact wait time lena — theory S6
            headers = getattr(getattr(e, "response", None), "headers", {})
            retry_after = float(headers.get("retry-after", 60))
            jitter = random.uniform(0, 2)
            wait = retry_after + jitter

            logger.warning(
                "429 mila (attempt %d/%d). Retry-after header=%ss + jitter=%.1fs = %.1fs wait.",
                attempt + 1, max_retries, retry_after, jitter, wait,
            )
            time.sleep(wait)

        except (APITimeoutError, APIConnectionError) as e:
            # Exponential backoff for non-rate-limit transient errors
            wait = (2 ** attempt) * 2 + random.uniform(0, 1)
            logger.warning("Transient error (attempt %d): %s. Wait %.1fs.", attempt + 1, type(e).__name__, wait)
            time.sleep(wait)

    return None


print("  smart_retry_on_429 function ready. LIVE_MODE:", LIVE_MODE)
if not LIVE_MODE:
    demo_result = smart_retry_on_429([{"role": "user", "content": "test"}])
    print(f"  Result (offline): {demo_result}")
print()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Timeout Configuration
# Theory ref: Doc07 Section 7
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 65)
print("SECTION 7: Timeout Configuration")
print("=" * 65)

print("""
Do tarah ke timeouts hote hain:

  Global timeout — client banate waqt:
    client = OpenAI(timeout=30.0)  # sabhi calls pe 30s limit

  Per-call timeout — individual call pe:
    client.chat.completions.create(..., timeout=10)  # sirf is call pe 10s

  httpx.Timeout — fine-grained control (streaming ke liye):
    import httpx
    OpenAI(timeout=httpx.Timeout(
        timeout=60.0,    # total
        connect=10.0,    # connection establish hone ka time
        read=30.0,       # har chunk padhne ka time (streaming mein)
    ))

Production tip: 30s reasonable default hai.
Streaming ke liye read timeout zyada rakhna padta hai.
""")


def demo_timeout_configs():
    """Different timeout configs dikhao."""
    configs = [
        ("Global 30s", "OpenAI(timeout=30.0)"),
        ("Per-call 10s", "client.chat.completions.create(..., timeout=10)"),
        ("httpx detailed", "httpx.Timeout(timeout=60.0, connect=10.0, read=30.0)"),
        ("No timeout (BAD!)", "OpenAI()  # hang ho sakta hai!"),
    ]
    for name, code in configs:
        print(f"  {name:<22}: {code}")
    print()


demo_timeout_configs()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 8: Circuit Breaker Pattern
# Theory ref: Doc07 Section 10
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 65)
print("SECTION 8: Circuit Breaker — Failing API ko Rest Do")
print("=" * 65)

print("""
Problem:
  Agar API bar bar fail kar raha hai, hum baar baar uspe request kyun bhejein?
  Har call wasted hai aur user ko aur zyada wait karna padta hai.

Circuit Breaker Solution (teen states):
  CLOSED (normal) — calls allow hain. Failure count badh raha hai.
  OPEN   (tripped) — failures ne threshold cross kiya. Koi call nahi,
                     seedha error. Recovery time ke baad half-open hoga.
  HALF-OPEN       — ek test call allow karo. Success? -> CLOSED. Fail? -> OPEN.

Theory S10 ka direct implementation hai yeh.
""")


class CircuitBreaker:
    """
    Circuit Breaker pattern — theory Doc07 Section 10.
    Baar baar fail hone wale endpoint ko protection deta hai.
    """

    def __init__(self, threshold: int = 5, recovery_sec: float = 60.0):
        self.threshold = threshold        # kitni failures ke baad trip karna
        self.recovery_sec = recovery_sec  # kitne seconds baad half-open hona
        self.failures = 0
        self.open_until: Optional[float] = None  # Unix timestamp
        self._state = "CLOSED"

    @property
    def state(self) -> str:
        if self.open_until is None:
            return "CLOSED"
        if time.time() < self.open_until:
            return "OPEN"
        return "HALF-OPEN"

    def call(self, func, *args, **kwargs):
        """
        func ko circuit breaker ke andar call karo.
        OPEN state mein seedha exception raise karo.
        """
        state = self.state
        if state == "OPEN":
            remaining = self.open_until - time.time()
            raise RuntimeError(
                f"Circuit OPEN hai — {remaining:.0f}s aur wait karo. "
                f"API repeatedly fail ho raha tha."
            )

        try:
            result = func(*args, **kwargs)
            # SUCCESS — failures reset karo, circuit band karo
            if self.failures > 0:
                logger.info("Circuit: call success, failures reset.")
            self.failures = 0
            self.open_until = None
            return result

        except Exception as e:
            self.failures += 1
            logger.warning(
                "Circuit: failure %d/%d — %s",
                self.failures, self.threshold, type(e).__name__
            )
            if self.failures >= self.threshold:
                self.open_until = time.time() + self.recovery_sec
                self.failures = 0
                logger.error(
                    "Circuit TRIPPED! API ko %.0f seconds rest de raha hai.",
                    self.recovery_sec
                )
            raise

    def status(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "failures": self.failures,
            "threshold": self.threshold,
            "open_until": self.open_until,
        }


def demo_circuit_breaker():
    """Circuit breaker ka offline simulation."""
    print("  Circuit Breaker simulation (offline):")
    breaker = CircuitBreaker(threshold=3, recovery_sec=10.0)

    call_count = 0

    def flaky_api():
        nonlocal call_count
        call_count += 1
        if call_count <= 4:
            raise ConnectionError(f"Simulated connection failure #{call_count}")
        return "Success!"

    for i in range(7):
        try:
            result = breaker.call(flaky_api)
            print(f"    Call {i+1}: SUCCESS — {result} | State: {breaker.state}")
        except RuntimeError as re:
            # Circuit open — blocked
            print(f"    Call {i+1}: BLOCKED by circuit — {str(re)[:60]}")
        except ConnectionError as ce:
            # Actual failure passed through
            print(f"    Call {i+1}: FAILED — {str(ce)} | State: {breaker.state} | Failures: {breaker.failures}")

    print(f"  Final circuit status: {breaker.status()}")
    print()


demo_circuit_breaker()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 9: Fallback Models
# Theory ref: Doc07 Section 9
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 65)
print("SECTION 9: Fallback Models")
print("=" * 65)

print("""
Primary model fail ho jaye toh backup models try karo.
Theory S9 — model hierarchy se gracefully degrade karo.

Example:
  llama-3.1-70b-versatile  <- primary (powerful, expensive)
  llama-3.1-8b-instant     <- fallback 1 (faster, cheaper)
  gemma2-9b-it             <- fallback 2 (last resort on Groq)
  STATIC_RESPONSE          <- ultimate fallback (offline mock)
""")

GROQ_MODEL_FALLBACK_CHAIN = [
    "llama-3.1-70b-versatile",
    "llama-3.1-8b-instant",
    "gemma2-9b-it",
]

STATIC_FALLBACK_RESPONSE = (
    "System abhi temporarily unavailable hai. "
    "Please thodi der baad try karein."
)


def fallback_call(messages: List[Dict]) -> str:
    """
    Model fallback chain — theory S9.
    Pehle primary try karo, fail ho toh agle pe jao.
    Sab fail ho toh static response do — user ko kuch na kuch milna chahiye.
    """
    if not LIVE_MODE:
        logger.info("fallback_call: OFFLINE — direct static fallback")
        return STATIC_FALLBACK_RESPONSE

    client = get_client()
    for model in GROQ_MODEL_FALLBACK_CHAIN:
        try:
            logger.info("Trying model: %s", model)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                timeout=20,
            )
            logger.info("Success with model: %s", model)
            return response.choices[0].message.content

        except (RateLimitError, InternalServerError) as e:
            logger.warning("Model %s failed (%s), next try kar raha hoon.", model, type(e).__name__)
            continue

        except (BadRequestError, AuthenticationError, NotFoundError) as e:
            # Ye errors fallback se theek nahi honge
            logger.error("Non-retryable error on model %s: %s", model, type(e).__name__)
            break

    # Sab models fail — static response
    logger.error("Sab models fail ho gaye. Static fallback return ho raha hai.")
    return STATIC_FALLBACK_RESPONSE


result = fallback_call([{"role": "user", "content": "Aaj ka weather kaisa hai?"}])
print(f"  fallback_call result: {result}")
print()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 10: Graceful Degradation — User ko Hamesha Kuch Milna Chahiye
# Theory ref: Doc07 Section 11
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 65)
print("SECTION 10: Graceful Degradation")
print("=" * 65)

print("""
Rule: User ko hamesha KUCH NA KUCH milna chahiye.
  Level 1 — Full RAG pipeline (ideal)
  Level 2 — Simple chat (degraded)
  Level 3 — Cached response (more degraded)
  Level 4 — Static message (last resort)

Har level pe user ko inform karo ki kya chal raha hai.
Theory S11 ka direct implementation.
""")


class LLMError(Exception):
    pass


def full_rag_pipeline(query: str) -> str:
    """Level 1 — pura RAG pipeline (vector search + LLM)."""
    if not LIVE_MODE:
        raise LLMError("OFFLINE: RAG pipeline skip")
    # Real implementation yahaan hogi
    raise LLMError("RAG pipeline demo error")


def simple_chat(query: str) -> str:
    """Level 2 — sirf basic LLM call."""
    if not LIVE_MODE:
        raise LLMError("OFFLINE: simple chat skip")
    client = get_client()
    return client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[{"role": "user", "content": query}],
        timeout=15,
    ).choices[0].message.content


RESPONSE_CACHE: Dict[str, str] = {
    "weather": "Weather information abhi available nahi hai.",
    "help": "Help ke liye support@example.com pe email karein.",
}


def cached_response(query: str) -> Optional[str]:
    """Level 3 — cached response se serve karo."""
    query_lower = query.lower()
    for keyword, response in RESPONSE_CACHE.items():
        if keyword in query_lower:
            return f"[CACHED] {response}"
    return None


def serve_user(query: str) -> str:
    """
    Graceful degradation chain — theory S11.
    User ko hamesha kuch na kuch milta hai.
    """
    # Level 1: Full pipeline
    try:
        result = full_rag_pipeline(query)
        return f"[FULL] {result}"
    except LLMError as e:
        logger.warning("RAG pipeline fail: %s. Level 2 try...", str(e)[:40])

    # Level 2: Simple chat
    try:
        result = simple_chat(query)
        return f"[SIMPLE] {result}"
    except LLMError as e:
        logger.warning("Simple chat fail: %s. Level 3 try...", str(e)[:40])

    # Level 3: Cache
    cached = cached_response(query)
    if cached:
        logger.info("Cache hit for query.")
        return cached

    # Level 4: Static fallback — hamesha milega
    logger.error("Sab levels fail. Static response de rahe hain.")
    return "Hum abhi technical issues face kar rahe hain. Thodi der mein try karein. Shukriya aapki patience ke liye!"


test_queries = [
    "Aaj ka mausam kaisa hai?",  # cache hit nahi -> static
    "Help chahiye mujhe",         # cache hit -> cached response
    "Tell me about AI",           # -> static fallback
]
print("  Graceful degradation demo:")
for q in test_queries:
    result = serve_user(q)
    print(f"    Q: {q!r}")
    print(f"    A: {result[:80]}")
    print()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 11: Structured Error Logging
# Theory ref: Doc07 Section 12
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 65)
print("SECTION 11: Structured Error Logging")
print("=" * 65)

print("""
Production mein sirf print nahi karte.
Structured logging use karo:
  - error_type   : konsa error tha
  - request_id   : OpenAI/Groq ka unique ID (debugging ke liye)
  - retry_count  : kitni baar try kiya
  - model        : konsa model use kiya
  - latency_ms   : kitna time laga

Isse production mein easily grep/filter kar sakte hain.
""")


def llm_call_with_structured_logging(
    messages: List[Dict],
    model: str = "llama-3.1-8b-instant",
    request_label: str = "unknown",
) -> Optional[str]:
    """
    Structured logging ke saath LLM call — theory S12.
    Har error pe context ke saath log karo.
    """
    if not LIVE_MODE:
        logger.info(
            "Structured log demo (offline)",
            extra={"request_label": request_label, "mode": "offline"}
        )
        return "[MOCK] structured logging offline demo."

    client = get_client()
    start = time.time()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            timeout=30,
        )
        latency_ms = (time.time() - start) * 1000
        logger.info(
            "LLM call success",
            extra={
                "request_label": request_label,
                "model": model,
                "latency_ms": round(latency_ms, 1),
                "usage_tokens": getattr(response.usage, "total_tokens", None),
            }
        )
        return response.choices[0].message.content

    except RateLimitError as e:
        logger.warning(
            "Rate limit hit",
            extra={
                "request_label": request_label,
                "error_type": "RateLimitError",
                "request_id": getattr(e, "request_id", None),
                "retry_after": getattr(getattr(e, "response", None), "headers", {}).get("retry-after"),
            }
        )
        raise

    except Exception as e:
        latency_ms = (time.time() - start) * 1000
        logger.error(
            "LLM call failed",
            extra={
                "request_label": request_label,
                "error_type": type(e).__name__,
                "error_msg": str(e)[:100],
                "latency_ms": round(latency_ms, 1),
                "model": model,
            },
            exc_info=False,  # stack trace only agar zarurat ho
        )
        raise


result = llm_call_with_structured_logging(
    [{"role": "user", "content": "Structured logging test."}],
    request_label="demo_section11"
)
print(f"  Result: {result}")
print()


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 12: Async Error Handling
# Theory ref: Doc07 Section 8
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 65)
print("SECTION 12: Async Error Handling — Parallel Calls")
print("=" * 65)

print("""
Async LLM calls mein errors alag handle hoti hain:
  asyncio.gather(*tasks, return_exceptions=True)
  <- har task ka result ya Exception object milta hai

Isse ek fail hone se baaki sab nahi rukein.
Individual results check karo — success vs failure alag karo.
Theory S8.
""")


async def async_safe_llm_call(
    messages: List[Dict],
    model: str = "llama-3.1-8b-instant",
    label: str = "task",
) -> str:
    """
    Async safe call — offline mein mock, live mein real call.
    Tenacity async ke saath bhi kaam karta hai.
    """
    if not LIVE_MODE:
        # Simulate variable delay
        await asyncio.sleep(random.uniform(0.01, 0.05))
        if "fail" in label:
            raise ConnectionError(f"Simulated async error in {label}")
        return f"[MOCK async] Response for {label}"

    from openai import AsyncOpenAI
    async_client = AsyncOpenAI(
        api_key=GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1",
        timeout=30.0,
    )
    response = await async_client.chat.completions.create(
        model=model,
        messages=messages,
    )
    return response.choices[0].message.content


async def parallel_safe_calls(prompts: List[str]) -> Dict[str, Any]:
    """
    Multiple prompts ko parallel mein call karo.
    return_exceptions=True — ek fail hone se baaki nahi rukein.
    Theory S8.
    """
    labels = [f"task_{i}" for i in range(len(prompts))]

    # Kuch labels mein "fail" daalo taaki error demo ho sake (offline mein)
    if not LIVE_MODE:
        labels[1] = "task_1_fail"  # second call fail hoga demo ke liye

    tasks = [
        async_safe_llm_call(
            [{"role": "user", "content": p}],
            label=labels[i]
        )
        for i, p in enumerate(prompts)
    ]

    # return_exceptions=True — Exception object milta hai, crash nahi
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    successes = []
    failures = []
    for prompt, result in zip(prompts, raw_results):
        if isinstance(result, Exception):
            failures.append({"prompt": prompt, "error": type(result).__name__, "msg": str(result)[:60]})
        else:
            successes.append({"prompt": prompt, "result": result[:60]})

    return {"successes": successes, "failures": failures}


async def run_async_demo():
    prompts = [
        "Python kya hai?",
        "Error handling kyun zaroori hai?",
        "Async kab use karna chahiye?",
    ]
    print("  Parallel async calls chal rahe hain...")
    start = time.time()
    results = await parallel_safe_calls(prompts)
    elapsed = time.time() - start

    print(f"  Completed in {elapsed:.3f}s")
    print(f"  Successes ({len(results['successes'])}):")
    for s in results["successes"]:
        print(f"    - {s['prompt']!r}: {s['result']}")
    print(f"  Failures ({len(results['failures'])}):")
    for f in results["failures"]:
        print(f"    - {f['prompt']!r}: {f['error']} — {f['msg']}")
    print()


asyncio.run(run_async_demo())


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 13: Live Call Demo (sirf LIVE_MODE mein)
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 65)
print("SECTION 13: Live Groq Call Demo")
print("=" * 65)

if LIVE_MODE:
    print("  LIVE MODE detect hua. Real Groq call kar raha hoon...")
    try:
        live_result = robust_llm_call_with_jitter(
            [{"role": "user", "content": "Ek line mein batao: error handling kyun zaroori hai?"}],
            model="llama-3.1-8b-instant",
        )
        print(f"  Groq response: {live_result[:200]}")
    except RetryError as re:
        print(f"  Sab retries exhaust ho gayi: {re}")
    except Exception as e:
        print(f"  Live call failed: {type(e).__name__}: {e}")
else:
    print("  OFFLINE MODE (GROQ_API_KEY nahi set hua).")
    print("  Live demo skip ho raha hai.")
    print("  Real call ke liye: GROQ_API_KEY=gsk_xxx uv run ...")
print()


# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 65)
print("SUMMARY — Key Takeaways (Theory Doc07)")
print("=" * 65)
print("""
  1. try-except se shuru karo — har error type alag handle karo
  2. tenacity use karo production mein — @retry decorator
  3. Exponential backoff — 2s, 4s, 8s, 16s, 32s (max 60s)
  4. Jitter add karo — thundering herd se bachne ke liye
  5. Sirf transient errors retry karo — 429, 500, timeout, connection
  6. Retry-after header respect karo — 429 pe smart sleep
  7. Timeout set karo — 30s typical, httpx.Timeout for streaming
  8. Circuit Breaker — failing API ko rest do (threshold + recovery)
  9. Fallback models — primary fail -> backup use karo
 10. Graceful degradation — user ko hamesha KUCH milna chahiye
 11. Structured logging — error_type, request_id, latency_ms sab log karo
 12. Async mein return_exceptions=True — ek fail se baaki nahi rukein
""")

print("  Lab complete! EXIT 0.")
