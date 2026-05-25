"""
Phase6_Specialized_AI — Complete Practical
============================================
Topics:
  1. Multimodal AI (vision, audio, video)
  2. Code generation and execution
  3. Document AI (PDF, tables, forms)
  4. Computer use / browser automation
  5. Tool-use patterns for specialized domains
  6. Structured output for specialized tasks

Install: pip install openai anthropic pillow pytesseract
Run: python 01_specialized_ai_practical.py
"""

import os, json, base64
from typing import List, Dict, Any, Optional
from pathlib import Path

MOCK_MODE = not (os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY"))
if MOCK_MODE:
    print("⚠  MOCK MODE — set OPENAI_API_KEY or ANTHROPIC_API_KEY\n")

print("=" * 60)
print("SPECIALIZED AI CAPABILITIES")
print("=" * 60)

SPECIALIZED_AI = {
    "Vision":           "Analyze images: GPT-4o, Claude Sonnet. Base64 or URL.",
    "Audio":            "Whisper (transcription), TTS (gpt-4o-audio), real-time voice",
    "Code execution":   "Code Interpreter / Python Executor tool. Run generated code safely.",
    "Document AI":      "PDF/table/form parsing. LlamaParse, GPT-4o vision, Textract.",
    "Computer use":     "Claude Computer Use: take screenshots, click, type, browse.",
    "Structured gen":   "Force JSON schema output. OpenAI JSON mode, Instructor, Claude.",
    "Multimodal RAG":   "Index images + text together. ColPali: vision embeddings for PDFs.",
}
for k, v in SPECIALIZED_AI.items():
    print(f"  {k:<20}: {v}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Vision (GPT-4o / Claude)
# INTERVIEW: Base64 encode local images, use URL for remote
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 1: Vision AI (Multimodal)")
print("=" * 60)

VISION_CODE = '''\
import base64
from openai import OpenAI
import anthropic

openai_client = OpenAI()
claude_client = anthropic.Anthropic()

# ── Encode local image ──────────────────────────────────────────
def encode_image(path: str) -> str:
    """Base64 encode image for API. JPEG/PNG/GIF/WEBP supported."""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

# ── GPT-4o vision ──────────────────────────────────────────────
def analyze_image_openai(image_path: str, question: str) -> str:
    b64 = encode_image(image_path)
    ext = Path(image_path).suffix.lower().replace(".", "")
    mime = {"jpg": "jpeg", "jpeg": "jpeg", "png": "png", "webp": "webp"}.get(ext, "jpeg")

    response = openai_client.chat.completions.create(
        model    = "gpt-4o",
        max_tokens = 1024,
        messages = [{
            "role": "user",
            "content": [
                {
                    "type":       "image_url",
                    "image_url":  {
                        "url":    f"data:image/{mime};base64,{b64}",
                        "detail": "high",  # "low" = fast+cheap, "high" = detailed
                    }
                },
                {"type": "text", "text": question},
            ]
        }]
    )
    return response.choices[0].message.content

# ── Claude vision ──────────────────────────────────────────────
def analyze_image_claude(image_path: str, question: str) -> str:
    b64 = encode_image(image_path)
    response = claude_client.messages.create(
        model      = "claude-sonnet-4-5",
        max_tokens = 1024,
        messages   = [{
            "role": "user",
            "content": [
                {
                    "type":   "image",
                    "source": {
                        "type":       "base64",
                        "media_type": "image/jpeg",
                        "data":       b64,
                    }
                },
                {"type": "text", "text": question},
            ]
        }]
    )
    return response.content[0].text

# ── URL-based (no upload needed) ──────────────────────────────
response = openai_client.chat.completions.create(
    model    = "gpt-4o",
    messages = [{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": "https://example.com/chart.png"}},
            {"type": "text", "text": "Describe the trends in this chart."},
        ]
    }]
)

# ── Multiple images ────────────────────────────────────────────
content = []
for img_path in image_paths:
    content.append({
        "type": "image_url",
        "image_url": {"url": f"data:image/jpeg;base64,{encode_image(img_path)}"}
    })
content.append({"type": "text", "text": "Compare these before/after screenshots."})
'''
print(VISION_CODE[:700])

print("\n  Vision use cases:")
VISION_USE_CASES = {
    "Document extraction":  "Read tables/forms from scanned PDFs",
    "UI testing":           "Verify screenshots match expected layout",
    "Chart analysis":       "Extract data trends from graphs/charts",
    "Code review from img": "Review code in screenshots",
    "Product QA":           "Defect detection in manufacturing images",
    "Medical imaging":      "Assist radiologists with DICOM/X-ray analysis",
}
for uc, desc in VISION_USE_CASES.items():
    print(f"  {uc:<24}: {desc}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: Code Generation + Execution
# INTERVIEW: Generate code + safely execute it
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 2: Code Generation + Execution")
print("=" * 60)

CODE_GEN_CODE = '''\
from openai import OpenAI
import subprocess, tempfile, os

client = OpenAI()

# ── Code generation ────────────────────────────────────────────
def generate_code(task: str, language: str = "python") -> str:
    """Generate code for a given task."""
    response = client.chat.completions.create(
        model    = "gpt-4o",
        messages = [
            {
                "role":    "system",
                "content": f"You are a {language} expert. Output ONLY code, no explanation. "
                           f"Wrap code in ```{language} ... ``` blocks."
            },
            {"role": "user", "content": task},
        ]
    )
    content = response.choices[0].message.content
    # Extract code block
    import re
    match = re.search(rf"```{language}\\n(.*?)```", content, re.DOTALL)
    return match.group(1).strip() if match else content

# ── Safe execution (sandboxed) ────────────────────────────────
def execute_python(code: str, timeout: int = 10) -> dict:
    """
    INTERVIEW: NEVER use eval() or exec() without sandboxing.
    Use subprocess with resource limits, or Docker container.
    """
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        script_path = f.name
    try:
        result = subprocess.run(
            ["python", script_path],
            capture_output = True,
            text           = True,
            timeout        = timeout,
            # Security: no network access in production sandbox
        )
        return {
            "stdout":      result.stdout,
            "stderr":      result.stderr,
            "returncode":  result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"error": f"Execution timed out ({timeout}s)"}
    finally:
        os.unlink(script_path)

# ── Code interpreter agent (OpenAI Assistants) ────────────────
# OpenAI Code Interpreter tool: upload file → generate + run code → return result
assistant = client.beta.assistants.create(
    name         = "Data Analyst",
    instructions = "Analyze data and generate visualizations.",
    tools        = [{"type": "code_interpreter"}],
    model        = "gpt-4o",
)
# Upload CSV, ask questions → assistant writes + runs Python → shows results

# ── E2B Code Sandbox (production) ─────────────────────────────
# pip install e2b_code_interpreter
from e2b_code_interpreter import Sandbox
sandbox = Sandbox()
result  = sandbox.run_code("print(2 + 2)")   # isolated sandbox, network available
print(result.text)   # "4"
sandbox.kill()
'''
print(CODE_GEN_CODE[:700])

# Demo safe code execution
import subprocess, tempfile

def execute_python_safely(code: str, timeout: int = 5) -> Dict[str, Any]:
    """Execute Python code in subprocess with timeout."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir="/tmp") as f:
        f.write(code)
        script_path = f.name
    try:
        result = subprocess.run(
            ["python3", script_path],
            capture_output=True, text=True, timeout=timeout
        )
        return {"stdout": result.stdout.strip(), "stderr": result.stderr.strip(), "ok": result.returncode == 0}
    except subprocess.TimeoutExpired:
        return {"error": "Timeout", "ok": False}
    except Exception as e:
        return {"error": str(e), "ok": False}
    finally:
        try:
            os.unlink(script_path)
        except:
            pass


import os
print("\n  Code execution demo:")
snippets = [
    ("Safe math",    "print(sum(range(1, 101)))"),
    ("List comp",    "print([x**2 for x in range(5)])"),
    ("Timeout test", "import time; time.sleep(10); print('done')"),
]
for name, code in snippets:
    result = execute_python_safely(code, timeout=2)
    if result.get("ok"):
        print(f"  ✓ {name}: {result['stdout']}")
    else:
        print(f"  ✗ {name}: {result.get('error', result.get('stderr', 'failed'))}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Document AI
# INTERVIEW: Extract structured data from PDFs, tables, forms
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 3: Document AI")
print("=" * 60)

DOCUMENT_AI_CODE = '''\
# ── LlamaParse (best for complex PDFs) ────────────────────────
from llama_parse import LlamaParse
from llama_index.core import SimpleDirectoryReader

parser = LlamaParse(
    api_key     = os.getenv("LLAMA_CLOUD_API_KEY"),
    result_type = "markdown",  # or "text"
    verbose     = True,
)
file_extractor = {".pdf": parser}
documents = SimpleDirectoryReader("./docs", file_extractor=file_extractor).load_data()

# ── GPT-4o vision for PDFs ────────────────────────────────────
from pdf2image import convert_from_path
import base64

def extract_from_pdf_vision(pdf_path: str, page: int = 1) -> str:
    """Convert PDF page to image, send to GPT-4o for extraction."""
    images = convert_from_path(pdf_path, first_page=page, last_page=page)
    img    = images[0]
    # Convert to base64
    import io
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    b64 = base64.b64encode(buf.getvalue()).decode()

    response = client.chat.completions.create(
        model    = "gpt-4o",
        messages = [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                {"type": "text", "text": "Extract all text and tables from this document page."},
            ]
        }]
    )
    return response.choices[0].message.content

# ── Structured extraction from documents ─────────────────────
import instructor
from pydantic import BaseModel

class InvoiceData(BaseModel):
    invoice_number: str
    date:           str
    vendor:         str
    line_items:     list[dict]
    total:          float

instruct_client = instructor.from_openai(OpenAI())

def extract_invoice(text: str) -> InvoiceData:
    return instruct_client.chat.completions.create(
        model          = "gpt-4o-mini",
        response_model = InvoiceData,
        messages       = [{"role": "user", "content": f"Extract invoice data:\\n{text}"}]
    )

# ── AWS Textract (enterprise OCR) ─────────────────────────────
import boto3
textract = boto3.client("textract", region_name="us-east-1")
response = textract.analyze_document(
    Document = {"S3Object": {"Bucket": "my-docs", "Name": "invoice.pdf"}},
    FeatureTypes = ["TABLES", "FORMS"],
)
# Returns structured blocks with table cells and form key-value pairs
'''
print(DOCUMENT_AI_CODE[:700])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Audio AI
# INTERVIEW: Whisper for transcription, TTS for speech output
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 4: Audio AI")
print("=" * 60)

AUDIO_CODE = '''\
from openai import OpenAI
import io

client = OpenAI()

# ── Whisper (speech-to-text) ──────────────────────────────────
# INTERVIEW: Fastest option for batch transcription
def transcribe(audio_path: str, language: str = None) -> str:
    with open(audio_path, "rb") as f:
        transcript = client.audio.transcriptions.create(
            model    = "whisper-1",
            file     = f,
            language = language,          # ISO 639-1 code, or None for auto-detect
            response_format = "json",     # json, text, srt, vtt, verbose_json
        )
    return transcript.text

# Translate to English (any language → English)
def translate_audio(audio_path: str) -> str:
    with open(audio_path, "rb") as f:
        return client.audio.translations.create(
            model = "whisper-1",
            file  = f,
        ).text

# ── TTS (text-to-speech) ──────────────────────────────────────
def text_to_speech(text: str, voice: str = "alloy") -> bytes:
    """
    INTERVIEW: Voices: alloy, echo, fable, onyx, nova, shimmer
    Models: tts-1 (fast), tts-1-hd (high quality)
    """
    response = client.audio.speech.create(
        model  = "tts-1",
        voice  = voice,       # alloy=neutral, nova=female, onyx=male
        input  = text,
        speed  = 1.0,         # 0.25–4.0
    )
    return response.content   # bytes of MP3

# Save to file
audio = text_to_speech("Hello! This is a test of text-to-speech.")
with open("output.mp3", "wb") as f:
    f.write(audio)

# ── Real-time voice (GPT-4o Audio) ────────────────────────────
# WebSocket API for low-latency voice assistants
# ws://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01
import websockets

async def realtime_voice():
    uri = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
    async with websockets.connect(
        uri,
        extra_headers = {"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}"}
    ) as ws:
        # Configure session
        await ws.send(json.dumps({
            "type":    "session.update",
            "session": {"voice": "alloy", "instructions": "You are a helpful assistant."}
        }))
        # Stream audio chunks and receive responses
        # → sub-300ms latency for voice assistant applications
'''
print(AUDIO_CODE[:700])


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Computer Use (Claude)
# INTERVIEW: Agent that controls a computer via screenshots
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 60)
print("SECTION 5: Computer Use (Claude)")
print("=" * 60)

COMPUTER_USE_CODE = '''\
import anthropic

client = anthropic.Anthropic()

# ── Computer use tools ─────────────────────────────────────────
# INTERVIEW: Claude Computer Use = agent loop with 3 special tools
COMPUTER_USE_TOOLS = [
    {
        "type":         "computer_20241022",
        "name":         "computer",
        "display_width_px":  1920,
        "display_height_px": 1080,
        "display_number":    1,
    },
    {
        "type": "bash_20241022",
        "name": "bash",
    },
    {
        "type": "text_editor_20241022",
        "name": "str_replace_editor",
    },
]

# ── Agent loop ────────────────────────────────────────────────
import subprocess

def take_screenshot() -> str:
    """Take screenshot, return as base64."""
    subprocess.run(["scrot", "/tmp/screen.png"])
    with open("/tmp/screen.png", "rb") as f:
        return base64.b64encode(f.read()).decode()

async def computer_use_agent(task: str):
    messages = [{"role": "user", "content": task}]
    while True:
        response = client.beta.messages.create(
            model      = "claude-sonnet-4-5",
            max_tokens = 4096,
            tools      = COMPUTER_USE_TOOLS,
            messages   = messages,
            betas      = ["computer-use-2024-10-22"],
        )
        if response.stop_reason == "end_turn":
            return response.content[0].text

        # Execute tool calls
        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                if block.name == "computer":
                    action = block.input["action"]
                    if action == "screenshot":
                        result = take_screenshot()
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": [{
                                "type": "image",
                                "source": {"type": "base64", "media_type": "image/png", "data": result}
                            }]
                        })
                    elif action == "left_click":
                        x, y = block.input["coordinate"]
                        subprocess.run(["xdotool", "click", "--", str(x), str(y)])
                    elif action == "type":
                        subprocess.run(["xdotool", "type", block.input["text"]])

        messages.extend([
            {"role": "assistant", "content": response.content},
            {"role": "user", "content": tool_results},
        ])
'''
print(COMPUTER_USE_CODE[:700])

print("\n  Computer Use use cases:")
print("  - Web scraping with login (bypass scraping restrictions)")
print("  - Automated software testing (real browser interaction)")
print("  - Legacy software automation (no API available)")
print("  - RPA (Robotic Process Automation) replacement")
print("  IMPORTANT: Run in sandboxed VM — never on production machine!")


print("\n" + "=" * 60)
print("SPECIALIZED AI INTERVIEW SUMMARY:")
print("  Vision: base64 encode local images, or URL for remote")
print("    GPT-4o: 'image_url' type. Claude: 'image' source type.")
print("  Code gen: generate → subprocess execute with timeout (no eval!)")
print("    E2B sandbox: isolated execution, safe for user code")
print("  Document AI: LlamaParse (complex PDFs), GPT-4o vision (scanned docs)")
print("  Audio: Whisper (transcribe), TTS (6 voices), Realtime API (<300ms)")
print("  Computer Use: Claude takes screenshots + clicks + types. Sandbox it!")
print("=" * 60)
