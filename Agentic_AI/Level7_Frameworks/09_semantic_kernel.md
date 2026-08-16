# Semantic Kernel — Microsoft's Agent Orchestration SDK (deep dive)

> **Practical code:** [`09_semantic_kernel_practical.py`](09_semantic_kernel_practical.py) — mock mode me
> bhi chalta hai (SDK/key na ho to bhi auto-function-calling loop apni aankho se dikhega).
>
> **Kyun padh rahe ho:** SK khud tumhara daily driver nahi banega. Par jo companies Azure/.NET
> shop hain (PwC ka "Microsoft" specialism, UnitedHealth, ZF, Dassault) unke JD me yeh naam
> aata hai. Aur 2026 me SK ka naam **Microsoft Agent Framework** ban chuka hai — yeh timeline
> jaanna interview me sabse strong signal hai (§15). Tumhe **nayi agent theory nahi** seekhni:
> tum LangChain/LangGraph/PydanticAI already jaante ho. Yeh doc SK ka **vocabulary + design
> philosophy** tumhare Python backend mental model pe map karta hai.

---

## ⚠️ 2026 reality check — pehle yeh padho (warna galat baat bologe)

Microsoft ne SK aur AutoGen ko merge karke ek naya SDK banaya: **Microsoft Agent Framework (MAF)**.

```
Oct 2025   → MAF announce (public preview). "SK + AutoGen = one SDK"
Feb 2026   → MAF Release Candidate — API surface freeze
Apr 2026   → MAF 1.0 ship (.NET + Python). SK aur AutoGen isme fold ho gaye
2026 me    → AutoGen maintenance mode. SK maintained + compatibility bridge, par
             naye greenfield projects ke liye Microsoft MAF recommend karta hai
```

**Iska matlab tumhare liye kya:**

| Sawal | Jawab |
|---|---|
| SK padhna waste hai? | Nahi. MAF ke **enterprise concepts SK se hi aaye** hain (middleware/filters, typed tools, telemetry, session state). SK samajh liya = MAF 80% samajh liya. |
| Interview me kya bolna? | "Main SK ke concepts pe kaam karta hoon; 2026 me wo Microsoft Agent Framework 1.0 me converge ho gaya hai — Kernel+Plugin model ab Agent+Tool model hai, aur migration ek weekend ka kaam hai, rewrite nahi." |
| Kya galti nahi karni? | SK ko "latest Microsoft agent SDK" bolke present karna. Aur **Planners** ko current feature bolna (§9). Dono outdated signals hain. |

**Version note:** SK Python ka API 1.x me kaafi hila hai (`kernel=` → `service=` in agents,
`SemanticTextMemory` → new vector store abstractions, `AgentGroupChat` → orchestrations).
Neeche ke snippets **concept-accurate** hain; exact import path apne installed version me verify karo:
```bash
pip show semantic-kernel && python -c "import semantic_kernel; print(semantic_kernel.__version__)"
```

---

## 1. Ek line me — aur SK exist kyun karta hai

**Semantic Kernel = Microsoft ka LangChain.** Same problem: LLM ko tumhare code/tools/data se
jodhna, aur us loop ko production-grade banana.

Par "same as LangChain" bolke ruk jaana adhoora hai. SK ka **design bias** alag hai, aur wahi
interview ka asli answer hai:

| | LangChain / LangGraph | Semantic Kernel |
|---|---|---|
| Pehla citizen | Python | **C#/.NET** (Python + Java parity ke saath) |
| Design metaphor | Functional composition (LCEL `\|` pipes), graph of nodes | **Dependency Injection container** (ASP.NET Core style) |
| Tool ka roop | `@tool` decorated function | **Plugin class** = related functions ka group |
| Governance | Callbacks + LangSmith | **Filters** = middleware pipeline (first-class, §8) |
| Cloud bias | Cloud-agnostic | **Azure-native** (AOAI, AI Search, Foundry, Managed Identity) |
| Kaun maangta hai | Startups, Python shops | Enterprise, regulated, Azure-committed |

**SK ka existence reason:** 2023 me enterprise ke paas C# backend the, aur LangChain Python-only
tha. Microsoft ko ek SDK chahiye tha jo ASP.NET developer ko familiar lage — isliye **kernel ek
DI container jaisa hai**, tools **classes** hain (not loose functions), aur cross-cutting concerns
**middleware/filters** se handle hote hain. Yeh accident nahi, deliberate hai.

> **Interview one-liner:** *"SK aur LangChain same problem solve karte hain — tool-calling LLM
> orchestration. Fark framework merit ka nahi, ecosystem fit ka hai. SK ka design ASP.NET DI se
> udhaar liya gaya hai, isliye Azure/.NET enterprise me natural lagta hai; LangGraph Python-first
> cloud-agnostic shops me. Main stack dekh ke choose karta hoon, framework fashion dekh ke nahi."*

---

## 2. Vocabulary map — jo tum already jaante ho uspe rakho

Yeh table sabse important cheez hai is doc me. Ise ratt lo, baaki syntax hai.

| Tumhara Python backend | SK ka naam | LangChain equivalent |
|---|---|---|
| FastAPI ka DI container / Django `settings` + app registry | **Kernel** | (koi single object nahi — chain khud) |
| Ek service class / router module | **Plugin** | tools ka module |
| Ek endpoint function | **Kernel Function** (native) | `@tool` function |
| Jinja template + LLM call wrapper | **Prompt Function** | `PromptTemplate \| llm` chain |
| Pydantic request model se OpenAPI schema | `Annotated[...]` se **auto JSON schema** | `args_schema` / docstring parsing |
| Middleware (`BaseHTTPMiddleware`) | **Filter** | callbacks/handlers |
| Celery task chain / state machine | **Process Framework** | LangGraph |
| Background worker with role | **Agent** (`ChatCompletionAgent`) | AgentExecutor / LangGraph node |
| Multiple workers coordinating | **Agent Orchestration** | LangGraph multi-agent / CrewAI |
| `requests`/httpx client to OpenAI | **AI Service connector** | `ChatOpenAI` |
| pgvector repo class | **Vector Store connector** | VectorStore |
| APM (OTel → Datadog) | **built-in OTel** → App Insights | LangSmith / Langfuse |

---

## 3. Kernel — asal me ek DI container hai

Yeh SK ka sabse misunderstood part hai. Log samajhte hain kernel "the agent" hai. Nahi —
**kernel ek registry + invoker hai**. Bilkul aisa jaise Django ka app registry: khud kuch nahi
karta, par har cheez usme registered hai aur wahi se resolve hoti hai.

```python
import asyncio
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion, AzureChatCompletion

kernel = Kernel()

# --- Option A: plain OpenAI ---
kernel.add_service(
    OpenAIChatCompletion(
        ai_model_id="gpt-4o-mini",
        api_key="sk-...",
        service_id="fast",          # <-- yeh label hai, isse baad me resolve karoge
    )
)

# --- Option B: Azure OpenAI (enterprise me 90% yahi) ---
kernel.add_service(
    AzureChatCompletion(
        deployment_name="gpt-4o",           # Azure me MODEL nahi, DEPLOYMENT name jaata hai
        endpoint="https://myres.openai.azure.com/",
        api_key="...",                      # ya credential=DefaultAzureCredential()
        service_id="smart",
    )
)
```

### Do cheezein jo interview me bolni chahiye

**(a) `service_id` = multi-model routing.** Ek hi kernel me sasta aur mehanga model dono
register karo, phir per-call choose karo. Yeh cost-control ka enterprise pattern hai:

```python
# cheap model se classify karo, mehange se likhwao
res = await kernel.invoke(function_name="classify", plugin_name="triage",
                          service_id="fast")
```

**(b) Azure me API key mat use karo — Managed Identity use karo.** Yeh wo detail hai jo
"portal khola hai" prove karti hai:

```python
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
)
kernel.add_service(AzureChatCompletion(
    deployment_name="gpt-4o",
    endpoint="https://myres.openai.azure.com/",
    ad_token_provider=token_provider,       # key nahi, identity
    service_id="smart",
))
```
> **Kyun:** key rotate karni padti hai, leak hoti hai, Key Vault chahiye. Managed Identity me
> app ko Azure AD role (`Cognitive Services OpenAI User`) milta hai — koi secret hi nahi hota.
> PwC/consulting client ke security review me literally yeh puchha jaata hai.

---

## 4. Native plugins — plain Python function jo LLM call kar sakta hai

### 4.1 Basic shape

```python
from typing import Annotated
from semantic_kernel.functions import kernel_function

class OrderPlugin:
    """Ek plugin = related functions ka group. Class hona zaroori nahi, par
    idiomatic SK me class hi use hoti hai (DI-friendly, testable, stateful)."""

    def __init__(self, db):          # <-- yahi asli fayda: dependency inject karo
        self.db = db

    @kernel_function(
        name="get_order_status",
        description="Get the current delivery status of an order by its order ID.",
    )
    def get_order_status(
        self,
        order_id: Annotated[str, "The order ID, e.g. ORD-4521"],
    ) -> Annotated[str, "Human-readable status string"]:
        row = self.db.fetch_order(order_id)
        return f"Order {order_id} is {row['status']}"

kernel.add_plugin(OrderPlugin(db=my_db), plugin_name="orders")
```

Model ke liye is function ka naam ban jaata hai: **`orders-get_order_status`**
(plugin name + separator + function name). LangChain me flat tool names hote hain; SK me
namespaced. Isse bade codebase me collision nahi hota — 40 tools ke saath yeh matter karta hai.

### 4.2 Schema kaise banta hai — yeh samajhna zaroori hai

SK `inspect` + type hints + `Annotated` metadata padhkar JSON schema banata hai, exactly
jaise FastAPI Pydantic model se OpenAPI banata hai:

```
@kernel_function(description=...)      →  function.description
parameter name                         →  properties key
Annotated[str, "..."]                  →  property type + description
default value hai?                     →  required se hat jaata hai
Pydantic model / dataclass type        →  nested object schema
```

Jo actually model ko bheja jaata hai:

```json
{
  "type": "function",
  "function": {
    "name": "orders-get_order_status",
    "description": "Get the current delivery status of an order by its order ID.",
    "parameters": {
      "type": "object",
      "properties": {
        "order_id": {"type": "string", "description": "The order ID, e.g. ORD-4521"}
      },
      "required": ["order_id"]
    }
  }
}
```

> **Rule jo har framework pe lagta hai:** `description` tumhara prompt hai. Model tumhara code
> nahi padhta, sirf yeh JSON padhta hai. Agar model galat tool call kar raha hai — 90% baar
> problem description me hai, model me nahi. Yeh baat interview me bolna — practitioner signal hai.

### 4.3 Async, streaming, aur return types

```python
class SearchPlugin:
    @kernel_function(description="Search internal docs for a query.")
    async def search(                                   # async fully supported
        self,
        query: Annotated[str, "Search query"],
        top_k: Annotated[int, "How many results"] = 3,  # default → optional param
    ) -> Annotated[list[str], "Matching snippets"]:
        return await self.client.search(query, top_k)
```

- **Async by default rakho** — SK ka core async hai (`await kernel.invoke(...)`). Sync function
  bhi chalta hai par event loop block karega. Tumhare FastAPI service me yeh disaster hai.
- Return type kuch bhi ho sakta hai; SK usko string me serialize karke model ko wapas deta hai.
  Bade objects (poora DB row dump) return karna = token bill. **Sirf jo model ko chahiye wahi return karo.**

### 4.4 Plugin banane ke 4 tareeke (interview me depth dikhata hai)

| Source | Kab use karo |
|---|---|
| **Native function** (`@kernel_function`) | Default. Tumhara business logic. |
| **Prompt function** (§5) | Jab "tool" khud ek LLM call hai (summarize, classify, rewrite) |
| **OpenAPI spec se import** | Existing REST API ko bina wrapper likhe tool bana do — enterprise favourite |
| **MCP server se import** | Standard tool servers (SK me MCP support hai; §15 me MAF me native hai) |

```python
# OpenAPI se plugin — enterprise me yeh killer feature hai
await kernel.add_plugin_from_openapi(
    plugin_name="billing",
    openapi_document_path="https://internal.api/billing/openapi.json",
)
# 30 endpoints = 30 tools, zero glue code. Auth headers execution settings me pass hote hain.
```
> Yeh baat bolna: *"Purane REST estate wali company me main OpenAPI import use karta hoon —
> team ka existing swagger hi tool catalog ban jaata hai, aur governance already API gateway pe hai."*

---

## 5. Prompt functions — prompt bhi ek function hai

SK ka signature idea: **prompt aur code dono "function" hain**, same interface se invoke hote hain.
Isse tum ek hi pipeline me code aur prompt mila sakte ho.

```python
from semantic_kernel.functions import KernelFunctionFromPrompt
from semantic_kernel.connectors.ai.open_ai import OpenAIChatPromptExecutionSettings

summarize = KernelFunctionFromPrompt(
    function_name="summarize",
    plugin_name="text_utils",
    prompt="""
    Summarize the text in {{$style}} style, under 3 sentences.

    TEXT:
    {{$input}}
    """,
    prompt_execution_settings=OpenAIChatPromptExecutionSettings(
        service_id="fast", temperature=0.2, max_tokens=200,   # per-prompt model config
    ),
)
kernel.add_function(plugin_name="text_utils", function=summarize)

result = await kernel.invoke(plugin_name="text_utils", function_name="summarize",
                             input="long article...", style="casual")
```

### 5.1 Templating — teen syntax available

| Syntax | Kaisa dikhta hai | Kab |
|---|---|---|
| SK native | `{{$style}}`, `{{orders-get_order_status $order_id}}` | default; **native function ko prompt ke andar call kar sakte ho** |
| Handlebars | `{{#if x}}...{{/if}}` | conditionals/loops chahiye |
| Jinja2 | `{% for %}` | Python devs ko familiar |

Sabse interesting native cheez: **prompt ke andar se native function call**:

```
Customer ka order status: {{orders-get_order_status $order_id}}
Uske hisaab se ek polite reply likho.
```
Yeh ek deterministic RAG-lite pattern hai — model ko decide karne hi nahi dete ki tool call kare
ya na kare, **hum khud data prompt me inject kar dete hain**. Reliability chahiye to yeh
auto-function-calling se better hai. (LangChain me yeh `RunnablePassthrough.assign()` hota hai.)

### 5.2 Prompt-as-file (`prompty` / YAML) — production pattern

Prompt ko code se bahar rakho, taaki prompt change ke liye redeploy na ho aur review diff saaf rahe:

```
prompts/
└── summarize/
    ├── skprompt.txt          # prompt text with {{$input}}
    └── config.json           # model settings + input variable descriptions
```
```python
kernel.add_plugin(parent_directory="./prompts", plugin_name="text_utils")
```
> **Interview:** *"Main prompts ko versioned files me rakhta hoon, code me hardcode nahi —
> isse prompt change ek reviewable diff banta hai aur eval suite ke saath pin ho jaata hai."*

---

## 6. KernelArguments, ChatHistory, content types

```python
from semantic_kernel.functions import KernelArguments
from semantic_kernel.contents import ChatHistory

args = KernelArguments(order_id="ORD-4521", style="formal", settings=settings)
res = await kernel.invoke(plugin_name="orders", function_name="get_order_status", arguments=args)
print(str(res))              # FunctionResult — str() se value, .value se raw
```

- **`KernelArguments`** = ek dict jo template variables **aur** execution settings dono carry karta
  hai. Chain me aage badhta hai (ek function ka output next ke args me).
- **`ChatHistory`** = messages list ka wrapper (`add_user_message`, `add_assistant_message`,
  `add_system_message`). Isme tool calls aur tool results bhi messages ban ke jaate hain —
  yani conversation state **tumhare haath me** hai, framework chhupa ke nahi rakhta.
- **Content types**: `ChatMessageContent` (role + items), `TextContent`, `ImageContent`,
  `FunctionCallContent`, `FunctionResultContent`. Multimodal aur tool-calls ek hi message
  structure me fit hote hain.

> Yeh "state tumhare paas hai" property SK ki strength hai: history ko tum apne Postgres/Redis me
> serialize kar sakte ho, framework ke opaque checkpointer pe depend nahi karna padta.
> (LangGraph ulta approach leta hai — checkpointer built-in, powerful par framework-coupled.)

---

## 7. Automatic function calling — asli loop, step by step

```python
from semantic_kernel.connectors.ai.open_ai import OpenAIChatPromptExecutionSettings
from semantic_kernel.connectors.ai.function_choice_behavior import FunctionChoiceBehavior
from semantic_kernel.contents import ChatHistory

settings = OpenAIChatPromptExecutionSettings(
    function_choice_behavior=FunctionChoiceBehavior.Auto(),   # model khud decide karega
)

history = ChatHistory()
history.add_system_message("You are a support agent. Use tools; never invent order data.")
history.add_user_message("Cancel order ORD-4521 if it hasn't shipped.")

chat = kernel.get_service(service_id="smart")
response = await chat.get_chat_message_content(
    chat_history=history,
    settings=settings,
    kernel=kernel,        # <-- yeh zaroori hai; isi se plugins visible hote hain
)
print(response)
```

### Andar kya hota hai (yeh sequence interview me bolna)

```
1. SK kernel ke saare registered plugins → JSON tool schemas banata hai
2. history + tools → model ko bheja
3. model reply: FunctionCallContent(orders-get_order_status, {order_id: ORD-4521})
4. SK khud us function ko dhoondhta hai, arguments validate/coerce karta hai, CALL karta hai
   ↳ (yahin Filters chalte hain — §8)
5. result → FunctionResultContent message ban ke history me add
6. loop back to step 2 — model ne dekha "not shipped" → ab cancel_order call karega
7. jab model text reply deta hai (koi tool call nahi) → loop khatam, wahi answer return
```
**Yeh ReAct loop hi hai.** LangChain ka `AgentExecutor`, PydanticAI ka agent run, OpenAI ka
tool-runner — sab yahi. Isliye "nayi theory nahi seekhni" wali baat sach hai.

### FunctionChoiceBehavior — teen modes

| Mode | Behaviour | Kab |
|---|---|---|
| `Auto()` | model decide kare, ya text bole | default agentic |
| `Required()` | model ko **koi ek tool call karna hi padega** | structured extraction, "must fetch data first" |
| `NoneInvoke()` / `None_()` | schemas dikhao par execute mat karo | dry-run, audit, "kya call karta yeh dekhna hai" |

Do knobs jo production me bachate hain:

```python
FunctionChoiceBehavior.Auto(
    auto_invoke=True,                        # False → tum khud call karoge (HITL)
    filters={"included_plugins": ["orders"]} # is call me sirf yeh plugins visible
)
settings.function_choice_behavior.maximum_auto_invoke_attempts = 5   # runaway loop guard
```
> **`included_plugins` ka asli use:** 40 tools ek saath model ko dikhana accuracy girata hai aur
> tokens khata hai. Step ke hisaab se tool subset dikhao. Yeh "tool scoping" hai — LangGraph me
> tum per-node `bind_tools` karke same karte ho.

---

## 8. Filters — SK ka asli differentiator (yeh yaad rakhna)

LangChain me callbacks observability ke liye hain. SK ke **filters middleware hain — wo call
ko rok sakte hain, badal sakte hain, retry kar sakte hain**. Mental model: FastAPI middleware /
Django middleware, bas LLM pipeline pe.

Teen filter points:

| Filter | Kab chalta hai | Kaam |
|---|---|---|
| `FUNCTION_INVOCATION` | har function call ke around (native + prompt) | timing, logging, caching, error handling, result rewrite |
| `PROMPT_RENDERING` | prompt render hone ke baad, model ko bhejne se pehle | PII redaction, prompt-injection scan, banned-word check |
| `AUTO_FUNCTION_INVOCATION` | jab **model** ne khud tool call decide kiya | **approval gate**, blocking dangerous tools, early loop termination |

```python
from semantic_kernel.filters import FilterTypes

@kernel.filter(FilterTypes.FUNCTION_INVOCATION)
async def timing_and_audit(context, next):
    t0 = time.perf_counter()
    try:
        await next(context)                                  # asli call
    except Exception as e:
        logger.exception("fn %s failed", context.function.name)
        context.result = FunctionResult(function=context.function.metadata,
                                        value="Tool temporarily unavailable.")
        return                                               # exception swallow → graceful degrade
    logger.info("fn=%s ms=%.0f", context.function.name, (time.perf_counter()-t0)*1000)
```

```python
@kernel.filter(FilterTypes.AUTO_FUNCTION_INVOCATION)
async def human_approval(context, next):
    """Model ne refund call kiya? Pehle insaan se poochho."""
    if context.function.name in {"issue_refund", "cancel_order"}:
        if not await ask_human(context.arguments):
            context.result = FunctionResult(function=context.function.metadata,
                                             value="Denied by human reviewer.")
            context.terminate = True          # loop yahin rok do
            return
    await next(context)
```

```python
@kernel.filter(FilterTypes.PROMPT_RENDERING)
async def redact_pii(context, next):
    await next(context)
    rendered = context.rendered_prompt
    context.rendered_prompt = PII_RE.sub("[REDACTED]", rendered)
```

> **Yeh interview me kyun jeetata hai:** har candidate "guardrails lagane chahiye" bolta hai.
> Tum bolo — *"SK me main auto-function-invocation filter lagata hoon: destructive tools ke liye
> human approval, aur `context.terminate` se loop cut. Yeh cross-cutting concern hai, isliye
> middleware me hai, har tool ke andar duplicate nahi."* Yeh architecture-level jawab hai.
>
> LangChain me iska clean equivalent nahi hai — tumhe tool ke andar check likhna padta hai ya
> LangGraph me `interrupt()` node use karna padta hai. Comparison bolna strong signal hai.

---

## 9. Planners — legacy. Interview trap.

Purane SK tutorials **SequentialPlanner / StepwisePlanner / ActionPlanner** push karte the:
ek natural-language goal do, planner LLM poora multi-step plan (XML/JSON me) generate karta,
phir wo plan execute hota.

**Ab (2024+) yeh mostly dead hai. Kyun:**

1. Auto function calling (§7) wahi kaam simpler tareeke se karta hai
2. Modern models multi-step tool calls turn-by-turn reliably kar lete hain — alag planning phase ki zaroorat nahi
3. Generated plan **opaque** tha — debug karna mushkil, aur ek galat step poora plan tod deta tha
4. Plan generate hone ke baad world badal jaata tha (stale plan problem)

**Agar interviewer planners pe puchhe, yeh bolo:**
> *"Planners SK ka early approach tha task decomposition ke liye — ek planner call upfront poora
> function-call sequence banata tha. Modern SK aur industry broadly native function calling pe
> shift ho gayi, jahan same model turn-by-turn next step decide karta hai. Wahi shift LangChain me
> `PlanAndExecute` deprecate hone me dikha. Trade-off classic hai: upfront explicit plan (fragile,
> opaque, stale) vs reactive step-by-step (adaptive, observable)."*

Same trade-off tumne yahan padha tha: [`../Level6_Agent_Patterns/05_plan_and_execute.md`](../Level6_Agent_Patterns/05_plan_and_execute.md).
Nuance: upfront planning **wapas relevant** hai jab steps parallelize karne hain ya cost predict
karni hai (LLMCompiler-style) — par "planner" naam ke SK feature ke through nahi.

---

## 10. Agent Framework (SK ke andar) — single aur multi agent

### 10.1 `ChatCompletionAgent` — ek role-based agent

```python
from semantic_kernel.agents import ChatCompletionAgent

agent = ChatCompletionAgent(
    service=chat,                  # newer SK: service=; older: kernel=kernel
    name="SupportAgent",
    instructions="You resolve order issues. Always verify status before cancelling.",
    plugins=[OrderPlugin(db)],     # agent-scoped tools
)

thread = None
async for resp in agent.invoke(messages="Cancel ORD-4521", thread=thread):
    print(resp.content)
    thread = resp.thread           # AgentThread = conversation state carrier
```
Agent = **kernel + instructions + tools + thread** ka bundle. Iska matlab: ek hi kernel pe
multiple agents ban sakte hain, har ek apne instructions/tool subset ke saath.

`AgentThread` important hai: conversation state agent ke bahar rehta hai, isliye tum thread
persist karke resume kar sakte ho (aur Azure me `AzureAIAgent` ke saath thread **service-side**
Foundry me store hota hai — tumhe DB banana hi nahi padta).

### 10.2 Agent types

| Agent | Kya | Kab |
|---|---|---|
| `ChatCompletionAgent` | tumhare code me chalne wala agent, koi chat model | default, portable |
| `AzureAIAgent` | **Foundry Agent Service** pe hosted agent (server-side threads, tools, file search) | Azure enterprise, "state Microsoft manage kare" |
| `OpenAIAssistantAgent` | OpenAI Assistants API wrapper | OpenAI-hosted state |
| `OpenAIResponsesAgent` | Responses API based | naya OpenAI surface |

> **Discussion point:** hosted agent (`AzureAIAgent`) me threads/state cloud me hai — compliance
> ke liye kabhi acha (managed, audited) aur kabhi problem (data residency, vendor lock).
> Yeh trade-off bolna maturity dikhata hai.

### 10.3 Multi-agent — `AgentGroupChat` (purana) → **Orchestrations** (naya)

Purana pattern jo abhi bhi docs/blogs me milega:

```python
from semantic_kernel.agents import AgentGroupChat
from semantic_kernel.agents.strategies import TerminationStrategy

class ApprovalTermination(TerminationStrategy):
    async def should_agent_terminate(self, agent, history):
        return "approved" in history[-1].content.lower()

chat = AgentGroupChat(
    agents=[writer, reviewer],
    termination_strategy=ApprovalTermination(agents=[reviewer], maximum_iterations=5),
)
await chat.add_chat_message("Write a tagline for a running shoe brand.")
async for msg in chat.invoke():
    print(f"{msg.name}: {msg.content}")
```

Naya model (SK 1.x late / MAF me carry hua) — **named orchestration patterns**:

| Orchestration | Shape | Kab |
|---|---|---|
| **Concurrent** | sab agents same input pe parallel | multiple opinions, ensemble, fan-out review |
| **Sequential** | pipeline, output → next input | draft → edit → translate |
| **Handoff** | agent decide karta hai kisko de | triage → billing/tech routing (CrewAI/OpenAI Swarm jaisa) |
| **Group chat** | manager turn-taking decide kare | debate, brainstorm |
| **Magentic** | Magentic-One style planner-led open-ended | research-y, uncertain plans |

> **Interview me:** *"SK me multi-agent AgentGroupChat + termination strategy se start hua tha,
> phir named orchestrations (concurrent/sequential/handoff/group-chat/magentic) me evolve hua,
> aur wahi patterns Microsoft Agent Framework me graph-based workflows ban gaye. Conceptually
> yeh CrewAI ke crew aur LangGraph ke graph ka same space hai."*

---

## 11. Memory aur vector stores

Do generations hain — dono ka naam bolna zaroori hai:

| Purana (deprecated) | Naya |
|---|---|
| `SemanticTextMemory` + `MemoryStore` | **Vector Store abstractions**: typed record model + collections + `VectorStoreTextSearch` |

```python
from dataclasses import dataclass
from typing import Annotated
from semantic_kernel.data import vectorstoremodel, VectorStoreField   # naam version-sensitive

@vectorstoremodel
@dataclass
class DocChunk:
    id: Annotated[str, VectorStoreField("key")]
    text: Annotated[str, VectorStoreField("data", is_full_text_indexed=True)]
    embedding: Annotated[list[float] | None, VectorStoreField("vector", dimensions=1536)] = None
```
Concept: **record ka schema tum declare karte ho (Pydantic/dataclass style), connector usko
apne backend pe map karta hai** — Azure AI Search, Cosmos DB, Redis, Postgres/pgvector, Qdrant,
in-memory. Yani ek hi RAG code, backend swap-able. Yeh SQLAlchemy-style abstraction hai.

Phir vector store ko **search plugin** bana ke agent ko de do:

```python
search = VectorStoreTextSearch(vector_record_collection=collection)
kernel.add_plugin(search.create_plugin(plugin_name="docs"), "docs")
# ab model khud decide karega kab retrieve karna hai → "agentic RAG"
```
Cross-ref: [`../Level5_RAG_Vector_Databases/11_azure_ai_search.md`](../Level5_RAG_Vector_Databases/11_azure_ai_search.md)
(hybrid + semantic ranker wahan hai — SK sirf connector hai, retrieval quality ka kaam wahan hota hai).

---

## 12. Process Framework — stateful business workflows

Yeh SK ka **LangGraph jawab** hai, par framing alag: "business process automation".

```
Process = steps + events
Step    = ek unit (function call, agent call) with its own state
Event   = step emit karta hai; doosra step usko subscribe karta hai
```
- Long-running, resumable, event-driven — human approval ke liye ruk sakta hai
- Deterministic control flow (LLM ko decide nahi karne dete ki agla step kya hai)
- Distributed runtime pe map ho sakta hai (Dapr / Orleans) — yeh .NET enterprise angle hai

**Kab use karo:** jab flow **business rule** hai, model ki marzi nahi. "Invoice aaya → extract →
validate → >₹1L to approval → post to ERP" — yeh graph tum likhoge, model sirf steps ke andar kaam karega.

> **Interview one-liner:** *"Agentic loop tab jab path unknown ho; process/graph tab jab path
> business rule ho. Production me main mostly deterministic graph rakhta hoon jiske andar
> chhote agentic steps hote hain — poora control model ko dene se reliability girti hai."*
> (Yahi baat LangGraph ke context me bhi valid hai — framework-independent judgement.)

---

## 13. Observability — OTel built-in

SK me tracing **OpenTelemetry** hai, koi proprietary SDK nahi:

```python
# env se on hota hai
SEMANTICKERNEL_EXPERIMENTAL_GENAI_ENABLE_OTEL_DIAGNOSTICS=true
SEMANTICKERNEL_EXPERIMENTAL_GENAI_ENABLE_OTEL_DIAGNOSTICS_SENSITIVE=true  # prompts/completions bhi
```
Spans milte hain: `chat.completions {model}`, per-function invocation, token usage attributes.
Exporter Azure Monitor / App Insights → Foundry tracing UI, ya koi bhi OTel backend (Jaeger, Datadog).

> **Yeh strong enterprise point hai:** *"SK ka telemetry OTel semantic conventions follow karta hai,
> isliye GenAI traces usi APM me jaate hain jahan mera baaki backend hai — separate LLM
> observability vendor onboard karne ki zaroorat nahi. Sensitive-data flag alag hai, isliye
> prompts capture karna ek conscious compliance decision banta hai, accident nahi."*

Cross-ref: [`../Level8_Production_LLMOps/`](../Level8_Production_LLMOps/) (tracing/eval),
[`../Modern_Topics/25_azure_ai_foundry_promptflow.md`](../Modern_Topics/25_azure_ai_foundry_promptflow.md) (Foundry side).

---

## 14. SK ko FastAPI me chalana — backend dev ke asli sawaal

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.kernel = build_kernel()      # ek hi baar banao, per-request nahi
    yield

app = FastAPI(lifespan=lifespan)

@app.post("/chat")
async def chat(req: ChatReq):
    kernel = app.state.kernel              # kernel shared, ChatHistory per-request
    history = load_history(req.session_id) # tumhare Redis/Postgres se
    ...
```

| Concern | Kya karo |
|---|---|
| Kernel per request banana? | **Nahi.** Kernel stateless registry hai — app startup pe ek. Par plugins me per-request state mat rakho (thread-safety). |
| Conversation state | `ChatHistory` serialize karke Redis/Postgres me. Kernel me state nahi rakhna. |
| Streaming | `get_streaming_chat_message_content()` → FastAPI `StreamingResponse` / SSE |
| Timeouts/retries | connector level pe configure karo + `asyncio.wait_for` outer guard. Auto-invoke loop unbounded ho sakta hai — `maximum_auto_invoke_attempts` set karo. |
| Cost control | `service_id` se model routing; `included_plugins` se tool scoping; response me `usage` metadata log karo |
| Testing | Plugins plain Python classes hain → **normal pytest**, koi LLM chahiye hi nahi. Yeh SK ki design win hai — DI ki wajah se fake `db` inject karna trivial hai. |
| Blocking code | Sync plugin function event loop block karega → `asyncio.to_thread()` me daalo |

> Yeh section tumhara **unfair advantage** hai. Baaki candidates notebook demo karke aate hain.
> Tum "kernel lifespan, per-request history, streaming, loop cap, plugin unit tests" bol sakte ho —
> yeh 8 saal ka backend experience bolta hai, framework tutorial nahi.

---

## 15. SK → Microsoft Agent Framework (2025–26) — migration map

MAF 1.0 (Apr 2026) me SK ka DI-heavy Kernel model simplify ho gaya. Concept mapping:

| Semantic Kernel | Microsoft Agent Framework |
|---|---|
| `Kernel` (DI container me sab register) | mostly **gone** — agent直 banate ho, tools directly pass karte ho |
| `Plugin` class + `add_plugin()` | **Tool** — function directly agent ko de do (`tools=[...]`) |
| `@kernel_function` | AI function (schema still type-hints se) |
| `ChatCompletionAgent` | **`ChatAgent`** (single unified agent type over providers) |
| `AgentGroupChat` / orchestrations | **Workflows** (graph-based, typed edges, checkpointing) |
| Filters (3 types) | **Middleware** (same idea, cleaner) |
| `ChatHistory` + `AgentThread` | **AgentThread** / session state (first-class, persistable) |
| SK vector stores | carried over + MCP native, A2A support |
| AutoGen `AssistantAgent`/`RoundRobinGroupChat` | same `ChatAgent` + workflows |

**Migration reality:** Microsoft ki guidance yeh hai ki most projects ek "weekend ka kaam" hain,
multi-sprint rewrite nahi — kyunki concepts 1:1 map karte hain. C# side me ek **compatibility bridge**
bhi hai (SK 1.38+ me `KernelFunction` `Microsoft.Extensions.AI.AIFunction` se derive karta hai),
yani SK plugins MAF agents me reuse ho sakte hain.

**Kya bolna hai (yeh poora answer yaad kar lo):**
> *"Semantic Kernel Microsoft ka orchestration SDK tha — Kernel as DI container, plugins as typed
> functions, filters as middleware. 2025 me Microsoft ne SK aur AutoGen ko merge karne ka announce
> kiya aur April 2026 me Microsoft Agent Framework 1.0 ship kiya: SK ke enterprise concerns
> (middleware, telemetry, typed tools, session state) + AutoGen ke simple multi-agent abstractions
> + graph-based workflows, ek SDK me. AutoGen maintenance mode me hai. Mere liye ramp syntax ka hai,
> architecture ka nahi — Kernel+Plugin se Agent+Tool, filters se middleware, group chat se workflows."*

⚠️ **Verify karo bolne se pehle** — yeh space teen mahine me hilta hai. Live check:
```bash
pip index versions agent-framework 2>/dev/null; pip index versions semantic-kernel
```
Aur docs: `learn.microsoft.com/agent-framework/migration-guide/from-semantic-kernel`

---

## 16. Decision table — kab kya choose karo

| Situation | Pick |
|---|---|
| Azure-committed enterprise, .NET + Python mix, governance heavy | **SK / MAF** |
| Greenfield Microsoft-shop agent project, 2026 me | **Microsoft Agent Framework** (SK nahi) |
| Python-only, biggest integration ecosystem, complex cyclic graphs + checkpointing | **LangGraph** |
| Fast role-based multi-agent prototype | **CrewAI** |
| Type-safe, minimal, Pydantic-native single agent | **PydanticAI** |
| Managed agent runtime — threads/tools/state Azure sambhale | **Foundry Agent Service** (`AzureAIAgent`) |
| Framework hi nahi chahiye | Plain SDK + apna loop (30 lines) — hamesha valid answer |

> **Meta-answer jo har framework interview me chalta hai:** *"Ye sab same 4 primitives ke wrapper
> hain — model call, tool schema, loop, state. Main framework tab lagata hoon jab wo mujhe
> observability, state persistence, ya governance free me de raha ho; sirf abstraction ke liye
> nahi. Aur main framework stack ke hisaab se choose karta hoon, hype ke hisaab se nahi."*

---

## 17. Interview Q&A (rapid-fire)

**Q1. SK kya hai, LangChain se kaise alag?** → §1 table + one-liner. Key: ecosystem fit, DI design,
filters, Azure-native. Merit ka fark nahi.

**Q2. Plugin aur function ka fark?** → Plugin = related functions ka named group (namespace);
function = ek callable. Model ko `pluginName-functionName` dikhta hai. Native (Python code) aur
prompt (templated LLM call) — dono functions hain, same interface.

**Q3. Tool schema kaise banta hai?** → `@kernel_function(description=)` + type hints + `Annotated`
metadata se JSON schema, FastAPI/Pydantic → OpenAPI jaisa. Description = prompt; galat tool
selection ka fix usually description me hota hai.

**Q4. Auto function calling ka loop samjhao.** → §7 ke 7 steps. `FunctionChoiceBehavior.Auto()`,
`kernel=` pass karna zaroori, `maximum_auto_invoke_attempts` loop guard.

**Q5. Planners?** → Legacy. §9 ka jawab. Trap question hai — "current feature" bolna outdated signal.

**Q6. Filters kya hain, kab use kiye?** → §8. Teen types. Killer example: auto-function-invocation
filter se destructive tool pe human approval + `context.terminate`. LangChain me clean equivalent nahi.

**Q7. Multi-agent SK me?** → `ChatCompletionAgent` + `AgentGroupChat`/termination strategy (purana) →
named orchestrations: concurrent, sequential, handoff, group-chat, magentic. AutoGen merge story.

**Q8. Azure me auth kaise?** → Managed Identity + `DefaultAzureCredential` + bearer token provider;
keys nahi. Role: `Cognitive Services OpenAI User`. Private endpoint + VNet enterprise me.

**Q9. SK me RAG kaise?** → Vector store connector (Azure AI Search) + typed record model +
`VectorStoreTextSearch` → search plugin → agent khud retrieve karega (agentic RAG). Ya prompt
function ke andar `{{docs-search $query}}` se deterministic injection.

**Q10. Testing/eval kaise?** → Plugins plain classes → pytest with injected fakes. Prompt functions →
golden-set eval (Azure AI Evaluation SDK / RAGAS). Filters → unit-testable middleware.
Tool-selection accuracy ka apna eval rakho, sirf end answer ka nahi.

**Q11. SK ab bhi use karoge 2026 me?** → §15 ka jawab. Naye project pe MAF, purane pe SK +
migration plan. Yeh sabse discriminating question hai — timeline jaanne wale bahut kam hain.

**Q12. SK ne kya galat kiya (opinion question)?** → Honest answer: Kernel ka DI-heavy model Python
devs ko boilerplate lagta tha (LangChain me 5 line, SK me 15); planners premature abstraction the;
Python SDK ka API 1.x me kaafi hila jisse tutorials tootey. MAF ne exactly yahi teen cheezein fix ki.
**Aisa jawab dena maturity dikhata hai — framework fan-boy nahi lagte.**

---

## 18. Gotchas / traps

1. **`kernel=` pass karna bhool jaana** auto-function-calling me → model ko tools hi nahi dikhte,
   silently plain answer aa jaata hai. Sabse common bug.
2. **Azure me `deployment_name` vs `ai_model_id`** — Azure deployment name maangta hai, model name nahi.
3. **Function name me `-` ya space** — namespacing separator se clash. `snake_case` rakho.
4. **Sync plugin function** async app me event loop block karega → `asyncio.to_thread`.
5. **Poora DB row return karna** → token blow-up. Sirf needed fields.
6. **Unbounded auto-invoke** → cost spike/infinite loop. `maximum_auto_invoke_attempts` set karo.
7. **`SemanticTextMemory` wale purane tutorials** follow karna — deprecated, naye vector store use karo.
8. **Docs 90% C# examples** dikhate hain — Python me API naam kabhi thoda alag. Installed version ke
   samples repo dekho, blog nahi.
9. **SK ko "latest" bolna** — §15. 2026 me MAF hai.

---

## 19. 10-minute revision cheat sheet

```
Kernel      = DI container (services + plugins registry). Stateless. App startup pe ek.
Plugin      = related functions ka group → model ko "plugin-function" dikhta hai
Function    = native (@kernel_function, Python) ya prompt (template + settings)
Schema      = type hints + Annotated + description → JSON schema (FastAPI→OpenAPI jaisa)
Args        = KernelArguments (template vars + execution settings)
History     = ChatHistory (messages + tool calls + results) — state TUMHARE paas
Auto FC     = FunctionChoiceBehavior.Auto() → ReAct loop; kernel= pass karna MUST
              Required() = force tool · None = schema dikhao, call mat karo
              included_plugins = tool scoping · maximum_auto_invoke_attempts = loop cap
Filters     = middleware (SK ka differentiator)
              FUNCTION_INVOCATION · PROMPT_RENDERING · AUTO_FUNCTION_INVOCATION
              → audit, caching, PII redaction, HITL approval, context.terminate
Planners    = LEGACY (auto FC ne replace kiya) — trap question
Agents      = ChatCompletionAgent (+ AzureAIAgent hosted) + AgentThread
Multi-agent = AgentGroupChat (purana) → orchestrations: concurrent/sequential/
              handoff/group-chat/magentic
Vectors     = typed record model + connector (AI Search/Cosmos/pgvector) → search plugin
Process FW  = deterministic stateful workflow (LangGraph ka SK jawab)
Telemetry   = OpenTelemetry built-in → App Insights / any APM
Azure auth  = Managed Identity, keys nahi
2026        = SK + AutoGen → Microsoft Agent Framework 1.0 (Apr 2026)
              Kernel+Plugin → Agent+Tool · Filters → Middleware · GroupChat → Workflows
```

---

## 20. Lab checklist (padhna ≠ karna)

Kam se kam yeh 5 karo — 2 ghante lagenge, aur "hands-on hai" claim sach ho jaayega:

- [ ] `python 09_semantic_kernel_practical.py` chalao — mock mode me auto-FC loop print dekho
- [ ] `pip install semantic-kernel`, ek native plugin (2 functions) + auto function calling live chalao
- [ ] Ek `FUNCTION_INVOCATION` filter likho jo har call ka latency + args log kare
- [ ] Ek `AUTO_FUNCTION_INVOCATION` filter likho jo `cancel_order` pe `input()` se approval maange
- [ ] Kernel ko FastAPI `lifespan` me daalo, `/chat` endpoint jo `ChatHistory` Redis/dict me persist kare
- [ ] Bonus: same agent LangGraph me likho aur **diff likh ke rakho** — interview me yeh comparison
      bolne se tum instantly "framework compare kar chuka hoon" wali category me chale jaate ho

---

## Architecture summary

```
                          ┌──────────────── Kernel (DI container) ────────────────┐
                          │                                                      │
 AI Services ─────────────┤  OpenAIChatCompletion / AzureChatCompletion          │
 (service_id se resolve)  │  Embeddings, TextToImage, ...                        │
                          │                                                      │
 Plugins ─────────────────┤  Native   (@kernel_function → auto JSON schema)      │
                          │  Prompt   ({{$var}}, {{plugin-fn $arg}})             │
                          │  OpenAPI  (add_plugin_from_openapi)                  │
                          │  MCP      (external tool servers)                    │
                          │                                                      │
 Filters (middleware) ────┤  FUNCTION_INVOCATION                                 │
                          │  PROMPT_RENDERING                                    │
                          │  AUTO_FUNCTION_INVOCATION  ← HITL gate, terminate     │
                          └───────────────────────┬──────────────────────────────┘
                                                  │
        ┌─────────────────────────────────────────┴─────────────────────────────┐
        │                                                                       │
  Auto function calling loop                                        Agent Framework
  (FunctionChoiceBehavior)                                  ChatCompletionAgent / AzureAIAgent
  model → tool → result → model                             + AgentThread (state)
                                                            + Orchestrations (concurrent,
                                                              sequential, handoff,
                                                              group chat, magentic)
        │                                                                       │
        └──────────────► Vector Stores · Process Framework · OTel telemetry ◄────┘

                                     ⇓ 2026
                        Microsoft Agent Framework 1.0
              Agent + Tool + Middleware + Workflows + MCP/A2A
```

**Where it fits in your prep:** agentic theory yahan naya kuch nahi — ReAct loop, tool schemas,
HITL, multi-agent sab tum [`01_langchain_complete.md`](01_langchain_complete.md),
[`03_langgraph_advanced.md`](03_langgraph_advanced.md), [`05_crewai_complete.md`](05_crewai_complete.md)
me padh chuke ho. SK ka ROI **vocabulary + filters + Azure integration + 2026 migration story** me hai.
Deep hands-on tabhi jab target Azure-heavy enterprise ho.

**Sources (2026 status):**
[MAF migration guide (devblogs)](https://devblogs.microsoft.com/agent-framework/migrate-your-semantic-kernel-and-autogen-projects-to-microsoft-agent-framework-release-candidate/) ·
[from-semantic-kernel migration docs](https://learn.microsoft.com/agent-framework/migration-guide/from-semantic-kernel) ·
[SK + AutoGen = Agent Framework (VS Magazine)](https://visualstudiomagazine.com/articles/2025/10/01/semantic-kernel-autogen--open-source-microsoft-agent-framework.aspx) ·
[MAF 1.0 shipped](https://blog.imseankim.com/microsoft-agent-framework-1-0-semantic-kernel-autogen-dotnet-python/) ·
[AutoGen maintenance mode](https://agentmarketcap.ai/blog/2026/04/13/microsoft-autogen-maintenance-mode-agent-framework-sunset-2026)
