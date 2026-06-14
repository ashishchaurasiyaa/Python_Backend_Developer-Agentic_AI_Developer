# LangChain V1 — Kya Naya Hai

> **Source:** Krish Naik — "Complete Agentic AI Course In 10 Hours" · 00:02:31 · notebook: `krishnaik06/Langchain-V1-Crash-Course` (`updatedlangchain/` + `llm_gateway_tutorial.ipynb`)

---

## 🎯 TL;DR

LangChain **V1** ek bada cleanup + standardization release hai. Sabse important badlaav: ek **`create_agent`** high-level agent constructor (purana `initialize_agent`/`AgentExecutor` boilerplate gaya), **`init_chat_model`** se provider-agnostic model loading (`"groq:..."`, `"google_genai:..."`), saare providers ke liye ek **standard message format**, saaf `with_structured_output` / `response_format`, aur sabse powerful naya feature — **agent middleware** (summarization, human-in-the-loop, guardrails — agent ke andar hooks).

---

## 🗣️ Hinglish Explanation

LangChain ka purana version aapko yaad hoga (Agentic course mein chhua tha): bahut saare alag-alag imports, `LLMChain`, `initialize_agent`, `AgentExecutor`, har provider ka apna interface — kaafi fragmented tha. **V1 ne isko tighten kiya hai** taaki ek hi consistent API se sab kuch ho. Chalo har area dekhte hain.

### 1. Agent banana — `create_agent` (sabse bada change)

Purane LangChain mein agent banane ke liye `initialize_agent` ya manually `AgentExecutor` + prompt + tools wire karna padta tha. V1 mein ek hi clean function:

```python
from langchain.agents import create_agent

def get_weather(city: str) -> str:
    """Get the weather for a city."""
    return f"The weather in {city} is sunny."

agent = create_agent(
    model="gpt-5",
    tools=[get_weather],
    system_prompt="You are a helpful assistant."
)

# run — input hamesha {"messages": [...]} shape mein
response = agent.invoke({"messages": [{"role": "user", "content": "What is the weather in New York?"}]})
response["messages"]   # poori conversation (human -> ai tool_call -> tool result -> final ai)
```

**Gaur karne layak:** `create_agent` andar se ek **LangGraph graph** banata hai (aapne LangGraph deeply padha hai — yahi `StateGraph` + tool node + conditional edge wala loop hai, bas prebuilt). Input/output hamesha `{"messages": [...]}` state ke through chalta hai — exactly LangGraph ka `MessagesState` pattern. Matlab `create_agent` = "LangGraph ka ReAct agent, ek line mein".

### 2. Model loading — `init_chat_model` (provider-agnostic)

V1 ka highlight: ek hi function se kisi bhi provider ka model load karo, **provider-prefixed string** se:

```python
from langchain.chat_models import init_chat_model

model = init_chat_model("gpt-4.1")                      # OpenAI
model = init_chat_model("google_genai:gemini-2.5-flash")# Gemini
model = init_chat_model("groq:qwen/qwen3-32b")          # Groq

response = model.invoke("Hello, how are you?")
print(response.content)
```

Provider-specific class (`ChatOpenAI`, `ChatGoogleGenerativeAI`, `ChatGroq`) abhi bhi available hain, par `init_chat_model` ka fayda: **model ko config/string se swap kar sakte ho bina code badle** — yeh exactly woh provider-abstraction hai jo aapne Production Track labs mein `get_client()` se manually banaya tha. Yahan framework hi de raha hai.

**Streaming aur batch** bhi standard hain:

```python
# token-by-token streaming
for chunk in model.stream("Write 200 words on AI"):
    print(chunk.text, end="|", flush=True)

# parallel batch (cost + speed) with concurrency cap
responses = model.batch(
    ["Why do parrots talk?", "How do planes fly?", "What is quantum computing?"],
    config={"max_concurrency": 5},
)
```

### 3. Messages — ek standard format sab providers ke liye

V1 mein messages "fundamental unit of context" hain, aur **ek standard message type sab providers pe consistently kaam karta hai** (chahe OpenAI ho ya Groq ya Gemini). Har message mein: **role**, **content** (text/image/audio/doc — multimodal), aur **metadata** (token usage, ids).

```python
from langchain.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage

messages = [
    SystemMessage("You are a senior Python developer. Always give code + reasoning."),
    HumanMessage("How do I create a REST API?"),
]
response = model.invoke(messages)
print(response.content)
print(response.usage_metadata)   # {input_tokens, output_tokens, total_tokens}
```

4 message types: **SystemMessage** (behaviour set karo), **HumanMessage** (user input, multimodal ho sakta), **AIMessage** (model output — text + tool_calls + metadata), **ToolMessage** (ek tool execution ka result, `tool_call_id` se match hota hai). Aap manually conversation history bhi bana sakte ho (AIMessage daal ke "as if model ne kaha"):

```python
ai_msg = AIMessage("I'd be happy to help!")
messages = [
    SystemMessage("You are a helpful assistant"),
    HumanMessage("Can you help me?"),
    ai_msg,                       # history mein insert
    HumanMessage("What's 2+2?"),
]
response = model.invoke(messages)
```

### 4. Tools — `@tool` + `bind_tools` + execution loop

Tool = (schema: naam + description + args) + (function). V1 ka clean pattern:

```python
from langchain.tools import tool

@tool
def get_weather(location: str) -> str:
    """Get the weather at a location"""   # docstring = LLM ke liye description
    return f"It's sunny in {location}"

model_with_tools = model.bind_tools([get_weather])
response = model_with_tools.invoke("What's the weather in Boston?")

for tc in response.tool_calls:           # model ne kaunse tools maange
    print(tc["name"], tc["args"])
```

Agar aap **manually** tool loop chalao (jo `create_agent` automate karta hai):

```python
messages = [{"role": "user", "content": "What's the weather in Boston?"}]
ai_msg = model_with_tools.invoke(messages)      # 1. model tool_call deta hai
messages.append(ai_msg)

for tool_call in ai_msg.tool_calls:             # 2. tool execute karo
    tool_result = get_weather.invoke(tool_call) # ToolMessage return karta hai (id auto-match)
    messages.append(tool_result)

final = model_with_tools.invoke(messages)       # 3. result wapas feed -> final answer
print(final.text)
```

Yeh wahi raw agent-loop hai jo aapne Week-1 (Ed Donner) mein scratch se likha tha — V1 mein `get_weather.invoke(tool_call)` seedha ek `ToolMessage` deta hai (`tool_call_id` khud match ho jaata), toh boilerplate kam.

### 5. Structured output — `with_structured_output` + `response_format`

V1 mein typed output lena bahut clean hai. Schema **Pydantic / TypedDict / dataclass** kuch bhi ho sakta hai:

```python
from pydantic import BaseModel, Field

class Movie(BaseModel):
    title: str = Field(description="The title of the movie")
    year: int = Field(description="The year the movie was released")
    director: str = Field(description="The director")
    rating: float = Field(description="Rating out of 10")

model_with_structure = model.with_structured_output(Movie)
response = model_with_structure.invoke("Provide details about the movie Inception")
# response ab ek Movie object hai — string parsing nahi
```

Useful variants:
- `with_structured_output(Movie, include_raw=True)` → parsed object **aur** raw AIMessage dono milte hain (debugging/metadata ke liye).
- **Nested** models (`list[Actor]` etc.) supported.
- **TypedDict** — jab runtime validation nahi chahiye, lightweight:

```python
from typing_extensions import TypedDict, Annotated

class MovieDict(TypedDict):
    title: Annotated[str, ..., "The title of the movie"]
    year:  Annotated[int, ..., "Release year"]
    rating: Annotated[float, ..., "Rating out of 10"]

model.with_structured_output(MovieDict).invoke("Details of Avengers")
```

Aur agent level pe — `create_agent(response_format=...)`: agent apni tool-loop ke baad final answer ko us schema mein de deta hai (`result["structured_response"]`):

```python
from langchain.agents import create_agent

class ContactInfo(BaseModel):
    name: str = Field(description="The name")
    email: str = Field(description="The email")
    phone: str = Field(description="The phone")

agent = create_agent(model="gpt-5", response_format=ContactInfo)  # auto ProviderStrategy
result = agent.invoke({"messages": [{"role": "user",
        "content": "Extract: John Doe, john@example.com, (555) 123-4567"}]})
result["structured_response"]   # ContactInfo(name='John Doe', ...)
```

Yeh wahi typed-handoff idea hai jo aapne ALEX multi-agent (Production Week 4) mein pydantic se manually kiya tha — yahan framework first-class de raha hai.

### 6. Middleware — V1 ka killer feature ⭐

**Middleware** = agent ke andar control hooks. Yeh V1 ka sabse naya/powerful concept hai. Use-cases (notebook se): logging/analytics/debugging, prompt/tool/output transform, retries+fallbacks+early-termination, aur **rate-limits, guardrails, PII detection**. Soch lo jaise web framework ka request/response middleware — par LLM agent ke har step pe.

**(a) SummarizationMiddleware** — jab conversation token-limit ke paas pohonche, purani history ko auto-summarize karke compress karta hai, recent messages preserve karke. (Aapne Production Week 4 mein context/memory manually handle kiya tha — yeh automate karta hai.)

```python
from langchain.agents import create_agent
from langchain.agents.middleware import SummarizationMiddleware
from langgraph.checkpoint.memory import InMemorySaver

agent = create_agent(
    model="gpt-4o-mini",
    checkpointer=InMemorySaver(),          # memory ke liye (LangGraph checkpointer!)
    middleware=[
        SummarizationMiddleware(
            model="gpt-4o-mini",
            trigger=("messages", 10),      # 10 messages cross -> summarize
            keep=("messages", 4),          # last 4 as-is rakho
        )
    ],
)
config = {"configurable": {"thread_id": "test-1"}}   # thread = ek conversation
agent.invoke({"messages": [HumanMessage(content="What is 2+2?")]}, config)
```

`trigger`/`keep` ko `("tokens", 550)` ya `("fraction", 0.005)` (context window ka %) se bhi de sakte ho — flexible.

**(b) HumanInTheLoopMiddleware** — high-stakes tool calls (DB write, email bhejna, paisa transfer) se pehle agent **pause** karke human ki approval maangta hai. Decisions: **approve / edit / reject**.

```python
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langgraph.types import Command

agent = create_agent(
    model="gpt-4o",
    tools=[read_email_tool, send_email_tool],
    checkpointer=InMemorySaver(),
    middleware=[
        HumanInTheLoopMiddleware(interrupt_on={
            "send_email_tool": {"allowed_decisions": ["approve", "edit", "reject"]},
            "read_email_tool": False,        # read safe hai -> no interrupt
        })
    ],
)

result = agent.invoke({"messages": [HumanMessage(content="Send email to john@test.com ...")]}, config)

if "__interrupt__" in result:              # agent ruk gaya, approval maang raha hai
    result = agent.invoke(
        Command(resume={"decisions": [{"type": "approve"}]}),   # ya "reject", ya "edit"
        config=config,
    )
```

`edit` decision mein aap tool ke args **badal** ke approve kar sakte ho (galat recipient theek karna, etc.) — `edited_action.args` mein naye values do. Yeh `__interrupt__` + `Command(resume=...)` pattern **bilkul LangGraph ka interrupt/checkpoint mechanism hai** jo aapne padha hai — middleware bas usko ek clean guardrail-API mein wrap karta hai. Isi tarah guardrails/PII-detection bhi middleware ke roop mein plug ho jaate hain (aapke Production Week-4 guardrails lab ka framework-native version).

---

## 🆚 Aapke Existing Knowledge Se Connect

Aapne LangGraph (23-lecture course), classic RAG, guardrails aur evals already deeply padhe hain — toh V1 ko "naya seekhna" mat samjho, **"jo manually kiya wo ab framework deta hai"** samjho:

| Aapne jo kiya / jaana | LangChain V1 mein woh ab... |
|---|---|
| Raw agent-loop scratch se (Ed W1), ya LangGraph ReAct graph manually | `create_agent(...)` — ek line, andar wahi LangGraph loop |
| `get_client()` provider-swap + fallback ladder (Prod labs) | `init_chat_model("groq:..."/"google_genai:...")` — provider string se swap |
| ALEX mein pydantic typed agent-to-agent handoff (Prod W4) | `with_structured_output(...)` / `create_agent(response_format=...)` first-class |
| Context/memory + summarization manually | `SummarizationMiddleware` (token/message/fraction trigger) |
| Guardrails + human approval manually (Prod W4 lab5) | `HumanInTheLoopMiddleware`, guardrail middleware |
| LangGraph `interrupt` + checkpointer | wahi mechanism — middleware `__interrupt__` + `Command(resume=...)` ke peeche |

**Genuinely naya samajhne layak:** (1) **middleware** abstraction — ek clean, composable jagah jahan cross-cutting concerns (summarize/guardrail/HITL/retry) plug hote hain, har agent dobara likhe bina; (2) **standard message + content format** jo provider-portability dega; (3) imports/API ka consolidation (`langchain.agents`, `langchain.chat_models`, `langchain.messages`, `langchain.tools`).

## 📋 Key Concepts

| Concept | Matlab |
|---|---|
| `create_agent` | High-level prebuilt agent (LangGraph ReAct loop), `initialize_agent`/`AgentExecutor` ko replace karta hai |
| `init_chat_model("provider:model")` | Provider-agnostic model loader — `groq:`, `google_genai:`, OpenAI default |
| Standard messages | `SystemMessage/HumanMessage/AIMessage/ToolMessage` (`langchain.messages`), sab providers pe consistent |
| `usage_metadata` | Har response pe token usage (input/output/total) |
| `@tool` + `bind_tools` | Tool define karo (docstring=description) + model se bind |
| `with_structured_output` | Pydantic/TypedDict/dataclass schema mein typed output; `include_raw=True` se raw+parsed |
| `response_format` (agent) | Agent ka final answer typed schema mein → `result["structured_response"]` |
| **Middleware** | Agent ke andar hooks: Summarization, HumanInTheLoop, guardrails, retries, logging |
| `checkpointer` (InMemorySaver) | Memory/thread persistence — wahi LangGraph checkpointer |
| `__interrupt__` + `Command(resume=...)` | HITL pause/approve/edit/reject flow |

## 💼 Backend Dev Ke Liye Note

V1 ko ek **opinionated SDK upgrade** ki tarah dekho — bilkul jaise koi web framework v1 release karke API saaf kar deta hai. Backend angle:
- **`init_chat_model` + config** = 12-factor friendly: model choice env/config se aaye, code se nahi (aapke `get_client` ka framework version). Provider migration ek string change.
- **Middleware = ASGI/Express middleware ka mental model** — auth/logging/rate-limit jaisa, par LLM-agent steps pe. Production mein guardrails, PII-redaction, summarization, HITL approval sab middleware list mein declarative ho jaate hain, business logic se decoupled.
- **`checkpointer` + `thread_id`** = per-session state (jaise request-scoped DB session) — Lambda/stateless deploy ke liye SqliteSaver/Postgres checkpointer use karo (aapke Prod W2 S3-memory + W4 Aurora wala hi concern).
- HITL `__interrupt__` ek **durable pause** hai — production mein isko queue/webhook se resume karwa sakte ho (long-running approval workflows).

## ✅ Takeaway

- LangChain V1 = **consolidation + standardization**: ek `create_agent`, ek `init_chat_model`, ek message format, ek structured-output API.
- **Middleware** is the headline feature — summarization, human-in-the-loop, guardrails ko agent ke andar declaratively plug karo, har baar dobara likhe bina.
- Andar sab kuch **LangGraph** par bana hai — aapka LangGraph gyaan seedha apply hota hai (`create_agent` = prebuilt graph, checkpointer/interrupt same).
- Jo cheezein aapne manually banayi thi (provider swap, typed handoff, memory summarization, HITL guardrails) — V1 unhe first-class API deta hai.

## 🔗 Source & Code

- **Video:** Krish Naik — "Complete Agentic AI Course In 10 Hours" — [youtu.be/rV3HJ4LEZ7k](https://www.youtube.com/watch?v=rV3HJ4LEZ7k) (LangChain section @ 00:02:31)
- **GitHub:** `github.com/krishnaik06/Langchain-V1-Crash-Course` → `updatedlangchain/` (1-intro, 2-models, 3-tools, 4-messages, 5-structuredoutput, 6-middleware) + `llm_gateway_tutorial.ipynb`
- **Run:** `pip install -U langchain langgraph langchain-openai langchain-groq langchain-google-genai` ; keys `.env` mein; `init_chat_model("groq:qwen/qwen3-32b")` se free Groq pe test karo.
- Extracted source cells: `_sources/lcv1_1_intro.txt` … `lcv1_6_middleware.txt`
