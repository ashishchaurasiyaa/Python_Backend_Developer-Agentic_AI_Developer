# PRACTICAL_RUNBOOK.md — Week 1 Hands-On Guide (Hinglish)

Ye runbook Week 1 ke **practical / coding** part ke liye hai — Ed Donner ke "Complete Agentic AI Engineering Course" ka foundations module. Theory notes (L01–L27 `.md`) tumne already padh liye honge; ab actual code chalana, todna, aur seekhna hai.

Tum experienced Python backend dev ho, to fundamentals skip — focus seedha **agentic patterns** par hai: LLM call chaining, multi-model orchestration, tool calling, aur raw agent loop.

---

## 1. Practical kaise karein — the Learning Loop

Har lab ke liye ye 7-step loop follow karo. Isse theory + code dono saath chipakte hain:

1. **Watch** — Ed ka lecture dekho (theory note ke topic se match karke).
2. **Read note** — parent `Week1_Foundations` folder ka matching Hinglish `.md` note padho (L01–L27).
3. **Open lab** — `Practical/` folder ka matching `labN_*.py` file kholo.
4. **Run** — `uv run ...` se chalao (exact command niche table me hai). Pehle bina kuch change kiye chalao — baseline dekho.
5. **Read comments** — file ke andar ke Hinglish comments padho. Har lab ke andar "kyun" explain kiya gaya hai, sirf "kya" nahi.
6. **Tweak / experiment** — chhoti cheez badlo: prompt change karo, model change karo, ek extra tool add karo. Phir dobara run karo, output ka farak dekho.
7. **Do the exercise** — lab ke end me jo suggested change/exercise hai use khud likho. Yahi se actual seekh aati hai — padhne se nahi, todne se.

> Rule of thumb: **kabhi bhi sirf padh ke aage mat jao.** Har lab ko ek baar apne haath se chalao aur kam-se-kam ek cheez badlo.

---

## 2. Lab → Lecture → Concept → Run Command map

Saare commands **`my-agentic-ai-project` root** se chalao (jahan `pyproject.toml` / `uv` setup hai).

| Lab file | Notes / Lectures | Kya concept sikhata hai | Run command |
|---|---|---|---|
| `lab1_basics.py` | L01–L08 (intro, first LLM call, chaining) | Foundational agentic pattern — **LLM call chaining**: ek call ka output agle call ka input banta hai. Connectivity check (2+2), 2-call Q→A chain, aur commercial 3-step business chain (sector → pain point → agentic AI solution). | `uv run Udemy_EdDonner_Course/Week1_Foundations/Practical/lab1_basics.py` |
| `lab2_multi_model_judge.py` | L09–L14 (multiple providers, evaluation) | **Multi-model orchestration + LLM-as-judge**: ek tough ethics/reasoning question multiple providers ko, phir answers anonymise+number karke ek judge LLM se best→worst rank karwana. Same OpenAI client, alag `base_url` per provider. | `uv run Udemy_EdDonner_Course/Week1_Foundations/Practical/lab2_multi_model_judge.py` |
| `lab3_gradio_chatbot.py` | L15–L19 (chat UI, stateless LLM, history) | **Persona-driven chat** `gr.ChatInterface` (gradio v6, `type="messages"`). Core lesson: LLM stateless hai — har turn pe `chat(message, history)` poori `messages` list dobara banata hai (system prompt + history + new msg), aur `yield` se token-by-token streaming. | `uv run Udemy_EdDonner_Course/Week1_Foundations/Practical/lab3_gradio_chatbot.py` |
| `lab4_career_agent.py` | L20–L24 (tools, function calling, capstone) | **Week-1 capstone — AI "digital twin"**: tumhare jaisa roleplay karke career questions answer karta hai. Function calling (2 tools: `record_user_details`, `record_unknown_question`) + agent loop. Deployable `gr.ChatInterface` — yahi HuggingFace Spaces pe jaata hai. | `uv run Udemy_EdDonner_Course/Week1_Foundations/Practical/lab4_career_agent.py` |
| `lab5_agent_loop_from_scratch.py` | L25–L27 (agent loop internals) | **RAW agent loop, no framework**: 2 real tools (safe AST `calculator` + canned `get_current_info`) + unke JSON schemas, aur explicit `run_agent()` while-loop jo LLM call karta hai, tool_calls execute karta hai, results `role="tool"` (sahi `tool_call_id`) ke saath wapas feed karta hai. Yahi cheez OpenAI Agents SDK / LangGraph baad me automate karte hain. | `uv run Udemy_EdDonner_Course/Week1_Foundations/Practical/lab5_agent_loop_from_scratch.py` |

> Note: lecture/note numbers approximate mapping hain (concept-wise). Exact lecture number ke liye apne L01–L27 notes ka topic match kar lo.

---

## 3. Provider note — sab kuch GROQ (free) pe default

Saare labs **Groq** pe default chalte hain — **bilkul free aur fast**. Trick simple hai: hum **OpenAI ka official client** use karte hain par `base_url` Groq ka point karte hain (Groq OpenAI-compatible API deta hai). Isi liye code me OpenAI client dikhta hai par bill OpenAI ka nahi aata.

```python
# har lab me aisa kuch hota hai (concept):
client = get_client("groq")   # default — free, fast, OpenAI-compatible base_url
```

**Provider switch karna ho** to bas `get_client("...")` ka argument badlo:

```python
get_client("groq")     # default, free  → GROQ_API_KEY chahiye
get_client("openai")   # paid           → OPENAI_API_KEY chahiye
get_client("gemini")   # Google         → GOOGLE_API_KEY chahiye
```

- `lab1` me top/`__main__` me `PROVIDER` variable badal sakte ho (`"groq"` / `"openai"` / `"gemini"`).
- `lab2` automatically Groq hamesha chalata hai; Gemini + OpenAI sirf tab jab unki key `.env` me ho, warna **`[SKIP]`** line print karke graceful skip — crash nahi.

**Seekhne ke liye Groq hi rakho.** Paid providers tab try karo jab specifically OpenAI/Gemini ka output compare karna ho.

---

## 4. Setup steps

### 4.1 `.env` (already done)
Root `.env` me ye honi chahiye (tumhare paas already hai):

```bash
GROQ_API_KEY=gsk_...your_key...
```

Optional (sirf jab us provider pe switch karo):

```bash
OPENAI_API_KEY=sk-...        # lab1/lab2 me openai pe switch karne ke liye
GOOGLE_API_KEY=...           # gemini ke liye
```

### 4.2 lab4 ke liye persona files (optional — lab inke bina bhi chalta hai)
lab4 placeholder bio ke saath out-of-the-box chalta hai. Apna real "digital twin" banane ke liye:

```bash
# Practical folder ke andar me/ banao
mkdir -p Udemy_EdDonner_Course/Week1_Foundations/Practical/me

# apna short bio likho (plain text, kuch paragraphs)
#   Practical/me/summary.txt

# optional: LinkedIn PDF export bhi daal sakte ho
#   Practical/me/linkedin.pdf
```

`summary.txt` me 2-3 paragraph: tum kaun ho, kya karte ho, skills, kis tarah ke kaam dhoond rahe ho. Agent isi ko apni "personality" banata hai.

### 4.3 lab4 push notifications (optional)
Jab agent koi tool fire kare (e.g. visitor ne email chhoda) to phone pe push aaye — uske liye `.env` me:

```bash
PUSHOVER_TOKEN=...
PUSHOVER_USER=...
```

Ye na ho to push **silent no-op** hai — lab phir bhi normal chalta hai.

---

## 5. Order to do them in (aur kyun)

Sequence mat todna — har lab pichle ka concept use karta hai:

1. **lab1** — pehle ek single LLM call + chaining samajh lo (sab kuch isi pe build hota hai).
2. **lab2** — ab ek se zyada model orchestrate karo + ek LLM se dusre ko judge karwao (evaluation pattern).
3. **lab3** — stateless LLM ko stateful "chat" jaisa banana + UI (gradio) — yahi user-facing layer hai.
4. **lab4** — chat + tools = real **agent** jo actions le sakta hai (capstone, deployable).
5. **lab5** — andar jhaank ke dekho ki agent loop actually kaise chalta hai (framework ke bina, raw).

> Logic: lab1–lab3 building blocks dete hain, lab4 unhe ek deployable agent me jodta hai, lab5 us magic ke neeche ka mechanism khol ke dikhata hai.

---

## 6. Week 1 done = milestone

**Week 1 khatam matlab tum ek deployable, tool-using agent khud bana sakte ho** — jo:
- multiple providers ke saath kaam kare (Groq/OpenAI/Gemini),
- LLM-as-judge se output evaluate kare,
- chat UI me persona ke saath baat kare,
- function calling se real tools chalaye,
- aur tumhe pata ho ki andar agent loop actually kaise chalta hai (lab5).

**Compare against the official repo:** Ed ke exact versions yahan hain — apne labs se milao, jahan farak ho wahan samjho kyun:

```
github.com/ed-donner/agents   →  folder: 1_foundations
```

**Final deployment step:** career agent (lab4) ka asli maza tab hai jab use **HuggingFace Spaces** pe deploy karo — yahi `gr.ChatInterface` object as-is upload hota hai, aur tumhara "digital twin" public URL pe live ho jaata hai. (Course me yahi Week-1 ka final deliverable hai.)

---

## 7. Common errors & fixes

| Error / symptom | Wajah | Fix |
|---|---|---|
| `AuthenticationError` / `401` / empty key | `.env` me galat key naam ya missing | Confirm karo naam exactly `GROQ_API_KEY` hai (typo nahi, e.g. `GROK` nahi). Provider switch kiya to uski key (`OPENAI_API_KEY` / `GOOGLE_API_KEY`) bhi honi chahiye. |
| `model ... does not support tools` / tool_calls empty | lab4/lab5 me aisa model use kar liya jo function calling support nahi karta | Tool-capable model rakho — default `llama-3.3-70b-versatile` (Groq) tools support karta hai. Chhote/instruct-only models avoid karo. |
| `OSError: address already in use` / port 7860 busy | lab3/lab4 ka pichla gradio process abhi chal raha hai | Purana process band karo, ya gradio `launch()` me `server_port=7861` set karo. Quick: terminal me `lsof -i :7860` se PID dhoond ke kill. |
| lab4 me generic/placeholder jawab | `me/summary.txt` nahi bana | Optional hai — par real persona ke liye `Practical/me/summary.txt` banao (section 4.2). File na ho to lab clearly-marked placeholder bio use karta hai, crash nahi. |
| `[SKIP] gemini/openai ...` lab2 me | us provider ki key `.env` me nahi | Expected behaviour hai — Groq se chalta rahega. Us provider ko include karna ho to uski key add karo. |
| `command not found: uv` | uv installed nahi | `uv` install karo (https://docs.astral.sh/uv/), phir saare commands `uv run` ke saath. |
| Galat folder se run kar rahe ho | relative path `Udemy_EdDonner_Course/...` resolve nahi hua | Hamesha **`my-agentic-ai-project` root** se chalao, warna `.env` aur path dono miss ho sakte hain. |

---

### Quick start (abhi shuru karna ho to)

```bash
# my-agentic-ai-project root se:
uv run Udemy_EdDonner_Course/Week1_Foundations/Practical/lab1_basics.py
uv run Udemy_EdDonner_Course/Week1_Foundations/Practical/lab2_multi_model_judge.py
uv run Udemy_EdDonner_Course/Week1_Foundations/Practical/lab3_gradio_chatbot.py
uv run Udemy_EdDonner_Course/Week1_Foundations/Practical/lab4_career_agent.py
uv run Udemy_EdDonner_Course/Week1_Foundations/Practical/lab5_agent_loop_from_scratch.py
```

Happy building. lab1 se shuru karo, har lab me kam-se-kam ek cheez todo. 🛠️
