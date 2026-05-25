# Modern Topics — Doc 1: Voice Agents

> **Goal:** Build voice-first AI agents — speech-to-text, LLM, text-to-speech. Real-time conversation possible.

---

## 1. Voice Agent Architecture

```
User speaks → STT → text → LLM → text → TTS → audio → User hears

Traditional pipeline (3 separate calls):
  1. Whisper: speech-to-text (~500ms)
  2. GPT-4: text → reasoning + response (~2s)
  3. ElevenLabs: text-to-speech (~500ms)
  Total: ~3 seconds per turn

Modern (OpenAI Realtime API):
  Speech in → Realtime API (audio-native) → Speech out
  Total: ~500ms latency
```

---

## 2. Component 1: Speech-to-Text (STT)

### OpenAI Whisper
```python
from openai import OpenAI
client = OpenAI()

with open("audio.mp3", "rb") as f:
    transcript = client.audio.transcriptions.create(
        model="whisper-1",
        file=f,
        language="en"
    )
print(transcript.text)
```

### Other options:
- **Deepgram** — best latency for real-time
- **AssemblyAI** — best accuracy
- **Cartesia** — extreme low-latency
- **Local Whisper** (`whisper-cpp`) — privacy

---

## 3. Component 2: LLM (text)

Standard LLM call. Same as text agents.

---

## 4. Component 3: Text-to-Speech (TTS)

### ElevenLabs (Best Quality)
```python
from elevenlabs import generate, play

audio = generate(
    text="Hello, this is your AI assistant.",
    voice="Rachel",
    model="eleven_turbo_v2"
)
play(audio)
```

### OpenAI TTS
```python
response = client.audio.speech.create(
    model="tts-1",
    voice="alloy",
    input="Hello world"
)
response.stream_to_file("output.mp3")
```

### Cartesia
Lowest latency, real-time streaming.

---

## 5. OpenAI Realtime API (Game Changer)

Audio in → audio out in same WebSocket. ~500ms latency.

```python
import asyncio
import websockets
import base64

async def voice_agent():
    headers = {
        "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
        "OpenAI-Beta": "realtime=v1"
    }
    async with websockets.connect(
        "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01",
        extra_headers=headers
    ) as ws:
        # Configure session
        await ws.send(json.dumps({
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": "You are a helpful voice assistant.",
                "voice": "alloy",
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "turn_detection": {"type": "server_vad"}
            }
        }))
        
        # Send audio
        await ws.send(json.dumps({
            "type": "input_audio_buffer.append",
            "audio": base64.b64encode(audio_chunk).decode()
        }))
        
        # Receive response
        async for message in ws:
            event = json.loads(message)
            if event["type"] == "response.audio.delta":
                # Stream audio to speakers
                audio = base64.b64decode(event["delta"])
                play(audio)
```

This is what powers ChatGPT voice mode.

---

## 6. Tool Use in Voice Agents

Realtime API supports function calling:
```python
{
    "type": "session.update",
    "session": {
        "tools": [{
            "type": "function",
            "name": "get_weather",
            "description": "Get current weather",
            "parameters": {...}
        }]
    }
}
```

User: "What's the weather?" → agent calls function → speaks response.

---

## 7. Voice Activity Detection (VAD)

How does agent know when user finished speaking?

### Server-side VAD (OpenAI Realtime)
OpenAI detects silence, automatically responds.

### Client-side VAD
```python
import webrtcvad
vad = webrtcvad.Vad(2)  # Aggressiveness 0-3

# Check if audio chunk contains speech
is_speech = vad.is_speech(audio_chunk, sample_rate=16000)
```

---

## 8. Latency Optimization

Goal: < 500ms perceived latency.

Techniques:
- **Streaming STT** (transcribe while user speaks)
- **Speculative generation** (start LLM before user finishes)
- **Streaming TTS** (speak while LLM still generating)
- **Lower-latency models** (Haiku, Flash)

---

## 9. Use Cases

### Customer Support
- 24/7 voice line
- Routes to human if complex

### Drive-Thru AI
- Order taking
- McDonald's, Wendy's testing

### Personal Assistant
- Like Siri but smarter
- Voice command + tool use

### Language Learning
- Conversational practice
- Real-time correction

### Accessibility
- Voice control of apps
- For visually impaired

---

## 10. Production Considerations

- **Audio quality** — 16kHz minimum for STT
- **Background noise** — affects STT accuracy
- **Interrupt handling** — user wants to interrupt agent
- **Multilingual** — different voices, accents
- **Hallucination** — voice hides errors. Verify outputs.
- **Compliance** — recording = consent needed in many regions

---

## 11. Frameworks

### Pipecat (Python framework for voice AI)
```python
from pipecat.pipeline import Pipeline
from pipecat.services import OpenAILLMService, ElevenLabsTTSService, DeepgramSTTService

pipeline = Pipeline([
    DeepgramSTTService(...),  # STT
    OpenAILLMService(...),    # LLM
    ElevenLabsTTSService(...) # TTS
])

pipeline.run()
```

Production framework for voice agents.

### Other:
- **Vocode** — easy voice agent framework
- **Voapi** — voice + AI low-code platform
- **LiveKit Agents** — built on LiveKit WebRTC

---

## 12. Key Takeaways

✅ Voice agents = STT + LLM + TTS pipeline
✅ Real-time = OpenAI Realtime API (audio-native)
✅ Whisper for STT, ElevenLabs/Cartesia for TTS
✅ Latency target: <500ms
✅ VAD detects when user stops speaking
✅ Streaming everywhere reduces perceived latency
✅ Frameworks: Pipecat, Vocode, LiveKit
✅ Compliance: consent for recording

**Next:** [02_computer_use.md](02_computer_use.md) — Claude controls computer desktop
