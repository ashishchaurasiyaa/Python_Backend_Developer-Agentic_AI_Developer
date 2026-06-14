"""
LAB 4 — Week 5 CAPSTONE: Agents that CREATE agents + agent-to-agent collaboration
(Ed Donner course L105-L107, AutoGen Core layer)

KYA SEEKHENGE:
  - "Creator" pattern: ek agent/LLM-call jo NAYE agents design karta hai aur unhe
    runtime me dynamically register karwa deta hai (course ka L105 climax).
  - AutoGen CORE layer: RoutedAgent + @message_handler + SingleThreadedAgentRuntime —
    yahan koi GroupChat nahi, hum khud message types define karke direct RPC-style
    send_message() karte hain (AgentChat ke upar wala low-level control).
  - Agent-to-agent collaboration (L106-L107): Round-robin idea -> neighbour refine ->
    final synthesizer pick. Ye wahi "agents messaging each other to refine ideas"
    flow hai jo course me Creator ke deploy kiye agents karte hain.

COURSE vs HUMARA APPROACH (important):
  - Course me Creator agent literally PYTHON CODE likhta hai naye agent ka, file me
    save karta hai, import karke runtime me register karta hai. Hum same idea SAFELY
    karte hain — code-gen ki jagah PERSONA-GEN: LLM se sirf {name, personality_prompt}
    generate karwa ke usse factory closure me inject karke register karte hain.
  # NOTE: arbitrary LLM-generated code execute karna risky hai (prompt-injection /
  # malicious code), isliye data (persona) generate karo, code nahi — same capability,
  # zero exec risk.
  - Version note: course AutoGen 0.5.1 use karta hai, hum 0.7.5 — API family same hai
    (autogen_agentchat / autogen_core / autogen_ext split), is lab ke Core APIs
    (RoutedAgent, message_handler, runtime) dono me identical hain.

KAISE CHALANA:
  cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project
  uv run Udemy_EdDonner_Course/Week5_AutoGen/Practical/lab4_agent_creator.py

OUTPUT ARTIFACTS (proof of "agents that create agents"):
  - Practical/output/generated_agents.json  -> Creator ke generate kiye personas
  - Practical/output/ideas_summary.md       -> ideas + refinements + final pick
"""

import asyncio
import json
import os
import re
import warnings
from dataclasses import dataclass
from pathlib import Path

# Known autogen 0.7.5 quirk: structured output (json_output=PydanticModel) par
# client internally CreateResult serialize karta hai aur pydantic ek harmless
# "serializer warnings" UserWarning deta hai — demo output clean rakhne ke liye mute.
warnings.filterwarnings("ignore", message="Pydantic serializer warnings")

from dotenv import load_dotenv
from pydantic import BaseModel, Field

# CORE layer imports — AgentChat ke AssistantAgent/teams se alag, yahan hum
# low-level actors banate hain jo typed messages handle karte hain.
from autogen_core import (
    AgentId,
    MessageContext,
    RoutedAgent,
    SingleThreadedAgentRuntime,
    message_handler,
)
from autogen_core.models import ModelInfo, SystemMessage, UserMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient

load_dotenv(override=True)

OUTPUT_DIR = Path(__file__).parent / "output"
PERSONAS_PATH = OUTPUT_DIR / "generated_agents.json"
SUMMARY_PATH = OUTPUT_DIR / "ideas_summary.md"

N_AGENTS = 3  # Creator kitne naye agents banayega


# ---------------------------------------------------------------------------
# MODEL CLIENT — free Groq via OpenAI-compatible endpoint.
# AutoGen ka OpenAIChatCompletionClient kisi bhi OpenAI-style API se baat kar
# sakta hai; non-OpenAI model ke liye model_info dena MANDATORY hai (warna
# client capabilities guess nahi kar pata).
# ---------------------------------------------------------------------------
def groq_client(model: str = "llama-3.3-70b-versatile") -> OpenAIChatCompletionClient:
    return OpenAIChatCompletionClient(
        model=model,
        base_url="https://api.groq.com/openai/v1",
        api_key=os.getenv("GROQ_API_KEY"),
        model_info=ModelInfo(
            vision=False,
            function_calling=True,
            json_output=True,
            family="llama-3.3-70b",
            structured_output=True,
        ),
    )


async def llm_call_with_retry(client, messages, attempts: int = 3, **kwargs) -> str:
    """Free Groq tier par transient 429/5xx aate hain — simple retry wrapper.

    client.create() Core layer ka raw LLM call hai (AgentChat ke run() ke neeche
    yahi chalta hai) — CreateResult.content me string aati hai.
    """
    last_err = None
    for i in range(attempts):
        try:
            result = await client.create(messages, **kwargs)
            return str(result.content)
        except Exception as e:  # noqa: BLE001 — demo me sab transient errors retry
            last_err = e
            print(f"   [retry {i + 1}/{attempts}] LLM call failed: {e}")
            await asyncio.sleep(2 * (i + 1))
    raise RuntimeError(f"LLM call failed after {attempts} attempts: {last_err}")


# ---------------------------------------------------------------------------
# MESSAGE TYPES — Core layer me communication TYPED hota hai. Runtime in types
# ko dekh kar sahi @message_handler route karta hai (isi liye "RoutedAgent").
# dataclass/pydantic dono chalte hain; hum dataclass use kar rahe (serializable).
# ---------------------------------------------------------------------------
@dataclass
class IdeaRequest:
    topic: str  # kis domain me business idea chahiye


@dataclass
class IdeaResponse:
    agent_name: str
    idea: str


@dataclass
class RefineRequest:
    other_idea: str  # neighbour agent ka idea jo refine/critique karna hai


# ---------------------------------------------------------------------------
# CREATOR STEP — "agents that create agents".
# Pydantic schema structured output ke liye (Groq json_schema support karta hai
# llama-3.3 par; flaky ho to neeche fallback ladder hai).
# ---------------------------------------------------------------------------
class Persona(BaseModel):
    name: str = Field(description="Short single-word agent name, e.g. 'Maverick'")
    personality_prompt: str = Field(
        description="2-3 sentence system prompt defining this entrepreneur's personality and style"
    )


class PersonaList(BaseModel):
    personas: list[Persona]


CREATOR_PROMPT = f"""You are a Creator agent whose job is to design NEW AI agents.
Generate exactly {N_AGENTS} DISTINCT entrepreneur agent personas. Each must have:
- name: one short unique single-word name
- personality_prompt: 2-3 sentences describing their entrepreneurial personality,
  risk appetite, and favourite industry. Make the three personas clearly different
  (e.g. cautious fintech analyst vs wild consumer-app dreamer vs sustainability nerd).
Return ONLY JSON matching: {{"personas": [{{"name": ..., "personality_prompt": ...}}]}}"""

# Agar Groq dono structured paths fail kar de to bhi lab chale — static fallback.
FALLBACK_PERSONAS = [
    Persona(
        name="Maverick",
        personality_prompt=(
            "You are Maverick, a bold risk-taking entrepreneur obsessed with consumer "
            "apps. You love wild, viral ideas and hate anything boring or incremental."
        ),
    ),
    Persona(
        name="Sage",
        personality_prompt=(
            "You are Sage, a cautious data-driven fintech entrepreneur. You only like "
            "ideas with clear revenue models, regulatory safety and defensible moats."
        ),
    ),
    Persona(
        name="Terra",
        personality_prompt=(
            "You are Terra, a sustainability-focused founder. Every idea you touch must "
            "reduce waste or carbon, and you think in circular-economy business models."
        ),
    ),
]


async def create_personas(client) -> tuple[list[Persona], str]:
    """Creator: ek Groq call -> N naye agent personas. Fallback ladder:
    1) json_output=PersonaList on "openai/gpt-oss-120b" -> native structured output.
       NOTE (verified): llama-3.3-70b par Groq json_schema 400 deta hai ("model does
       not support response format json_schema"), isliye structured path ke liye
       gpt-oss-120b use karte hain jo Groq par structured outputs support karta hai.
    2) json_output=True (llama-3.3) -> json_object mode + manual pydantic validation
       (ye path bhi verified working hai agar #1 fail ho).
    3) static FALLBACK_PERSONAS -> network/model dono fail ho jaye tab.
    """
    messages = [
        SystemMessage(content="You design AI agent personas. Output strict JSON only."),
        UserMessage(content=CREATOR_PROMPT, source="user"),
    ]
    # Path 1: native structured output — client khud schema enforce karwata hai.
    try:
        structured_client = groq_client("openai/gpt-oss-120b")
        try:
            raw = await llm_call_with_retry(
                structured_client, messages, attempts=2, json_output=PersonaList
            )
        finally:
            await structured_client.close()
        personas = PersonaList.model_validate_json(raw).personas
        if len(personas) >= N_AGENTS:
            return personas[:N_AGENTS], "structured (json_output=PersonaList, gpt-oss-120b)"
    except Exception as e:  # noqa: BLE001
        print(f"   structured output path failed -> {e}")

    # Path 2: prompt-JSON — json_object mode + khud parse/validate.
    try:
        raw = await llm_call_with_retry(client, messages, attempts=2, json_output=True)
        match = re.search(r"\{.*\}", raw, re.DOTALL)  # stray text ke against guard
        personas = PersonaList.model_validate_json(match.group(0) if match else raw).personas
        if len(personas) >= N_AGENTS:
            return personas[:N_AGENTS], "prompt-JSON (json_output=True + manual parse)"
    except Exception as e:  # noqa: BLE001
        print(f"   prompt-JSON path failed -> {e}")

    # Path 3: offline-safe static personas.
    return FALLBACK_PERSONAS, "static fallback (no LLM)"


# ---------------------------------------------------------------------------
# ENTREPRENEUR AGENT — Core RoutedAgent. Har instance ko Creator ka generate
# kiya personality_prompt inject hota hai (factory closure se). Handlers ka
# RETURN VALUE hi runtime.send_message() ka result ban jata hai (RPC style).
# ---------------------------------------------------------------------------
class EntrepreneurAgent(RoutedAgent):
    def __init__(self, name: str, personality_prompt: str, client) -> None:
        super().__init__(description=f"Entrepreneur agent '{name}' created by the Creator")
        self._name = name
        self._system = SystemMessage(
            content=personality_prompt
            + " Always answer in at most 3 sentences. Be concrete and specific."
        )
        self._client = client

    @message_handler
    async def handle_idea_request(self, message: IdeaRequest, ctx: MessageContext) -> IdeaResponse:
        # Round 1: apni personality ke hisaab se ek fresh business idea.
        idea = await llm_call_with_retry(
            self._client,
            [
                self._system,
                UserMessage(
                    content=f"Pitch ONE new business idea in the domain of: {message.topic}.",
                    source="user",
                ),
            ],
        )
        return IdeaResponse(agent_name=self._name, idea=idea.strip())

    @message_handler
    async def handle_refine_request(self, message: RefineRequest, ctx: MessageContext) -> IdeaResponse:
        # Round 2: neighbour ka idea critique + improve karo (collaboration!).
        refined = await llm_call_with_retry(
            self._client,
            [
                self._system,
                UserMessage(
                    content=(
                        "Another entrepreneur pitched this idea:\n"
                        f"---\n{message.other_idea}\n---\n"
                        "Critique it briefly from YOUR perspective, then give an "
                        "IMPROVED version of the idea."
                    ),
                    source="user",
                ),
            ],
        )
        return IdeaResponse(agent_name=self._name, idea=refined.strip())


def agent_type_name(persona_name: str) -> str:
    """Persona name -> valid runtime agent-type string (alnum + underscore)."""
    return "entrepreneur_" + re.sub(r"\W+", "_", persona_name.lower()).strip("_")


# ---------------------------------------------------------------------------
# MAIN FLOW: Creator -> dynamic register -> 3 collaboration rounds -> artifacts
# ---------------------------------------------------------------------------
async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = groq_client()

    # ---- STEP 1: CREATOR generates new agents (personas) --------------------
    print("=" * 70)
    print("STEP 1 — CREATOR: LLM se naye agent personas generate")
    print("=" * 70)
    personas, mode = await create_personas(client)
    print(f"   creator mode used: {mode}")
    for p in personas:
        print(f"   -> {p.name}: {p.personality_prompt[:90]}...")

    # Proof artifact: Creator ka output disk par (course me yahan .py file hoti).
    PERSONAS_PATH.write_text(
        json.dumps(
            {"creator_mode": mode, "personas": [p.model_dump() for p in personas]},
            indent=2,
        )
    )
    print(f"   saved -> {PERSONAS_PATH}")

    # ---- STEP 2: DYNAMIC REGISTRATION on the Core runtime --------------------
    # SingleThreadedAgentRuntime = single-process actor runtime. register() ko
    # FACTORY milti hai — agent lazily tab banta hai jab pehla message aata hai.
    # Closure (p=p) se har factory me ALAG persona capture hota hai — yahi
    # "Creator ne runtime me naya agent deploy kiya" wala moment hai.
    print("\n" + "=" * 70)
    print("STEP 2 — runtime me dynamically register (factory closures)")
    print("=" * 70)
    runtime = SingleThreadedAgentRuntime()
    type_names: list[str] = []
    for p in personas:
        tname = agent_type_name(p.name)
        await EntrepreneurAgent.register(
            runtime,
            tname,
            lambda p=p: EntrepreneurAgent(p.name, p.personality_prompt, client),
        )
        type_names.append(tname)
        print(f"   registered agent type: {tname}")

    runtime.start()  # background message-processing loop shuru

    topic = "AI tools for small local businesses"
    print(f"\n   collaboration topic: {topic}")

    # ---- STEP 3 / ROUND 1: har agent apna idea de ----------------------------
    print("\n" + "=" * 70)
    print("ROUND 1 — har agent ka fresh business idea")
    print("=" * 70)
    ideas: list[IdeaResponse] = []
    for tname in type_names:
        # send_message = direct RPC: handler ka return value yahan wapas milta hai.
        resp: IdeaResponse = await runtime.send_message(
            IdeaRequest(topic=topic), AgentId(tname, "default")
        )
        ideas.append(resp)
        print(f"\n   [{resp.agent_name}] IDEA:\n   {resp.idea}")

    # ---- ROUND 2: neighbour refinement (agent-to-agent collaboration) -------
    # Agent i apna idea NEXT neighbour (i+1 mod N) ko bhejta hai refine karne —
    # course ka L106-L107 "messaging each other to refine ideas" pattern.
    print("\n" + "=" * 70)
    print("ROUND 2 — neighbour refinement (idea[i] -> agent[i+1])")
    print("=" * 70)
    refinements: list[IdeaResponse] = []
    for i, idea in enumerate(ideas):
        neighbour = type_names[(i + 1) % len(type_names)]
        resp: IdeaResponse = await runtime.send_message(
            RefineRequest(other_idea=idea.idea), AgentId(neighbour, "default")
        )
        refinements.append(resp)
        print(f"\n   [{resp.agent_name}] refining {idea.agent_name}'s idea:\n   {resp.idea}")

    # ---- ROUND 3: SYNTHESIZER — best refined idea choose karo ---------------
    print("\n" + "=" * 70)
    print("ROUND 3 — Synthesizer: teen refined ideas me se best pick")
    print("=" * 70)
    numbered = "\n\n".join(
        f"IDEA {i + 1} (refined by {r.agent_name}):\n{r.idea}" for i, r in enumerate(refinements)
    )
    verdict = await llm_call_with_retry(
        client,
        [
            SystemMessage(
                content="You are a sharp venture capitalist. Pick the single best idea."
            ),
            UserMessage(
                content=(
                    f"Here are {len(refinements)} refined business ideas:\n\n{numbered}\n\n"
                    "Pick the BEST one. Answer with the idea number, its one-line summary, "
                    "and 2 sentences explaining why it wins."
                ),
                source="user",
            ),
        ],
    )
    print(f"\n   SYNTHESIZER VERDICT:\n   {verdict.strip()}")

    # ---- STEP 4: summary artifact --------------------------------------------
    lines = [
        "# Lab 4 — Agent Creator: Ideas Summary",
        "",
        f"**Topic:** {topic}",
        f"**Creator mode:** {mode}",
        "",
        "## Generated Agent Personas",
    ]
    lines += [f"- **{p.name}** — {p.personality_prompt}" for p in personas]
    lines += ["", "## Round 1 — Original Ideas"]
    lines += [f"### {r.agent_name}\n{r.idea}\n" for r in ideas]
    lines += ["## Round 2 — Neighbour Refinements"]
    lines += [
        f"### {r.agent_name} (refined {ideas[i].agent_name}'s idea)\n{r.idea}\n"
        for i, r in enumerate(refinements)
    ]
    lines += ["## Round 3 — Synthesizer Final Pick", verdict.strip(), ""]
    SUMMARY_PATH.write_text("\n".join(lines))
    print(f"\n   summary saved -> {SUMMARY_PATH}")

    # ---- graceful shutdown ----------------------------------------------------
    # stop_when_idle: pending messages drain hone ke baad runtime band hota hai.
    await runtime.stop_when_idle()
    await client.close()
    print("\nDONE — Creator ne agents banaye, agents ne collaborate kiya, artifacts saved.")


if __name__ == "__main__":
    asyncio.run(main())
