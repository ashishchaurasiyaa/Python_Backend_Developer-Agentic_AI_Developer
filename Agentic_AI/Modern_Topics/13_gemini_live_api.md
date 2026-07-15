# Modern Topics — Doc 13: Gemini Live API (Real-Time Multimodal) ⭐

> **Goal:** Gemini Live API = Google ka low-latency, **bidirectional streaming** API. Text/audio/video ek saath, real-time, dono taraf. Ye OpenAI Realtime API ka counterpart hai — voice agents aur "screen/camera dekh ke baat kare" wale agents isse bante hain. Interview me "real-time voice agent kaise banaoge" ka jawab yahi (Google side).

---

## 1. Normal Gemini API vs Live API

| | `generateContent` (normal) | **Live API** |
|--|--|--|
| Pattern | Request → response (one-shot) | Persistent **WebSocket** session |
| Direction | Unidirectional | **Bidirectional** (dono taraf stream) |
| Input | Text / image / whole audio file | Live mic audio, camera/screen frames, text — streaming |
| Output | Text (ya batch audio) | Streaming text **+ streaming TTS audio** |
| Latency | Normal | Sub-second — conversation-grade |
| Interruption | ❌ | ✅ **Barge-in** (user beech me bol de to model ruk jaye) |

Live API `bidiGenerateContent` WebSocket endpoint use karta hai. Iske do backend: **Gemini Developer API** (AI Studio key) aur **Vertex AI** (enterprise).

---

## 2. Kab use karo

- **Voice assistant** — real-time bol ke baat, natural turn-taking (barge-in ke saath).
- **Live screen/camera share** — model tumhari screen ya camera feed dekh ke live guide kare ("ab wo button dabao").
- **Live translation / captioning** — bolte jao, translate hote jao.
- **Interactive tutoring / support** — awaaz + visual context ek saath.

Agar sirf audio file transcribe karni hai (batch) → normal API kaafi hai; Live API tab jab **real-time + bidirectional** chahiye.

---

## 3. Core concepts

- **Session** — ek WebSocket connection = ek live conversation. `session.connect()` se khulta hai, context isi ke andar rehta hai.
- **Modalities** — session start pe batao output text chahiye ya audio (`response_modalities`). Input hamesha mixed ho sakta hai.
- **Voice Activity Detection (VAD)** — server khud detect karta hai user ne bolna kab shuru/band kiya; turn boundaries automatic.
- **Interruptions (barge-in)** — model bol raha ho aur user bol de → model ka current output cancel, user ko sunta hai.
- **Ephemeral audio** — audio chunks stream me aate hain (PCM), tum play karte jao; poora file wait nahi.
- **Tool use** — Live session me bhi function calling + Google Search grounding + code execution chalta hai.

---

## 4. Minimal text-in / text-out session

```python
# pip install google-genai
import asyncio
from google import genai

client = genai.Client(api_key="...")          # AI Studio key
MODEL = "gemini-2.0-flash-live-001"           # live-capable model

async def main():
    config = {"response_modalities": ["TEXT"]}
    async with client.aio.live.connect(model=MODEL, config=config) as session:
        await session.send_client_content(
            turns={"role": "user", "parts": [{"text": "2 line me quantum computing samjhao"}]},
            turn_complete=True,
        )
        async for response in session.receive():
            if response.text:
                print(response.text, end="", flush=True)

asyncio.run(main())
```

---

## 5. Audio out (voice agent ka core)

```python
config = {
    "response_modalities": ["AUDIO"],          # TTS audio wapas chahiye
    "speech_config": {
        "voice_config": {"prebuilt_voice_config": {"voice_name": "Puck"}}
    },
}

async with client.aio.live.connect(model=MODEL, config=config) as session:
    await session.send_client_content(
        turns={"role": "user", "parts": [{"text": "Namaste bolo"}]},
        turn_complete=True,
    )
    async for response in session.receive():
        if response.data:                      # raw PCM audio chunk
            play_audio(response.data)          # 24kHz PCM -> speaker
```

Mic audio bhejna (real-time input): chunks ko `send_realtime_input(audio=...)` se stream karo — 16kHz PCM. Camera/screen frames bhi `send_realtime_input(video=...)` se ja sakte hain.

---

## 6. Function calling in a live session

```python
config = {
    "response_modalities": ["AUDIO"],
    "tools": [{"function_declarations": [{
        "name": "get_weather",
        "description": "city ka weather",
        "parameters": {"type": "object", "properties": {"city": {"type": "string"}}},
    }]}],
}

async with client.aio.live.connect(model=MODEL, config=config) as session:
    await session.send_client_content(
        turns={"role": "user", "parts": [{"text": "Delhi ka mausam?"}]}, turn_complete=True)
    async for response in session.receive():
        if response.tool_call:                 # model ne tool maanga
            for fc in response.tool_call.function_calls:
                result = {"temp_c": 34}        # tumhara real function
                await session.send_tool_response(function_responses=[{
                    "id": fc.id, "name": fc.name, "response": result,
                }])
```
Built-in tools bhi hain: **Google Search grounding** aur **code execution** (config me enable karo).

---

## 7. Gemini Live vs OpenAI Realtime — interview table

| | Gemini Live API | OpenAI Realtime API |
|--|--|--|
| Vendor | Google (Gemini) | OpenAI |
| Transport | WebSocket (`bidiGenerateContent`) | WebSocket / WebRTC |
| Video/screen input | ✅ native (frames stream) | Limited (mainly audio+text) |
| Barge-in / VAD | ✅ | ✅ |
| SDK | `google-genai` (`client.aio.live`) | `openai` realtime client |
| Best for | Multimodal (voice + vision) live agents | Voice-first live agents |

Anthropic ka abhi direct real-time bidi audio API nahi hai (Claude voice typically STT → Claude → TTS pipeline se, see [01_voice_agents.md](01_voice_agents.md)).

---

## 8. Production considerations

- **Session limits** — live session ki max length + concurrent-session quota hoti hai; long sessions ke liye reconnect/resume handle karo (session resumption tokens).
- **Audio format** — input 16kHz PCM, output 24kHz PCM (little-endian, mono) — resampling galat hui to distorted/no audio. Ye #1 bug hai.
- **Latency budget** — network + VAD + model; jitter buffer chhota rakho warna choppy.
- **Cost** — audio tokens text se mehnge; live/streaming usage alag priced. Long always-on sessions monitor karo.
- **Interruption handling** — barge-in pe apne playback buffer ko turant flush karna (warna purani awaaz bajti rahegi).
- **Privacy** — live mic/camera = sensitive; consent + retention policy zaroori (PII, [09_ai_security_threats.md](09_ai_security_threats.md)).

---

## 9. Key Takeaways

- Live API = Google ka **real-time bidirectional multimodal** API over WebSocket — voice + vision live agents ka core.
- Normal `generateContent` one-shot; Live API persistent session with **barge-in + streaming audio**.
- `client.aio.live.connect()` (Python `google-genai`), modalities text/audio, tools + Google Search grounding supported.
- Native **video/screen frame** input isko OpenAI Realtime se alag banata hai.
- OpenAI ka analog = Realtime API; Anthropic voice = STT→LLM→TTS pipeline.

## Related Topics
- Voice agents / STT-TTS pipeline → [01_voice_agents.md](01_voice_agents.md)
- Multimodal (vision/audio/video) → [05_multimodal_agents.md](05_multimodal_agents.md)
- OpenAI agentic API counterpart → [12_openai_responses_api.md](12_openai_responses_api.md)
- Streaming events (OpenAI) → [12_openai_responses_api.md](12_openai_responses_api.md) §6
