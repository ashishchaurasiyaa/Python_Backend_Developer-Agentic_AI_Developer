"""
LAB 1 — CrewAI Fundamentals + Debate Project (Lectures L49-L54)
================================================================

KYA SEEKHENGE (Hinglish me):
----------------------------
1. CrewAI ka MENTAL MODEL — Agents SDK se kaise alag hai:
   - OpenAI Agents SDK me: tum khud system prompt likhte ho, khud Runner.run()
     se loop chalate ho, handoffs/tools manually wire karte ho. LOW-LEVEL control.
   - CrewAI me: tum sirf ROLE-GOAL-BACKSTORY declare karte ho — CrewAI internally
     in teeno ko ek structured SYSTEM PROMPT me convert karta hai. HIGH-LEVEL,
     opinionated framework — "kaam batao, orchestration framework karega".

2. CrewAI ke 4 core building blocks:
   - Agent  = role + goal + backstory  (yahi uska "personality" / system prompt)
   - Task   = description + expected_output  (yahi uska "user prompt" + success criteria)
   - Crew   = agents[] + tasks[] + process  (poora orchestra)
   - Process.sequential  = tasks ek-ke-baad-ek chalte hain (pipeline)
     Process.hierarchical = ek manager LLM decide karta hai kaun-sa agent kab chale
     (hierarchical me manager_llm dena padta hai — is lab me sequential use karenge)

3. TASK CONTEXT CHAINING — context=[task1, task2] param se ek task ke OUTPUTS
   doosre task ke INPUT me inject hote hain. Yahi CrewAI ka "output -> input" wiring hai.

4. TEMPLATING — task description me {motion} placeholder, jo kickoff(inputs={...})
   se runtime par fill hota hai. Reusable crew, alag-alag inputs.

PROJECT (Ed ka Day-1 Debate project):
-------------------------------------
- Ek "Debater" agent (Groq llama-3.3-70b) PEHLE motion ke PAKSH (propose) me bolta hai,
  PHIR wahi agent motion ke KHILAF (oppose) bolta hai. (Same agent, 2 tasks — dikhata
  hai ki agent reusable hai, task hi kaam define karta hai.)
- Ek "Judge" agent (Gemini 2.0 Flash — multi-provider demo!) dono
  arguments padh ke winner declare karta hai, SIRF argument quality par.
  Agar Gemini error de to automatic GROQ FALLBACK hai.

COURSE NOTE: Ed apne course me YAML config approach use karta hai —
agents.yaml/tasks.yaml files + @CrewBase/@agent/@task decorators wali
crew class ("crewai create crew" scaffolding). Hamara lab self-contained
code-style me hai taaki sab kuch ek file me dikhe — concepts same hain,
bas YAML me role/goal/backstory strings config file me chali jaati hain.

KAISE CHALANA HAI:
------------------
cd /Users/youngmanindia/Documents/PythonRevision/Agentic_AI/my-agentic-ai-project
uv run Udemy_EdDonner_Course/Week3_CrewAI/Practical/lab1_crewai_debate.py
"""

import os
import time

from dotenv import load_dotenv

# .env se GROQ_API_KEY / GOOGLE_API_KEY load karo (override=True => .env wins)
load_dotenv(override=True)

# Telemetry band — speed + privacy (CrewAI by default anonymized telemetry bhejta hai)
os.environ.setdefault("CREWAI_DISABLE_TELEMETRY", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

# Gemini provider GEMINI_API_KEY env var dhoondhta hai,
# par hamare .env me key GOOGLE_API_KEY naam se hai — isliye copy kar do.
os.environ["GEMINI_API_KEY"] = os.getenv("GOOGLE_API_KEY", "")

from crewai import LLM, Agent, Crew, Process, Task

# ============================================================================
# STEP 1: LLMs define karo
# ----------------------------------------------------------------------------
# Ed ke course (purana CrewAI) me model string LiteLLM ke through jaati thi —
# wahan seedha LLM(model="groq/llama-3.3-70b-versatile") likh dete the,
# "provider/model" format me. NAYA CrewAI (1.14.x) by default NATIVE provider
# SDKs use karta hai (openai, gemini, anthropic, ...) aur "groq" native list
# me NAHI hai (litellm extra install karna padta — par uska openai==2.24 pin
# hamare project ke openai>=2.38 se conflict karta hai, openai-agents tod deta).
# FIX: Groq ka API OpenAI-COMPATIBLE hai => native "openai" provider ko
# base_url se Groq endpoint par point kar do. provider= kwarg explicitly dene
# se CrewAI model-name validation skip karke seedha us provider ko use karta hai.
# Concept wahi hai — ek string/URL badlo, provider switch. Ye OpenAI Agents
# SDK ke AsyncOpenAI(base_url=...) wale multi-model trick jaisa hi hai.
# ============================================================================
groq_llm = LLM(
    model="llama-3.3-70b-versatile",
    provider="openai",                                # native openai provider...
    base_url="https://api.groq.com/openai/v1",        # ...par endpoint Groq ka
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.7,
)
# Gemini NATIVE provider hai (google-genai SDK installed) — ye GOOGLE_API_KEY
# env var khud bhi utha leta hai, hum explicitly de rahe hain clarity ke liye.
# NOTE: gemini-2.0-flash ka FREE tier quota ab 0 hai (429 deta hai), isliye
# gemini-2.5-flash use kar rahe hain — free tier par ye chalta hai.
gemini_llm = LLM(
    model="gemini-2.5-flash",
    provider="gemini",
    api_key=os.getenv("GOOGLE_API_KEY"),
    temperature=0.3,  # judge ko thanda dimaag chahiye
)


# ============================================================================
# STEP 2: Crew builder
# ----------------------------------------------------------------------------
# Function isliye banaya kyunki Judge ka LLM swap karna hai (gemini -> groq
# fallback). Crew objects stateful hote hain, isliye fresh build karna safest hai.
# ============================================================================
def build_debate_crew(judge_llm: LLM) -> tuple[Crew, Task, Task, Task]:
    # ------------------------------------------------------------------
    # AGENT = role + goal + backstory
    # CrewAI in teeno ko jod ke ek structured system prompt banata hai:
    #   "You are {role}. {backstory}. Your personal goal is: {goal}"
    # Isliye backstory me persona-detail daalna = prompt engineering hi hai,
    # bas framework-managed. (Agents SDK me ye sab `instructions` string thi.)
    # ------------------------------------------------------------------
    debater = Agent(
        role="Champion Debater",
        goal="Present the most convincing, well-structured argument for whichever side of the motion you are assigned",
        backstory=(
            "You are a world-class competitive debater who has won multiple international "
            "debate championships. You can argue ANY side of ANY motion with equal skill, "
            "using sharp logic, concrete examples, and persuasive rhetoric. You never "
            "hedge — when assigned a side, you commit to it fully."
        ),
        llm=groq_llm,  # Debater hamesha Groq par
        verbose=True,
    )

    judge = Agent(
        role="Impartial Debate Judge",
        goal="Decide the winner of a debate based purely on the quality of the arguments presented",
        backstory=(
            "You are a respected, scrupulously neutral debate adjudicator. You have NO "
            "personal opinion on any motion. You evaluate only: logical rigor, evidence, "
            "structure, and persuasiveness of the arguments as written. You always pick "
            "exactly one winner and justify your verdict crisply."
        ),
        llm=judge_llm,  # Gemini (ya fallback me Groq) — multi-provider crew!
        verbose=True,
    )

    # ------------------------------------------------------------------
    # TASK = description + expected_output (+ agent + optional context)
    # NOTE: {motion} ek TEMPLATE PLACEHOLDER hai — kickoff(inputs={"motion": ...})
    # se runtime par interpolate hota hai. Yahi CrewAI templating hai.
    # ------------------------------------------------------------------
    propose_task = Task(
        description=(
            "You are PROPOSING the motion: '{motion}'. "
            "Write a compelling argument IN FAVOUR of this motion. "
            "Use clear logic and concrete examples. Keep it under 250 words."
        ),
        expected_output="A persuasive ~200-250 word argument supporting the motion.",
        agent=debater,
    )

    # SAME debater agent, OPPOSITE side — dikhata hai ki agent reusable persona
    # hai; konsa kaam karna hai ye Task decide karta hai, Agent nahi.
    oppose_task = Task(
        description=(
            "You are OPPOSING the motion: '{motion}'. "
            "Write a compelling argument AGAINST this motion. "
            "Use clear logic and concrete examples. Keep it under 250 words."
        ),
        expected_output="A persuasive ~200-250 word argument against the motion.",
        agent=debater,
    )

    # ------------------------------------------------------------------
    # CONTEXT CHAINING (lab ka hero concept!):
    # context=[propose_task, oppose_task] => in dono tasks ke FINAL OUTPUTS
    # judge ke task-prompt me automatically inject ho jaate hain.
    # Yahi CrewAI ka "output -> input" wiring hai — Agents SDK me ye kaam
    # tumhe manually karna padta tha (pichle run ka result agle prompt me
    # khud paste karna). Yahan framework handle karta hai.
    # ------------------------------------------------------------------
    judge_task = Task(
        description=(
            "Two debaters have argued the motion: '{motion}'. "
            "You have been given the PROPOSING argument and the OPPOSING argument "
            "(see context). Judge ONLY the quality of the arguments — logic, evidence, "
            "structure, persuasiveness. Do NOT inject your own views on the motion. "
            "Declare exactly one winner: 'PROPOSITION' or 'OPPOSITION', then justify "
            "your verdict in 3-5 sentences."
        ),
        expected_output="Verdict line ('Winner: PROPOSITION' or 'Winner: OPPOSITION') followed by a 3-5 sentence justification.",
        agent=judge,
        context=[propose_task, oppose_task],  # <-- yahi hai output->input chaining
    )

    # ------------------------------------------------------------------
    # CREW = agents + tasks + process
    # Process.sequential => tasks list-order me chalenge: propose -> oppose -> judge.
    # (Process.hierarchical hota to ek manager_llm dynamically delegate karta —
    #  Day-1 project ke liye sequential hi sahi hai.)
    # ------------------------------------------------------------------
    crew = Crew(
        agents=[debater, judge],
        tasks=[propose_task, oppose_task, judge_task],
        process=Process.sequential,
        verbose=True,
        # memory=True yahan AVOID kiya — default OpenAI embeddings use hote
        # jo invalid OPENAI_API_KEY par 401 dete. Memory Lab me alag se dekhenge.
    )
    return crew, propose_task, oppose_task, judge_task


# ============================================================================
# STEP 3: Kickoff with retry + Gemini->Groq judge fallback
# ----------------------------------------------------------------------------
# Free Groq tier kabhi-kabhi transient/rate-limit error deta hai, isliye
# simple retry loop. Aur agar Gemini (judge) hi fail ho jaye to poora crew
# Groq-judge ke saath rebuild karke dobara try karte hain.
# ============================================================================
def run_debate(motion: str, attempts: int = 3):
    judge_llms = [("gemini", gemini_llm), ("groq-fallback", groq_llm)]
    last_error: Exception | None = None

    for judge_name, judge_llm in judge_llms:
        for attempt in range(1, attempts + 1):
            try:
                crew, t_propose, t_oppose, t_judge = build_debate_crew(judge_llm)
                print(f"\n>>> Kickoff (judge={judge_name}, attempt {attempt}/{attempts}) ...")
                # kickoff(inputs=...) => {motion} placeholders sab task
                # descriptions me yahin interpolate hote hain.
                crew.kickoff(inputs={"motion": motion})
                return t_propose, t_oppose, t_judge, judge_name
            except Exception as e:
                last_error = e
                print(f"!!! Attempt {attempt} failed (judge={judge_name}): {e}")
                time.sleep(5 * attempt)  # transient/rate-limit ke liye backoff
        print(f"!!! Judge '{judge_name}' exhausted, trying next fallback (if any)...")

    raise RuntimeError(f"Debate crew failed on all attempts/fallbacks: {last_error}")


# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    motion = "There needs to be strict laws to regulate LLMs"

    t_propose, t_oppose, t_judge, judge_used = run_debate(motion)

    # Har Task ke baad uska result task.output (TaskOutput) me store hota hai —
    # .raw = plain text. (Structured chahiye ho to output_pydantic — agle lab me.)
    print("\n" + "=" * 78)
    print("DEBATE KA FINAL SUMMARY (Hinglish)")
    print("=" * 78)
    print(f"\nMOTION: {motion}")
    print(f"JUDGE LLM USED: {judge_used} "
          f"({'gemini-2.5-flash' if judge_used == 'gemini' else 'llama-3.3-70b (fallback)'})")

    print("\n--- [1] PAKSH ME (PROPOSE — Debater @ Groq) ---")
    print(t_propose.output.raw)

    print("\n--- [2] KHILAF ME (OPPOSE — same Debater @ Groq) ---")
    print(t_oppose.output.raw)

    print("\n--- [3] FAISLA (VERDICT — Judge, context=[propose, oppose] se) ---")
    print(t_judge.output.raw)

    print("\nSeekh: Agent=persona, Task=kaam, Crew=orchestra, context=[]=output->input "
          "wiring, kickoff(inputs)={placeholders} fill. Bas yahi CrewAI ka core hai!")
