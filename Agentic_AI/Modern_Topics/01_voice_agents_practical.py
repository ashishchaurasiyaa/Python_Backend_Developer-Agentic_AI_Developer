"""
Modern Topics — Doc 1: Voice Agents (PRACTICAL — Hands On)
===========================================================
Pipecat-style voice pipeline ko andar se samjho: VAD → STT → LLM → TTS.
Lesson (01_voice_agents.md) me 10-line sketch tha — ye REAL cheez hai:
ek chalta hua pipeline jisme har stage alag processor hai, frames queue
se flow karte hain, latency per-stage measure hoti hai, aur barge-in
(user interrupts agent) properly handle hota hai.

Sab kuch TEXT-MODE SIMULATION me chalta hai — zero audio deps, zero API
keys. Mic ki jagah stdin, speaker ki jagah stdout, per-stage sleep()
real-world latency simulate karta hai. OPENAI_API_KEY set karo to LLM
stage real streaming ban jaata hai; warna mock canned responses.

Sections:
  1. Latency budget — kyun <800ms voice-to-voice TTFB zaroori hai
  2. Pipeline anatomy — frames + processors + stage boundaries
  3. Simulated voice turns — full VAD→STT→LLM→TTS with latency report
  4. Barge-in / interruption handling (the hard part of voice agents)
  5. Real Pipecat wiring (import-guarded, actual service classes)
  6. LiveKit Agents equivalents — concept mapping + guarded code
  7. Production gotchas + interview angle

Install (sim mode ke liye KUCH NAHI chahiye — pure stdlib):
    # optional, LLM stage real banane ke liye:
    pip install openai            # + export OPENAI_API_KEY=sk-...
    # optional, section 5 (real audio pipeline):
    pip install "pipecat-ai[silero,deepgram,openai,elevenlabs,local]"
    # optional, section 6:
    pip install "livekit-agents[deepgram,openai,elevenlabs,silero]"

Run:
    python 01_voice_agents_practical.py          # saare sections
    python 01_voice_agents_practical.py 3        # ek section
    python 01_voice_agents_practical.py chat     # interactive: stdin → LLM → stdout
    echo "hello" | python 01_voice_agents_practical.py chat   # piped bhi chalta hai
"""

import asyncio
import os
import re
import sys
import time
from dataclasses import dataclass

# ─────────────────────────────────────────────────────────────────────────────
# LATENCY BUDGET — the numbers every voice-agent engineer knows by heart
# ─────────────────────────────────────────────────────────────────────────────
# "Voice-to-voice TTFB" = user ne bolna band kiya → agent ki awaaz ka
# PEHLA sample speaker pe. Har stage ka hissa (cascaded pipeline):

BUDGET_MS = {
    "transport_in":  50,    # mic → server (WebRTC one-way)
    "vad":          200,    # silence window — VAD ko itna quiet SUNNA padta hai
    "stt":          100,    # streaming STT ka final-transcript flush
    "llm_ttft":     300,    # LLM time-to-first-token
    "tts_ttfb":     100,    # TTS time-to-first-audio-byte
    "transport_out": 50,    # server → speaker
}
TOTAL_TTFB_BUDGET_MS = 800  # sum ≈ 800ms — the industry target for cascaded

# Simulation constants — sim me hum in latencies ko sleep() se model karte
# hain, taki metrics table realistic dikhe. (transport spans sim me nahi hain
# kyunki stdin/stdout local hai.)
SIM_VAD_MS = 200            # endpoint silence wait (irreducible — silence IS the signal)
SIM_STT_MS = 100            # final transcript latency
SIM_LLM_TTFT_MS = 300       # mock LLM first-token delay
SIM_LLM_MS_PER_TOKEN = 30   # mock LLM streaming speed (~33 tok/s)
SIM_TTS_TTFB_MS = 100       # mock TTS first-byte delay
SIM_PLAYBACK_MS_PER_WORD = 60  # compressed playback (real bolne se tez, demo ke liye)


# ─────────────────────────────────────────────────────────────────────────────
# FRAMES — pipeline me data-ki-unit (Pipecat ka core idea)
# ─────────────────────────────────────────────────────────────────────────────
# Pipecat me har cheez ek Frame hai: AudioRawFrame, TranscriptionFrame,
# TextFrame, TTSAudioRawFrame, StartInterruptionFrame... Stages frames ko
# consume/produce karte hain aur aage push karte hain. Yahi "stage boundary"
# hai — har stage sirf apne input-frame-type ko jaanta hai, baaki passthrough.
#
# turn_id kyun? Barge-in ke baad purane turn ke stale frames pipeline me
# tairte reh sakte hain. Generation-counter pattern: har frame pe turn_id,
# stage current turn_id se match na ho to frame DROP. (Pipecat isi kaam ke
# liye interruption pe in-flight frames invalidate karta hai.)

class Frame:
    """Base class — sirf type-tag ka kaam karta hai."""


@dataclass
class SimUtteranceFrame(Frame):     # "mic" — sim me user ka bola hua text
    text: str = ""
    turn_id: int = 0


@dataclass
class AudioSegmentFrame(Frame):     # VAD ne speech segment carve kiya
    text: str = ""                  # (sim me audio == text payload)
    turn_id: int = 0


@dataclass
class TranscriptionFrame(Frame):    # STT ka final transcript
    text: str = ""
    turn_id: int = 0


@dataclass
class LLMTokenFrame(Frame):         # LLM ka streamed token
    token: str = ""
    turn_id: int = 0


@dataclass
class LLMResponseEndFrame(Frame):   # LLM turn khatam (ya interrupt hua)
    turn_id: int = 0
    interrupted: bool = False


class EndFrame(Frame):              # pipeline shutdown sentinel
    pass


# ─────────────────────────────────────────────────────────────────────────────
# METRICS — per-turn latency instrumentation
# ─────────────────────────────────────────────────────────────────────────────

class TurnMetrics:
    """Har turn ke stage-transition timestamps. report() budget-vs-actual
    table print karta hai — production me yehi data OpenTelemetry spans
    banta hai (har stage = ek span)."""

    def __init__(self):
        self.t0 = time.perf_counter()
        self.marks = {"turn_start": self.t0}
        self.extra = {}

    def mark(self, label):
        # setdefault: pehla occurrence hi count hota hai (first token, first byte)
        self.marks.setdefault(label, time.perf_counter())

    def since_start(self):
        return time.perf_counter() - self.t0

    def span_ms(self, a, b):
        ta, tb = self.marks.get(a), self.marks.get(b)
        return (tb - ta) * 1000 if (ta is not None and tb is not None) else None

    def report(self, interrupted=False):
        rows = [
            ("VAD endpoint wait",      BUDGET_MS["vad"],      self.span_ms("turn_start", "vad_done")),
            ("STT finalize",           BUDGET_MS["stt"],      self.span_ms("vad_done", "stt_done")),
            ("LLM first token (TTFT)", BUDGET_MS["llm_ttft"], self.span_ms("stt_done", "llm_first_token")),
            ("token→first chunk",      None,                  self.span_ms("llm_first_token", "first_chunk_ready")),
            ("TTS first byte (TTFB)",  BUDGET_MS["tts_ttfb"], self.span_ms("first_chunk_ready", "tts_first_audio")),
        ]
        total = self.span_ms("turn_start", "tts_first_audio")
        print("   ── turn latency report ─────────────────────────────────")
        print(f"   {'stage':<26}{'budget':>8}{'actual':>9}   status")
        for label, budget, actual in rows:
            b = f"{budget}ms" if budget else "—"
            if actual is None:
                print(f"   {label:<26}{b:>8}{'—':>9}   (not reached)")
                continue
            if budget is None:
                status = "(hidden cost — see note)"
            elif actual <= budget * 1.15:          # 15% jitter allowance
                status = "OK"
            else:
                status = f"OVER +{actual - budget:.0f}ms"
            print(f"   {label:<26}{b:>8}{actual:>7.0f}ms   {status}")
        print("   " + "─" * 56)
        if total is not None:
            verdict = "PASS" if total <= TOTAL_TTFB_BUDGET_MS * 1.15 else f"OVER +{total - TOTAL_TTFB_BUDGET_MS:.0f}ms"
            tb = f"{TOTAL_TTFB_BUDGET_MS}ms"
            print(f"   {'voice-to-voice TTFB':<26}{tb:>8}{total:>7.0f}ms   {verdict}")
        if "llm_tokens" in self.extra:
            print(f"   (llm tokens streamed: {self.extra['llm_tokens']})")
        if interrupted:
            print("   (turn INTERRUPTED by barge-in — partial response)")


# ─────────────────────────────────────────────────────────────────────────────
# STAGES — har ek FrameProcessor jaisa: inbox queue → process() → push aage
# ─────────────────────────────────────────────────────────────────────────────

class Stage:
    """Ek pipeline stage = apna asyncio.Queue inbox + ek long-running task.
    Pipecat ka FrameProcessor bilkul yehi hai (plus system-frames jo queue
    BYPASS karte hain — hum wo interrupt() me simulate karte hain)."""

    name = "stage"

    def __init__(self, pipe):
        self.pipe = pipe
        self.inbox = asyncio.Queue()
        self.next = None

    def link(self, nxt):
        self.next = nxt
        return nxt

    def reset(self):
        """Naya turn shuru — per-turn state saaf karo."""

    async def push(self, frame):
        if self.next is not None:
            await self.next.inbox.put(frame)

    async def process(self, frame):
        await self.push(frame)      # default: passthrough (unknown frames aage)

    async def run(self):
        while True:
            frame = await self.inbox.get()
            if isinstance(frame, EndFrame):
                await self.push(frame)
                return
            # Generation-counter check: stale turn ke frames drop
            tid = getattr(frame, "turn_id", None)
            if tid is not None and tid != self.pipe.turn_id:
                continue
            await self.process(frame)


class SimVADStage(Stage):
    """VAD: kachcha audio sunta hai, speech segments carve karta hai.
    In: SimUtteranceFrame → Out: AudioSegmentFrame.
    Asli VAD (Silero/WebRTC-VAD) har 20-30ms audio chunk pe speech-prob
    deta hai; 'user ruk gaya' tabhi pata chalta hai jab stop_secs (~200ms)
    tak silence mile. Ye wait IRREDUCIBLE hai — kam karo to user ke
    saans lene pe hi agent bol padega (false endpointing)."""

    name = "vad"

    async def process(self, frame):
        if not isinstance(frame, SimUtteranceFrame):
            await self.push(frame)
            return
        await asyncio.sleep(SIM_VAD_MS / 1000)          # silence window wait
        self.pipe.metrics.mark("vad_done")
        await self.push(AudioSegmentFrame(text=frame.text, turn_id=frame.turn_id))


class SimSTTStage(Stage):
    """STT: audio segment → final transcript.
    In: AudioSegmentFrame → Out: TranscriptionFrame.
    Real me streaming STT (Deepgram/Whisper-streaming) user ke BOLTE HUE
    partial transcripts deta hai; endpoint pe sirf final flush ka intezar
    hota hai (~100ms). Batch Whisper (poora clip ek saath) yaha 500ms+
    kha jaata — isliye realtime me hamesha streaming STT."""

    name = "stt"

    async def process(self, frame):
        if not isinstance(frame, AudioSegmentFrame):
            await self.push(frame)
            return
        await asyncio.sleep(SIM_STT_MS / 1000)          # final-transcript flush
        self.pipe.metrics.mark("stt_done")
        print(f"   [t={self.pipe.metrics.since_start():5.2f}s] [stt] transcript: {frame.text!r}")
        await self.push(TranscriptionFrame(text=frame.text, turn_id=frame.turn_id))


class LLMStage(Stage):
    """LLM: transcript → streamed tokens.
    In: TranscriptionFrame → Out: LLMTokenFrame*, LLMResponseEndFrame.
    Streaming NON-NEGOTIABLE hai: poore response ka wait karo to TTFB
    me LLM ka FULL generation time judta (1-3s). Token-by-token push
    karo to TTS pehle sentence pe hi bolna shuru kar deta hai."""

    name = "llm"

    def __init__(self, pipe, llm_stream):
        super().__init__(pipe)
        self.llm_stream = llm_stream    # async generator fn: prompt → tokens

    async def process(self, frame):
        if not isinstance(frame, TranscriptionFrame):
            await self.push(frame)
            return
        m = self.pipe.metrics
        n = 0
        async for token in self.llm_stream(frame.text):
            # Cooperative interruption check har token pe. (Real Pipecat
            # generation TASK ko cancel karta hai — CancelledError pattern.
            # Flag-check version yaha clarity ke liye hai; lesson same hai:
            # token loop me interrupt ka exit point HONA CHAHIYE.)
            if self.pipe.interrupted.is_set():
                print(f"   [t={m.since_start():5.2f}s] [llm] BARGE-IN → generation stopped at {n} tokens")
                m.extra["llm_tokens"] = n
                return      # end-frame interrupt() khud inject karta hai
            if n == 0:
                m.mark("llm_first_token")
            n += 1
            await self.push(LLMTokenFrame(token=token, turn_id=frame.turn_id))
        m.extra["llm_tokens"] = n
        m.mark("llm_done")
        await self.push(LLMResponseEndFrame(turn_id=frame.turn_id))


def pop_sentence(buf):
    """Buffer se pehla complete sentence nikaalo (streaming TTS chunking).
    Production chunkers abbreviations ('Dr.', 'v2.1') handle karte hain
    aur TTFB bachane ke liye pehla chunk COMMA/clause pe bhi bhej dete
    hain — sentence ka wait TTFB me seedha judta hai (report me dikhega)."""
    m = re.search(r"[.!?](\s|$)", buf)
    if not m:
        return None, buf
    end = m.end()
    return buf[:end], buf[end:]


class SimTTSStage(Stage):
    """TTS: tokens → bola hua audio (sim: stdout).
    In: LLMTokenFrame/LLMResponseEndFrame → Out: (speaker).
    Tokens ko sentence-chunks me jama karta hai; har complete sentence
    turant synthesize + 'play'. LLM abhi generate kar raha hota hai jab
    pehla sentence bol chuka hota hai — yehi streaming overlap hai."""

    name = "tts"

    def __init__(self, pipe):
        super().__init__(pipe)
        self.buffer = ""

    def reset(self):
        self.buffer = ""

    async def speak(self, text):
        m = self.pipe.metrics
        m.mark("first_chunk_ready")
        if "tts_first_audio" not in m.marks:
            await asyncio.sleep(SIM_TTS_TTFB_MS / 1000)     # synth first-byte
            m.mark("tts_first_audio")
        print(f"   [t={m.since_start():5.2f}s] [speaker] agent: {text.strip()}")
        # Playback simulate (compressed). Real me playback client pe hota
        # hai, pipeline block nahi karta — par barge-in demo ke liye humein
        # 'abhi bol raha hai' ka window chahiye.
        words = len(text.split())
        await asyncio.sleep(min(words * SIM_PLAYBACK_MS_PER_WORD, 900) / 1000)

    async def process(self, frame):
        if isinstance(frame, LLMTokenFrame):
            if self.pipe.interrupted.is_set():
                return                          # muh band — playback stop
            self.buffer += frame.token
            while True:
                sent, self.buffer = pop_sentence(self.buffer)
                if sent is None:
                    break
                if self.pipe.interrupted.is_set():
                    return
                await self.speak(sent)
        elif isinstance(frame, LLMResponseEndFrame):
            if self.pipe.turn_done.is_set():
                return                          # duplicate end-frame guard
            leftover, self.buffer = self.buffer.strip(), ""
            if frame.interrupted:
                if leftover:
                    print(f"   [t={self.pipe.metrics.since_start():5.2f}s] "
                          f"[tts] flushed unspoken text: {leftover[:48]!r}...")
            elif leftover:
                await self.speak(leftover)      # trailing text bina [.!?] ke
            self.pipe.metrics.report(interrupted=frame.interrupted)
            self.pipe.turn_done.set()
        else:
            await self.push(frame)


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE — stages ko jodta hai, turns chalata hai, barge-in karta hai
# ─────────────────────────────────────────────────────────────────────────────

class VoicePipeline:
    """mic → VAD → STT → LLM → TTS → speaker (sim: stdin → ... → stdout).
    Pipecat me: Pipeline([transport.input(), stt, llm, tts, transport.output()])
    LiveKit me: AgentSession(vad=..., stt=..., llm=..., tts=...)"""

    def __init__(self, llm_stream):
        self.turn_id = 0
        self.interrupted = asyncio.Event()
        self.turn_done = asyncio.Event()
        self.metrics = TurnMetrics()
        self.stages = [SimVADStage(self), SimSTTStage(self),
                       LLMStage(self, llm_stream), SimTTSStage(self)]
        for a, b in zip(self.stages, self.stages[1:]):
            a.link(b)
        self.tasks = []

    async def start(self):
        self.tasks = [asyncio.create_task(s.run()) for s in self.stages]

    async def say(self, text):
        """Ek user turn: utterance push karo, TTS ke 'response done' tak wait."""
        self.turn_id += 1
        self.metrics = TurnMetrics()
        self.turn_done = asyncio.Event()
        self.interrupted.clear()
        for s in self.stages:
            s.reset()
        print(f"\n   [t= 0.00s] [mic] user: {text!r}")
        await self.stages[0].inbox.put(SimUtteranceFrame(text=text, turn_id=self.turn_id))
        await self.turn_done.wait()

    async def interrupt(self):
        """BARGE-IN. Real pipeline me trigger: agent ke bolte waqt VAD ne
        user speech detect ki. Teen kaam ATOMIC hone chahiye:
          1. flag set  → LLM generation ruke, TTS playback ruke
          2. queues flush → jo tokens/sentences bole nahi gaye, kabhi na bolein
          3. turn close → naye turn ke liye pipeline saaf
        Pipecat isko StartInterruptionFrame se karta hai jo SYSTEM frame
        hai — data queues ko BYPASS karke turant har stage tak pahunchta
        hai (warna interrupt hi queue me phas jaata!)."""
        if self.turn_done.is_set():
            return
        self.interrupted.set()
        for s in self.stages:                       # queued (unspoken) frames flush
            while not s.inbox.empty():
                s.inbox.get_nowait()
        # Turn ko close karne ke liye end-frame seedha TTS ko (system-frame sim)
        await self.stages[-1].inbox.put(
            LLMResponseEndFrame(turn_id=self.turn_id, interrupted=True))

    async def shutdown(self):
        await self.stages[0].inbox.put(EndFrame())
        await asyncio.gather(*self.tasks)


# ─────────────────────────────────────────────────────────────────────────────
# LLM BACKENDS — mock (zero deps) ya real OpenAI streaming (key ho to)
# ─────────────────────────────────────────────────────────────────────────────

_CANNED = [
    (("mars",),
     "Mars is the fourth planet from the Sun. It looks red because of iron "
     "oxide dust. A day there lasts about twenty five hours."),
    (("solar", "planet"),
     "The solar system has eight planets. Mercury sits closest to the Sun. "
     "Venus is the hottest world. Earth is our home planet. Mars is the red "
     "planet. Jupiter is the largest gas giant. Saturn carries the famous "
     "rings. Uranus and Neptune are the distant ice giants."),
    (("weather", "baarish", "rain"),
     "I do not have live weather data in mock mode. In Mumbai this season "
     "expect monsoon showers. Carry an umbrella just in case."),
    (("hello", "hi", "namaste", "kaun"),
     "Hello there! I am the voice pipeline demo. Ask me about the solar "
     "system, or about Mars, or the weather."),
]
_DEFAULT_CANNED = ("That is a good question. In mock mode I only know a few "
                   "canned answers. Set OPENAI_API_KEY to get real streaming "
                   "responses through this same pipeline.")


async def mock_llm_stream(prompt):
    """Canned response, word-by-word streamed — real LLM ke TTFT aur
    token-rate ki nakal karta hai taki latency table sach jaisi lage."""
    low = prompt.lower()
    text = _DEFAULT_CANNED
    for keys, resp in _CANNED:
        if any(k in low for k in keys):
            text = resp
            break
    await asyncio.sleep(SIM_LLM_TTFT_MS / 1000)         # TTFT
    for word in text.split():
        yield word + " "
        await asyncio.sleep(SIM_LLM_MS_PER_TOKEN / 1000)


async def openai_llm_stream(prompt):
    """Real streaming LLM — wahi async-generator contract, isliye pipeline
    me drop-in replace ho jaata hai. (Stage boundary ka fayda yehi hai.)"""
    from openai import AsyncOpenAI
    client = AsyncOpenAI()
    stream = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system",
             "content": "You are a voice assistant. Spoken style, short words, "
                        "max three sentences. No markdown, no lists."},
            {"role": "user", "content": prompt},
        ],
        stream=True, max_tokens=120,
    )
    async for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content:
            yield chunk.choices[0].delta.content


def pick_llm():
    """Key + sdk ho to real, warna mock. File HAMESHA chalti hai."""
    if os.getenv("OPENAI_API_KEY"):
        try:
            import openai  # noqa: F401
            print("   [llm] OPENAI_API_KEY found → real gpt-4o-mini streaming")
            return openai_llm_stream
        except ImportError:
            print("   [llm] key hai par sdk nahi → pip install openai (mock use kar raha)")
    else:
        print("   [llm] no OPENAI_API_KEY → mock LLM (canned, streamed)")
    return mock_llm_stream


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Latency budget — kyun <800ms TTFB matter karta hai
# ─────────────────────────────────────────────────────────────────────────────

def section_1_budget():
    print("\n[1] Latency budget — the <800ms rule")
    print("""
   Human conversation me turn-gap ~200-500ms hota hai. Agent ka feel:
     < 500ms   : human-jaisa (speech-to-speech models ka target)
     500-800ms : acceptable — 'assistant' feel, production target
     800-1200ms: laggy — users agent ke UPAR bolna shuru karte hain
     > 1500ms  : 'lagta hai toot gaya' — user repeat karta hai, transcripts
                 overlap ho jaate hain, poora turn-taking hi bigad jaata hai
   Isliye TTFB (time-to-first-BYTE of speech) hi king metric hai —
   total response time nahi. Pehla shabd jaldi bolo, baaki stream hoga.
""")
    print(f"   {'stage':<26}{'budget':>8}   note")
    notes = {
        "transport_in":  "WebRTC one-way (region co-location!)",
        "vad":           "silence window — IRREDUCIBLE tradeoff",
        "stt":           "streaming STT final flush",
        "llm_ttft":      "chhota system prompt = chhota TTFT",
        "tts_ttfb":      "streaming TTS (Cartesia/ElevenLabs turbo)",
        "transport_out": "server → speaker",
    }
    for k, v in BUDGET_MS.items():
        print(f"   {k:<26}{v:>6}ms   {notes[k]}")
    print("   " + "─" * 56)
    print(f"   {'TOTAL voice-to-voice':<26}{sum(BUDGET_MS.values()):>6}ms   ≈ {TOTAL_TTFB_BUDGET_MS}ms target")
    print("""
   Levers jab budget phat jaaye:
     - streaming EVERYWHERE (STT partials, LLM tokens, TTS chunks)
     - clause-level TTS chunking (comma pe hi bolna shuru)
     - speculative generation (STT partial pe LLM warm-start)
     - chhote/tez models (Haiku, Flash, gpt-4o-mini)
     - services ko same region me co-locate karo (har hop ~50-100ms)
   Speech-to-speech route (GPT-4o Realtime, Gemini Live): ~300-500ms —
   text round-trip hi nahi hai. Tradeoff: stages ke beech deterministic
   guardrails/logging nahi laga sakte, cost zyada, voice-cloning kam control.""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Pipeline anatomy — frames, processors, stage boundaries
# ─────────────────────────────────────────────────────────────────────────────

def section_2_anatomy():
    print("\n[2] Pipeline anatomy (Pipecat mental model)")
    print("""
   mic → [ VAD ] → [ STT ] → [ LLM ] → [ TTS ] → speaker
          200ms     100ms     300ms     100ms          (budget per stage)

   Har stage = FrameProcessor: apna inbox queue + async task.
   Stage boundaries = frame types (yehi contract hai):""")
    flow = [
        ("vad", "SimUtteranceFrame", "AudioSegmentFrame", "speech carve karo, endpoint detect"),
        ("stt", "AudioSegmentFrame", "TranscriptionFrame", "audio → final text"),
        ("llm", "TranscriptionFrame", "LLMTokenFrame*", "text → streamed tokens"),
        ("tts", "LLMTokenFrame*", "(speaker)", "sentence-chunks → audio"),
    ]
    print(f"   {'stage':<6}{'consumes':<20}{'produces':<20}kaam")
    for name, cin, cout, job in flow:
        print(f"   {name:<6}{cin:<20}{cout:<20}{job}")
    print("""
   Do design rules jo Pipecat se seekhne layak hain:
   1. Unknown frames PASSTHROUGH hote hain — isliye pipeline me beech me
      naya stage (logger, guardrail, translation) daalna free hai.
   2. System frames (interruption, error) data queues BYPASS karte hain —
      warna 'ruk jao!' message khud hi queue me line lagata.
   SENIOR TIP: stage boundary text/frames me rakhne ka asli fayda —
   har boundary pe log/moderate/cache kar sakte ho. Speech-to-speech
   models me ye seams hote hi nahi.""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Simulated voice turns — full pipeline + latency report
# ─────────────────────────────────────────────────────────────────────────────

def section_3_sim_turns():
    print("\n[3] Simulated voice turns (text-mode, zero audio deps)")
    llm = pick_llm()

    async def main():
        p = VoicePipeline(llm_stream=llm)
        await p.start()
        # Scripted utterances (interactive chahiye to: `python <file> chat`)
        await p.say("Hello there, kaun ho tum?")
        await p.say("What's the weather like in Mumbai today?")
        await p.shutdown()

    asyncio.run(main())
    print("""
   Note 'token→first chunk' row: TTS ko pehla POORA sentence chahiye tha,
   wo wait TTFB me chhupa hua judta hai. Production frameworks isliye
   pehla chunk comma/clause pe hi bhej dete hain — 100-200ms ki bachat.""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Barge-in — user agent ko beech me kaat de (the hard part)
# ─────────────────────────────────────────────────────────────────────────────

def section_4_bargein():
    print("\n[4] Barge-in / interruption handling")
    print("""
   Scenario: agent lamba jawab bol raha hai, user beech me hi bol pada.
   Bina barge-in ke agent bolta rahega — worst UX in voice. Chain:
     VAD detects user speech DURING playback
       → LLM generation cancel (paise + stale tokens bachao)
       → TTS playback stop + queued audio flush
       → naya turn shuru
   Prereq jo log bhool jaate hain: ECHO CANCELLATION (AEC). Speaker ki
   awaaz mic me wapas aati hai — AEC ke bina agent KHUD KO sunkar khud
   ko interrupt kar lega (self-barge-in loop).""")
    llm = pick_llm()

    async def main():
        p = VoicePipeline(llm_stream=llm)
        await p.start()
        # Lamba jawab trigger karo, phir 1.4s pe user "bolna shuru" karta hai
        turn = asyncio.create_task(p.say("tell me all about the solar system"))
        await asyncio.sleep(1.4)
        print("   [t= 1.40s] [mic] (user starts speaking — VAD fires during playback)")
        await p.interrupt()
        await turn
        # Interrupted turn ke baad pipeline saaf hai — naya turn normal chalta hai
        await p.say("actually just tell me about mars")
        await p.shutdown()

    asyncio.run(main())
    print("""
   Dekho kya hua: LLM aadhe response pe hi ruk gaya (bache hue tokens kabhi
   generate/BILL nahi hue), unspoken sentences flush ho gaye, aur turn_id ne
   stale frames ko naye turn me leak hone se roka.
   Pipecat me yehi: PipelineParams(allow_interruptions=True) —
   StartInterruptionFrame system-frame ki tarah sab stages ko turant
   milta hai. LiveKit me: AgentSession default se interruptions allow
   karta hai (min_interruption_duration se tune hota hai).
   SENIOR TIP: barge-in ke baad conversation-context me sirf UTNA hi
   assistant text daalo jitna user ne actually SUNA — warna LLM sochta
   hai usne poori baat keh di thi. (LiveKit isko khud handle karta hai —
   'truncated message' context me jaata hai.)""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: REAL Pipecat wiring (import-guarded — actual service classes)
# ─────────────────────────────────────────────────────────────────────────────

def section_5_real_pipecat():
    print("\n[5] Real Pipecat wiring")
    try:
        from pipecat.audio.vad.silero import SileroVADAnalyzer
        from pipecat.pipeline.pipeline import Pipeline
        from pipecat.pipeline.runner import PipelineRunner
        from pipecat.pipeline.task import PipelineParams, PipelineTask
        from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
        from pipecat.services.deepgram.stt import DeepgramSTTService
        from pipecat.services.elevenlabs.tts import ElevenLabsTTSService
        from pipecat.services.openai.llm import OpenAILLMService
        from pipecat.transports.local.audio import (LocalAudioTransport,
                                                    LocalAudioTransportParams)
    except ImportError:
        print("""   pipecat not installed → sim sections (1-4) hi kaafi hain concepts ke liye.
   Install (real mic/speaker pipeline):
       pip install "pipecat-ai[silero,deepgram,openai,elevenlabs,local]"
       # macOS: brew install portaudio   (pyaudio ke liye)
   Env: DEEPGRAM_API_KEY, OPENAI_API_KEY, ELEVENLABS_API_KEY
   (Import paths pipecat versions ke beech shift hote hain — docs.pipecat.ai)""")
        return

    missing = [k for k in ("DEEPGRAM_API_KEY", "OPENAI_API_KEY", "ELEVENLABS_API_KEY")
               if not os.getenv(k)]
    if missing:
        print(f"   pipecat installed, par keys missing: {', '.join(missing)}")
        return

    async def main():
        # Sim pipeline se 1:1 mapping — bas classes real hain:
        transport = LocalAudioTransport(LocalAudioTransportParams(   # mic+speaker
            audio_in_enabled=True, audio_out_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),                        # == SimVADStage
        ))
        stt = DeepgramSTTService(api_key=os.getenv("DEEPGRAM_API_KEY"))   # == SimSTTStage
        llm = OpenAILLMService(api_key=os.getenv("OPENAI_API_KEY"),       # == LLMStage
                               model="gpt-4o-mini")
        tts = ElevenLabsTTSService(api_key=os.getenv("ELEVENLABS_API_KEY"),  # == SimTTSStage
                                   voice_id="21m00Tcm4TlvDq8ikWAM")
        # Context aggregator = conversation memory (sim me humne skip kiya)
        context = OpenAILLMContext([{"role": "system",
                                     "content": "You are a concise voice assistant. "
                                                "Two short sentences max."}])
        agg = llm.create_context_aggregator(context)
        pipeline = Pipeline([
            transport.input(),   # mic frames
            stt,                 # audio → TranscriptionFrame
            agg.user(),          # transcript → context me user msg
            llm,                 # context → token frames
            tts,                 # tokens → audio frames
            transport.output(),  # speaker
            agg.assistant(),     # bola hua text → context me (truncation-aware!)
        ])
        task = PipelineTask(pipeline, params=PipelineParams(
            allow_interruptions=True,      # barge-in ON — section 4 wala pura dance
            enable_metrics=True,           # per-stage TTFB metrics (hamare report jaisa)
        ))
        await PipelineRunner().run(task)

    if os.getenv("VOICE_DEMO_RUN") == "1":
        print("   starting real audio pipeline (Ctrl+C to stop)...")
        asyncio.run(main())
    else:
        print("   pipecat + keys ready. Ye infinite mic session hai isliye")
        print("   auto-run nahi kiya → VOICE_DEMO_RUN=1 set karke chalao.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: LiveKit Agents — concept mapping + guarded code
# ─────────────────────────────────────────────────────────────────────────────

def section_6_livekit():
    print("\n[6] LiveKit Agents equivalents")
    rows = [
        ("concept",            "this file (sim)",        "Pipecat",                     "LiveKit Agents"),
        ("pipeline container", "VoicePipeline",          "Pipeline([...])",             "AgentSession(...)"),
        ("stage unit",         "Stage subclass",         "FrameProcessor",              "plugin (stt=, llm=, tts=)"),
        ("data unit",          "Frame dataclasses",      "Frames (TextFrame...)",       "internal plugin streams"),
        ("VAD",                "SimVADStage",            "SileroVADAnalyzer",           "silero.VAD.load()"),
        ("turn detection",     "silence sleep()",        "VADParams(stop_secs=...)",    "vad / semantic turn model"),
        ("barge-in",           "interrupt()+turn_id",    "allow_interruptions=True",    "on by default (tunable)"),
        ("transport",          "stdin/stdout",           "LocalAudio/Daily/WebRTC",     "Room (WebRTC) via worker"),
        ("scaling",            "n/a",                    "self-host containers",        "worker pool + job dispatch"),
    ]
    w = (19, 25, 30, 27)
    for i, r in enumerate(rows):
        print("   " + "".join(c.ljust(w[j]) for j, c in enumerate(r)))
        if i == 0:
            print("   " + "─" * sum(w))
    print("""
   Farq samajhna interview-gold hai:
   - Pipecat = LIBRARY: pipeline khud assemble karte ho, transport khud
     chunte ho, deploy khud karte ho. Max control.
   - LiveKit Agents = FRAMEWORK + INFRA: WebRTC rooms, worker dispatch,
     phone (SIP) integration built-in. AgentSession me components
     inject karo, session lifecycle framework sambhalta hai.""")
    try:
        from livekit import agents
        from livekit.agents import Agent, AgentSession
        from livekit.plugins import deepgram, elevenlabs, silero
        from livekit.plugins import openai as lk_openai
    except ImportError:
        print("""   livekit-agents not installed. Install:
       pip install "livekit-agents[deepgram,openai,elevenlabs,silero]"
   Phir ye hi pipeline LiveKit style me (compare with section 5!):

       async def entrypoint(ctx: agents.JobContext):
           session = AgentSession(
               vad=silero.VAD.load(),                # == SileroVADAnalyzer
               stt=deepgram.STT(model="nova-3"),     # == DeepgramSTTService
               llm=openai.LLM(model="gpt-4o-mini"),  # == OpenAILLMService
               tts=elevenlabs.TTS(),                 # == ElevenLabsTTSService
           )
           await session.start(room=ctx.room,
                               agent=Agent(instructions="Concise voice assistant."))

       agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))

   Run: `python agent.py console` → LOCAL mic/speaker me test (no server!),
        `python agent.py dev`     → LiveKit server se connect (WebRTC).""")
        return

    async def entrypoint(ctx: "agents.JobContext"):
        session = AgentSession(
            vad=silero.VAD.load(),
            stt=deepgram.STT(model="nova-3"),
            llm=lk_openai.LLM(model="gpt-4o-mini"),
            tts=elevenlabs.TTS(),
        )
        await session.start(room=ctx.room,
                            agent=Agent(instructions="You are a concise voice assistant."))

    print("   livekit-agents installed — entrypoint defined OK.")
    print("   Ye worker-process model hai (apna CLI chahiye), isliye yahan se")
    print("   auto-run nahi hota. Is function ko apni file me daal ke:")
    print("       agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))")
    print("   phir `python agent.py console` (local mic) ya `dev` (LiveKit room).")
    _ = entrypoint  # defined-for-reference; worker CLI ke bina call nahi hota


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 7: Production gotchas + interview angle
# ─────────────────────────────────────────────────────────────────────────────

def section_7_gotchas():
    print("\n[7] Production gotchas (jo demo me kabhi nahi dikhte)")
    gotchas = [
        ("AEC missing",
         "agent khud ki awaaz sunkar khud ko interrupt karta hai",
         "WebRTC transport ka echo-cancel ON rakho; headphones se test mat karo"),
        ("Turn ends too early",
         "user soch raha tha, VAD ne silence ko 'done' samajh liya",
         "stop_secs badhao (200→500ms) ya semantic turn-detection model use karo"),
        ("Numbers/units bakwaas",
         "TTS '2/3' ko 'two slash three' bolta hai, '₹1,50,000' bhi",
         "LLM ko spoken-form me likhne bolo, ya TTS se pehle text-normalize karo"),
        ("Markdown bol diya",
         "'asterisk asterisk bold asterisk asterisk' — real production bug",
         "system prompt: 'no markdown, no lists, no emoji'; TTS se pehle strip bhi karo"),
        ("Tool call = dead air",
         "3s ka DB/API call aur line pe pin-drop silence",
         "filler bolo ('ek second, check karta hoon') phir tool chalao — async"),
        ("Context after barge-in",
         "history me poora reply hai jabki user ne aadha suna",
         "assistant message ko SPOKEN text tak truncate karke history me daalo"),
        ("Cost blowup",
         "har turn pe poora audio + poora context — bill 10x",
         "context trim karo, barge-in pe generation cancel karo, chhota model lo"),
        ("Recording consent",
         "call recording 2-party-consent states/GDPR me illegal",
         "turn ke shuru me disclosure bolo aur consent log karo"),
    ]
    for name, symptom, fix in gotchas:
        print(f"\n   ▸ {name}")
        print(f"     symptom : {symptom}")
        print(f"     fix     : {fix}")
    print("""
   ── INTERVIEW ANGLE ─────────────────────────────────────
   Q: Cascaded (STT→LLM→TTS) vs speech-to-speech — kya choose karoge?
   A: Cascaded jab control chahiye — har boundary pe transcript milta hai,
      to logging/PII-redaction/guardrails/deterministic tool-gating laga
      sakte ho, aur har stage independently swap/tune hota hai. Cost bhi
      kam. Speech-to-speech jab latency (~300ms) aur prosody/emotion
      matter kare — par beech me koi seam nahi, debug karna mushkil.

   Q: <800ms budget me sabse bada aur sabse chhupa hua hissa?
   A: Sabse bada LLM TTFT (~300ms). Sabse CHHUPA hua: TTS ko pehla
      complete sentence banne ka wait — pipeline diagram me dikhta hi
      nahi, par 100-300ms kha jaata hai (section 3 ka 'token→first
      chunk' row). Clause-level chunking se ye bachta hai.

   Q: Barge-in implement karne me sabse aasan galti?
   A: Interrupt signal ko usi data queue me daal dena jisme audio frames
      hain — wo apni baari ka intezar karta rehta hai jabki agent bolta
      rehta hai. Interrupt SYSTEM path pe jaana chahiye (queue bypass),
      aur uske baad in-flight frames invalidate hone chahiye (turn_id /
      generation counter) warna purana jawab naye turn me leak karta hai.

   Q: VAD ka 200ms wait kam kyun nahi kar dete?
   A: Silence hi endpoint ka signal hai. Kam karoge to user ke saans
      lete hi agent bol padega (false endpointing) — jo laggy agent se
      bhi zyada irritating hai. Isliye ye latency 'kharch' hai, 'waste'
      nahi. Bachana hai to semantic turn-detection lagao jo shabdon se
      samajhta hai ki baat poori hui ya nahi.""")


# ─────────────────────────────────────────────────────────────────────────────
# CHAT MODE — interactive: stdin → pipeline → stdout (piped input bhi chalta hai)
# ─────────────────────────────────────────────────────────────────────────────

def chat_mode():
    print("\n[chat] Interactive text-sim voice loop (type 'quit' to exit)")
    llm = pick_llm()

    async def main():
        p = VoicePipeline(llm_stream=llm)
        await p.start()
        while True:
            try:
                # input() thread me — asyncio loop block na ho. (Real agent me
                # yaha WebRTC audio track hota; stdin hamara 'mic' hai.)
                line = await asyncio.to_thread(input, "\n   you> ")
            except EOFError:            # piped input khatam → clean exit
                break
            line = line.strip()
            if not line:
                continue
            if line.lower() in {"quit", "exit", "q"}:
                break
            await p.say(line)
        await p.shutdown()
        print("\n   [chat] session closed.")

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n   [chat] interrupted — bye.")


# ─────────────────────────────────────────────────────────────────────────────
# Runner
# ─────────────────────────────────────────────────────────────────────────────

SECTIONS = {
    1: section_1_budget,
    2: section_2_anatomy,
    3: section_3_sim_turns,
    4: section_4_bargein,
    5: section_5_real_pipecat,
    6: section_6_livekit,
    7: section_7_gotchas,
}

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "chat":
        chat_mode()
    elif len(sys.argv) > 1:
        arg = sys.argv[1]
        if not arg.isdigit() or int(arg) not in SECTIONS:
            print(f"unknown section {arg!r}. "
                  f"choose {min(SECTIONS)}-{max(SECTIONS)}, or 'chat'.")
            sys.exit(1)
        SECTIONS[int(arg)]()
    else:
        for n, fn in SECTIONS.items():
            try:
                fn()
            except Exception as e:          # ek section gire to baaki chalein
                print(f"   [section {n} skipped: {e}]")
        print("\nDone. Interactive mode: python 01_voice_agents_practical.py chat")
