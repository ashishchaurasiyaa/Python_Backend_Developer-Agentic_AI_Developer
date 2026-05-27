# FastAPI — Voice Agent Backend (Twilio + OpenAI Realtime + ElevenLabs)
**Phase 2 FastAPI | Senior Backend + Agentic AI**

## Quick Concepts
- **Voice agent** = AI that conducts phone/web voice conversations (call center automation, sales bots, support)
- **STT** = Speech-to-Text (Whisper, Deepgram, AssemblyAI)
- **TTS** = Text-to-Speech (ElevenLabs, OpenAI TTS, Cartesia, PlayHT)
- **Realtime API** = OpenAI's speech-to-speech (skip STT+LLM+TTS pipeline)
- **VAD** = Voice Activity Detection (detect when user stops speaking)
- **Twilio Media Streams** = bidirectional audio over WebSocket for phone calls
- **End-to-end latency** = user finishes talking → AI starts responding (target < 1.5s)
- **Barge-in** = user can interrupt AI mid-sentence
- **Diarization** = identify who's speaking (in multi-party calls)

---

## Why Voice Agents in 2026

```
Use cases exploding:
─────────────────
• Call center deflection (60-80% of calls automated)
• Outbound sales / appointment booking
• Customer service (Indian govt PoCs at scale)
• Voice-first interfaces for elderly / accessibility
• Drive-through ordering automation
• Medical triage hotlines

Market: $50B by 2030 (voice AI). Backend devs are bottleneck.
```

---

## Architecture Options

### A. Pipeline (STT → LLM → TTS) — older approach

```
User mic → audio chunks → Whisper STT → text
                                          ↓
                                        LLM (Claude/GPT)
                                          ↓
                                        ElevenLabs TTS
                                          ↓
                                        audio → speaker

Latency: 2-4 seconds (chained)
Pros: cheap, swap components
Cons: high latency, no tone awareness
```

### B. Realtime (speech-to-speech) — 2026 standard

```
User mic → audio bytes → OpenAI Realtime API → audio bytes → speaker
                          (does STT+LLM+TTS internally)

Latency: 300-800ms
Pros: low latency, emotion-aware
Cons: expensive ($/min), less control
```

### C. Hybrid (recommended for production)

```
User mic → Deepgram streaming STT  (~50ms partial transcripts)
                                          ↓
                                  LLM with streaming
                                          ↓
                                  Cartesia/ElevenLabs TTS (streaming)
                                          ↓
                                  Audio → user

Latency: 700-1200ms
Pros: control, cost, customization
Cons: more components
```

---

## Interview Questions & Answers

### Q1: Twilio Media Streams + FastAPI WebSocket — how does call flow work?

**Answer:**

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from twilio.twiml.voice_response import VoiceResponse, Start, Stream
import base64
import json

app = FastAPI()

# Step 1: Twilio webhook when call comes in
@app.post("/twilio/incoming")
async def twilio_incoming(From: str = Form(...), To: str = Form(...)):
    """Twilio hits this when call rings. Return TwiML."""
    response = VoiceResponse()

    # Greet caller
    response.say("Hello! Connecting you to your AI assistant.", voice="alice")

    # Open bidirectional audio stream to our WebSocket
    start = Start()
    start.stream(url=f"wss://api.acme.com/twilio/stream")
    response.append(start)

    # Keep call alive (Twilio needs this)
    response.pause(length=600)  # 10 min max

    return Response(content=str(response), media_type="application/xml")

# Step 2: WebSocket receives audio
@app.websocket("/twilio/stream")
async def twilio_stream(websocket: WebSocket):
    await websocket.accept()

    stream_sid = None
    audio_buffer = bytearray()

    try:
        async for raw_message in websocket.iter_text():
            data = json.loads(raw_message)
            event = data.get("event")

            if event == "start":
                stream_sid = data["start"]["streamSid"]
                call_sid = data["start"]["callSid"]
                print(f"Call started: {call_sid}")

                # Initialize per-call state
                session = await create_session(call_sid)

            elif event == "media":
                # Audio chunk (base64-encoded mulaw, 20ms = 160 bytes)
                payload = base64.b64decode(data["media"]["payload"])
                audio_buffer.extend(payload)

                # Forward to STT/Realtime API
                await session.stt.send_audio(payload)

            elif event == "stop":
                print(f"Call ended")
                await session.cleanup()

            elif event == "mark":
                # We can send marks to track playback position
                pass

    except WebSocketDisconnect:
        await session.cleanup()
```

**Twilio audio format:** mulaw 8kHz 20ms chunks (160 bytes per chunk).

---

### Q2: OpenAI Realtime API — minimal voice agent?

**Answer:** Direct audio-in / audio-out via WebSocket.

```python
import asyncio
import json
import base64
import websockets

OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-12-17"

class RealtimeSession:
    def __init__(self, twilio_ws):
        self.twilio_ws = twilio_ws
        self.openai_ws = None
        self.stream_sid = None

    async def connect(self):
        self.openai_ws = await websockets.connect(
            OPENAI_REALTIME_URL,
            extra_headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "OpenAI-Beta": "realtime=v1",
            },
        )

        # Configure session
        await self.openai_ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "modalities": ["audio", "text"],
                "instructions": (
                    "You are a friendly customer service agent for Acme. "
                    "Be concise. Speak naturally. Use Indian English."
                ),
                "voice": "shimmer",  # or alloy, echo, fable, onyx, nova
                "input_audio_format": "g711_ulaw",   # matches Twilio
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
                        "description": "Look up an order by order number",
                        "parameters": {
                            "type": "object",
                            "properties": {"order_id": {"type": "string"}},
                            "required": ["order_id"],
                        },
                    },
                ],
                "tool_choice": "auto",
                "temperature": 0.8,
            },
        }))

        # Start two-way audio bridging
        await asyncio.gather(
            self._twilio_to_openai(),
            self._openai_to_twilio(),
        )

    async def _twilio_to_openai(self):
        """Forward incoming audio from Twilio to OpenAI."""
        async for raw_msg in self.twilio_ws.iter_text():
            data = json.loads(raw_msg)
            if data["event"] == "start":
                self.stream_sid = data["start"]["streamSid"]
            elif data["event"] == "media":
                audio_b64 = data["media"]["payload"]
                # OpenAI Realtime expects base64 audio appended to buffer
                await self.openai_ws.send(json.dumps({
                    "type": "input_audio_buffer.append",
                    "audio": audio_b64,
                }))

    async def _openai_to_twilio(self):
        """Forward AI audio responses back to Twilio."""
        async for raw_msg in self.openai_ws:
            event = json.loads(raw_msg)

            if event["type"] == "response.audio.delta":
                # AI audio chunk — forward to Twilio
                await self.twilio_ws.send_text(json.dumps({
                    "event": "media",
                    "streamSid": self.stream_sid,
                    "media": {"payload": event["delta"]},
                }))

            elif event["type"] == "response.function_call_arguments.done":
                # AI wants to call a tool
                tool_name = event["name"]
                args = json.loads(event["arguments"])
                result = await execute_tool(tool_name, args)
                # Send result back
                await self.openai_ws.send(json.dumps({
                    "type": "conversation.item.create",
                    "item": {
                        "type": "function_call_output",
                        "call_id": event["call_id"],
                        "output": json.dumps(result),
                    },
                }))
                await self.openai_ws.send(json.dumps({"type": "response.create"}))

            elif event["type"] == "error":
                logger.error(f"OpenAI error: {event}")

@app.websocket("/twilio/realtime")
async def twilio_realtime(twilio_ws: WebSocket):
    await twilio_ws.accept()
    session = RealtimeSession(twilio_ws)
    await session.connect()
```

**Latency breakdown (Realtime API):**
- Audio Twilio → backend: ~50-100ms
- Backend → OpenAI WS: ~30-80ms
- AI processing: 200-400ms
- TTS streaming: starts almost instantly
- **Total TTFB**: 300-700ms (acceptable for voice)

---

### Q3: Hybrid pipeline (Deepgram + LLM + Cartesia) for cost optimization?

**Answer:** When Realtime API too expensive, build the pipeline.

```python
from deepgram import DeepgramClient, LiveTranscriptionEvents, LiveOptions
import httpx
from cartesia import AsyncCartesia

class HybridVoiceAgent:
    def __init__(self, twilio_ws):
        self.twilio_ws = twilio_ws
        self.dg = DeepgramClient(DEEPGRAM_API_KEY)
        self.cartesia = AsyncCartesia(api_key=CARTESIA_API_KEY)
        self.history = []
        self.current_transcript = ""

    async def start(self):
        # 1. Setup Deepgram streaming STT
        self.dg_conn = self.dg.listen.asynclive.v("1")
        self.dg_conn.on(LiveTranscriptionEvents.Transcript, self._on_transcript)
        self.dg_conn.on(LiveTranscriptionEvents.UtteranceEnd, self._on_utterance_end)

        options = LiveOptions(
            model="nova-2",
            language="en-IN",        # Indian English
            encoding="mulaw",
            sample_rate=8000,
            channels=1,
            interim_results=True,    # partial transcripts
            endpointing=300,          # 300ms silence = end of utterance
            utterance_end_ms="1000",
        )
        await self.dg_conn.start(options)

        # 2. Bridge Twilio → Deepgram
        async for msg in self.twilio_ws.iter_text():
            data = json.loads(msg)
            if data["event"] == "media":
                audio = base64.b64decode(data["media"]["payload"])
                await self.dg_conn.send(audio)

    async def _on_transcript(self, _connection, result, **kwargs):
        """Partial transcripts — show "thinking" cues if needed."""
        transcript = result.channel.alternatives[0].transcript
        if result.is_final:
            self.current_transcript += " " + transcript

    async def _on_utterance_end(self, _connection, **kwargs):
        """User finished speaking — trigger LLM."""
        if not self.current_transcript.strip():
            return

        user_text = self.current_transcript.strip()
        self.current_transcript = ""

        # 3. Stream LLM response
        self.history.append({"role": "user", "content": user_text})

        async with anthropic.messages.stream(
            model="claude-haiku-4-5",     # fast for voice
            system="You are a phone agent. Keep responses under 50 words. Speak naturally.",
            messages=self.history,
            max_tokens=200,
        ) as stream:
            full_response = ""
            buffer = ""
            async for token in stream.text_stream:
                buffer += token
                full_response += token

                # 4. Stream to TTS as soon as we have a clause
                if any(p in buffer for p in [".", "!", "?", ","]):
                    await self._speak(buffer)
                    buffer = ""

            if buffer:
                await self._speak(buffer)

            self.history.append({"role": "assistant", "content": full_response})

    async def _speak(self, text: str):
        """Stream TTS audio back to Twilio."""
        async for audio_chunk in self.cartesia.tts.bytes(
            model_id="sonic-english",
            transcript=text,
            voice={"mode": "id", "id": "INDIAN_FEMALE_VOICE_ID"},
            output_format={
                "container": "raw",
                "encoding": "pcm_mulaw",
                "sample_rate": 8000,
            },
        ):
            # Forward to Twilio
            await self.twilio_ws.send_text(json.dumps({
                "event": "media",
                "streamSid": self.stream_sid,
                "media": {"payload": base64.b64encode(audio_chunk).decode()},
            }))
```

---

### Q4: Latency optimization — kaise sub-1s TTFR (Time To First Response)?

**Answer:** Stream everything; predict; pre-warm.

**Trick 1: Speculative LLM call on partial transcript**
```python
# Don't wait for final transcript — start LLM as soon as you have a sentence
async def _on_partial_transcript(self, result):
    text = result.transcript
    if text.endswith(("?", ".", "!")) and len(text) > 20:
        # User likely finished asking — start LLM speculatively
        if not self.speculative_response:
            self.speculative_response = asyncio.create_task(
                self._llm_call(text)
            )

async def _on_utterance_end(self):
    if self.speculative_response and self.speculative_response.text == final_text:
        # Reuse speculative result — saved LLM time
        response = self.speculative_response.result()
    else:
        # Real call
        response = await self._llm_call(final_text)
```

**Trick 2: TTS streaming, not buffering**
```python
# BAD: wait for full LLM response, then TTS
text = await llm_complete()      # 2s
audio = await tts(text)          # 1s
play(audio)                       # total 3s

# GOOD: stream LLM → stream TTS → play as soon as bytes arrive
async for token in llm_stream():
    audio_bytes = await tts_partial(token)  # streaming TTS
    play(audio_bytes)                        # plays as it arrives
# Effective TTFR: 700ms instead of 3s
```

**Trick 3: Pre-warm connections**
```python
# Keep WebSocket pool to OpenAI/Deepgram ready
class ConnectionPool:
    def __init__(self):
        self.idle_connections = asyncio.Queue(maxsize=10)

    async def warm_up(self):
        """Pre-establish 10 connections."""
        for _ in range(10):
            ws = await websockets.connect(OPENAI_URL, ...)
            await self.idle_connections.put(ws)

    async def get(self):
        ws = await asyncio.wait_for(self.idle_connections.get(), timeout=0.1)
        # Refill in background
        asyncio.create_task(self._refill())
        return ws
```

**Trick 4: Indian network latency**
```python
# Use Mumbai-region deployment for Indian users
# AWS ap-south-1 → user latency: 20-50ms
# AWS us-east-1 → user latency: 200-300ms
```

---

### Q5: Barge-in (interrupting AI)?

**Answer:** Detect user speaking mid-AI-response → stop playback + audio queue.

```python
class VoiceAgentWithBargein:
    def __init__(self):
        self.is_ai_speaking = False
        self.current_tts_task = None
        self.tts_audio_queue = asyncio.Queue()

    async def _on_user_speaking(self):
        """Deepgram detects user voice while AI talking."""
        if self.is_ai_speaking:
            # 1. Stop streaming TTS
            if self.current_tts_task:
                self.current_tts_task.cancel()

            # 2. Tell Twilio to stop playing buffered audio
            await self.twilio_ws.send_text(json.dumps({
                "event": "clear",
                "streamSid": self.stream_sid,
            }))

            # 3. Drain queue
            while not self.tts_audio_queue.empty():
                self.tts_audio_queue.get_nowait()

            # 4. Track what AI had said so far (for context)
            self.history[-1]["content"] += " [user interrupted]"

            self.is_ai_speaking = False
```

**OpenAI Realtime API handles this automatically** with `turn_detection: server_vad`.

---

### Q6: Tool use during voice call?

**Answer:** Same as text, but stream audio cues while tool runs.

```python
async def handle_tool_call(self, tool_name: str, args: dict):
    # 1. Play "thinking" cue (don't leave silence)
    await self._speak("Let me look that up for you...")

    # 2. Execute tool (may take 2-5 seconds)
    if tool_name == "lookup_order":
        result = await order_service.get_order(args["order_id"])
    elif tool_name == "schedule_callback":
        result = await crm.schedule_callback(args["time"], args["phone"])

    # 3. Send result back to LLM
    self.history.append({
        "role": "tool",
        "tool_use_id": tool_call_id,
        "content": json.dumps(result),
    })

    # 4. LLM continues from there
    await self._llm_streaming_response()
```

**Common tool patterns:**
- CRM lookup (orders, tickets)
- Booking/scheduling
- Payment processing (with HOLD/transfer to human)
- Knowledge base search (RAG)
- SMS/email sending
- Transfer to human agent

---

### Q7: Compliance + recording (TRAI, DPDP)?

**Answer:** India regulates voice AI heavily.

```python
# 1. Disclosure mandatory (TRAI norms)
@app.post("/twilio/incoming")
async def incoming_call(From: str = Form(...)):
    response = VoiceResponse()

    # MUST disclose AI nature (DPDP + TRAI guidance)
    response.say(
        "This call may be answered by an AI assistant. "
        "Press 1 to continue or 0 to speak with a human.",
        voice="Polly.Aditi",  # Indian voice
    )

    response.gather(
        num_digits=1,
        action="/twilio/route",
        method="POST",
    )
    return Response(content=str(response), media_type="application/xml")

# 2. Consent recording
async def start_call_with_consent(call_sid: str, from_number: str):
    # Log consent
    await db.execute(
        """
        INSERT INTO voice_call_consents (call_sid, phone, consented_at, recording_consent, ai_consent)
        VALUES (:sid, :phone, NOW(), TRUE, TRUE)
        """,
        {"sid": call_sid, "phone": hash_phone(from_number)},
    )

# 3. Recording with retention policy
@app.post("/twilio/recording")
async def recording_callback(
    CallSid: str = Form(...),
    RecordingUrl: str = Form(...),
    RecordingDuration: int = Form(...),
):
    # Store with auto-delete
    await db.execute(
        """
        INSERT INTO call_recordings (call_sid, url, duration_sec, expires_at)
        VALUES (:sid, :url, :dur, NOW() + INTERVAL '90 days')
        """,
        {"sid": CallSid, "url": RecordingUrl, "dur": RecordingDuration},
    )

# 4. Schedule deletion
@celery_app.task
def expire_recordings():
    """Run daily — delete recordings past retention."""
    expired = db.execute("SELECT call_sid, url FROM call_recordings WHERE expires_at < NOW()")
    for row in expired:
        twilio_client.recordings(row.call_sid).delete()
        db.execute("DELETE FROM call_recordings WHERE call_sid = :sid", {"sid": row.call_sid})

# 5. DND list compliance (TRAI mandate for outbound)
TRAI_DND_API = "https://api.trai.gov.in/dnd/check"

async def can_call_number(phone: str) -> bool:
    response = await httpx.AsyncClient().get(f"{TRAI_DND_API}?phone={phone}")
    return response.json()["status"] == "active_for_calls"
```

**TRAI rules (outbound calls):**
- DND scrubbing mandatory
- Call only 09:00 - 21:00 IST
- Caller ID must be valid (registered)
- Promotional calls need separate consent

---

### Q8: Production monitoring for voice agents?

**Answer:** Quality metrics + business metrics.

```python
# Per-call metrics
call_duration_seconds = Histogram("voice_call_duration_seconds")
turn_latency_seconds = Histogram("voice_turn_latency_seconds", "Time to AI response")
asr_word_error_rate = Histogram("voice_asr_wer", "Whisper/Deepgram WER")
calls_total = Counter("voice_calls_total", ["disposition"])  # completed, abandoned, transferred
transfer_to_human = Counter("voice_transfers_to_human_total", ["reason"])
tts_cost_usd = Counter("voice_tts_cost_usd_total")
llm_cost_usd = Counter("voice_llm_cost_usd_total")

# Business KPIs (track per call)
@dataclass
class CallOutcome:
    call_sid: str
    duration_sec: int
    user_satisfied: bool          # asked at end / sentiment analysis
    issue_resolved: bool
    transferred: bool
    transfer_reason: str
    cost_usd: float
    sentiment_score: float        # -1 (angry) to +1 (happy)
    topics_discussed: list[str]   # extracted via post-call LLM
```

**Quality checks:**
```python
# Audio quality monitoring
async def monitor_audio_quality(audio_chunk):
    rms = calc_rms(audio_chunk)
    if rms < 100:        # too quiet
        alert("Low audio quality detected")
    if rms > 10000:      # clipping
        alert("Audio clipping")

# Post-call analysis (async)
@celery_app.task
async def analyze_completed_call(call_sid: str):
    transcript = await get_full_transcript(call_sid)

    # LLM-as-judge for quality
    analysis = await anthropic.messages.create(
        model="claude-sonnet-4-6",
        system="Analyze this customer service call. Output JSON: {satisfied, resolved, sentiment, topics, escalation_needed}",
        messages=[{"role": "user", "content": transcript}],
    )

    outcome = parse_json(analysis.content[0].text)
    await save_call_analytics(call_sid, outcome)

    # Alert if escalation patterns
    if outcome.get("sentiment") < -0.5:
        await alert_supervisor(call_sid, "Angry customer")
```

---

## Cost Breakdown (per call)

| Component | 5-min call | 10-min call |
|---|---|---|
| Twilio (call + media stream) | $0.05 | $0.10 |
| Deepgram STT | $0.04 | $0.08 |
| LLM (Claude Sonnet, ~10 turns) | $0.10 | $0.20 |
| Cartesia TTS | $0.08 | $0.16 |
| **Pipeline total** | **$0.27** | **$0.54** |
| OpenAI Realtime (alternative) | $0.30 | $0.60 |
| Self-hosted everything | $0.08 | $0.16 |

**Indian market expectations:** ₹3-15 per call (depends on quality).

---

## Production Gotchas

| Gotcha | Fix |
|---|---|
| AI talks over user | Implement barge-in detection |
| Awkward silences | Play "let me check" while tool runs |
| Background noise → bad transcripts | Use noise-suppression preprocessing |
| Accent issues | Use locale-specific STT (Deepgram en-IN) |
| Long tail of edge phrases | Custom vocabulary in STT |
| AI talks too fast/slow | Tune TTS speed; match user pace |
| Caller drops mid-tool-call | Save state; resume on callback |
| Compliance violations | Always disclose AI; consent first |
| Network drops audio | Buffer + retry; degrade to text |
| Outbound DND violations | TRAI DND scrubbing mandatory |

---

## Senior-level Checklist

- [ ] Architecture chosen (Realtime vs pipeline vs hybrid)
- [ ] Twilio Media Streams configured
- [ ] STT with VAD + endpointing
- [ ] LLM streaming with system prompt for voice
- [ ] TTS streaming (no full-message buffering)
- [ ] Barge-in detection + handling
- [ ] Tool calling with "thinking" audio cues
- [ ] AI disclosure at call start
- [ ] DND scrubbing (outbound)
- [ ] Recording retention policy (DPDP)
- [ ] Per-call cost tracking
- [ ] Quality monitoring (WER, sentiment, resolution)
- [ ] Transfer-to-human fallback
- [ ] Multi-language support (Hindi + regional)
- [ ] Indian region deployment (ap-south-1)
- [ ] Postmortem analysis via LLM-as-judge

---

## Related Docs
- `31_llm_integration_fastapi.md` — LLM base
- `32_function_calling_endpoints.md` — tool use
- `33_prompt_injection_security.md` — voice attacks (yes, exists)
- `36_local_llm_serving.md` — self-host for cost
- `Phase2_WebSocket_SSE/` — WebSocket fundamentals
- `Phase3_Security/17_india_dpdp_compliance.md` — voice data privacy

## External References
- Twilio Media Streams: https://www.twilio.com/docs/voice/media-streams
- OpenAI Realtime API: https://platform.openai.com/docs/guides/realtime
- Deepgram streaming: https://developers.deepgram.com/docs/getting-started-with-live-streaming-audio
- Cartesia: https://docs.cartesia.ai
- ElevenLabs: https://elevenlabs.io/docs
