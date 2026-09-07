"""
Modern Topics — Doc 5: Multi-Modal Agents (PRACTICAL)
========================================================
Topics covered:
  1. Generating a real test image (no need to find/download one)
  2. Sending it to GPT-4o vision (OpenAI shape) — live if key set
  3. The Claude vision shape, for comparison (content-block structure differs)
  4. Document understanding — structured extraction from an image
  5. Visual QA — "what's wrong with this screenshot" pattern

Install: pip install openai pillow python-dotenv
Run: python 05_multimodal_agents_practical.py
"""

import base64
import io
import os
from dotenv import load_dotenv

load_dotenv()
HAS_KEY = bool(os.getenv("OPENAI_API_KEY"))


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 1: Generate a Real Test Image (No Download Needed)
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 1: Generating a Test Image")
print("=" * 70)


def make_invoice_image() -> bytes:
    """A synthetic 'invoice' — real pixels, real JPEG bytes, so the vision
    API call below is genuinely encoding and sending an image, not a stub."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (500, 300), color="white")
    draw = ImageDraw.Draw(img)
    draw.text((20, 20), "INVOICE", fill="black")
    draw.text((20, 60), "Vendor: Acme Corp", fill="black")
    draw.text((20, 90), "Date: 2026-08-31", fill="black")
    draw.text((20, 120), "Total: $4,500.00", fill="black")
    draw.rectangle([10, 10, 490, 290], outline="black", width=2)
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


img_bytes = make_invoice_image()
img_b64 = base64.b64encode(img_bytes).decode()
print(f"\n  Generated a {len(img_bytes)}-byte synthetic invoice image, base64-encoded to {len(img_b64)} chars.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 2: GPT-4o Vision — Live If Key Set
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 2: GPT-4o Vision Call")
print("=" * 70)


def describe_image_openai(img_b64: str, prompt: str) -> str:
    if not HAS_KEY:
        return "[NO_API_KEY — set OPENAI_API_KEY to run this live]"
    from openai import OpenAI
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
            ],
        }],
        max_tokens=200,
    )
    return response.choices[0].message.content


description = describe_image_openai(img_b64, "What's in this image? Be brief.")
print(f"\n  {description}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 3: Claude's Vision Shape — Same Idea, Different Content Blocks
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 3: Claude's Content-Block Shape (for comparison)")
print("=" * 70)

print("""
  OpenAI puts the image inside a data URL:
    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}}

  Claude splits media_type and data as separate fields, and typically puts
  the image BEFORE the text block (order matters less functionally, but
  Anthropic's own examples consistently image-then-text):
    {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": img_b64}},
    {"type": "text", "text": "Describe this image."}

  Same underlying idea (base64 image bytes + a text instruction in one turn),
  different wire format — this is exactly the kind of provider-specific
  detail LiteLLM (Level3) exists to paper over if you're calling both.
""")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 4: Document Understanding — Structured Extraction
# ─────────────────────────────────────────────────────────────────────────────

print("=" * 70)
print("SECTION 4: Structured Extraction From an Image")
print("=" * 70)


def extract_invoice_json(img_b64: str) -> str:
    if not HAS_KEY:
        return '{"vendor": "[mock — set OPENAI_API_KEY]", "total": null, "date": null}'
    from openai import OpenAI
    client = OpenAI()
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": "Extract this invoice as JSON with keys: vendor, total, date. Return ONLY the JSON."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
            ],
        }],
        max_tokens=150,
    )
    return response.choices[0].message.content


extracted = extract_invoice_json(img_b64)
print(f"\n  {extracted}")
print("\n  This is OCR + structured extraction in ONE call — no separate OCR")
print("  engine needed, because the vision model reads the pixels directly.")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 5: Visual QA Pattern
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 5: Visual QA — 'What's Wrong With This Screenshot'")
print("=" * 70)


def make_broken_code_screenshot() -> bytes:
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (500, 150), color="black")
    draw = ImageDraw.Draw(img)
    draw.text((10, 10), "def add(a, b)", fill="lightgreen")
    draw.text((10, 30), "    return a + b", fill="lightgreen")
    draw.text((10, 60), "SyntaxError: expected ':'", fill="red")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


code_img_b64 = base64.b64encode(make_broken_code_screenshot()).decode()
answer = describe_image_openai(code_img_b64, "What's the bug in this code screenshot? One sentence.")
print(f"\n  {answer}")


# ─────────────────────────────────────────────────────────────────────────────
# SECTION 6: Exercises
# ─────────────────────────────────────────────────────────────────────────────

print("\n" + "=" * 70)
print("SECTION 6: EXERCISES")
print("=" * 70)
print("""
EASY:
1. Generate a synthetic image with a deliberate typo/error and ask the model
   to find it — vary the prompt wording, does specificity change accuracy?

MEDIUM:
2. Write describe_image_claude() mirroring Section 3's shape, using the
   anthropic package — compare its output to describe_image_openai() on the
   same invoice image (needs ANTHROPIC_API_KEY too).

HARD:
3. Build a 2-image comparison prompt — generate two slightly different
   invoice images, ask the model to spot the difference between them.

PRO:
4. Extend extract_invoice_json() to validate its own output against a
   Pydantic schema (vendor: str, total: float, date: str) and retry once
   with a corrective prompt if the JSON doesn't parse or validate.
""")

if __name__ == "__main__":
    print("\nDone. Next: 07_ai_coding_tools_practical.py")
