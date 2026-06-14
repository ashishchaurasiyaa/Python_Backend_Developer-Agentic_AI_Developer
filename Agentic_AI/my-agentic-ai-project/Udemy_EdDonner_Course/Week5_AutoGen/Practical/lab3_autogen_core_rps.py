"""
LAB 3 — AutoGen CORE: RoutedAgent + message handlers + runtime (Rock Paper Scissors)
====================================================================================
Lectures: L98-L101 (AutoGen Core), L102-L104 (gRPC distributed runtime — sirf concept note)

KYA SEEKHENGE (yeh lab AgentChat se ek level NEECHE utarta hai):
-----------------------------------------------------------------
1. autogen_core = agent-to-agent MESSAGING runtime — Erlang/Akka jaisa ACTOR MODEL.
   - Tum apne MESSAGE TYPES khud define karte ho (dataclass ya pydantic model).
   - Agent = RoutedAgent subclass. Uske andar @message_handler decorated methods
     batate hain ki "is TYPE ka message aaye to yeh method chalao".
   - RUNTIME (yahan SingleThreadedAgentRuntime) dispatch karta hai: message ka
     python TYPE dekh kar sahi agent ke sahi handler ko route karta hai.
   - send_message() = RPC-style direct message; handler jo return kare wahi
     caller ko response milta hai. (publish_message broadcast bhi hota hai.)
2. AgentChat (AssistantAgent, RoundRobinGroupChat — lab1/lab2) ISI Core ke UPAR
   bana hai. AssistantAgent bhi andar se ek RoutedAgent hi hai jo ChatMessage
   handle karta hai. Core seekhna == samajhna ki teams/handoffs andar kaise chalte hain.
3. DISTRIBUTED note (L102-L104): course me gRPC runtime
   (GrpcWorkerAgentRuntimeHost/Worker) dikhaya jata hai — SAME register/send_message
   API, bas agents alag PROCESSES/machines me chalte hain. Humne grpc extra install
   nahi kiya, isliye SingleThreadedAgentRuntime use kar rahe — code pattern identical
   rehta hai, sirf runtime class swap hoti hai. Yahi Core ka selling point hai.
4. VERSION NOTE: course AutoGen 0.5.1 use karta hai, hum 0.7.5 — same API family
   (autogen_core / autogen_agentchat / autogen_ext split), is lab ke imports/signatures
   dono me same hain.

GAME DESIGN:
------------
- Player1Agent / Player2Agent: apne Groq LLM se EK move choose karte hain
  (defensive parsing + seeded random fallback agar LLM kuch ajeeb bole).
- JudgeAgent: winner PURE PYTHON rules se decide hota hai (LLM ko game logic
  mat do jab deterministic rules kaafi hain!) — LLM sirf funny one-line
  commentary ke liye (woh creative kaam hai, wahan LLM shine karta hai).
- main(): runtime me teeno register karo, 3 rounds khelo, scoreboard print karo.

KAISE CHALANA:
--------------
cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project
uv run Udemy_EdDonner_Course/Week5_AutoGen/Practical/lab3_autogen_core_rps.py
(.env me GROQ_API_KEY chahiye)
"""

import asyncio
import os
import random
from dataclasses import dataclass

from dotenv import load_dotenv

# ---- CORE layer imports (AgentChat ke imports se compare karo — yahan koi
#      AssistantAgent/team nahi, sab kuch low-level building blocks hain) ----
from autogen_core import (
    AgentId,            # kis agent ko message bhejna hai: (type, key) pair
    MessageContext,     # handler ko milta hai: sender, topic, cancellation token
    RoutedAgent,        # base class — type-based message routing deta hai
    SingleThreadedAgentRuntime,  # in-process runtime (gRPC wala cross-process hota)
    message_handler,    # decorator: "is message type ke liye yeh method"
)
# Core me LLM call ke liye DIRECT model client use hota hai (AgentChat ka
# AssistantAgent wrapper nahi) — messages ki list do, CreateResult wapas milta hai.
from autogen_core.models import ModelInfo, SystemMessage, UserMessage
from autogen_ext.models.openai import OpenAIChatCompletionClient

load_dotenv(override=True)

MOVES = ["rock", "paper", "scissors"]


# ---------------------------------------------------------------------------
# GROQ CLIENT — OpenAI-compatible endpoint, isliye OpenAIChatCompletionClient
# hi kaam karta hai; bas base_url + model_info (non-OpenAI model ke liye
# capabilities manually batani padti hain) dena hota hai.
# ---------------------------------------------------------------------------
def groq_client(model: str = "llama-3.3-70b-versatile") -> OpenAIChatCompletionClient:
    return OpenAIChatCompletionClient(
        model=model,
        base_url="https://api.groq.com/openai/v1",
        api_key=os.getenv("GROQ_API_KEY"),
        model_info=ModelInfo(
            vision=False, function_calling=True, json_output=True,
            family="llama-3.3-70b", structured_output=True,
        ),
    )


async def llm_text(client: OpenAIChatCompletionClient, system: str, user: str,
                   attempts: int = 3) -> str:
    """Core-style direct LLM call + retry (free Groq tier kabhi-kabhi 429/5xx deta hai).

    NOTE: yeh AgentChat ka agent.run() NahI hai — Core me hum khud
    client.create([SystemMessage, UserMessage]) bulate hain. AssistantAgent
    andar se yahi karta hai, bas history/tools manage karke.
    """
    last_err: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            result = await client.create(
                [SystemMessage(content=system), UserMessage(content=user, source="user")]
            )
            return str(result.content)
        except Exception as e:  # transient rate-limit/network — retry
            last_err = e
            print(f"      [retry {attempt}/{attempts}] LLM call failed: {e}")
            await asyncio.sleep(2 * attempt)
    raise RuntimeError(f"LLM call failed after {attempts} attempts: {last_err}")


# ---------------------------------------------------------------------------
# 1) MESSAGE TYPES — Core ka contract. Plain dataclasses (pydantic bhi chalta).
#    Runtime inhi TYPES se routing karta hai: handler ka type-hint match hona
#    chahiye. Distributed (gRPC) runtime me yehi types serialize hote hain.
# ---------------------------------------------------------------------------
@dataclass
class PlayRequest:
    """Game master -> player: 'round N ke liye apna move do'."""
    round_no: int


@dataclass
class PlayResponse:
    """Player -> game master: chosen move ('rock'/'paper'/'scissors')."""
    move: str


@dataclass
class JudgeRequest:
    """Game master -> judge: dono moves, faisla karo."""
    move1: str
    move2: str


@dataclass
class JudgeResponse:
    """Judge -> game master: winner (0=draw, 1=player1, 2=player2) + commentary."""
    winner: int
    commentary: str


# ---------------------------------------------------------------------------
# 2) PLAYER AGENTS — RoutedAgent subclass.
#    @message_handler wala method tabhi chalega jab PlayRequest type ka message
#    is agent ko bheja jaye. Method ka RETURN value send_message() caller ko
#    response ke roop me milta hai (request/response RPC pattern).
# ---------------------------------------------------------------------------
class RPSPlayerBase(RoutedAgent):
    """Shared player logic — Player1/Player2 sirf persona/seed me alag hain.

    NOTE: @message_handler INHERIT hota hai — RoutedAgent class ke methods
    inspect karke routing table banata hai, isliye base me handler likhna safe hai.
    """

    def __init__(self, description: str, persona: str, player_no: int,
                 client: OpenAIChatCompletionClient) -> None:
        super().__init__(description)  # RoutedAgent ko sirf description chahiye
        self._persona = persona
        self._player_no = player_no
        self._client = client

    @message_handler  # <-- runtime: "PlayRequest aaya to yeh method"
    async def handle_play(self, message: PlayRequest, ctx: MessageContext) -> PlayResponse:
        # ctx me sender/topic/cancellation hota hai — yahan zaroorat nahi, par
        # real systems me ctx.sender se reply-routing hoti hai.
        system = (
            f"You are playing rock-paper-scissors. {self._persona} "
            "Reply with EXACTLY ONE word: rock, paper, or scissors. Nothing else."
        )
        user = f"Round {message.round_no}. Your move?"
        move = await self._pick_move(system, user, message.round_no)
        return PlayResponse(move=move)

    async def _pick_move(self, system: str, user: str, round_no: int) -> str:
        # DEFENSIVE PARSING: LLM se "Rock!" ya "I choose paper." jaisa kuch bhi
        # aa sakta hai — substring match karo; bilkul na mile to seeded random
        # fallback (seed = round + player, taki run reproducible-ish rahe).
        try:
            raw = (await llm_text(self._client, system, user)).strip().lower()
        except Exception as e:
            print(f"      [fallback] player{self._player_no} LLM down: {e}")
            raw = ""
        found = [m for m in MOVES if m in raw]
        if len(found) == 1:
            return found[0]
        return random.Random(round_no * 10 + self._player_no).choice(MOVES)


class Player1Agent(RPSPlayerBase):
    def __init__(self, client: OpenAIChatCompletionClient) -> None:
        super().__init__("RPS player one", "You are aggressive and unpredictable.", 1, client)


class Player2Agent(RPSPlayerBase):
    def __init__(self, client: OpenAIChatCompletionClient) -> None:
        super().__init__("RPS player two", "You are calm and strategic.", 2, client)


# ---------------------------------------------------------------------------
# 3) JUDGE AGENT — winner PURE PYTHON se (deterministic rules ko LLM mat do),
#    LLM sirf masaledaar one-line commentary ke liye.
# ---------------------------------------------------------------------------
BEATS = {"rock": "scissors", "paper": "rock", "scissors": "paper"}  # key beats value


class JudgeAgent(RoutedAgent):
    def __init__(self, client: OpenAIChatCompletionClient) -> None:
        super().__init__("RPS judge with commentary")
        self._client = client

    @message_handler
    async def handle_judge(self, message: JudgeRequest, ctx: MessageContext) -> JudgeResponse:
        m1, m2 = message.move1, message.move2
        # -- winner: 3 line ka pure python, 100% reliable --
        if m1 == m2:
            winner = 0
        elif BEATS[m1] == m2:
            winner = 1
        else:
            winner = 2
        outcome = {0: "a draw", 1: "Player 1 wins", 2: "Player 2 wins"}[winner]

        # -- commentary: yahan LLM ka creative kaam hai; fail ho to game mat roko --
        try:
            commentary = (await llm_text(
                self._client,
                "You are a hilarious sports commentator for rock-paper-scissors. "
                "Reply with EXACTLY ONE short funny sentence. No preamble.",
                f"Player 1 played {m1}, Player 2 played {m2}, result: {outcome}.",
            )).strip().split("\n")[0]
        except Exception:
            commentary = f"{m1} vs {m2} — {outcome}, the crowd shrugs politely."
        return JudgeResponse(winner=winner, commentary=commentary)


# ---------------------------------------------------------------------------
# 4) GAME LOOP — runtime banao, agents REGISTER karo, messages bhejo.
# ---------------------------------------------------------------------------
async def main() -> None:
    print("=" * 64)
    print("  ROCK PAPER SCISSORS — AutoGen CORE (RoutedAgent + runtime)")
    print("=" * 64)

    # SingleThreadedAgentRuntime: in-process message broker + agent host.
    # gRPC version me yahi do hisson me bat jata: Host (broker) + Worker(s)
    # jisme agents register hote hain — register/send_message code SAME rehta.
    runtime = SingleThreadedAgentRuntime()

    client = groq_client()  # ek hi client teeno agents share kar sakte hain

    # REGISTER: (runtime, "agent_type_string", factory). Agent INSTANCE abhi
    # nahi banta — runtime LAZILY factory chalata hai jab us (type, key) ko
    # pehla message milta hai. Isi liye AgentId("player1", "default") se
    # address karte hain — "default" key; alag keys = alag instances
    # (e.g. per-tenant agents) — actor model ka classic pattern.
    await Player1Agent.register(runtime, "player1", lambda: Player1Agent(client))
    await Player2Agent.register(runtime, "player2", lambda: Player2Agent(client))
    await JudgeAgent.register(runtime, "judge", lambda: JudgeAgent(client))

    runtime.start()  # background me message-processing loop shuru (sync call!)

    scores = {1: 0, 2: 0}
    try:
        for round_no in range(1, 4):  # 3 rounds
            print(f"\n--- ROUND {round_no} ---")

            # Dono players ko PARALLEL me PlayRequest bhejo. send_message
            # await karne par handler ka return (PlayResponse) milta hai.
            resp1, resp2 = await asyncio.gather(
                runtime.send_message(PlayRequest(round_no=round_no), AgentId("player1", "default")),
                runtime.send_message(PlayRequest(round_no=round_no), AgentId("player2", "default")),
            )
            print(f"  Player 1 throws: {resp1.move}")
            print(f"  Player 2 throws: {resp2.move}")

            # Ab judge ko dono moves bhejo
            verdict: JudgeResponse = await runtime.send_message(
                JudgeRequest(move1=resp1.move, move2=resp2.move),
                AgentId("judge", "default"),
            )
            if verdict.winner == 0:
                print("  Result: DRAW")
            else:
                scores[verdict.winner] += 1
                print(f"  Result: Player {verdict.winner} wins the round!")
            print(f"  Commentary: {verdict.commentary}")
            print(f"  Scoreboard: Player1={scores[1]}  Player2={scores[2]}")
    finally:
        # stop_when_idle(): pending messages process hone do, phir runtime band.
        await runtime.stop_when_idle()
        await client.close()

    print("\n" + "=" * 64)
    if scores[1] == scores[2]:
        print(f"  FINAL: It's a TIE at {scores[1]}-{scores[2]}!")
    else:
        champ = 1 if scores[1] > scores[2] else 2
        print(f"  FINAL WINNER: Player {champ}  ({scores[1]}-{scores[2]})")
    print("=" * 64)


if __name__ == "__main__":
    asyncio.run(main())
