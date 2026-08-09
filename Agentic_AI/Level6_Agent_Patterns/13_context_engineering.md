# Level 6 — Doc 13: Context Engineering ⭐

**Agentic AI · Level 6 — Agent Patterns | Senior AI Engineer**

> **Goal:** "Context engineering" 2026 ki JD keyword hai — aur yeh sirf fancy naam
> nahi hai prompt engineering ka. Yeh ek alag discipline hai: har API call se
> pehle **decide karna ki context window me exactly kya jayega, kis order me,
> aur kya bahar rahega**. Prompt engineering ek turn ke WORDS optimize karta hai.
> Context engineering poore agent run ke TOKEN BUDGET ko engineer karta hai.

> **Prerequisite:** `12_agent_harness_engineering.md` padho pehle — woh harness ka
> overall shape deta hai (loop, permissions, sandboxing) aur context management ko
> ek section ke roop me cover karta hai. Yeh doc us section ko **poora topic** bana
> deta hai. Jahan mechanics wahan already hain, main cross-link kar raha hoon —
> duplicate nahi.

---

## Quick Reference Card

| Concept | Ek line me | Kab uthao |
|---|---|---|
| **Context budget** | Har token ki ek cost hai aur ek opportunity cost — kya usne apni jagah kamayi? | Har design decision pe |
| **Stable prefix discipline** | Static content pehle, volatile content baad me — warna cache invalidate | Har multi-turn agent |
| **Compaction** | Purani history ko summary se replace karo | Budget ka ~70-80% bhar jaye |
| **Context editing (clearing)** | Purane tool results ko **hata** do (summarize nahi) | Tool-heavy loops |
| **Sub-agent isolation** | Exploration alag context me, wapas sirf **result** aaye | Fan-out / wide search |
| **Retrieval vs preload** | Preload = predictable + cacheable; retrieval = scalable | Corpus size decide karta hai |
| **Tool-result truncation** | Bade outputs ko head/tail + pointer bana do | File reads, logs, SQL dumps |
| **Memory files** | Cross-session state disk pe, context me sirf pointer | Multi-session agents |
| **Context rot / poisoning** | Lamba ya galat context = quality gir jaati hai | Long-horizon runs |

**Ek hi vaakya me:** *Context window ek RAM hai, hard disk nahi — usme woh rakho jo
model ko **is turn** me chahiye, baaki sab kahin aur rakho aur pointer do.*

---

## 1. Definition — Context Engineering ≠ Prompt Engineering

```
PROMPT ENGINEERING
    Question: "Model ko kya BOLNA hai taaki behaviour theek ho?"
    Artifact: instruction text, examples, output format
    Scope:    ek call
    Failure:  model ne galat cheez samjhi

CONTEXT ENGINEERING
    Question: "Is call ke context window me kya JANA chahiye — aur kya nahi?"
    Artifact: assembly pipeline (kya load ho, kis order me, kitna, kab drop ho)
    Scope:    poora agent run (50+ calls, ghanto)
    Failure:  model ka signal noise me doob gaya, ya budget khatam ho gaya
```

Yeh distinction naukri me literally dikhti hai. Prompt engineering ek **authoring**
skill hai. Context engineering ek **systems** skill hai — aap ek pipeline likhte ho
jo har iteration pe context assemble karti hai, aur uska output measurable hai
(tokens/task, cache hit rate, task success rate).

```python
# Prompt engineering ka artifact
SYSTEM = "You are a senior Python reviewer. Report bugs with file:line."

# Context engineering ka artifact — yeh function har loop iteration pe chalta hai
def assemble_context(state) -> list[dict]:
    """Decide karo ki IS turn me context window me kya jayega."""
    blocks = []
    blocks += stable_prefix(state)         # cached — kabhi mat badlo
    blocks += project_memory(state)        # CLAUDE.md / notes, chhota rakho
    blocks += retrieved_snippets(state)    # sirf relevant, top-k
    blocks += compacted_history(state)     # purana → summary
    blocks += recent_turns(state, n=10)    # verbatim tail
    return blocks
```

> **Senior Tip:** Interview me agar aap sirf "main achhe prompts likhta hoon" bolte
> ho, aap junior sound karte ho. Agar aap bolte ho "maine context assembly ko ek
> explicit pipeline banaya, aur tokens-per-completed-task 40% gir gaya" — yeh
> staff-level signal hai.

---

## 2. The Context Budget Mindset — kaun sa token apni jagah kamata hai?

Har agent call ka ek **budget** hota hai. Modern models pe window bada hai
(Claude Opus 5 / Sonnet 5 pe 1M tokens, Haiku 4.5 pe 200K), par **window size
budget nahi hai** — budget teen constraints ka minimum hai:

```
1. COST      — input tokens har call pe dobara bhejte ho. 50-call loop me
               100K ka context = 5M input tokens. Cache ke bina yeh mehanga hai.

2. LATENCY   — bada prefill = slower time-to-first-token. User feel karta hai.

3. QUALITY   — yeh sabse under-rated. Bada context ≠ behtar answer. Relevant
               signal jab noise me dabta hai to model distract hota hai
               ("context rot", section 6).
```

Har block ke liye ek hi sawal poocho:

| Sawal | Agar "nahi" | Action |
|---|---|---|
| Kya model ise **is turn** me use karega? | Nahi | Retrieval ke peeche daalo |
| Kya yeh model ko **pehle se nahi pata**? | Nahi | Nikaal do (generic Python docs mat bhejo) |
| Kya yeh har call pe **badalta** hai? | Haan | Cache breakpoint ke **baad** rakho |
| Kya yeh **verbatim** chahiye ya gist chalega? | Gist chalega | Compact/summarize karo |
| Agar main ise hata doon, kya task fail hoga? | Nahi | Hata do, phir measure karo |

```python
# Budget accounting — approximate mat karo, count karo
resp = client.messages.count_tokens(
    model="claude-opus-5",
    system=SYSTEM_PROMPT,
    tools=TOOLS,
    messages=messages,
)
print(resp.input_tokens)   # yeh real number hai
```

> ⚠️ **`tiktoken` mat use karo Claude ke liye.** Woh OpenAI ka tokenizer hai —
> typical text pe ~15-20% undercount karta hai, code/non-English pe aur zyada.
> Har provider ka apna `count_tokens` endpoint hai; wahi use karo.

**Budget ko response me verify karo** — `usage` object sach bolta hai:

```python
u = response.usage
total_prompt = u.input_tokens + u.cache_creation_input_tokens + u.cache_read_input_tokens
#              ^ uncached      ^ cache me likha (1.25x)      ^ cache se pada (0.1x)
```

Common trap: agent ghanton chala aur `input_tokens` sirf 4K dikha raha hai — matlab
baaki sab cache se aaya. **Sum dekho, single field nahi.**

---

## 3. Caching-Aware Layout — stable prefix discipline

Yeh section 2 ka sabse bada cost lever hai, aur galat karna aasan hai.

**Ek invariant, sab kuch usi se nikalta hai:**

```
Prompt caching ek PREFIX MATCH hai.
Prefix me kahin bhi ek byte badla → uske baad ka SAB kuch invalidate.

Render order:  tools  →  system  →  messages
```

Iska seedha matlab: **stability order = physical order.** Jo cheez kabhi nahi
badalti woh sabse pehle, jo har request pe badalti hai woh sabse aakhir me.

```
┌─ tools (position 0) ─────────────┐  kabhi mat badlo mid-conversation
│  deterministic order (sort!)      │  ek tool add karna = poora cache gaya
├─ system ─────────────────────────┤
│  frozen role + rules              │  ← cache_control breakpoint yahan
├─ messages: old turns ────────────┤
│  conversation history             │  ← breakpoint har few turns
├─ messages: recent turns ─────────┤
│  latest tool results              │
└─ messages: current user turn ────┘  volatile — koi breakpoint nahi
```

```python
response = client.messages.create(
    model="claude-opus-5",
    max_tokens=16000,
    system=[{
        "type": "text",
        "text": FROZEN_SYSTEM_PROMPT,          # <- zero interpolation
        "cache_control": {"type": "ephemeral"} # tools + system dono cache honge
    }],
    tools=sorted(TOOLS, key=lambda t: t["name"]),  # deterministic serialization
    messages=messages,
)
```

### Silent cache killers (yeh grep karo apne code me)

| Pattern | Kyun toota | Fix |
|---|---|---|
| `datetime.now()` system prompt me | Har request ka prefix alag | Date ko last user message me daalo |
| `uuid4()` / request-id prefix me | Same | Aakhir me, breakpoint ke baad |
| `json.dumps(d)` bina `sort_keys=True` | Bytes non-deterministic | `sort_keys=True` |
| `tools = build_tools(user)` | Tools position 0 pe — per-user prefix | Ek global tool set |
| `if flag: system += "..."` | Har flag combo alag prefix | Flag ko message content me bhejo |
| Mid-run model switch | Cache model-scoped hota hai | Main loop ek model pe rakho |

### Numbers jo interview me poochte hain

```
Cache READ   ≈ 0.1x  base input price   ← yahi to jackpot hai
Cache WRITE  ≈ 1.25x (5-min TTL) / 2x (1-hour TTL)

Break-even:  5-min TTL  → 2 requests   (1.25 + 0.1 = 1.35x vs 2x uncached)
             1-hour TTL → 3 requests   (2.0 + 0.2 = 2.2x  vs 3x uncached)

Max 4 cache_control breakpoints per request.
Minimum cacheable prefix MODEL-DEPENDENT (aur monotonic NAHI hai):
    Claude Opus 5           →  512 tokens
    Opus 4.8 / Sonnet 5/4.6 → 1024 tokens
    Opus 4.6 / Haiku 4.5    → 4096 tokens
Isse chhota prefix chupchaap cache nahi hoga — koi error nahi milega.
```

### Do cache traps jo production me kaatte hain

**1. 20-block lookback window.** Har breakpoint peeche **max 20 content blocks**
tak dhoondhta hai. Agentic loop me ek turn easily 20+ blocks bana deta hai
(tool_use + tool_result pairs). Phir agla breakpoint purana entry dhoondh hi nahi
paata → silent miss. Fix: lambe turns me har ~15 blocks pe intermediate breakpoint.

**2. Concurrent fan-out.** Cache entry tabhi readable hoti hai jab pehli response
**stream hona shuru** ho jaye. N parallel requests ek saath bhejoge to sabhi full
price denge. Fix: 1 request bhejo → first token aane do → baaki N-1 fire karo.

> **Senior Tip — mid-conversation system messages.** Agar beech me operator
> instruction daalni ho (mode switch, injected state), top-level `system` mat edit
> karo — woh poori history ka prefix badal deta hai. Iski jagah `messages[]` me
> `{"role": "system", "content": "..."}` append karo: cached prefix bacha rehta hai
> **aur** yeh prompt-injection-safe operator channel hai (user turn me chhupaya gaya
> `<system-reminder>` text koi bhi forge kar sakta hai; `role: "system"` nahi).
> Model-gated feature hai — Claude Opus 5 / Opus 4.8 / Fable 5 pe available, Sonnet 5
> pe nahi (unsupported model pe 400 aata hai, catch karke fallback rakho).

---

## 4. Compaction & Summarization — kab, kya bachta hai

`12_agent_harness_engineering.md` §4 me basic `manage_context()` shape hai.
Yahan **policy** hai — code nahi, decisions.

### Kab trigger karo

```
GALAT:  jab window bhar jaye
SAHI:   jab budget ka ~70-80% bhar jaye

Kyun? Compaction ke liye khud ek LLM call chahiye, jisme purani history
input jaati hai. Agar 100% pe trigger karoge to compaction call hi
context-window-exceeded se fail ho jayegi. Headroom chhodo.
```

Server-side compaction bhi ek option hai (Claude pe beta `compact-2026-01-12`,
default trigger ~150K tokens) — API khud earlier context summarize kar deta hai.
**Critical gotcha:** response me aayi `compaction` block ko wapas bhejna padta hai.
Yaani `messages.append({"role": "assistant", "content": response.content})` —
sirf `.text` nikaal ke append karoge to compaction state chupchaap kho jayega.

### Compaction me kya BACHNA chahiye (priority order)

```
1. ORIGINAL TASK / user requirement      ← yeh kabhi mat kho, warna agent bhatak jayega
2. DECISIONS + unke reasons              ← "X approach chuna kyunki Y fail hua"
3. CURRENT STATE                          ← kaunsi files chhui, kya pass/fail hua
4. CONSTRAINTS discovered mid-run         ← "yeh API rate-limited hai", "test DB read-only"
5. OPEN QUESTIONS / next steps

Aur kya CHHOD sakte ho:
- Routine tool-call noise (successful `ls`, `grep` jinka result use ho chuka)
- Verbose file contents jo ab relevant nahi
- Intermediate reasoning jiska conclusion point 2 me capture ho gaya
```

### Compaction vs Context Editing — ek jaise nahi hain

| | **Compaction** | **Context Editing (clearing)** |
|---|---|---|
| Kya karta hai | Purani history ko **summary se replace** | Purane blocks ko **hata deta hai** |
| Cost | Ek extra LLM call | Zero — pure deletion |
| Loss | Detail chali jaati hai, gist bachta hai | Content poora chala jata hai |
| Best for | Conversation ka reasoning thread | Stale tool results, purane thinking blocks |
| Claude API | beta `compact-2026-01-12`, type `compact_20260112` | beta `context-management-2025-06-27`, types `clear_tool_uses_20250919` / `clear_thinking_20251015` |

```python
# Context editing — purane tool results clear karo bina summarize kiye
client.beta.messages.create(
    model="claude-opus-5",
    max_tokens=16000,
    betas=["context-management-2025-06-27"],
    context_management={"edits": [
        {"type": "clear_tool_uses_20250919", "clear_tool_inputs": True},
        {"type": "clear_thinking_20251015"},
    ]},
    tools=TOOLS,
    messages=messages,
)
```

**Practical rule:** pehle **clear** karo (free hai), phir bhi bhara hai to
**compact** karo (LLM call lagti hai). Dono use karna normal hai.

> **Interview Angle:** "Aap compaction ke baad quality regression kaise detect
> karoge?" → Golden-task eval set (dekho `10_agent_evaluation.md`) jisme **long-horizon**
> tasks hon jo compaction trigger karein. Metric: same task, compaction on vs off,
> success rate delta. Agar delta bada hai to summary prompt me "preserve original
> requirements verbatim" add karo — sabse common miss yahi hota hai.

---

## 5. Sub-Agent Context Isolation — fan-out beats one long context

`12_agent_harness_engineering.md` §6 me "kab delegate karein" hai. Yahan **kyun**
context ke angle se.

```
ONE LONG CONTEXT (naive):
    main agent 50 files khud padhta hai
    → 50 × ~2K tokens = 100K tokens context me, permanently
    → har agle turn pe yeh 100K dobara bhejna padta hai
    → 90% content ek baar use hua tha, phir bhi 40 turns tak ride kar raha hai
    → aur signal (actual task) is noise me dab gaya

FAN-OUT (context isolation):
    main agent 5 sub-agents spawn karta hai, har ek 10 files
    → har sub-agent ka apna FRESH context window
    → sub-agent wapas bhejta hai: 200-token finding, poora transcript NAHI
    → main context me total ~1K tokens aaya, 100K ki jagah
```

**Sabse important rule — result return karo, transcript nahi:**

```python
# GALAT — sub-agent ka poora trace main context me daal diya
main_messages.append({"role": "user", "content": subagent.full_transcript})

# SAHI — sirf distilled answer
main_messages.append({"role": "user", "content": [{
    "type": "tool_result",
    "tool_use_id": call_id,
    "content": subagent.final_answer,   # "auth.py:142 me race condition, 3 files affected"
}]})
```

Isi wajah se `07_multi_agent_supervisor.md` ka supervisor pattern context-economics
lens se dobara padhna chahiye: decomposition sirf task-clarity ke liye nahi, **token
economics** ke liye bhi hai.

### Ek aur isolation trick: Programmatic Tool Calling

Standard tool use me har result **model ke context** me aata hai. PTC me model ek
script likhta hai jo tools ko function ki tarah call karta hai — results **script
ko** milte hain, context ko nahi. Sirf final output context me aata hai.

```
Standard:  read 200 rows → 200 rows context me → model filter karta hai → 3 rows chahiye the
PTC:       script 200 rows read kare, loop me filter kare, 3 rows return kare
           → context cost = 3 rows, 200 nahi
```

Jab bhi "bahut saare sequential calls" ya "bade intermediate results" ho, PTC socho.

> **Sub-agent ka cache trap:** fork operation (summarizer, sub-agent, verifier)
> agar `system`/`tools`/`model` dobara build karega aur zara sa bhi alag hoga, to
> parent ka cache completely miss karega. Parent ka `system`, `tools`, `model`
> **verbatim copy** karo, phir fork-specific content aakhir me append karo.

---

## 6. Failure Modes — Context Poisoning aur Context Rot

Yeh section woh hai jo zyadatar candidates miss karte hain.

### A. Context Poisoning

Ek galat fact context me aa gaya, aur ab **har agle turn** me model use padhta hai
aur us par build karta rehta hai.

```
Turn 3:  model hallucinate karta hai "config file /etc/app/settings.yaml me hai"
Turn 4:  woh statement ab conversation history ka hissa hai
Turn 5-40: model us path pe kaam karta rehta hai, fail hota hai, workaround likhta hai
         → self-reinforcing loop, kabhi khud se recover nahi karta
```

Yeh khaas taur pe khatarnak hai jab thinking disabled ho aur tool call **plain
text** me nikal jaye: turn normally complete hota hai, koi error nahi, tool
actually chala hi nahi — par woh bogus text history me baith gaya aur aage ke
turns skew karta hai.

**Mitigations:**
- **Ground claims in tool results.** System prompt me: *"Progress report karne se
  pehle har claim ko is session ke ek tool result se verify karo. Jo verified nahi,
  usko explicitly 'unverified' bolo."*
- Tool results ko **authoritative** treat karo, model ke apne statements ko nahi.
- Compaction ko poison ko flush karne ka mauka samjho — summary regenerate karte
  waqt sirf tool-verified facts carry karo.

### B. Context Rot (a.k.a. "lost in the middle")

Context jitna lamba, per-token attention utni patli. Long-context benchmarks pe
models beech ka material sabse zyada miss karte hain.

```
Recall quality (approx shape):

  high │██                              ██
       │██                              ██
       │██        ▂▂▂▂▂▂▂▂▂▂            ██
  low  │██        ░░░░░░░░░░            ██
       └──────────────────────────────────
        start        middle           end

Isliye: sabse important cheez SYSTEM PROMPT (start) me
        ya LAST USER TURN (end) me rakho — beech me nahi.
```

**Mitigations:**
- Critical constraints ko **end** me repeat karo (chhota `<key_constraints>` block).
- Middle ko aggressively compact karo — waise bhi wahan recall sabse kamzor hai.
- Har cheez preload karne ki jagah retrieval use karo (section 7).

### C. Distraction / over-triggering

Zyada tools, zyada examples, zyada "IMPORTANT: YOU MUST" — modern models
instructions ko **literally** follow karte hain, isliye purane models ke liye likha
gaya aggressive prompt ab over-trigger karta hai. Kam tools + plain language
generally behtar hai.

### D. Budget countdown anxiety

Agar aap remaining-token count model ko dikha doge, kuch models premature
wrap-up karne lagte hain ("main naya session suggest karta hoon"). Countdown
context me render mat karo — budget harness ke paas rakho.

---

## 7. Retrieval vs Preloading — kaunsa kab

```
PRELOAD (sab kuch context me daal do)
  ✅ Predictable — model ko dhoondhna nahi padta, koi retrieval-miss nahi
  ✅ Cacheable — static prefix, 0.1x read cost
  ✅ Zero extra latency (no vector search round-trip)
  ❌ Fixed cost har call pe
  ❌ Corpus badhne pe scale nahi karta
  ❌ Context rot — 200K ka preload signal ko patla kar deta hai

RETRIEVAL (on-demand khincho)
  ✅ Corpus size ke saath scale karta hai (millions of docs)
  ✅ Context me sirf relevant material
  ❌ Retrieval miss = model ko pata bhi nahi chalega ki kuch chhoot gaya
  ❌ Extra latency + embedding infra
  ❌ Har query ka result alag → CACHE INVALIDATE (yeh sabse under-appreciated cost hai)
```

**Decision heuristic:**

| Situation | Choose |
|---|---|
| Corpus < ~30-50K tokens aur har task me relevant | **Preload** (cache kar do, sasta ho jayega) |
| Corpus bada par har task ka subset chhota | **Retrieval** |
| Corpus bada, aur agent khud navigate kar sakta hai (filesystem, repo) | **Agentic search** — `grep`/`glob` de do, vector DB mat banao |
| Bahut saare tools, har request me kuch hi relevant | **Tool search + `defer_loading`** |

Teesra option jo log bhool jaate hain: **agentic retrieval**. Coding agents
mostly vector DB nahi use karte — woh `grep`, `glob`, `read` use karte hain. Model
khud dhoondhta hai, aur woh search ek sub-agent me chal sakti hai (section 5) taaki
intermediate noise main context me na aaye. `05_...` se `08_query_transformation.md`
tak ka Level5 RAG material tab lagta hai jab corpus genuinely unstructured aur
bada ho — repo ke liye nahi.

**Tool schemas bhi context hain.** 50 tools ke schemas har call pe bheje jaate
hain. `defer_loading: true` + tool-search tool use karo: schemas tabhi load hote
hain jab relevant ho, aur — important — woh **append** hote hain, swap nahi, isliye
cached prefix bacha rehta hai.

---

## 8. Tool-Result Truncation — bada output kaise handle karein

Sabse tezi se context bharne wali cheez: ek `read_file` jo 3000-line file wapas
karta hai, ya ek `SELECT *` jo 10K rows deta hai.

```
Strategy ladder (upar se neeche, jaise output bada hota jaye):

1. FULL             — chhota output, jaisa hai waisa daal do
2. HEAD + TAIL      — pehli 50 + aakhri 50 lines + "… 2900 lines omitted …"
3. SUMMARIZE        — LLM se gist banwao (extra call, isliye selectively)
4. OFFLOAD + POINTER— disk pe likho, context me sirf path + preview do
5. NEVER IN CONTEXT — PTC (section 5) — result script me rahe, context me nahi
```

```python
MAX_TOOL_RESULT_TOKENS = 2000

def shape_tool_result(name: str, raw: str, run_dir: str) -> str:
    if count_tokens(raw) <= MAX_TOOL_RESULT_TOKENS:
        return raw

    # Offload — model ko pointer do, poora content nahi
    path = f"{run_dir}/{name}_{uuid4().hex[:8]}.txt"
    Path(path).write_text(raw)
    lines = raw.splitlines()
    return (
        f"[Output {len(lines)} lines / ~{count_tokens(raw)} tokens — truncated]\n"
        f"[Full output saved to: {path} — use read_file with a line range]\n\n"
        + "\n".join(lines[:50])
        + f"\n… {len(lines) - 100} lines omitted …\n"
        + "\n".join(lines[-50:])
    )
```

Yeh pattern itna standard ho gaya hai ki APIs khud kar rahe hain: Claude Managed
Agents me koi tool 100,000 characters (~25K tokens) se zyada return kare to output
**automatically** sandbox file me offload ho jaata hai — model ko truncated preview
+ file path milta hai, aur woh chahe to `read` kar sakta hai.

**Do critical details:**

1. **Purane tool results ko current turn se zyada aggressively trim karo.** Abhi
   ka `read_file` full chahiye; 20 turns purana `read_file` ka result shayad ek
   line me collapse ho sakta hai (ya context editing se clear ho sakta hai).
2. **Truncation ko visible banao.** Kabhi chupchaap mat kaato — model ko batao ki
   kaata gaya hai aur poora kaise milega. Silent truncation se model galat
   conclusion nikaalta hai ("file me sirf 50 lines hain").

---

## 9. Memory Files vs In-Context

```
IN-CONTEXT MEMORY (conversation history)
    Scope:     ek session
    Cost:      har call pe re-sent (cache ke saath sasta, par zero nahi)
    Fidelity:  verbatim
    Limit:     window size

FILE-BASED MEMORY (/memories, CLAUDE.md, notes.md)
    Scope:     sessions ke paar — process restart survive karta hai
    Cost:      context me sirf tab jab model read kare
    Fidelity:  jo likha tha wahi (par model ko read karna yaad rehna chahiye)
    Limit:     practically unlimited
```

Claude ka memory tool (`{"type": "memory_20250818", "name": "memory"}`) ek
client-side tool hai — model `/memories` directory me `view` / `create` /
`str_replace` / `insert` / `delete` / `rename` karta hai, aur **storage backend
aap implement karte ho**.

Yahi mechanism aap already use kar rahe ho: is repo ka `CLAUDE.md` ek memory file
hai jise harness padh ke system prompt me fold kar deta hai.

**Memory file design rules (jo actually kaam karte hain):**

```
✅  Ek file = ek lesson, upar ek-line summary
✅  Architecture, data models, workflows likho — inhe model guess nahi kar sakta
✅  Correction aur confirmed approach dono likho, aur "kyun" bhi
✅  Purani note update karo, duplicate mat banao; galat note delete karo

❌  Hardcoded paths / flags / version numbers — code ship hote hi rot ho jaate hain
❌  Woh cheez jo repo ya chat history me already hai
❌  Ek session ka stumble permanent rule bana dena ("recency trap")
❌  Secrets, API keys, tokens — memory har future session me replay hoti hai
```

> ⚠️ **Security:** memory files future contexts me verbatim replay hoti hain. Ek
> baar API key likh di to woh har us session me chali jayegi jo store mount karta
> hai. Credentials kabhi memory me mat likho.

---

## 10. Worked Example — ek coding agent ka context layout, block by block

Yeh ek realistic 200K-budget coding agent ka assembled context hai, turn 25 pe.
Har block ke saath: kitne tokens, kyun hai, kahan baithta hai, cache status.

```
╔══════════════════════════════════════════════════════════════════════════════╗
║ BLOCK 1 — TOOL SCHEMAS                              ~4,000 tok   [CACHED]    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ read_file, write_file, edit_file, glob, grep, bash, run_tests, spawn_agent   ║
║                                                                              ║
║ WHY:  8 tools, alphabetically sorted → deterministic bytes                   ║
║ NOTE: 40 aur specialist tools `defer_loading: true` pe hain — tool-search se ║
║       load hote hain, isliye prefix nahi badalta                             ║
║ RULE: mid-run ek bhi tool add/remove nahi. Yeh position 0 hai — sab invalid.  ║
╚══════════════════════════════════════════════════════════════════════════════╝
╔══════════════════════════════════════════════════════════════════════════════╗
║ BLOCK 2 — FROZEN SYSTEM PROMPT                      ~2,500 tok   [CACHED]    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ Role, safety rules, output conventions, tool-usage guidance                  ║
║                                                                              ║
║ WHY:  behaviour define karta hai, har turn pe relevant                       ║
║ RULE: ZERO interpolation. Koi date nahi, koi username nahi, koi mode flag    ║
║       nahi. Ek f-string yahan poore cache ko maar deta hai.                   ║
╚══════════════════════════════════════════════════════════════════════════════╝
╔══════════════════════════════════════════════════════════════════════════════╗
║ BLOCK 3 — PROJECT MEMORY (CLAUDE.md)                ~1,800 tok   [CACHED]    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ Repo conventions, architecture, build/test commands, gotchas                  ║
║                                                                              ║
║ WHY:  har turn pe relevant, session ke andar kabhi nahi badalta               ║
║ SIZE: deliberately chhota. Yeh grow karta rehta hai agar discipline na ho —   ║
║       "ek session me yeh galti hui" wali lines audit karke nikalte raho.      ║
║                          ◄── cache_control breakpoint #1 YAHAN ──►            ║
║ Ab tak: ~8,300 tokens cached. Har call pe 0.1x cost. Yeh 90% saving hai.      ║
╚══════════════════════════════════════════════════════════════════════════════╝
╔══════════════════════════════════════════════════════════════════════════════╗
║ BLOCK 4 — COMPACTED EARLY HISTORY                   ~1,200 tok   [CACHED]    ║
╠══════════════════════════════════════════════════════════════════════════════╣
║ "Turns 1-14 summary: user ne payment retry bug fix karne ko kaha.            ║
║  Root cause `retry.py:88` me exponential backoff ka overflow.                ║
║  Approach A (clamp) reject kiya kyunki test_max_delay fail hua.              ║
║  Approach B (cap + jitter) chuna. Files chhui: retry.py, test_retry.py.      ║
║  Constraint discovered: staging DB read-only hai, isliye integration test    ║
║  local sqlite pe chalana hai."                                                ║
║                                                                              ║
║ WHY:  original requirement + decisions + constraints — sab bacha              ║
║ GONE: 14 turns ke raw tool outputs (~38,000 tokens the) — 97% reduction       ║
║                          ◄── cache_control breakpoint #2 YAHAN ──►            ║
╚══════════════════════════════════════════════════════════════════════════════╝
╔══════════════════════════════════════════════════════════════════════════════╗
║ BLOCK 5 — RETRIEVED CODE CONTEXT                    ~6,000 tok   [not cached]║
╠══════════════════════════════════════════════════════════════════════════════╣
║ retry.py (full, 180 lines) + test_retry.py ke 3 relevant test functions       ║
║                                                                              ║
║ WHY:  yeh woh files hain jo IS waqt edit ho rahi hain — full fidelity chahiye ║
║ NOT:  poora repo. 400 aur files `grep`/`read` ke peeche hain, on demand.      ║
║ NOTE: yeh badalta rehta hai jaise focus shift hota hai, isliye breakpoint     ║
║       ke baad hai — warna har file switch cache ko maarta                     ║
╚══════════════════════════════════════════════════════════════════════════════╝
╔══════════════════════════════════════════════════════════════════════════════╗
║ BLOCK 6 — RECENT TURNS (verbatim, last 10)          ~9,000 tok   [not cached]║
╠══════════════════════════════════════════════════════════════════════════════╣
║ Turn 15-24: tool_use / tool_result pairs, poore detail me                     ║
║                                                                              ║
║ WHY:  immediate working state — model ko exact test output, exact error       ║
║       message, exact diff chahiye. Yahan summarize karna quality maarta hai.  ║
║ NOTE: purane tool results (turn 15-18) truncated hain (head+tail+pointer);    ║
║       turn 22-24 full hain. Recency = fidelity.                              ║
║ TRAP: agar ek turn 20+ blocks bana de, next breakpoint peeche dekh nahi       ║
║       paayega (20-block lookback) → yahan intermediate breakpoint daalo       ║
╚══════════════════════════════════════════════════════════════════════════════╝
╔══════════════════════════════════════════════════════════════════════════════╗
║ BLOCK 7 — SUB-AGENT FINDINGS                          ~400 tok   [not cached]║
╠══════════════════════════════════════════════════════════════════════════════╣
║ "Search agent: `compute_backoff` ke 3 aur call-sites mile —                   ║
║  worker.py:210, jobs/dispatch.py:77, legacy/poller.py:145.                    ║
║  Pehle do same bug se affected; teesra apna clamp use karta hai."             ║
║                                                                              ║
║ WHY:  sub-agent ne 40 files padhi (~85,000 tokens uske apne context me)       ║
║       aur 400 tokens wapas kiye. Yeh 99.5% context saving hai.                ║
║ RULE: transcript nahi aaya — sirf finding. Yeh isolation ka pura point hai.   ║
╚══════════════════════════════════════════════════════════════════════════════╝
╔══════════════════════════════════════════════════════════════════════════════╗
║ BLOCK 8 — CURRENT USER TURN + KEY CONSTRAINTS         ~300 tok   [not cached]║
╠══════════════════════════════════════════════════════════════════════════════╣
║ "Baaki do call-sites bhi fix karo."                                          ║
║ <key_constraints>                                                            ║
║   - legacy/poller.py mat chhuo (alag team owns it)                           ║
║   - har edit ke baad `pytest tests/test_retry.py` chalao                      ║
║ </key_constraints>                                                           ║
║                                                                              ║
║ WHY:  END position = strongest recall (context rot, section 6B). Sabse        ║
║       important constraints yahan repeat karte hain, beech me nahi.           ║
║ NOTE: yahan koi breakpoint nahi — yeh har turn badalta hai, cache karna       ║
║       ulta nuksan (har turn ek naya cache write = 1.25x)                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

TOTAL: ~25,200 tokens  (cached: ~9,500 @ 0.1x  |  fresh: ~15,700 @ 1.0x)

Bina context engineering ke yeh context ~180,000 tokens hota —
har call pe full price, aur quality bhi kharab (context rot).
Effective input cost ≈ 16,650 token-equivalents vs 180,000. ~10x saving.
```

**Is layout ke 6 load-bearing decisions:**

1. Tools + system + memory sabse pehle → sabse bada cacheable prefix.
2. Compaction ne decisions bachaye, tool-noise phenka — original requirement verbatim.
3. Retrieval ne 400 files ko 2 files bana diya.
4. Sub-agent ne 85K exploration ko 400-token finding bana diya.
5. Truncation ne purane tool results ko pointer bana diya, naye full rakhe.
6. Critical constraints end me repeat — jahan recall sabse strong hai.

---

## 11. Metrics — context engineering ko measure kaise karein

Bina numbers ke yeh sab vibes hai. Yeh 5 metrics track karo:

| Metric | Formula | Kya batata hai |
|---|---|---|
| **Tokens per completed task** | total input+output tokens ÷ successful tasks | Overall efficiency — primary north star |
| **Cache hit ratio** | `cache_read` ÷ (`cache_read` + `cache_creation` + `input_tokens`) | Prefix discipline kitni achhi hai |
| **Context utilization** | peak context tokens ÷ window size | Kab compaction trigger hoga |
| **Compaction frequency** | compactions per task | Zyada = budget ya retrieval strategy galat hai |
| **Post-compaction success delta** | success rate (compacted runs) − (non-compacted) | Compaction quality kaat raha hai ya nahi |

```python
# Har API call pe accumulate karo — yeh basic observability hai
def record(usage, run):
    run["input"]  += usage.input_tokens
    run["write"]  += usage.cache_creation_input_tokens
    run["read"]   += usage.cache_read_input_tokens
    run["output"] += usage.output_tokens

def cache_hit_ratio(run):
    total_prompt = run["input"] + run["write"] + run["read"]
    return run["read"] / total_prompt if total_prompt else 0.0
```

Agar `cache_hit_ratio` repeated-prefix requests pe ~0 hai, koi silent invalidator
hai — section 3 ki table dobara padho aur do consecutive requests ke rendered
prompt bytes diff karo.

`08_observability.md` (Level 8) me tracing side hai; yeh uska token-economics half hai.

---

## 12. Anti-Patterns Checklist

```
❌  Sab kuch preload karna "kyunki window bada hai"
     → cost + context rot. Window budget nahi hai.

❌  System prompt me timestamp / user ID interpolate karna
     → poore cache ko maar deta hai, aur usually koi zaroorat nahi hoti

❌  Mid-conversation tools add/remove karna
     → tools position 0 pe hain, poora prefix invalid.
       Modern APIs me iska cache-safe raasta hai (deferred tools + tool_addition
       blocks), par default assumption "mat karo" hi rakho.

❌  Sub-agent ka poora transcript main context me daalna
     → isolation ka pura point khatam. Result do, trace nahi.

❌  Tool results ko chupchaap truncate karna
     → model ko lagega poora data mila hai, galat conclusion nikaalega

❌  Context 100% bharne ka wait karna compaction ke liye
     → compaction call khud fail ho jayegi. 70-80% pe trigger karo.

❌  Compaction summary me original user requirement drop kar dena
     → agent bhatak jayega. #1 preserved item yahi hai.

❌  Remaining-token countdown model ko dikhana
     → premature wrap-up behaviour trigger hota hai

❌  Memory file ko append-only treat karna
     → 6 mahine me 40K-token file jo har session me load hoti hai.
       Prune karo. Galat notes delete karo.

❌  `tiktoken` se Claude tokens count karna
     → galat tokenizer. 15-20%+ undercount. Provider ka count_tokens use karo.

❌  Har context problem pe RAG lagana
     → agar agent ke paas grep/glob hai, agentic search simpler + behtar hai
```

---

## Interview Q&A

**Q: Context engineering aur prompt engineering me exact difference kya hai?**
A: Prompt engineering **content** ka question hai — model ko kya bolein taaki
behaviour theek ho; scope ek call ka hota hai, artifact text hai. Context
engineering **assembly** ka question hai — har call pe context window me kya jayega,
kis order me, kitna, aur kya nahi jayega; scope poora agent run hai (50+ calls),
artifact ek pipeline hai. Prompt engineering ka failure "model ne galat samjha" hai;
context engineering ka failure "signal noise me dab gaya" ya "budget khatam ho gaya"
hai. Practically: prompt engineer prompt file edit karta hai, context engineer
`assemble_context()` function likhta hai.

**Q: Context window 1M tokens ka hai — to context management ki zaroorat hi kya hai?**
A: Teen wajah. **Cost** — har call pe poora context dobara bhejte ho; 50-call loop
me 200K context = 10M input tokens. **Latency** — bada prefill matlab slow
time-to-first-token. Aur sabse important, **quality** — bada context better answer
guarantee nahi karta; long-context recall beech me sabse kamzor hoti hai
("lost in the middle"), aur relevant signal irrelevant material me dab jaata hai.
Window ek ceiling hai, target nahi.

**Q: Prompt caching ka core invariant kya hai, aur usse layout kaise decide hota hai?**
A: Caching ek **prefix match** hai — prefix me kahin bhi ek byte badla to uske
baad ka sab invalidate. Render order `tools → system → messages` hai. Isliye
layout rule ban jaata hai: **stability order = physical order**. Jo kabhi nahi
badalta (tool schemas, frozen system prompt, project memory) sabse pehle, breakpoint
uske baad; jo har request pe badalta hai (current question, retrieved snippets)
sabse aakhir me. Cache read ~0.1x cost hai, write ~1.25x, to 5-min TTL pe
break-even 2 requests hai — agent loops me trivially cross ho jaata hai.

**Q: Ek team bol rahi hai unki caching kaam nahi kar rahi. Aap kaise debug karoge?**
A: Pehle confirm karo — `usage.cache_read_input_tokens` repeated requests pe zero
hai? Agar haan, silent invalidator hai. Common culprits order me: system prompt me
`datetime.now()` ya request UUID; `json.dumps` bina `sort_keys=True` (non-deterministic
bytes); per-user tool list (`build_tools(user)` — tools position 0 pe hain);
conditional system sections; mid-run model switch (cache model-scoped hai). Do
consecutive requests ke rendered prompt bytes diff kar do, culprit turant dikhega.
Do aur non-obvious cases: prefix model ke minimum se chhota hai (Opus 4.6/Haiku 4.5
pe 4096 tokens — chhota prefix chupchaap cache nahi hota, error nahi milta), aur
20-block lookback — agentic turn me 20+ content blocks ban gaye to next breakpoint
purana entry dhoondh hi nahi paata.

**Q: Compaction aur context editing me kya farak hai? Kaunsa kab?**
A: Compaction purani history ko **summary se replace** karta hai — ek extra LLM
call lagti hai, detail chali jaati hai par reasoning thread bacha rehta hai.
Context editing purane blocks ko **hata deta** hai — free hai, par content poora
chala jata hai. Rule: pehle **clear** karo (stale tool results, purane thinking
blocks — free hai), phir bhi bhara hai to **compact** karo. Production agents
dono use karte hain. Aur trigger 70-80% pe rakho, 100% pe nahi — warna compaction
call khud context-window-exceeded se fail ho jayegi.

**Q: Compaction me kya bachana zaroori hai?**
A: Priority order: (1) original user requirement — yeh kho gaya to agent bhatak
jaata hai, yahi #1 miss hai; (2) decisions aur unke reasons ("A reject kiya kyunki
test X fail hua") — warna agent wahi dead-end dobara try karega; (3) current state
(kaunsi files chhui, kya pass/fail); (4) mid-run discovered constraints; (5) open
questions. Chhod sakte ho: routine tool-call noise, verbose file contents jo ab
irrelevant hain, aur woh intermediate reasoning jiska conclusion (2) me capture ho
gaya. Server-side compaction use kar rahe ho to compaction block wapas bhejna mat
bhoolo — sirf `.text` append karoge to state chupchaap kho jayega.

**Q: Sub-agent context isolation kya hai aur woh ek lambe context se better kyun hai?**
A: Sub-agent ko apna **fresh context window** milta hai. Main agent 50 files khud
padhe to 100K tokens permanently uske context me baith jaate hain aur har agle turn
pe re-send hote hain — jabki 90% content ek baar hi use hua tha. Uski jagah 5
sub-agents spawn karo, har ek apne context me kaam kare, aur wapas **result** bheje
— transcript nahi. Practice me 85K ka exploration 400-token finding ban jaata hai.
Do gotchas: (1) transcript kabhi wapas mat daalo, isolation ka pura point wahi hai;
(2) fork ko parent ka `system`/`tools`/`model` **verbatim** copy karna chahiye,
warna parent ka cache completely miss karega.

**Q: Context poisoning kya hai aur usse kaise bachein?**
A: Ek galat fact context me aa gaya (model hallucination, ya galat tool result),
aur ab woh conversation history ka permanent hissa hai — model har agle turn me use
padhta hai aur us par build karta rehta hai. Self-reinforcing loop hai, model khud
se recover nahi karta. Mitigations: system prompt me require karo ki har progress
claim ek tool result se verify ho ("jo verified nahi, usko explicitly unverified
bolo"); tool results ko authoritative treat karo model ke apne statements ke
mukable; aur compaction ko flush ka mauka samjho — summary regenerate karte waqt
sirf tool-verified facts carry karo.

**Q: Retrieval karein ya preload? Decide kaise karoge?**
A: Corpus size aur cache economics se. Corpus ~30-50K tokens se chhota aur har
task me relevant → **preload** karo aur cache kar do; 0.1x read cost pe woh
retrieval se sasta aur zyada reliable hai (koi retrieval miss nahi). Corpus bada
par per-task subset chhota → **retrieval**. Corpus bada aur agent khud navigate kar
sakta hai (repo, filesystem) → **agentic search** — `grep`/`glob` do, vector DB mat
banao. Retrieval ka under-appreciated cost yeh hai ki har query ka result alag
hota hai, isliye woh **cache invalidate** karta hai — usko breakpoint ke baad rakho.

**Q: Ek tool 5000-line file return karta hai. Kya karoge?**
A: Ladder hai: chhota output as-is; medium output head+tail+omitted-count;
usse bada LLM summary (selectively, extra call hai); usse bada **offload +
pointer** — disk pe likho, context me path + preview do, model chahe to line-range
se read kare; aur sabse aggressive, PTC — tool result script me rahe, model ke
context me aaye hi na. Do rules: purane tool results ko current turn se zyada
aggressively trim karo (recency = fidelity), aur truncation **hamesha visible**
banao — silent truncation se model sochega poora data mila hai aur galat conclusion
nikaalega.

**Q: Memory file kab use karein aur in-context kab?**
A: In-context = ek session, verbatim, har call pe re-sent, window-limited.
Memory file = cross-session, restart survive karta hai, context me tabhi aata hai
jab model read kare. Rule: **session state** in-context; **durable knowledge**
(architecture, conventions, workflows, learned corrections) file me. Memory file
design: ek file ek lesson, upar one-line summary, "kyun" bhi likho, purani note
update karo duplicate mat banao, aur prune karte raho — warna 6 mahine me 40K-token
file ban jaati hai jo har session me load hoti hai. Aur kabhi credentials mat likho:
memory har future session me verbatim replay hoti hai.

**Q: Context engineering ki success kaise measure karoge?**
A: Primary metric **tokens per completed task** hai — completion se normalize
karna zaroori hai, warna aap sirf context chhota kar ke success rate gira sakte ho.
Supporting: cache hit ratio (`cache_read` ÷ total prompt tokens) prefix discipline
batata hai; context utilization (peak ÷ window) batata hai compaction kab lagega;
compactions-per-task zyada ho to budget ya retrieval strategy galat hai; aur
post-compaction success delta — same golden tasks compaction on vs off — batata hai
ki summarization quality kaat raha hai ya nahi.

---

## Related Topics

- `12_agent_harness_engineering.md` — **pehle padho.** Harness ka overall shape;
  yeh doc uske §4 (context management) aur §6 (sub-agents) ko poora topic banata hai
- `07_multi_agent_supervisor.md` — delegation pattern; yahan usko context-economics
  lens se dobara dekha gaya hai
- `03_agent_memory.md` — memory frameworks (Mem0, Zep); yeh doc batata hai ki
  memory **context budget** me kaise fit hoti hai
- `10_agent_evaluation.md` — eval harness; context metrics wahan ke metrics ke saath belong karte hain
- [../Level3_LLM_APIs_SDKs](../Level3_LLM_APIs_SDKs) — `10_cost_optimization.md` +
  prompt caching mechanics
- [../Level5_RAG_Vector_Databases](../Level5_RAG_Vector_Databases) — retrieval side
  (`04_chunking_strategies.md`, `07_reranking.md`, `10_contextual_retrieval.md`)
- [../Level8_Production_LLMOps](../Level8_Production_LLMOps) — `08_observability.md`
  (tracing) + `10_cost_optimization_advanced.md`
- `Modern_Topics/11_coding_agent_harness_deep_dive.md` — real coding-agent context
  layouts, section 10 ka production version
