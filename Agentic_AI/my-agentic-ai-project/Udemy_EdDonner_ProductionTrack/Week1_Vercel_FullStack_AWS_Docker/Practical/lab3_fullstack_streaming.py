"""
LAB 3 — Full-stack streaming (token-by-token LLM ko browser tak SSE se push karna)
==================================================================================

KYA SEEKHENGE (what we learn here):
- FRONTEND <-> BACKEND separation: ek hi file me dono dikhayenge — backend
  (FastAPI) jo LLM call karta hai + secrets rakhta hai, aur frontend (browser
  ka HTML+JS) jo us backend ke endpoint ko hit karke UI update karta hai.
- STREAMING kyun matter karta hai (UX angle): LLM (khaaskar bade "thinking"
  models) slow hote hain. Agar hum pura response generate hone ka wait karein
  to user ko 5-10 sec tak khaali screen dikhti hai = bura feel. Token-by-token
  stream karne se PERCEIVED LATENCY girti hai — pehla word turant aata hai,
  user ko lagta hai app "alive" hai. (Total time same, par feeling fast.)
- SSE (Server-Sent Events) kaise kaam karta hai: ek long-lived HTTP connection
  par server client ko chunks PUSH karta rehta hai. Wire format simple hai —
  har event ek line: `data: <chunk>\n\n` (do newline = ek event ka end).
  Browser ka `EventSource` API isko natively parse karta hai.
- FastAPI ka `StreamingResponse` + OpenAI ka `stream=True`: ek Python generator
  (jo `yield` karta hai) ko StreamingResponse me wrap karte hain; FastAPI use
  chunked-transfer-encoding se client tak bhejta hai. Yeh exactly wahi pattern
  hai jo Ed L14 me sikhaata hai.
- NEXT.JS/REACT mapping: yahan hum vanilla HTML+JS use kar rahe hain (intuition
  ke liye, L09 ka "Tier 1" vanilla approach). Real course me frontend ek alag
  Next.js app hota hai jo isi tarah ke FastAPI `/api/...` endpoint ko fetch-stream
  karta hai. Runbook (neeche COST/notes) batayega ki Next.js ko kaise wire karna.

KAISE CHALANA (how to run):
    # Default-safe self-demo (NO API key zaroori) — TestClient se apne hi routes
    # call karke streamed tokens print karta hai, phir EXIT 0:
    uv run Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/lab3_fullstack_streaming.py

    # Real server launch (browser/curl ke liye) — http://127.0.0.1:8000 par kholo:
    uv run Udemy_EdDonner_ProductionTrack/Week1_Vercel_FullStack_AWS_Docker/Practical/lab3_fullstack_streaming.py --serve

LECTURE MAPPING:
- Ed Donner "AI Engineer Production Track", Week 1 · Day 2.
- L09 (Frontend/Backend architecture: JSON-API vs full-page serve),
  L10 (React/FastAPI/Next.js stack), L12 (first FastAPI backend `api/index.py`),
  L13 (deploying full-stack Next.js + FastAPI), L14 (real-time streaming with
  SSE: `stream=True` + `StreamingResponse`, professional UI). Yeh lab L14 ka
  streaming core hai, ek self-contained chhote full-stack ke roop me.

COST:
- YEH LAB LOCAL PAR FREE hai. No-key path (default) bilkul $0 — fake token
  generator offline chalta hai. With-key path Groq (llama-3.3-70b) use karta hai
  jo free-tier/zero-cost + fast hai (Ed ka recommended cheap provider).
- CLOUD DEPLOY (runbook): is app ka Next.js+FastAPI version Vercel par deploy
  karna hobby-tier par effectively FREE hota hai (small traffic). AWS path (L23+:
  ECR + App Runner) par App Runner ~$5-25/month idle-to-light range me aata hai
  (provisioned container 24x7 chalta hai), plus LLM token cost alag. Matlab:
  streaming mechanics free me seekho, deploy choice (Vercel free vs AWS paid)
  Week 1 ke aage decide hota hai.
"""

import os
import sys

from dotenv import load_dotenv
from openai import OpenAI

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse

# .env load — override=True => .env wali value shell ki purani value ko jeet legi
# (Ed isi convention ko follow karta hai taaki keys predictably load hon).
load_dotenv(override=True)


# ---------------------------------------------------------------------------
# get_client: provider ke hisaab se (client, model_name) return karta hai.
# Groq aur Gemini dono OpenAI-compatible hain — bas base_url alag hota hai,
# isliye hum ek hi `openai` SDK se teeno ke saath baat kar sakte hain.
# File ko SELF-CONTAINED rakhne ke liye yeh helper yahin inline define kiya hai
# (course ki strict convention — naya helper invent mat karo).
# ---------------------------------------------------------------------------
def get_client(provider: str = "groq"):
    """(client, model) return karta hai. Default groq => zero cost, fast, OpenAI-compatible."""
    if provider == "groq":
        return OpenAI(base_url="https://api.groq.com/openai/v1",
                      api_key=os.getenv("GROQ_API_KEY") or "placeholder"), "llama-3.3-70b-versatile"
    if provider == "gemini":
        return OpenAI(base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                      api_key=os.getenv("GOOGLE_API_KEY") or "placeholder"), "gemini-2.5-flash"
    raise ValueError(f"Unknown provider: {provider}")


# ---------------------------------------------------------------------------
# FAKE token generator (no-key / offline fallback)
# ---------------------------------------------------------------------------
# WHY: is course ka core sabak streaming MECHANICS hai — "tokens browser tak
# kaise pahunchte hain" — na ki LLM ki intelligence. Agar GROQ_API_KEY nahi hai
# to bhi reader ko streaming dikhni chahiye. Isliye hum ek canned sentence ke
# words ko ek-ek karke yield karte hain. NOTE: yahan koi sleep() nahi hai —
# self-demo (TestClient) ko kabhi hang nahi karna chahiye, instantly finish ho.
# (Real server me chaaho to artificial delay daal sakte ho "typewriter" feel ke
#  liye, par lab ki default-safe path fast + deterministic rehni chahiye.)
def fake_token_stream(prompt: str):
    """Ek canned jawaab ke words ek-ek karke yield karta hai (no LLM, no key)."""
    canned = (
        f"[FAKE-MODE] No GROQ_API_KEY mila, isliye offline demo chal raha hai. "
        f"Aapne poocha: '{prompt}'. Streaming aise kaam karta hai: server har "
        f"token ko alag-alag bhejta hai, aur browser use turant screen par "
        f"append kar deta hai jaise jaise aata hai. Yahi perceived-latency win hai."
    )
    # split() se words milte hain; har word ke baad space wapas jod dete hain
    # taaki client side par join karne par sentence sahi bane.
    for word in canned.split():
        yield word + " "


# ---------------------------------------------------------------------------
# REAL token generator (with-key path) — OpenAI-compatible stream=True
# ---------------------------------------------------------------------------
# WHY stream=True: normally API pura response ek saath deta hai. stream=True
# bolne par API ek LAZY ITERATOR deta hai — hum `for chunk in completion` se
# use consume karte hain, har chunk me ek chhota `delta` (naya text-piece) hota
# hai. Hum pura response buffer nahi karte => memory-efficient + token turant
# forward kar paate hain. Yahi L14 ka exact pattern hai.
def real_token_stream(prompt: str):
    """Groq (OpenAI-compatible) se ek chhota completion token-by-token yield karta hai."""
    client, model = get_client("groq")
    completion = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are concise. Reply in 2-3 short sentences."},
            {"role": "user", "content": prompt},
        ],
        stream=True,          # <-- yahi switch hai: token-by-token mode ON
        temperature=0.7,
        max_tokens=200,       # chhota cap => demo fast + sasta
    )
    for chunk in completion:
        # delta.content kabhi None ho sakta hai (e.g. role-only opening chunk),
        # isliye `or ""` se guard karte hain warna "None" concat ho jaayega.
        delta = chunk.choices[0].delta.content or ""
        if delta:
            yield delta


# ---------------------------------------------------------------------------
# SSE wrapper: upar wale token generators ko SSE wire-format me badalta hai.
# ---------------------------------------------------------------------------
# SSE protocol bilkul simple text hai: har event ek ya zyada `field: value`
# lines, aur ek BLANK line (do `\n`) event ka end mark karti hai. Sabse common
# field `data:` hota hai. Hum har token ko `data: <token>\n\n` bana ke yield
# karte hain. Aakhir me ek sentinel `data: [DONE]\n\n` bhejte hain taaki client
# ko pata chale stream khatam — phir wo connection close kar sake.
#
# Edge case: agar token me khud newline ho to SSE spec ke hisaab se use multiple
# `data:` lines me todna chahiye. Demo simplicity ke liye hum yahan single-line
# tokens assume kar rahe hain (LLM deltas aksar chhote chunks hote hain).
def sse_event_stream(prompt: str):
    """Token generator (fake ya real) ko `data: ...\\n\\n` SSE events me convert karta hai."""
    # DEFAULT-SAFE decision: key hai? -> real, warna fake. Yeh check yahan hai
    # taaki har request fresh decide kare (key baad me set ho to restart bina kaam kare).
    key_present = bool(os.getenv("GROQ_API_KEY") or "placeholder")
    token_gen = real_token_stream(prompt) if key_present else fake_token_stream(prompt)

    try:
        for token in token_gen:
            # SSE event: client ka EventSource is `data:` payload ko event.data
            # me dega. Do newline (\n\n) = "event yahan khatam".
            yield f"data: {token}\n\n"
    except Exception as e:
        # Agar real call beech me fail ho (network/key/rate-limit), to crash mat
        # karo — ek error event bhej do taaki frontend graceful dikha sake.
        yield f"data: [ERROR] LLM call fail hui: {e}\n\n"
    finally:
        # Sentinel: frontend isse dekhke EventSource band kar dega.
        yield "data: [DONE]\n\n"


# ---------------------------------------------------------------------------
# Embedded frontend (vanilla HTML + JS). Yeh string GET `/` par serve hota hai.
# ---------------------------------------------------------------------------
# WHY embedded: L09 ka "Pattern 2 — backend serves a full web page" (SSR-style).
# Backend hi pura HTML bhej deta hai. Frontend logic vanilla JS hai (L09 Tier-1)
# taaki streaming ka mechanism naked dikhe — koi React magic chhupa nahi hai.
#
# JS side me hum EventSource use kar rahe hain — browser ka built-in SSE client.
# `new EventSource("/stream?prompt=...")` automatically GET request kholta hai,
# connection ko open rakhta hai, aur har `data:` event par `onmessage` fire karta
# hai. Hum har chunk ko output div me append karte hain => live "typing" effect.
INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Lab 3 — Full-stack streaming</title>
  <style>
    /* Minimal styling — L14 me yeh kaam Tailwind + React-Markdown karta hai.
       Yahan hum sirf readable rakhne ke liye thodi vanilla CSS de rahe hain. */
    body { font-family: system-ui, sans-serif; max-width: 680px; margin: 40px auto; padding: 0 16px; }
    h1 { font-size: 1.4rem; }
    #prompt { width: 100%; padding: 8px; font-size: 1rem; box-sizing: border-box; }
    button { margin-top: 8px; padding: 8px 16px; font-size: 1rem; cursor: pointer; }
    #output { white-space: pre-wrap; margin-top: 20px; padding: 14px; border: 1px solid #ccc;
              border-radius: 8px; min-height: 60px; background: #fafafa; }
    .status { color: #888; font-size: 0.85rem; margin-top: 8px; }
  </style>
</head>
<body>
  <h1>Lab 3 — Full-stack streaming (SSE)</h1>
  <p>Type a prompt; tokens browser me LIVE append honge (EventSource ke through).</p>

  <input id="prompt" value="Give me one tiny tip for fast APIs." />
  <button id="go">Stream it</button>
  <div class="status" id="status"></div>
  <div id="output"></div>

  <script>
    // -------------------------------------------------------------------
    // Vanilla JS frontend logic. Koi framework nahi — pure DOM manipulation
    // (L09 Tier-1). Real Next.js app me yahi kaam ek React component karta,
    // streamed text ko useState me accumulate karke <ReactMarkdown> me render.
    // -------------------------------------------------------------------
    const promptEl = document.getElementById("prompt");
    const outEl    = document.getElementById("output");
    const statusEl = document.getElementById("status");
    const goBtn    = document.getElementById("go");
    let es = null; // current EventSource (taaki naya stream se pehle purana band kar sakein)

    goBtn.onclick = () => {
      // Reset UI
      outEl.textContent = "";
      statusEl.textContent = "Connecting...";
      if (es) es.close();

      const prompt = encodeURIComponent(promptEl.value);
      // EventSource hamesha GET karta hai — isliye humne /stream ko GET banaya
      // (SSE GET-only protocol hai). Query string me prompt bhejte hain.
      es = new EventSource(`/stream?prompt=${prompt}`);

      // Har `data:` event par yeh fire hota hai. event.data = humara token.
      es.onmessage = (event) => {
        if (event.data === "[DONE]") {
          // Sentinel mila => server done => connection band kar do.
          statusEl.textContent = "Done.";
          es.close();
          return;
        }
        statusEl.textContent = "Streaming...";
        // Token ko append karo => live "typewriter" effect. Yahi perceived-latency win.
        outEl.textContent += event.data;
      };

      // Network error / server connection drop par browser yahan call karta hai.
      es.onerror = () => {
        statusEl.textContent = "Connection closed (ya error).";
        es.close();
      };
    };
  </script>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# FastAPI app + routes
# ---------------------------------------------------------------------------
app = FastAPI(title="Lab 3 — Full-stack streaming")


@app.get("/", response_class=HTMLResponse)
def index():
    """GET / => pura HTML page (L09 Pattern-2: backend serves the page).
    Browser ise load karta hai, phir uske andar ka JS /stream ko hit karta hai."""
    return HTMLResponse(content=INDEX_HTML)


@app.get("/stream")
def stream(prompt: str = "Say hello in one short sentence."):
    """GET /stream?prompt=... => SSE StreamingResponse.

    media_type="text/event-stream" => yahi SSE ka official content-type hai,
    iske bina browser ka EventSource isse SSE nahi maanega. StreamingResponse
    hamare generator ko chunked-transfer se client tak push karta hai.
    """
    return StreamingResponse(
        sse_event_stream(prompt),
        media_type="text/event-stream",
        # SSE best-practice headers: caching band + proxy buffering off ka hint.
        # (Production me nginx ke saamne `X-Accel-Buffering: no` zaroori hota hai
        #  warna proxy tokens ko buffer karke streaming kha jaata hai.)
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/health")
def health():
    """GET /health => simple liveness probe. Cloud (App Runner/Vercel) health
    checks aise hi endpoint ko poll karte hain. Yahan key-mode bhi bata dete hain."""
    mode = "real (GROQ_API_KEY present)" if os.getenv("GROQ_API_KEY") else "fake (offline, no key)"
    return {"status": "ok", "stream_mode": mode}


# ---------------------------------------------------------------------------
# SELF-DEMO (default `uv run <file>`): TestClient se apne hi routes call karke
# streamed tokens assemble + print karta hai, phir EXIT 0. No real server,
# no network zaroori (no-key path default-safe hai).
# ---------------------------------------------------------------------------
def run_self_demo():
    """Apne hi /health aur /stream routes ko TestClient se hit karke print karta hai."""
    # TestClient import yahin (sirf demo ke liye) — top-level import bloat se bachte hain.
    from fastapi.testclient import TestClient

    print("\n" + "#" * 72)
    print("#  LAB 3 — Full-stack streaming  (SELF-DEMO via TestClient, no real server)")
    print("#" * 72 + "\n")

    key_present = bool(os.getenv("GROQ_API_KEY") or "placeholder")
    if not key_present:
        # Mandatory graceful-degrade message: key missing => fake path, EXIT 0.
        print(">>> GROQ_API_KEY missing/empty hai — LIVE call skip kar rahe hain.")
        print(">>> FAKE token generator se streaming mechanics demo karenge (offline, $0).\n")
    else:
        print(">>> GROQ_API_KEY mila — REAL Groq stream chalega (short completion).\n")

    client = TestClient(app)

    # --- 1) /health ------------------------------------------------------
    print("-" * 72)
    print("GET /health")
    print("-" * 72)
    health_resp = client.get("/health")
    print(f"  status_code = {health_resp.status_code}")
    print(f"  body        = {health_resp.json()}\n")

    # --- 2) /  (page serve hota hai — sirf prove karte hain HTML aaya) ----
    print("-" * 72)
    print("GET /  (frontend HTML page)")
    print("-" * 72)
    root_resp = client.get("/")
    print(f"  status_code = {root_resp.status_code}")
    print(f"  content-type= {root_resp.headers.get('content-type')}")
    print(f"  html length = {len(root_resp.text)} chars (embedded vanilla frontend)\n")

    # --- 3) /stream  (SSE — yahi lab ka dil hai) -------------------------
    print("-" * 72)
    print("GET /stream?prompt=...   (SSE events ko consume + assemble karte hain)")
    print("-" * 72)
    demo_prompt = "Give me one tiny tip for writing fast web APIs."
    print(f"  prompt = {demo_prompt!r}\n")

    assembled = []   # tokens ko jod ke pura jawaab banayenge (jaise browser karta)
    n_events = 0
    # TestClient streaming: .stream() context manager se SSE lines padhte hain.
    with client.stream("GET", "/stream", params={"prompt": demo_prompt}) as resp:
        print(f"  status_code  = {resp.status_code}")
        print(f"  content-type = {resp.headers.get('content-type')}")
        print("\n  --- live tokens (jaise aate hain, waise print) ---")
        for line in resp.iter_lines():
            if not line:
                continue  # blank line = SSE event boundary, skip
            # Har data line `data: <payload>` format me hai.
            if line.startswith("data: "):
                payload = line[len("data: "):]
                if payload == "[DONE]":
                    break  # sentinel => stream khatam
                n_events += 1
                assembled.append(payload)
                # Inline print taaki "streaming" visually feel ho (end="").
                print(payload, end="", flush=True)
        print("\n  --- stream end ---\n")

    full = "".join(assembled)
    print(f"  total SSE events received = {n_events}")
    print(f"  assembled response        = {full.strip()!r}\n")

    print("#" * 72)
    print("#  AHA: Backend ne tokens ko `data: ...\\n\\n` (SSE) me push kiya, client ne")
    print("#  unhe ek-ek karke consume + assemble kiya. Browser bhi BILKUL yahi karta")
    print("#  hai (EventSource) — bas wahan tokens screen par live append hote hain.")
    print("#" * 72 + "\n")


# ---------------------------------------------------------------------------
# ENTRYPOINT: default => self-demo (safe, no server, no key zaroori).
#             --serve => real uvicorn server (browser/curl testing).
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # sys.argv parse: agar "--serve" diya hai to real server, warna self-demo.
    if "--serve" in sys.argv:
        import uvicorn
        print("Launching real server -> http://127.0.0.1:8000  (Ctrl+C to stop)")
        print("Browser me kholo aur 'Stream it' dabao. /stream ko curl bhi kar sakte ho:")
        print('  curl -N "http://127.0.0.1:8000/stream?prompt=hello"\n')
        # host 127.0.0.1 => sirf local machine; port 8000 = FastAPI/uvicorn default.
        uvicorn.run(app, host="127.0.0.1", port=8000)
    else:
        run_self_demo()
        # Explicit clean exit 0 (convention: default path kabhi crash/hang na ho).
        raise SystemExit(0)
