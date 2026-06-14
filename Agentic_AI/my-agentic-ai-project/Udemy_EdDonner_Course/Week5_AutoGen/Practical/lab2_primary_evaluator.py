"""
LAB 2 — AutoGen Teams: Primary + Evaluator, Termination Conditions, Structured Output
=====================================================================================
(Ed Donner course Week 5, Lectures L95-L97)

KYA SEEKHENGE:
  1. STRUCTURED OUTPUT (L95) — AssistantAgent ko `output_content_type=PydanticModel`
     de do, to agent ka final reply ek typed Pydantic object hota hai (string nahi).
     Ye OpenAI-style "structured outputs / json_schema response_format" par chalta hai.
  2. PRIMARY-EVALUATOR TEAM (L96) — classic AutoGen tutorial pattern:
     ek "primary" agent kaam karta hai (tagline likhna), ek "evaluator" agent
     feedback deta hai; jab satisfied ho to EXACTLY 'APPROVE' bolta hai.
     RoundRobinGroupChat dono ko baari-baari chalata hai, aur
     TextMentionTermination("APPROVE") conversation ko rok deta hai.
     => Ye hi "reflection / feedback loop" hai — bina kisi graph framework ke,
        sirf team + termination condition se mil jaata hai.
  3. WEB FETCH TOOL (L97 ka free substitute) — course me MCP fetch server use hota
     hai; hum ek simple async `fetch_page(url)` httpx tool denge "researcher"
     agent ko. Week 6 me real MCP servers aayenge — concept wahi hai:
     agent ko external capability tool ke roop me milti hai.

AUTOGEN CONCEPTS RECAP (backend dev ke liye):
  - AutoGen 2 layers me split hai: `autogen_core` (low-level runtime, RoutedAgent,
    message handlers) aur `autogen_agentchat` (high-level AssistantAgent, Teams).
    Is lab me hum AgentChat layer use kar rahe hain — "batteries included" wali.
  - Team = ek group-chat abstraction. RoundRobinGroupChat sabse simple hai:
    agents fixed order me bolte hain (primary -> evaluator -> primary -> ...).
    Har agent ka output team ke shared context me jaata hai, isliye evaluator
    ko primary ka draft dikh jaata hai automatically.
  - TerminationCondition composable hai: `cond1 | cond2` => OR (jo pehle trigger ho).
    `&` => AND bhi supported. Yahan: APPROVE mention YA 10 messages — jo pehle ho.

VERSION NOTE: course AutoGen 0.5.1 use karta hai, hum 0.7.5 par hain — same API
family (agentchat / core / ext split), is lab ke imports/patterns identical hain.

KAISE CHALANA:
  cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project
  uv run Udemy_EdDonner_Course/Week5_AutoGen/Practical/lab2_primary_evaluator.py

Requires .env: GROQ_API_KEY (primary), GOOGLE_API_KEY (evaluator via Gemini).
"""

import asyncio
import os
import warnings

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_core.models import ModelInfo
from autogen_ext.models.openai import OpenAIChatCompletionClient

load_dotenv(override=True)

# AutoGen 0.7.5 + structured output par pydantic ek harmless serializer warning
# deta hai (StructuredMessage ke 'parsed' field par) — output clean rakhne ke liye mute.
warnings.filterwarnings("ignore", message="Pydantic serializer warnings")


# ---------------------------------------------------------------------------
# MODEL CLIENTS — OpenAIChatCompletionClient kisi bhi OpenAI-compatible API
# ke saath chalta hai; bas base_url + model_info batao. Free tier ke liye
# Groq (llama) aur Gemini dono ka OpenAI-compat endpoint use kar rahe hain.
# model_info zaroori hai kyunki non-OpenAI model ke capabilities (function
# calling, structured output, vision) client ko khud nahi pata hote.
# ---------------------------------------------------------------------------

def groq_client(model: str = "llama-3.3-70b-versatile") -> OpenAIChatCompletionClient:
    """Groq ka free OpenAI-compatible endpoint."""
    return OpenAIChatCompletionClient(
        model=model,
        base_url="https://api.groq.com/openai/v1",
        api_key=os.getenv("GROQ_API_KEY"),
        model_info=ModelInfo(
            vision=False,
            function_calling=True,
            json_output=True,
            family=model,
            structured_output=True,
        ),
    )


def gemini_client(model: str = "gemini-2.0-flash") -> OpenAIChatCompletionClient:
    """Gemini ka OpenAI-compatible endpoint — evaluator ke liye alag 'brain'.

    Multi-model team ka point: evaluator agar DIFFERENT model ho to feedback
    less sycophantic hota hai (apne hi output ko approve karne ka bias kam).
    """
    return OpenAIChatCompletionClient(
        model=model,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key=os.getenv("GOOGLE_API_KEY"),
        model_info=ModelInfo(
            vision=False,
            function_calling=True,
            json_output=True,
            family=model,
            structured_output=True,
        ),
    )


async def with_retry(coro_factory, attempts: int = 3, delay: float = 4.0):
    """Free-tier Groq/Gemini par transient 429/5xx aate hain — simple retry wrapper.

    coro_factory: zero-arg callable jo FRESH coroutine return kare (coroutine
    ek hi baar await ho sakta hai, isliye factory pattern).
    """
    last_err = None
    for i in range(1, attempts + 1):
        try:
            return await coro_factory()
        except Exception as e:  # noqa: BLE001 — demo me sab transient treat karo
            last_err = e
            print(f"   [retry] attempt {i}/{attempts} fail hua: {type(e).__name__}: {str(e)[:120]}")
            if i < attempts:
                await asyncio.sleep(delay * i)
    raise last_err


def header(title: str) -> None:
    print("\n" + "=" * 78)
    print(f"  {title}")
    print("=" * 78)


# ===========================================================================
# DEMO 1 — STRUCTURED OUTPUT (L95)
# ===========================================================================

class FlightQuote(BaseModel):
    """Typed result — LLM ka jawab is schema me FORCE hota hai.

    Internally AutoGen response_format me json_schema bhejta hai; agent ka
    final message phir StructuredMessage[FlightQuote] hota hai jiska
    `.content` seedha Pydantic instance hai — manual json.loads() nahi.
    """
    destination: str = Field(description="City the user wants to fly to")
    price_usd: float = Field(description="Round-trip price estimate in USD")
    summary: str = Field(description="One-line friendly summary of the quote")


async def demo1_structured_output() -> None:
    header("DEMO 1 — Structured Output: output_content_type=FlightQuote (L95)")

    # FALLBACK CHAIN (verified): Groq par llama-3.3-70b `response_format:
    # json_schema` support hi NAHI karta (400 BadRequest aata hai), isliye
    # structured output ke liye groq "openai/gpt-oss-120b" first choice hai —
    # ye chal ke verify ho chuka hai. Gemini backup hai (free tier quota
    # allowing). Jo pehla chal jaaye, wahi use hota hai (print me dikhega).
    candidates = [
        ("groq/openai/gpt-oss-120b", lambda: groq_client("openai/gpt-oss-120b")),
        ("gemini/gemini-2.0-flash", lambda: gemini_client()),
    ]

    task = "Give me a flight quote from Mumbai to Tokyo, around next month. Invent a realistic price."

    for label, factory in candidates:
        client = factory()
        agent = AssistantAgent(
            name="flight_quoter",
            model_client=client,
            system_message=(
                "You are a travel pricing assistant. Respond with a realistic "
                "(invented) round-trip flight quote."
            ),
            # YE line magic hai: ab agent ka final output FlightQuote object hai.
            output_content_type=FlightQuote,
        )
        try:
            result = await with_retry(lambda a=agent: a.run(task=task), attempts=2)
            quote = result.messages[-1].content  # StructuredMessage -> pydantic obj
            assert isinstance(quote, FlightQuote)
            print(f"   Model used: {label}")
            print(f"   TYPED RESULT -> type: {type(quote).__name__}")
            print(f"     destination : {quote.destination}")
            print(f"     price_usd   : {quote.price_usd}")
            print(f"     summary     : {quote.summary}")
            await client.close()
            return
        except Exception as e:  # noqa: BLE001
            print(f"   [{label}] structured output fail: {type(e).__name__}: {str(e)[:100]}")
            await client.close()

    print("   Saare structured-output candidates fail — API keys / rate limits check karo.")


# ===========================================================================
# DEMO 2 — PRIMARY + EVALUATOR TEAM (L96)
# ===========================================================================

async def gemini_quota_available() -> bool:
    """Ek chhota direct probe call — Gemini free tier ka quota zinda hai ya nahi.

    Kyun zaroori: agar evaluator mid-conversation 429 khaye to poori team
    GroupChatError me gir jaati hai. Pehle hi sasta probe karke decide karo.
    """
    if not os.getenv("GOOGLE_API_KEY"):
        return False
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                headers={"Authorization": f"Bearer {os.getenv('GOOGLE_API_KEY')}"},
                json={
                    "model": "gemini-2.0-flash",
                    "messages": [{"role": "user", "content": "hi"}],
                    "max_tokens": 5,
                },
            )
            return resp.status_code == 200
    except Exception:  # noqa: BLE001
        return False


async def demo2_primary_evaluator() -> None:
    header("DEMO 2 — Primary + Evaluator feedback loop, RoundRobinGroupChat (L96)")

    primary_client = groq_client()  # primary hamesha groq llama

    # Evaluator ke liye Gemini try karo (DIFFERENT model = honest critic,
    # apne hi output ko approve karne ka bias kam). Lekin Gemini free tier
    # quota aksar khatam rehta hai — isliye probe karke decide; fallback me
    # bhi Groq ka ALAG model (gpt-oss-120b) lo taaki cross-model review rahe.
    if await gemini_quota_available():
        evaluator_client = gemini_client()
        eval_label = "gemini-2.0-flash"
    else:
        evaluator_client = groq_client("openai/gpt-oss-120b")
        eval_label = "groq/openai/gpt-oss-120b (gemini quota nahi tha, groq fallback)"
    print(f"   primary  -> groq/llama-3.3-70b | evaluator -> {eval_label}")

    def build_team() -> RoundRobinGroupChat:
        """Har retry attempt par FRESH agents + team banao.

        Important gotcha: fail hui team ka internal state corrupt ho sakta hai
        (group chat 'stopped' reh jaata hai), isliye retry me reuse mat karo.
        """
        primary = AssistantAgent(
            name="primary",
            model_client=primary_client,
            system_message=(
                "You are a creative marketing copywriter. Write a short, punchy "
                "tagline (max 12 words) for the product the user asks about. "
                "When you receive feedback, rewrite the tagline incorporating it. "
                "Output ONLY the tagline, nothing else."
            ),
        )
        evaluator = AssistantAgent(
            name="evaluator",
            model_client=evaluator_client,
            system_message=(
                "You are a strict but fair marketing critic. Evaluate the tagline "
                "for punchiness, clarity and originality. Give ONE short concrete "
                "improvement suggestion if it is not great yet. "
                "When the tagline is good enough, respond with EXACTLY the single "
                "word 'APPROVE' and nothing else. Approve within 2 rounds of feedback."
            ),
        )

        # TERMINATION CONDITIONS — composable via `|` (OR) operator:
        #   * TextMentionTermination("APPROVE") -> kisi bhi message me 'APPROVE'
        #     aate hi team ruk jaati hai (evaluator ka satisfaction signal).
        #   * MaxMessageTermination(10)         -> safety cap, infinite ping-pong
        #     se bachne ke liye (free tier tokens bachao!).
        # Jo bhi pehle trigger ho, wahi conversation band karta hai.
        termination = TextMentionTermination("APPROVE") | MaxMessageTermination(10)

        # RoundRobinGroupChat: fixed order me bolte hain — primary, evaluator,
        # primary, evaluator... Har message shared context me hai, isliye
        # evaluator ko draft dikhta hai aur primary ko feedback.
        return RoundRobinGroupChat([primary, evaluator], termination_condition=termination)

    result = await with_retry(
        lambda: build_team().run(
            task="Write a tagline for a coffee shop for late-night programmers."
        )
    )

    # Poora exchange print — feedback loop saaf dikhna chahiye.
    print("\n   --- POORA EXCHANGE (feedback loop) ---")
    labels = {
        "user": "USER (task)",
        "primary": "PRIMARY (copywriter ka draft)",
        "evaluator": "EVALUATOR (critic ka feedback)",
    }
    for i, msg in enumerate(result.messages, start=1):
        who = labels.get(msg.source, msg.source)
        text = msg.to_text().strip()
        print(f"\n   [{i}] {who}:")
        for line in text.splitlines():
            print(f"       {line}")

    print(f"\n   Stop reason: {result.stop_reason}")
    print(f"   Total messages: {len(result.messages)} "
          f"(APPROVE mila to TextMentionTermination ne roka)")

    await primary_client.close()
    await evaluator_client.close()


# ===========================================================================
# DEMO 3 — WEB FETCH TOOL: researcher agent (L97 ka free substitute)
# ===========================================================================

async def fetch_page(url: str) -> str:
    """Fetch a web page and return its text content (truncated).

    Course L97 me ye kaam MCP 'fetch' server karta hai — agent ko ek
    standardized tool protocol se milta hai. Week 6 me hum real MCP servers
    use karenge; abhi wahi capability ek plain async function se de rahe hain.
    AgentChat type hints + docstring se khud FunctionTool bana leta hai —
    schema LLM ko function-calling ke liye bheja jaata hai.
    """
    async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        text = resp.text
    # Free-tier context bachao: 1500 chars tak truncate.
    return text[:1500]


async def demo3_web_fetch_researcher() -> None:
    header("DEMO 3 — Researcher agent with fetch_page tool (L97 free substitute)")
    print("   NOTE: course yahan MCP fetch server use karta hai; Week 6 me real MCP aayega.")

    client = groq_client()
    researcher = AssistantAgent(
        name="researcher",
        model_client=client,
        # tools=[plain function] — AutoGen khud FunctionTool wrap kar leta hai.
        tools=[fetch_page],
        # reflect_on_tool_use=True: tool ka raw HTML wapas user ko nahi jaata;
        # LLM ek aur pass karke result ko summarize karta hai.
        reflect_on_tool_use=True,
        system_message=(
            "You are a web researcher. Use the fetch_page tool to fetch pages "
            "when asked, then answer based on the fetched content."
        ),
    )

    result = await with_retry(
        lambda: researcher.run(
            task="Fetch https://example.com and give me a 1-line summary of what the page says."
        )
    )

    # Messages me ToolCallRequestEvent / ToolCallExecutionEvent bhi dikhte hain
    # — tool ka poora lifecycle transparent hai.
    print("\n   --- AGENT KA TOOL LIFECYCLE ---")
    for msg in result.messages:
        kind = type(msg).__name__
        text = msg.to_text().strip().replace("\n", " ")
        if len(text) > 160:
            text = text[:160] + "..."
        print(f"   [{kind}] ({msg.source}): {text}")

    print(f"\n   FINAL SUMMARY -> {result.messages[-1].to_text().strip()}")
    await client.close()


# ===========================================================================
# MAIN
# ===========================================================================

async def main() -> None:
    print("LAB 2 — AutoGen Teams: Structured Output | Primary-Evaluator | Fetch Tool")
    print("(AutoGen 0.7.5; course 0.5.1 — same agentchat/core/ext API family)")

    try:
        await demo1_structured_output()
    except Exception as e:  # noqa: BLE001
        print(f"   DEMO 1 poori tarah fail: {type(e).__name__}: {str(e)[:150]}")

    try:
        await demo2_primary_evaluator()
    except Exception as e:  # noqa: BLE001
        print(f"   DEMO 2 poori tarah fail: {type(e).__name__}: {str(e)[:150]}")

    try:
        await demo3_web_fetch_researcher()
    except Exception as e:  # noqa: BLE001
        print(f"   DEMO 3 poori tarah fail: {type(e).__name__}: {str(e)[:150]}")

    print("\nLAB 2 DONE — teams + termination + structured output + tool, sab dekh liya.")


if __name__ == "__main__":
    asyncio.run(main())
