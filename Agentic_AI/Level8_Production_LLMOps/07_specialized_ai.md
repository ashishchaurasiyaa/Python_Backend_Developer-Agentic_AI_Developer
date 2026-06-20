# Specialized AI — Document Processing, OCR, Speech, Image Generation

## Quick Concepts
- **Document AI** = extract structured data from PDFs, tables, forms using LLMs + OCR
- **OCR** = Optical Character Recognition — image/scan → text (Tesseract=local, Google Vision=cloud)
- **Whisper** = OpenAI's speech-to-text model — open source, multilingual
- **DALL-E / Stable Diffusion** = text-to-image generation APIs
- **Web scraping + AI** = BeautifulSoup scrape → LLM parse/extract structured data

---

## Interview Questions & Answers

### Q1: PDF processing — text, tables, forms extract karna?
**Answer:**
```python
# pip install pypdf pymupdf pdfplumber unstructured[pdf] langchain

# ===== METHOD 1: PyPDF2 — simple text extraction =====
from pypdf import PdfReader

def extract_pdf_text(pdf_path: str) -> str:
    reader = PdfReader(pdf_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

# ===== METHOD 2: pymupdf (fitz) — better quality =====
import fitz  # pymupdf

def extract_with_pymupdf(pdf_path: str) -> list[dict]:
    doc = fitz.open(pdf_path)
    pages = []
    for page_num, page in enumerate(doc):
        pages.append({
            "page": page_num + 1,
            "text": page.get_text(),
            "blocks": page.get_text("blocks"),  # Text blocks with coordinates
        })
    return pages

# ===== METHOD 3: pdfplumber — best for tables =====
import pdfplumber

def extract_tables_from_pdf(pdf_path: str) -> list[list]:
    all_tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            all_tables.extend(tables)
    return all_tables

# ===== METHOD 4: Unstructured — complex documents (forms, mixed) =====
from unstructured.partition.pdf import partition_pdf
from unstructured.staging.base import elements_to_json

elements = partition_pdf(
    filename="invoice.pdf",
    strategy="hi_res",              # "fast", "ocr_only", "hi_res"
    extract_images_in_pdf=True,
    infer_table_structure=True,
)

for element in elements:
    print(type(element).__name__, element.text[:100])
    # Types: Title, NarrativeText, Table, Image, etc.

# ===== METHOD 5: LLM-based extraction =====
import anthropic
import base64

def extract_invoice_data(pdf_path: str) -> dict:
    """Use Claude to extract structured data from PDF."""
    client = anthropic.Anthropic()
    
    # Read PDF as base64
    with open(pdf_path, "rb") as f:
        pdf_data = base64.standard_b64encode(f.read()).decode("utf-8")
    
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_data,
                    }
                },
                {
                    "type": "text",
                    "text": """Extract this invoice data as JSON:
                    {
                        "invoice_number": "...",
                        "date": "YYYY-MM-DD",
                        "vendor": "...",
                        "total_amount": 0.00,
                        "line_items": [{"description": "...", "amount": 0.00}]
                    }"""
                }
            ]
        }]
    )
    import json
    return json.loads(response.content[0].text)
```

---

### Q2: OCR — image/scan to text?
**Answer:**
```python
# ===== METHOD 1: Tesseract (local, free) =====
# pip install pytesseract pillow
# brew install tesseract  (mac)

import pytesseract
from PIL import Image

def ocr_image_tesseract(image_path: str, lang: str = "eng") -> str:
    """Extract text from image using Tesseract."""
    img = Image.open(image_path)
    
    # Preprocess for better OCR
    img = img.convert("RGB")
    
    # Custom config for better accuracy
    custom_config = r"--oem 3 --psm 6"  # LSTM engine, uniform block of text
    text = pytesseract.image_to_string(img, lang=lang, config=custom_config)
    return text.strip()

# OCR with layout info
data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
# Returns bounding boxes, confidence, text per word

# ===== METHOD 2: Google Cloud Vision (cloud, accurate) =====
# pip install google-cloud-vision

from google.cloud import vision

def ocr_google_vision(image_path: str) -> str:
    client = vision.ImageAnnotatorClient()
    
    with open(image_path, "rb") as f:
        content = f.read()
    
    image = vision.Image(content=content)
    response = client.document_text_detection(image=image)
    
    full_text = response.full_text_annotation.text
    return full_text

# ===== METHOD 3: AWS Textract (forms + tables) =====
import boto3

def ocr_textract(image_path: str) -> dict:
    client = boto3.client("textract", region_name="us-east-1")
    
    with open(image_path, "rb") as f:
        document = {"Bytes": f.read()}
    
    # Detect text
    response = client.detect_document_text(Document=document)
    
    text_blocks = [
        block["Text"]
        for block in response["Blocks"]
        if block["BlockType"] == "LINE"
    ]
    return {"text": "\n".join(text_blocks)}

# For forms and tables
response = client.analyze_document(
    Document=document,
    FeatureTypes=["FORMS", "TABLES"]
)
# Returns key-value pairs for forms, structured tables

# ===== METHOD 4: Claude Vision (best for complex docs) =====
import anthropic
import base64

def ocr_claude(image_path: str) -> str:
    """Use Claude to OCR and understand complex documents."""
    client = anthropic.Anthropic()
    
    with open(image_path, "rb") as f:
        img_data = base64.standard_b64encode(f.read()).decode("utf-8")
    
    ext = image_path.split(".")[-1].lower()
    media_type = {"jpg": "image/jpeg", "jpeg": "image/jpeg", 
                  "png": "image/png", "gif": "image/gif"}.get(ext, "image/jpeg")
    
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2000,
        messages=[{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {"type": "base64", "media_type": media_type, "data": img_data}
                },
                {
                    "type": "text",
                    "text": "Extract all text from this image. Preserve formatting and structure."
                }
            ]
        }]
    )
    return response.content[0].text
```

---

### Q3: Whisper — Speech to text?
**Answer:**
```python
# ===== METHOD 1: OpenAI Whisper API =====
# pip install openai

from openai import OpenAI

client = OpenAI()

def transcribe_audio(audio_path: str, language: str = "en") -> dict:
    """Transcribe audio file using OpenAI Whisper API."""
    with open(audio_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language=language,          # ISO 639-1 code (en, hi, es)
            response_format="verbose_json",  # Includes timestamps
            timestamp_granularities=["word", "segment"],
        )
    
    return {
        "text": transcript.text,
        "language": transcript.language,
        "duration": transcript.duration,
        "segments": [
            {"start": s.start, "end": s.end, "text": s.text}
            for s in transcript.segments
        ],
        # NOTE: word-level timestamps `transcript.words` me aate hain (segments me NAHI) —
        # "word" granularity manga hai to yahan se padho:
        "words": [
            {"start": w.start, "end": w.end, "word": w.word}
            for w in (transcript.words or [])
        ],
    }

# Translation (any language → English)
def translate_to_english(audio_path: str) -> str:
    with open(audio_path, "rb") as f:
        result = client.audio.translations.create(
            model="whisper-1",
            file=f,
        )
    return result.text

# ===== METHOD 2: Local Whisper (free, private) =====
# pip install openai-whisper torch

import whisper

model = whisper.load_model("base")  # tiny, base, small, medium, large

def transcribe_local(audio_path: str) -> dict:
    result = model.transcribe(
        audio_path,
        language=None,      # Auto-detect
        task="transcribe",  # or "translate"
        fp16=False,         # Set True for GPU
    )
    return {
        "text": result["text"],
        "language": result["language"],
        "segments": result["segments"],
    }

# ===== METHOD 3: FastWhisper (4x faster) =====
# pip install faster-whisper

from faster_whisper import WhisperModel

model = WhisperModel("base", device="cpu", compute_type="int8")

def fast_transcribe(audio_path: str) -> str:
    segments, info = model.transcribe(audio_path, beam_size=5)
    return " ".join([seg.text for seg in segments])

# ===== FastAPI endpoint for audio transcription =====
from fastapi import FastAPI, UploadFile, File
import tempfile, os

app = FastAPI()

@app.post("/transcribe")
async def transcribe_endpoint(audio: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(
        suffix=f".{audio.filename.split('.')[-1]}", delete=False
    ) as tmp:
        content = await audio.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        result = transcribe_audio(tmp_path)
        return result
    finally:
        os.unlink(tmp_path)
```

---

### Q4: Image generation — DALL-E and Stable Diffusion?
**Answer:**
```python
# ===== DALL-E 3 (OpenAI) =====
from openai import OpenAI
import httpx, base64

client = OpenAI()

def generate_image_dalle(
    prompt: str,
    size: str = "1024x1024",    # 1024x1024, 1792x1024, 1024x1792
    quality: str = "standard",  # "standard" or "hd"
    style: str = "natural",     # "natural" or "vivid"
) -> str:
    """Generate image using DALL-E 3. Returns image URL."""
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size=size,
        quality=quality,
        style=style,
        n=1,
    )
    return response.data[0].url

# Edit existing image
def edit_image(image_path: str, mask_path: str, prompt: str) -> str:
    with open(image_path, "rb") as img, open(mask_path, "rb") as mask:
        response = client.images.edit(
            model="dall-e-2",
            image=img,
            mask=mask,
            prompt=prompt,
            size="1024x1024",
        )
    return response.data[0].url

# ===== Stable Diffusion via Replicate API =====
# pip install replicate

import replicate

def generate_image_sd(prompt: str, negative_prompt: str = "") -> str:
    """Generate image using Stable Diffusion XL on Replicate."""
    output = replicate.run(
        "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
        input={
            "prompt": prompt,
            "negative_prompt": negative_prompt,
            "width": 1024,
            "height": 1024,
            "num_inference_steps": 30,
            "guidance_scale": 7.5,
        }
    )
    return output[0]  # URL of generated image

# ===== Download and save generated image =====
def save_generated_image(image_url: str, save_path: str) -> str:
    response = httpx.get(image_url)
    with open(save_path, "wb") as f:
        f.write(response.content)
    return save_path
```

---

### Q5: Web scraping + AI — BeautifulSoup + LLM extraction?
**Answer:**
```python
# pip install beautifulsoup4 httpx instructor anthropic

import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel
import instructor
import anthropic

# ===== BASIC SCRAPING =====
def scrape_page(url: str) -> str:
    """Scrape webpage and return clean text."""
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; ResearchBot/1.0)"
    }
    response = httpx.get(url, headers=headers, timeout=30, follow_redirects=True)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Remove noise
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    
    return soup.get_text(separator="\n", strip=True)

# ===== LLM EXTRACTION =====
class ProductInfo(BaseModel):
    name: str
    price: float | None
    rating: float | None
    features: list[str]
    in_stock: bool

def extract_product_info(url: str) -> ProductInfo:
    """Scrape product page and extract structured data with LLM."""
    raw_text = scrape_page(url)
    
    client = instructor.from_anthropic(anthropic.Anthropic())
    
    result = client.messages.create(
        model="claude-haiku-4-5-20251001",  # Cheap model for extraction
        max_tokens=1000,
        response_model=ProductInfo,
        messages=[{
            "role": "user",
            "content": f"Extract product information from this webpage:\n\n{raw_text[:5000]}"
        }]
    )
    return result

# ===== ASYNC SCRAPING FOR MULTIPLE URLS =====
import asyncio

async def scrape_async(url: str, client: httpx.AsyncClient) -> dict:
    try:
        response = await client.get(url, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer"]):
            tag.decompose()
        return {"url": url, "text": soup.get_text(separator="\n", strip=True)[:3000]}
    except Exception as e:
        return {"url": url, "error": str(e)}

async def scrape_many(urls: list[str]) -> list[dict]:
    async with httpx.AsyncClient(headers={"User-Agent": "ResearchBot/1.0"}) as client:
        tasks = [scrape_async(url, client) for url in urls]
        return await asyncio.gather(*tasks)

# ===== ANTI-SCRAPING HANDLING =====
# For JavaScript-heavy sites: use Playwright
# pip install playwright && playwright install

from playwright.async_api import async_playwright

async def scrape_js_site(url: str) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await page.goto(url, wait_until="networkidle")
        content = await page.content()
        
        await browser.close()
        
        soup = BeautifulSoup(content, "html.parser")
        return soup.get_text(separator="\n", strip=True)
```

---

## Technology Comparison

```
DOCUMENT EXTRACTION:
  pypdf:         Simple, fast, plain text only
  pymupdf:       Better quality, layout info, images
  pdfplumber:    Best for tables
  unstructured:  Complex docs, multiple file types
  Claude/GPT-4:  Best understanding, most expensive

OCR COMPARISON:
  Tesseract:     Free, local, 90%+ accuracy clean scans
  Google Vision: 99%+ accuracy, $1.50/1000 images
  AWS Textract:  Best for forms/tables, $1.50/page
  Claude Vision: Best understanding, ~$0.01-0.10/image

SPEECH TO TEXT:
  Whisper API:   $0.006/minute, reliable, multi-language
  Local Whisper: Free, slower, runs on CPU/GPU
  Faster Whisper: 4x faster than original, same accuracy

IMAGE GENERATION:
  DALL-E 3:      Best quality, $0.04-$0.12/image
  Stable Diffusion: More customizable, open source
  Replicate:     Easy API, pay-per-use ($0.003-0.05/image)
```
