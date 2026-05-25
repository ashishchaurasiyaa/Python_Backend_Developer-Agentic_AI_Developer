# Modern Topics — Doc 5: Multi-Modal Agents (Vision + Text + Audio)

> **Goal:** Agents that see, hear, and read. Image + text + audio in one model.

---

## 1. Multi-Modal Capabilities

Modern LLMs are multi-modal natively:

| Model | Text | Image | Audio | Video |
|---|---|---|---|---|
| GPT-4o | ✅ | ✅ | ✅ (Realtime) | ✅ (frames) |
| Claude 3.5/4 | ✅ | ✅ | ❌ | ✅ (frames) |
| Gemini 2.0 | ✅ | ✅ | ✅ | ✅ (native) |
| Llama 3.2 | ✅ | ✅ (11B+) | ❌ | ❌ |

---

## 2. Vision Input

### OpenAI GPT-4o with image
```python
import base64

with open("image.jpg", "rb") as f:
    img_data = base64.b64encode(f.read()).decode()

response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "What's in this image?"},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{img_data}"}
            }
        ]
    }]
)
```

### Claude with image
```python
response = client.messages.create(
    model="claude-3-5-sonnet-20241022",
    max_tokens=1024,
    messages=[{
        "role": "user",
        "content": [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/jpeg",
                    "data": img_data
                }
            },
            {"type": "text", "text": "Describe this image."}
        ]
    }]
)
```

---

## 3. Use Cases for Vision

### Document Understanding
```python
# OCR + structured extraction in one call
response = gpt4o(
    "Extract this invoice as JSON",
    image=invoice_image
)
# Returns: {"vendor": "Acme", "total": 500, "date": "2024-01-15", ...}
```

### Visual QA
```python
# "What's wrong with this code screenshot?"
# "What's the error in this log?"
# "Read this whiteboard"
```

### Code from Sketch
```python
# Sketch UI on paper → photo → code
response = gpt4o(
    "Generate React code matching this UI design",
    image=sketch_photo
)
```

### Accessibility
```python
# Describe images for visually impaired users
# Read receipts aloud
# Identify objects
```

---

## 4. Document Processing

### OCR + Extract (Multi-page)
```python
import fitz  # PyMuPDF

def process_pdf(pdf_path):
    doc = fitz.open(pdf_path)
    results = []
    
    for page_num in range(len(doc)):
        # Render page as image
        page = doc[page_num]
        pix = page.get_pixmap()
        img_b64 = base64.b64encode(pix.tobytes("png")).decode()
        
        # Process with vision LLM
        result = vision_llm(
            "Extract all text + tables from this page as structured JSON",
            image=img_b64
        )
        results.append(result)
    
    return results
```

### Specialized: Mistral Document Reader, Anthropic PDF support
Some providers handle PDFs natively without manual rendering.

---

## 5. Multi-Image Reasoning

```python
# Compare two images
response = gpt4o([
    "Are these two photos of the same person?",
    {"image": photo1},
    {"image": photo2}
])

# Process a series
response = gpt4o([
    "These are sequential frames of a video. Describe what's happening.",
    *[{"image": frame} for frame in frames]
])
```

---

## 6. Video Understanding

### Approach 1: Frame Sampling
```python
import cv2

def video_to_frames(video_path, max_frames=20):
    cap = cv2.VideoCapture(video_path)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    step = total_frames // max_frames
    
    frames = []
    for i in range(0, total_frames, step):
        cap.set(cv2.CAP_PROP_POS_FRAMES, i)
        ret, frame = cap.read()
        if ret:
            _, buffer = cv2.imencode(".jpg", frame)
            frames.append(base64.b64encode(buffer).decode())
    
    return frames

# Send to LLM
frames = video_to_frames("video.mp4")
response = gpt4o(
    "Describe this video",
    images=frames
)
```

### Approach 2: Gemini Native Video
Gemini supports video files directly:
```python
import google.generativeai as genai

model = genai.GenerativeModel("gemini-2.0-flash")
video_file = genai.upload_file("video.mp4")
response = model.generate_content([
    video_file,
    "Summarize this video"
])
```

---

## 7. Audio Input (GPT-4o)

```python
# Direct audio input (not just Whisper transcript)
response = client.chat.completions.create(
    model="gpt-4o-audio-preview",
    modalities=["text", "audio"],
    audio={"voice": "alloy", "format": "wav"},
    messages=[{
        "role": "user",
        "content": [
            {"type": "text", "text": "Transcribe and summarize"},
            {"type": "input_audio", "input_audio": {"data": audio_b64, "format": "wav"}}
        ]
    }]
)
```

GPT-4o can "hear" tone, emotion, music — not just transcribe.

---

## 8. Combining Modalities

### Multi-modal RAG
```python
# Index PDFs (text + images)
for pdf in pdfs:
    text = extract_text(pdf)
    images = extract_images(pdf)
    
    # Index text chunks
    for chunk in chunk_text(text):
        vector_db.add(chunk, embedding=text_embed(chunk))
    
    # Index images (multimodal embeddings — CLIP)
    for img in images:
        vector_db.add(img, embedding=clip_embed(img))

# Query (text or image)
results = vector_db.search(query)
# Pass mixed results to multimodal LLM
```

### Visual Tool Use
```python
@tool
def take_screenshot():
    """Take a screenshot of current screen."""
    return capture_screen()

agent.use_tool(take_screenshot)
# LLM sees the image, decides next action
```

---

## 9. Real-World Multimodal Agents

### Customer Support
- User uploads photo of broken product
- Agent identifies issue, suggests fix
- Or initiates RMA

### Healthcare
- Doctor uploads X-ray
- Agent highlights regions of interest
- (Adjunct only, not diagnosis)

### Legal
- Upload contract PDF
- Agent extracts terms, flags risks

### Real Estate
- Photos of property
- Agent describes features for listing
- Compares to market

### Education
- Student photographs math problem
- Agent shows solution steps

---

## 10. Cost Considerations

Vision is expensive:
- High-res image (1024x1024): ~1500 tokens
- 10 image queries: ~15K tokens just for images
- + text response

Optimize:
- **Resize** before sending (224x224 often enough)
- **Low-detail** mode (OpenAI offers)
- **Cache** image embeddings

```python
# OpenAI image detail
{"image_url": {"url": "...", "detail": "low"}}  # Cheaper
{"image_url": {"url": "...", "detail": "high"}} # Better but expensive
```

---

## 11. Multimodal Embeddings (CLIP)

```python
import clip
import torch

model, preprocess = clip.load("ViT-B/32")

# Image embedding
image = preprocess(image_pil).unsqueeze(0)
with torch.no_grad():
    image_features = model.encode_image(image)

# Text embedding (same space!)
text = clip.tokenize(["a photo of a cat"])
with torch.no_grad():
    text_features = model.encode_text(text)

# Compare: similarity between image and text
similarity = (image_features @ text_features.T)
```

Used for: image search, multimodal RAG.

---

## 12. Common Pitfalls

❌ Sending huge images (resize first)
❌ High-detail when low-detail enough (cost)
❌ Treating vision as perfect (hallucinations exist)
❌ Ignoring privacy (faces, license plates, PII)
❌ Not specifying format (LLM hallucinates JSON structure)

---

## 13. Privacy + Vision

Images can contain:
- People's faces
- License plates
- Documents with PII
- Confidential info

Always:
- Get user consent
- Auto-blur faces if not needed
- Don't log raw images long-term
- Comply with GDPR/CCPA

---

## 14. Key Takeaways

✅ GPT-4o, Claude, Gemini all support vision natively
✅ Image input: base64 in messages
✅ Use cases: docs, code from sketch, accessibility, support
✅ Video = frames (or Gemini native)
✅ Audio = Whisper + LLM, or GPT-4o direct
✅ CLIP for multimodal embeddings
✅ Cost: optimize with resize + low-detail mode
✅ Privacy: faces, PII, consent matters

**Modern Topics series complete!** 🎉

Series:
- [01 — Voice Agents](01_voice_agents.md)
- [02 — Computer Use](02_computer_use.md)
- [03 — Local Serving](03_local_serving.md)
- [04 — Memory Frameworks](04_memory_frameworks.md)
- [05 — Multi-modal Agents](05_multimodal_agents.md) ← You are here
