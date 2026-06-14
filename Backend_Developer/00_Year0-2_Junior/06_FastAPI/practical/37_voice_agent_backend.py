"""
FastAPI Voice Agent Backend — Production Patterns
=================================================
Covers:
  - Twilio Media Streams webhook + WebSocket bridge
  - OpenAI Realtime API session (speech-to-speech, sub-700ms latency)
  - Hybrid pipeline: Deepgram streaming STT → LLM streaming → Cartesia TTS
  - Barge-in detection and audio queue management
  - Tool / function calling during a live voice call
  - Latency optimisation: speculative LLM calls, connection pre-warming
  - TRAI / DPDP compliance: AI disclosure, DND scrubbing, recording retention
  - Prometheus metrics: turn latency, cost tracking, call disposition counters
  - Post-call quality analysis with LLM-as-judge

Architecture choices (theory doc §Architecture Options):
  A. Pipeline  (STT → LLM → TTS)     — 2-4 s latency, cheap, swappable
  B. Realtime  (speech-to-speech)     — 300-800 ms, expensive, less control
  C. Hybrid    (recommended)          — 700-1200 ms, balanced cost/control

pip install fastapi uvicorn[standard] websockets httpx
pip install twilio                      # TwiML helper
pip install openai                      # OpenAI Realtime WS client
pip install deepgram-sdk                # streaming STT
pip install cartesia                    # streaming TTS
pip install anthropic                   # LLM (Haiku is fastest for voice)
pip install prometheus-client structlog  # observability
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Any

import httpx
import structlog
import websockets
from fastapi import FastAPI, Form, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import ORJSONResponse
from prometheus_client import Counter, Gauge, Histogram, make_asgi_app

# ---------------------------------------------------------------------------
# Logging / structured output
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Environment — never hard-code keys in source
# ---------------------------------------------------------------------------
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "sk-REPLACE_ME")
DEEPGRAM_API_KEY: str = os.getenv("DEEPGRAM_API_KEY", "dg-REPLACE_ME")
CARTESIA_API_KEY: str = os.getenv("CARTESIA_API_KEY", "ca-REPLACE_ME")
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "sk-ant-REPLACE_ME")
TRAI_DND_API: str = "https://api.trai.gov.in/dnd/check"  # mandatory for outbound

OPENAI_REALTIME_URL = (
    "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17"
)


# ==========================================================================
# 1. FASTAPI APP SETUP
# ==========================================================================

app = FastAPI(
    title="Voice Agent Backend",
    description="Twilio + OpenAI Realtime + Deepgram + Cartesia — production voice AI",
    version="1.0.0",
    default_response_class=ORJSONResponse,
)


# ==========================================================================
# 2. PROMETHEUS METRICS (theory doc §Q8 — production monitoring)
# ==========================================================================

# pip install prometheus-client

CALL_DURATION = Histogram(
    "voice_call_duration_seconds",
    "Total duration of a voice call",
    buckets=(30, 60, 120, 300, 600, 1200),
)

TURN_LATENCY = Histogram(
    "voice_turn_latency_seconds",
    "Time from user utterance end to AI first audio byte (TTFR)",
    buckets=(0.2, 0.4, 0.7, 1.0, 1.5, 2.5, 5.0),
)

ASR_WER = Histogram(
    "voice_asr_word_error_rate",
    "Word Error Rate from STT provider (sampled via post-call analysis)",
    buckets=(0.0, 0.05, 0.1, 0.2, 0.4, 0.6, 1.0),
)

CALLS_TOTAL = Counter(
    "voice_calls_total",
    "Total inbound calls by disposition",
    labelnames=["disposition"],   # completed | abandoned | transferred
)

HUMAN_TRANSFERS = Counter(
    "voice_transfers_to_human_total",
    "Escalations to a human agent",
    labelnames=["reason"],
)

TTS_COST_USD = Counter("voice_tts_cost_usd_total", "Cumulative TTS spend in USD")
LLM_COST_USD = Counter("voice_llm_cost_usd_total", "Cumulative LLM spend in USD")

ACTIVE_CALLS = Gauge("voice_active_calls", "Calls currently in progress")

# Mount /metrics for Prometheus scraping
metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)


# ==========================================================================
# 3. CALL OUTCOME DATACLASS (business KPIs)
# ==========================================================================

@dataclass
class CallOutcome:
    """Collected at the end of every call and stored in the analytics table."""
    call_sid: str
    duration_sec: int
    user_satisfied: bool = False
    issue_resolved: bool = False
    transferred: bool = False
    transfer_reason: str = ""
    cost_usd: float = 0.0
    sentiment_score: float = 0.0   # -1 (angry) → +1 (happy)
    topics_discussed: list[str] = field(default_factory=list)


# ==========================================================================
# 4. COMPLIANCE HELPERS (theory doc §Q7 — TRAI / DPDP)
# ==========================================================================

def hash_phone(phone: str) -> str:
    """One-way hash caller phone number before storing (DPDP data minimisation)."""
    return hashlib.sha256(phone.encode()).hexdigest()


async def can_call_number(phone: str) -> bool:
    """
    Check TRAI DND registry before placing an outbound call.
    Outbound calls to DND-registered numbers are illegal under TRAI regulations.
    """
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(TRAI_DND_API, params={"phone": phone})
            return resp.json().get("status") == "active_for_calls"
    except Exception:
        # Fail-safe: block the call if DND check is unavailable
        logger.warning("dnd_check_failed", phone_hash=hash_phone(phone))
        return False


def within_calling_hours() -> bool:
    """
    TRAI mandate: outbound calls only between 09:00 and 21:00 IST.
    In production, use a proper IST-aware datetime library (pytz / zoneinfo).
    """
    import datetime
    # UTC+5:30 offset
    ist_offset = datetime.timezone(datetime.timedelta(hours=5, minutes=30))
    ist_now = datetime.datetime.now(ist_offset)
    return 9 <= ist_now.hour < 21


# ==========================================================================
# 5. AUDIO QUALITY MONITOR (theory doc §Q8)
# ==========================================================================

def calc_rms(audio_chunk: bytes) -> float:
    """
    Root Mean Square of a raw PCM buffer — used as a simple audio quality proxy.
    Expects 16-bit little-endian samples; for mulaw pass after decoding.
    """
    if not audio_chunk:
        return 0.0
    import struct
    n = len(audio_chunk) // 2
    if n == 0:
        return 0.0
    samples = struct.unpack(f"<{n}h", audio_chunk[: n * 2])
    mean_sq = sum(s * s for s in samples) / n
    return mean_sq ** 0.5


def monitor_audio_quality(audio_chunk: bytes) -> None:
    """Raise structured log warnings on low-signal or clipping audio."""
    rms = calc_rms(audio_chunk)
    if rms < 100:
        logger.warning("audio_quality_low", rms=rms)
    elif rms > 10_000:
        logger.warning("audio_clipping", rms=rms)


# ==========================================================================
# 6. CONNECTION PRE-WARM POOL (theory doc §Q4 Trick 3)
# ==========================================================================

class WebSocketPool:
    """
    Keep a pool of pre-established WebSocket connections to a remote server
    so the first audio byte is forwarded without cold-start handshake overhead.
    Reduces per-call connection time by ~150-300ms.
    """

    def __init__(self, url: str, headers: dict[str, str], size: int = 5):
        self._url = url
        self._headers = headers
        self._pool: asyncio.Queue = asyncio.Queue(maxsize=size)
        self._size = size

    async def warm_up(self) -> None:
        """Call once at application startup."""
        tasks = [self._open_one() for _ in range(self._size)]
        await asyncio.gather(*tasks, return_exceptions=True)
        logger.info("ws_pool_warmed", size=self._size, url=self._url)

    async def _open_one(self) -> None:
        try:
            ws = await websockets.connect(self._url, extra_headers=self._headers)
            await self._pool.put(ws)
        except Exception as exc:
            logger.warning("ws_pool_open_failed", error=str(exc))

    async def get(self) -> Any:
        """Return a ready connection; replenish pool asynchronously."""
        try:
            ws = self._pool.get_nowait()
        except asyncio.QueueEmpty:
            # All connections busy — open a fresh one (cold path)
            logger.warning("ws_pool_empty_cold_open")
            ws = await websockets.connect(self._url, extra_headers=self._headers)
        # Refill pool in background
        asyncio.create_task(self._open_one())
        return ws

    async def release(self, ws: Any) -> None:
        """Return a healthy connection back to the pool."""
        try:
            self._pool.put_nowait(ws)
        except asyncio.QueueFull:
            await ws.close()


# Global pool — initialised at startup
openai_ws_pool: WebSocketPool | None = None


@app.on_event("startup")
async def startup_event() -> None:
    global openai_ws_pool
    openai_ws_pool = WebSocketPool(
        url=OPENAI_REALTIME_URL,
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "OpenAI-Beta": "realtime=v1",
        },
        size=5,
    )
    # Pre-warm; errors are tolerated (keys may be absent in dev)
    try:
        await openai_ws_pool.warm_up()
    except Exception as exc:
        logger.warning("pool_warm_up_skipped", error=str(exc))
    logger.info("voice_agent_backend_started")


# ==========================================================================
# 7. TWILIO WEBHOOK — INCOMING CALL (theory doc §Q7 + §Q1)
# ==========================================================================

@app.post("/twilio/incoming")
async def twilio_incoming(
    From: str = Form(...),
    To: str = Form(...),
):
    """
    Twilio hits this URL when a call arrives.
    Returns TwiML that:
      1. Discloses AI nature (TRAI / DPDP mandatory).
      2. Lets caller consent or opt out.
      3. Starts a bidirectional Media Stream to our WebSocket.

    Twilio audio format: mulaw 8 kHz, 20 ms chunks (160 bytes each).
    """
    # pip install twilio
    from twilio.twiml.voice_response import Gather, Start, VoiceResponse

    response = VoiceResponse()

    # --- Mandatory AI disclosure (TRAI guidance + DPDP 2023) ---------------
    response.say(
        "This call may be handled by an AI assistant. "
        "Press 1 to continue, or press 0 to speak with a human agent.",
        voice="Polly.Aditi",   # Indian English voice via Amazon Polly
        language="en-IN",
    )
    response.gather(
        num_digits=1,
        action="/twilio/route",
        method="POST",
        timeout=5,
    )

    logger.info("incoming_call", from_number=hash_phone(From), to=To)
    return Response(content=str(response), media_type="application/xml")


@app.post("/twilio/route")
async def twilio_route(Digits: str = Form(default="1")):
    """Route caller based on consent choice (1 = AI, 0 = human)."""
    from twilio.twiml.voice_response import Dial, Start, VoiceResponse

    response = VoiceResponse()
    if Digits == "0":
        # Transfer to human queue
        HUMAN_TRANSFERS.labels(reason="caller_preference").inc()
        response.say("Connecting you to a human agent. Please hold.", voice="Polly.Aditi")
        response.dial("+911234567890")  # replace with real queue number
        return Response(content=str(response), media_type="application/xml")

    # Start bidirectional audio stream to our WebSocket handler
    start = Start()
    start.stream(url="wss://api.acme.com/twilio/realtime")
    response.append(start)

    # Keep the call leg alive while we handle audio over the WS
    response.pause(length=600)  # 10-minute maximum; extend if needed

    return Response(content=str(response), media_type="application/xml")


# ==========================================================================
# 8. OPENAI REALTIME SESSION (theory doc §Q2)
# ==========================================================================

class RealtimeSession:
    """
    Bridges a Twilio Media Stream WebSocket with the OpenAI Realtime API.

    Data flow (Architecture B — sub-700ms TTFR):
      Twilio WS → mulaw audio bytes → OpenAI Realtime WS
      OpenAI Realtime WS → mulaw audio bytes → Twilio WS

    The Realtime API handles STT, LLM reasoning, and TTS internally.
    Tool calls are intercepted and dispatched to local async handlers.
    """

    SYSTEM_PROMPT = (
        "You are a friendly customer-service agent for Acme India. "
        "Keep every response under 40 words. Speak naturally in Indian English. "
        "If you cannot resolve an issue, politely offer to transfer to a human agent."
    )

    def __init__(self, twilio_ws: WebSocket) -> None:
        self.twilio_ws = twilio_ws
        self.openai_ws: Any = None
        self.stream_sid: str | None = None
        self.call_sid: str | None = None
        self._start_time: float = 0.0
        self._turn_start: float = 0.0

    async def run(self) -> None:
        """Entry point — connect to OpenAI and bridge audio bidirectionally."""
        assert openai_ws_pool is not None, "Pool not initialised"
        self.openai_ws = await openai_ws_pool.get()
        self._start_time = time.monotonic()
        ACTIVE_CALLS.inc()

        try:
            await self._configure_session()
            await asyncio.gather(
                self._twilio_to_openai(),
                self._openai_to_twilio(),
            )
        except asyncio.CancelledError:
            pass
        finally:
            ACTIVE_CALLS.dec()
            duration = int(time.monotonic() - self._start_time)
            CALL_DURATION.observe(duration)
            await openai_ws_pool.release(self.openai_ws)
            logger.info("call_ended", call_sid=self.call_sid, duration_sec=duration)

    async def _configure_session(self) -> None:
        """Send session.update to configure voice, VAD, tools, etc."""
        payload = {
            "type": "session.update",
            "session": {
                "modalities": ["audio", "text"],
                "instructions": self.SYSTEM_PROMPT,
                "voice": "shimmer",                  # or alloy, echo, fable, onyx, nova
                "input_audio_format": "g711_ulaw",   # matches Twilio mulaw
                "output_audio_format": "g711_ulaw",
                "input_audio_transcription": {"model": "whisper-1"},
                "turn_detection": {
                    "type": "server_vad",            # OpenAI handles VAD
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500,      # 500ms silence = end of turn
                },
                "tools": [
                    {
                        "type": "function",
                        "name": "lookup_order",
                        "description": "Look up an order status by order number.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "order_id": {"type": "string", "description": "The order number"},
                            },
                            "required": ["order_id"],
                        },
                    },
                    {
                        "type": "function",
                        "name": "schedule_callback",
                        "description": "Book a callback with a human agent.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "time": {"type": "string", "description": "ISO-8601 datetime"},
                                "phone": {"type": "string"},
                            },
                            "required": ["time", "phone"],
                        },
                    },
                    {
                        "type": "function",
                        "name": "transfer_to_human",
                        "description": "Escalate the call to a live human agent.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "reason": {"type": "string"},
                            },
                            "required": ["reason"],
                        },
                    },
                ],
                "tool_choice": "auto",
                "temperature": 0.8,
            },
        }
        await self.openai_ws.send(json.dumps(payload))

    async def _twilio_to_openai(self) -> None:
        """Relay incoming Twilio audio to the OpenAI input buffer."""
        async for raw_msg in self.twilio_ws.iter_text():
            data: dict = json.loads(raw_msg)
            event = data.get("event")

            if event == "start":
                self.stream_sid = data["start"]["streamSid"]
                self.call_sid = data["start"]["callSid"]
                self._turn_start = time.monotonic()
                logger.info("call_started", call_sid=self.call_sid)

            elif event == "media":
                # Forward raw audio — OpenAI expects base64-encoded mulaw
                audio_b64: str = data["media"]["payload"]
                await self.openai_ws.send(json.dumps({
                    "type": "input_audio_buffer.append",
                    "audio": audio_b64,
                }))

            elif event == "stop":
                logger.info("twilio_stop", call_sid=self.call_sid)
                break

    async def _openai_to_twilio(self) -> None:
        """Relay OpenAI audio responses back to Twilio; handle tool calls."""
        async for raw_msg in self.openai_ws:
            event: dict = json.loads(raw_msg)
            etype = event.get("type", "")

            # --- AI audio chunk: forward immediately for low latency ----------
            if etype == "response.audio.delta":
                # Record TTFR on first audio byte of the turn
                if self._turn_start:
                    ttfr = time.monotonic() - self._turn_start
                    TURN_LATENCY.observe(ttfr)
                    logger.info("ttfr_seconds", ttfr=round(ttfr, 3))
                    self._turn_start = 0.0   # reset until next user utterance

                await self.twilio_ws.send_text(json.dumps({
                    "event": "media",
                    "streamSid": self.stream_sid,
                    "media": {"payload": event["delta"]},
                }))

            # --- Tool call completed: dispatch + inject result ---------------
            elif etype == "response.function_call_arguments.done":
                tool_name: str = event.get("name", "")
                args: dict = json.loads(event.get("arguments", "{}"))
                call_id: str = event.get("call_id", "")
                result = await self._execute_tool(tool_name, args)
                await self.openai_ws.send(json.dumps({
                    "type": "conversation.item.create",
                    "item": {
                        "type": "function_call_output",
                        "call_id": call_id,
                        "output": json.dumps(result),
                    },
                }))
                await self.openai_ws.send(json.dumps({"type": "response.create"}))

            # --- User utterance detected: reset TTFR clock -------------------
            elif etype == "input_audio_buffer.speech_started":
                self._turn_start = time.monotonic()

            elif etype == "error":
                logger.error("openai_realtime_error", detail=event)

    async def _execute_tool(self, tool_name: str, args: dict) -> dict:
        """
        Dispatch tool calls originating from the Realtime API.
        Play a "thinking" cue before any slow operation (theory doc §Q6).
        """
        logger.info("tool_call", tool=tool_name, args=args)

        if tool_name == "lookup_order":
            # Simulated CRM lookup
            await asyncio.sleep(0.5)   # simulate I/O
            return {
                "order_id": args.get("order_id"),
                "status": "shipped",
                "estimated_delivery": "2026-06-15",
            }

        elif tool_name == "schedule_callback":
            await asyncio.sleep(0.3)
            return {"scheduled": True, "confirmation": "CB-99281"}

        elif tool_name == "transfer_to_human":
            reason = args.get("reason", "unspecified")
            HUMAN_TRANSFERS.labels(reason=reason).inc()
            # Signal Twilio to bridge call to human queue
            return {"transfer_initiated": True, "queue": "tier-1-support"}

        return {"error": f"Unknown tool: {tool_name}"}


@app.websocket("/twilio/realtime")
async def twilio_realtime_ws(websocket: WebSocket) -> None:
    """
    Twilio sends bidirectional audio here via Media Streams.
    Architecture B: OpenAI Realtime API (speech-to-speech, ~500ms TTFR).
    """
    await websocket.accept()
    session = RealtimeSession(websocket)
    try:
        await session.run()
    except WebSocketDisconnect:
        logger.info("twilio_ws_disconnected")
    except Exception as exc:
        logger.exception("realtime_session_error", error=str(exc))


# ==========================================================================
# 9. BARGE-IN HANDLER (theory doc §Q5)
# ==========================================================================

class BargeinController:
    """
    Tracks whether the AI is currently speaking and implements barge-in:
    user speaks mid-AI-response → cancel TTS task + clear Twilio audio buffer.

    Used by the Hybrid pipeline (§10) where we control TTS streaming ourselves.
    The OpenAI Realtime API handles barge-in automatically via server_vad.
    """

    def __init__(self, twilio_ws: WebSocket, stream_sid: str) -> None:
        self.twilio_ws = twilio_ws
        self.stream_sid = stream_sid
        self.is_ai_speaking: bool = False
        self.current_tts_task: asyncio.Task | None = None
        self.tts_audio_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._interrupted_text: str = ""   # partial AI text for conversation context

    async def on_user_speaking(self) -> None:
        """
        Called by the STT layer when it detects voice activity during AI playback.
        Implements barge-in by cancelling TTS and clearing Twilio's buffer.
        """
        if not self.is_ai_speaking:
            return

        logger.info("bargein_detected")

        # 1. Cancel the streaming TTS coroutine
        if self.current_tts_task and not self.current_tts_task.done():
            self.current_tts_task.cancel()

        # 2. Instruct Twilio to discard any already-buffered audio
        await self.twilio_ws.send_text(json.dumps({
            "event": "clear",
            "streamSid": self.stream_sid,
        }))

        # 3. Drain our local queue
        while not self.tts_audio_queue.empty():
            try:
                self.tts_audio_queue.get_nowait()
            except asyncio.QueueEmpty:
                break

        self.is_ai_speaking = False
        logger.info("bargein_complete")

    async def send_audio(self, audio_chunk: bytes) -> None:
        """Enqueue a TTS audio chunk for delivery to Twilio."""
        await self.tts_audio_queue.put(audio_chunk)

    async def flush_audio(self) -> None:
        """Drain the queue to Twilio while is_ai_speaking == True."""
        self.is_ai_speaking = True
        try:
            while True:
                chunk = await asyncio.wait_for(self.tts_audio_queue.get(), timeout=5.0)
                payload = base64.b64encode(chunk).decode()
                await self.twilio_ws.send_text(json.dumps({
                    "event": "media",
                    "streamSid": self.stream_sid,
                    "media": {"payload": payload},
                }))
        except asyncio.TimeoutError:
            pass
        finally:
            self.is_ai_speaking = False


# ==========================================================================
# 10. HYBRID PIPELINE AGENT (theory doc §Q3 — Deepgram + LLM + Cartesia)
# ==========================================================================

class HybridVoiceAgent:
    """
    Architecture C — recommended for cost-sensitive production.

    Pipeline:
      Twilio mulaw → Deepgram streaming STT (50 ms partials)
                          ↓  (utterance complete)
                     Claude Haiku streaming  (~80ms TTFT)
                          ↓  (clause-boundary buffering)
                     Cartesia streaming TTS  (starts before LLM finishes)
                          ↓
                     mulaw audio → Twilio

    Effective TTFR: 700-1200 ms.

    External libs required:
      pip install deepgram-sdk cartesia anthropic
    """

    SYSTEM_PROMPT = (
        "You are a phone customer-service agent. "
        "Reply in under 40 words. Speak naturally. Use Indian English. "
        "Never mention you are an AI unless directly asked."
    )

    # Cost constants (rough; update from provider dashboards)
    DEEPGRAM_COST_PER_MIN = 0.0059
    LLM_COST_PER_1K_TOKENS = 0.00025  # Claude Haiku
    CARTESIA_COST_PER_1K_CHARS = 0.00005

    def __init__(self, twilio_ws: WebSocket) -> None:
        self.twilio_ws = twilio_ws
        self.stream_sid: str | None = None
        self.call_sid: str | None = None
        self.history: list[dict] = []
        self.current_transcript: str = ""
        self._speculative_task: asyncio.Task | None = None
        self._speculative_text: str = ""
        self._call_cost_usd: float = 0.0
        self._start_time: float = time.monotonic()
        self._turn_start: float = 0.0

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """
        Start the Deepgram streaming STT connection, then pump Twilio audio into it.
        """
        # pip install deepgram-sdk
        from deepgram import DeepgramClient, LiveOptions, LiveTranscriptionEvents

        dg = DeepgramClient(DEEPGRAM_API_KEY)
        dg_conn = dg.listen.asynclive.v("1")

        dg_conn.on(LiveTranscriptionEvents.Transcript, self._on_transcript)
        dg_conn.on(LiveTranscriptionEvents.UtteranceEnd, self._on_utterance_end)
        dg_conn.on(LiveTranscriptionEvents.SpeechStarted, self._on_speech_started)

        options = LiveOptions(
            model="nova-2",
            language="en-IN",          # Indian English — better accent handling
            encoding="mulaw",
            sample_rate=8000,
            channels=1,
            interim_results=True,      # fire partials for speculative LLM calls
            endpointing=300,           # 300ms silence = turn end
            utterance_end_ms="1000",
        )
        await dg_conn.start(options)

        # Bridge Twilio audio → Deepgram
        async for raw_msg in self.twilio_ws.iter_text():
            data: dict = json.loads(raw_msg)
            event = data.get("event")

            if event == "start":
                self.stream_sid = data["start"]["streamSid"]
                self.call_sid = data["start"]["callSid"]
                logger.info("hybrid_call_started", call_sid=self.call_sid)

            elif event == "media":
                audio = base64.b64decode(data["media"]["payload"])
                monitor_audio_quality(audio)
                await dg_conn.send(audio)

            elif event == "stop":
                break

        await dg_conn.finish()
        await self._finalize()

    # ------------------------------------------------------------------
    # Deepgram event handlers
    # ------------------------------------------------------------------

    async def _on_speech_started(self, _conn: Any, **_kwargs: Any) -> None:
        """Deepgram fires this as soon as voice energy is detected."""
        self._turn_start = time.monotonic()

    async def _on_transcript(self, _conn: Any, result: Any, **_kwargs: Any) -> None:
        """
        Partial transcript received — run speculative LLM call on likely-complete
        utterances to shave ~200ms off TTFR (theory doc §Q4 Trick 1).
        """
        transcript: str = result.channel.alternatives[0].transcript
        is_final: bool = result.is_final

        if is_final:
            self.current_transcript += " " + transcript

        # Speculative: if partial ends with sentence-terminating punctuation
        # and we haven't already started a speculative call, kick one off.
        if (
            not is_final
            and len(transcript) > 20
            and transcript.rstrip().endswith(("?", ".", "!"))
            and self._speculative_task is None
        ):
            self._speculative_text = transcript
            self._speculative_task = asyncio.create_task(
                self._llm_call(transcript, speculative=True)
            )

    async def _on_utterance_end(self, _conn: Any, **_kwargs: Any) -> None:
        """Deepgram declares the user has finished speaking — trigger LLM pipeline."""
        user_text = self.current_transcript.strip()
        self.current_transcript = ""

        if not user_text:
            return

        logger.info("utterance_complete", text=user_text[:80])

        # Reuse speculative result if the text matches
        if (
            self._speculative_task is not None
            and self._speculative_text == user_text
            and self._speculative_task.done()
        ):
            logger.info("speculative_hit")
            llm_text = self._speculative_task.result()
        else:
            # Cancel stale speculative task and do a fresh call
            if self._speculative_task and not self._speculative_task.done():
                self._speculative_task.cancel()
            llm_text = await self._llm_call(user_text)

        self._speculative_task = None
        self._speculative_text = ""

        if llm_text:
            await self._tts_and_send(llm_text)

    # ------------------------------------------------------------------
    # LLM streaming (theory doc §Q3 step 3)
    # ------------------------------------------------------------------

    async def _llm_call(self, user_text: str, speculative: bool = False) -> str:
        """
        Stream LLM response and pipeline each clause into TTS immediately.
        Returns the full assembled response string.
        """
        import anthropic  # pip install anthropic

        self.history.append({"role": "user", "content": user_text})
        client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

        full_response = ""
        buffer = ""

        try:
            async with client.messages.stream(
                model="claude-haiku-4-5",          # fastest Claude for voice
                system=self.SYSTEM_PROMPT,
                messages=self.history,
                max_tokens=200,
            ) as stream:
                async for token in stream.text_stream:
                    buffer += token
                    full_response += token

                    # Flush to TTS at natural speech boundaries
                    # (theory doc §Q4 Trick 2: stream TTS, don't buffer)
                    if not speculative and any(
                        p in buffer for p in [".", "!", "?", ",", ";", "—"]
                    ):
                        await self._tts_and_send(buffer)
                        buffer = ""

                if buffer and not speculative:
                    await self._tts_and_send(buffer)

            self.history.append({"role": "assistant", "content": full_response})
            # Rough cost estimation
            token_est = len(full_response) // 4
            cost = (token_est / 1000) * self.LLM_COST_PER_1K_TOKENS
            self._call_cost_usd += cost
            LLM_COST_USD.inc(cost)

        except Exception as exc:
            logger.exception("llm_error", error=str(exc))
            full_response = "I'm sorry, I ran into a technical issue. Can you repeat that?"

        # Record TTFR on first real LLM call
        if self._turn_start and not speculative:
            ttfr = time.monotonic() - self._turn_start
            TURN_LATENCY.observe(ttfr)
            logger.info("hybrid_ttfr", ttfr=round(ttfr, 3))
            self._turn_start = 0.0

        return full_response

    # ------------------------------------------------------------------
    # TTS streaming (theory doc §Q3 step 4)
    # ------------------------------------------------------------------

    async def _tts_and_send(self, text: str) -> None:
        """
        Stream TTS audio from Cartesia to Twilio.
        Audio arrives as raw PCM mulaw — Twilio plays it immediately.
        """
        if not text.strip():
            return

        try:
            from cartesia import AsyncCartesia  # pip install cartesia

            cartesia = AsyncCartesia(api_key=CARTESIA_API_KEY)
            char_count = len(text)

            async for audio_chunk in cartesia.tts.bytes(
                model_id="sonic-english",
                transcript=text,
                voice={"mode": "id", "id": "INDIAN_FEMALE_VOICE_ID"},  # replace with real ID
                output_format={
                    "container": "raw",
                    "encoding": "pcm_mulaw",
                    "sample_rate": 8000,
                },
            ):
                payload = base64.b64encode(audio_chunk).decode()
                await self.twilio_ws.send_text(json.dumps({
                    "event": "media",
                    "streamSid": self.stream_sid,
                    "media": {"payload": payload},
                }))

            cost = (char_count / 1000) * self.CARTESIA_COST_PER_1K_CHARS
            self._call_cost_usd += cost
            TTS_COST_USD.inc(cost)

        except Exception as exc:
            logger.exception("tts_error", error=str(exc))

    # ------------------------------------------------------------------
    # Tool use (theory doc §Q6)
    # ------------------------------------------------------------------

    async def handle_tool_call(
        self, tool_name: str, args: dict, tool_call_id: str
    ) -> None:
        """
        Handle LLM tool calls during a call.
        Speak a "thinking" cue immediately — never leave dead air.
        """
        await self._tts_and_send("Let me look that up for you...")

        result: dict
        if tool_name == "lookup_order":
            # Simulate CRM lookup (replace with real async DB call)
            await asyncio.sleep(0.5)
            result = {
                "order_id": args.get("order_id"),
                "status": "in transit",
                "eta": "2026-06-16",
            }
        elif tool_name == "schedule_callback":
            await asyncio.sleep(0.2)
            result = {"scheduled": True, "ref": "CB-77341"}
        else:
            result = {"error": f"Unknown tool: {tool_name}"}

        self.history.append({
            "role": "tool",
            "tool_use_id": tool_call_id,
            "content": json.dumps(result),
        })

        # Resume LLM with tool result
        await self._llm_call("")   # empty user_text signals continuation turn

    # ------------------------------------------------------------------
    # Post-call cleanup
    # ------------------------------------------------------------------

    async def _finalize(self) -> None:
        duration = int(time.monotonic() - self._start_time)
        CALL_DURATION.observe(duration)
        CALLS_TOTAL.labels(disposition="completed").inc()
        logger.info(
            "hybrid_call_complete",
            call_sid=self.call_sid,
            duration_sec=duration,
            cost_usd=round(self._call_cost_usd, 4),
        )


@app.websocket("/twilio/stream")
async def twilio_stream_ws(websocket: WebSocket) -> None:
    """
    Twilio Media Stream endpoint for the Hybrid pipeline.
    Architecture C: Deepgram STT → Claude Haiku → Cartesia TTS (~900ms TTFR).
    """
    await websocket.accept()
    ACTIVE_CALLS.inc()
    agent = HybridVoiceAgent(websocket)
    try:
        await agent.start()
    except WebSocketDisconnect:
        logger.info("hybrid_ws_disconnected")
    except Exception as exc:
        logger.exception("hybrid_agent_error", error=str(exc))
    finally:
        ACTIVE_CALLS.dec()


# ==========================================================================
# 11. COMPLIANCE ENDPOINTS (theory doc §Q7)
# ==========================================================================

@app.post("/twilio/recording")
async def recording_callback(
    CallSid: str = Form(...),
    RecordingUrl: str = Form(...),
    RecordingDuration: int = Form(...),
) -> dict:
    """
    Twilio POSTs here after a call recording is ready.
    Log with 90-day retention per DPDP guidelines.
    In production, persist to DB and schedule deletion via a cron job.
    """
    logger.info(
        "recording_received",
        call_sid=CallSid,
        duration_sec=RecordingDuration,
        # Never log actual URL in plaintext — it grants access to audio
        url_hash=hashlib.sha256(RecordingUrl.encode()).hexdigest()[:16],
    )
    # Pseudo DB insert — replace with real async database call
    # await db.execute(
    #     "INSERT INTO call_recordings (call_sid, url, duration_sec, expires_at) "
    #     "VALUES (:sid, :url, :dur, NOW() + INTERVAL '90 days')",
    #     {"sid": CallSid, "url": RecordingUrl, "dur": RecordingDuration},
    # )
    return {"status": "recorded", "expires_after_days": 90}


@app.post("/outbound/call")
async def initiate_outbound_call(phone: str, message: str) -> dict:
    """
    Initiate an outbound call — with mandatory TRAI compliance checks.
    1. DND scrubbing
    2. Calling-hours gate (09:00-21:00 IST)
    """
    if not within_calling_hours():
        return {"error": "Outside permitted calling hours (09:00-21:00 IST)"}

    if not await can_call_number(phone):
        logger.info("dnd_blocked", phone_hash=hash_phone(phone))
        return {"error": "Number is on DND registry — call blocked by TRAI mandate"}

    # Place call via Twilio REST API (pip install twilio)
    # twilio_client.calls.create(
    #     to=phone,
    #     from_=TWILIO_NUMBER,
    #     url="https://api.acme.com/twilio/incoming",
    # )
    logger.info("outbound_call_initiated", phone_hash=hash_phone(phone))
    return {"status": "queued"}


# ==========================================================================
# 12. POST-CALL QUALITY ANALYSIS — LLM-as-judge (theory doc §Q8)
# ==========================================================================

async def analyze_completed_call(call_sid: str, transcript: str) -> CallOutcome:
    """
    Run LLM-as-judge over the full call transcript after the call ends.
    Returns structured quality metrics — store in analytics DB.

    In production, schedule this as a background task (Celery, ARQ, etc.)
    to avoid blocking the webhook response.
    """
    import anthropic  # pip install anthropic

    client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)
    analysis_prompt = (
        "You are a quality-assurance analyst for a customer-service voice agent. "
        "Analyse the following call transcript and respond with a single JSON object "
        "with these fields:\n"
        '  "satisfied": bool,\n'
        '  "resolved": bool,\n'
        '  "transferred": bool,\n'
        '  "transfer_reason": string or null,\n'
        '  "sentiment": float between -1 (angry) and 1 (happy),\n'
        '  "topics": list of strings,\n'
        '  "escalation_needed": bool\n\n'
        f"TRANSCRIPT:\n{transcript}"
    )

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            system="Respond ONLY with valid JSON. No markdown.",
            messages=[{"role": "user", "content": analysis_prompt}],
            max_tokens=300,
        )
        outcome_raw: dict = json.loads(response.content[0].text)
        outcome = CallOutcome(
            call_sid=call_sid,
            duration_sec=0,  # filled by caller
            user_satisfied=outcome_raw.get("satisfied", False),
            issue_resolved=outcome_raw.get("resolved", False),
            transferred=outcome_raw.get("transferred", False),
            transfer_reason=outcome_raw.get("transfer_reason") or "",
            sentiment_score=float(outcome_raw.get("sentiment", 0.0)),
            topics_discussed=outcome_raw.get("topics", []),
        )

        # Alert supervisor on strongly negative calls
        if outcome.sentiment_score < -0.5:
            logger.warning(
                "angry_customer_alert",
                call_sid=call_sid,
                sentiment=outcome.sentiment_score,
            )

        ASR_WER.observe(0.0)   # placeholder — replace with real WER measurement
        CALLS_TOTAL.labels(disposition="completed").inc()
        return outcome

    except Exception as exc:
        logger.exception("post_call_analysis_error", call_sid=call_sid, error=str(exc))
        return CallOutcome(call_sid=call_sid, duration_sec=0)


# ==========================================================================
# 13. HEALTH CHECK
# ==========================================================================

@app.get("/health")
async def health() -> dict:
    """Minimal liveness probe — Kubernetes / load-balancer friendly."""
    return {"status": "ok", "service": "voice-agent-backend"}


# ==========================================================================
# 14. REFERENCE DATA: COST MODEL (theory doc §Cost Breakdown)
# ==========================================================================

COST_PER_CALL: dict[str, dict[str, float]] = {
    "5_min": {
        "twilio_media_stream_usd": 0.05,
        "deepgram_stt_usd": 0.04,
        "llm_claude_sonnet_usd": 0.10,
        "cartesia_tts_usd": 0.08,
        "pipeline_total_usd": 0.27,
        "openai_realtime_alternative_usd": 0.30,
        "self_hosted_usd": 0.08,
    },
    "10_min": {
        "twilio_media_stream_usd": 0.10,
        "deepgram_stt_usd": 0.08,
        "llm_claude_sonnet_usd": 0.20,
        "cartesia_tts_usd": 0.16,
        "pipeline_total_usd": 0.54,
        "openai_realtime_alternative_usd": 0.60,
        "self_hosted_usd": 0.16,
    },
}


@app.get("/reference/cost-model")
async def cost_model() -> dict:
    """Return cost-per-call breakdown — useful for product/finance teams."""
    return COST_PER_CALL


# ==========================================================================
# 15. PRODUCTION DEPLOYMENT REFERENCE (reference strings, not executed)
# ==========================================================================

_DEPLOY_NOTES = """
# Recommended deployment (AWS Mumbai ap-south-1 — 20-50ms RTT to Indian users)
# versus us-east-1 which adds 200-300ms.

# Uvicorn with uvloop + httptools for ~2x throughput over default asyncio:
#   pip install uvloop httptools
#   uvicorn 37_voice_agent_backend:app \\
#       --host 0.0.0.0 --port 8000 \\
#       --loop uvloop --http httptools \\
#       --workers 4

# Gunicorn + UvicornWorker for process-level isolation:
#   gunicorn 37_voice_agent_backend:app \\
#       -w 4 -k uvicorn.workers.UvicornWorker \\
#       --bind 0.0.0.0:8000 --timeout 30

# Twilio TwiML app must point to:
#   POST https://<your-domain>/twilio/incoming
# Webhook for recordings:
#   POST https://<your-domain>/twilio/recording

# Environment variables required:
#   OPENAI_API_KEY, DEEPGRAM_API_KEY, CARTESIA_API_KEY, ANTHROPIC_API_KEY
"""
