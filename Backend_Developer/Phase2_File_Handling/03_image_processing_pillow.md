# 03 — Image Processing with Pillow

> Resize, crop, optimize, watermark images server-side. Standard pattern for any app handling user-uploaded images.

---

## Setup

```bash
pip install Pillow
```

```python
from PIL import Image, ImageOps, ImageFilter, ImageDraw, ImageFont
```

---

## Basic Operations

### Open & save
```python
img = Image.open("input.jpg")
print(img.size, img.format, img.mode)   # (1920, 1080) JPEG RGB

img.save("output.jpg", quality=85, optimize=True)
img.save("output.webp", quality=80)
```

### Resize
```python
# Preserve aspect ratio (best)
img.thumbnail((800, 800))   # in-place modify; longest side = 800
img.save("thumb.jpg")

# Force size (may distort)
img.resize((800, 600), Image.Resampling.LANCZOS)
```

### Crop
```python
# Center crop
w, h = img.size
crop_size = min(w, h)
left = (w - crop_size) // 2
top = (h - crop_size) // 2
img.crop((left, top, left + crop_size, top + crop_size))

# Smart crop (ImageOps.fit)
fit = ImageOps.fit(img, (400, 400), Image.Resampling.LANCZOS)
```

### Rotate
```python
rotated = img.rotate(90, expand=True)
```

### Format conversion
```python
img = Image.open("input.png")
img.convert("RGB").save("output.jpg")   # PNG → JPG
```

---

## EXIF Orientation Fix

Phones embed orientation metadata. Web browsers honor it; raw rendering doesn't.

```python
from PIL import ImageOps

img = Image.open("phone-photo.jpg")
img = ImageOps.exif_transpose(img)   # rotates based on EXIF
```

**Always do this** for user uploads. Otherwise photos show sideways.

---

## Generate Multiple Sizes (Thumbnails)

```python
SIZES = {
    "small": (128, 128),
    "medium": (512, 512),
    "large": (1024, 1024)
}

def make_thumbnails(input_path, output_dir):
    img = Image.open(input_path)
    img = ImageOps.exif_transpose(img)

    for name, size in SIZES.items():
        thumb = img.copy()
        thumb.thumbnail(size, Image.Resampling.LANCZOS)
        thumb.save(f"{output_dir}/{name}.webp", quality=80)
```

For user avatars / product images / blog covers.

---

## Compression & Optimization

### JPEG
```python
img.save("output.jpg", quality=85, optimize=True, progressive=True)
```
- `quality=85`: sweet spot. 70-90 typical.
- `optimize=True`: extra encoding pass.
- `progressive=True`: progressive rendering in browser.

### PNG
```python
img.save("output.png", optimize=True, compress_level=9)
```

### WebP (modern, 25-35% smaller)
```python
img.save("output.webp", quality=80, method=6)  # method 0=fast, 6=best
```

### AVIF (next-gen, 50% smaller than JPEG)
Requires `pillow-avif-plugin`.
```python
img.save("output.avif", quality=70)
```

---

## Watermarks

```python
def add_watermark(img_path, output_path, text="© MyApp"):
    img = Image.open(img_path).convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    font = ImageFont.truetype("Arial.ttf", 24)

    # Position bottom-right
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    pos = (img.width - text_width - 20, img.height - text_height - 20)

    draw.text(pos, text, fill=(255, 255, 255, 128), font=font)

    img.paste(overlay, (0, 0), overlay)
    img.convert("RGB").save(output_path, "JPEG", quality=85)
```

---

## Filters & Effects

```python
img.filter(ImageFilter.BLUR)
img.filter(ImageFilter.GaussianBlur(radius=5))
img.filter(ImageFilter.SHARPEN)
img.filter(ImageFilter.EDGE_ENHANCE)
img.filter(ImageFilter.SMOOTH)
```

### Grayscale
```python
gray = img.convert("L")
```

### Color adjustments
```python
from PIL import ImageEnhance

ImageEnhance.Brightness(img).enhance(1.5)
ImageEnhance.Contrast(img).enhance(1.2)
ImageEnhance.Color(img).enhance(0.5)   # 0 = grayscale
ImageEnhance.Sharpness(img).enhance(2.0)
```

---

## Background Removal

### With `rembg` library
```bash
pip install rembg
```

```python
from rembg import remove
from PIL import Image
import io

input_img = Image.open("photo.jpg")
output_img = remove(input_img)
output_img.save("no_bg.png")
```

ML-based, accurate for portraits/objects.

---

## OCR (Text Extraction)

```bash
brew install tesseract   # macOS
apt install tesseract-ocr   # Ubuntu
pip install pytesseract
```

```python
import pytesseract

img = Image.open("receipt.jpg")
text = pytesseract.image_to_string(img, lang="eng")
```

For receipts, IDs, document scanning.

---

## Image Hashing (Deduplication)

```bash
pip install imagehash
```

```python
import imagehash

hash1 = imagehash.average_hash(Image.open("photo1.jpg"))
hash2 = imagehash.average_hash(Image.open("photo2.jpg"))

diff = hash1 - hash2   # Hamming distance
if diff < 5: print("Similar images")
```

Use for:
- Duplicate upload detection.
- Reverse image search.
- NSFW image filtering (compared against known hashes).

---

## Async Processing

Pillow is sync. For high-throughput:

```python
import asyncio
from concurrent.futures import ProcessPoolExecutor

executor = ProcessPoolExecutor(max_workers=4)

async def resize_async(input_path, output_path, size):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(executor, resize_sync, input_path, output_path, size)

def resize_sync(input_path, output_path, size):
    img = Image.open(input_path)
    img = ImageOps.exif_transpose(img)
    img.thumbnail(size, Image.Resampling.LANCZOS)
    img.save(output_path, quality=85)
```

Use ProcessPool (not ThreadPool) because Pillow operations are CPU-bound (release GIL during native ops, but ProcessPool is safer).

---

## Pillow-SIMD (Faster Pillow)

Drop-in replacement using SIMD instructions. 4-6x faster for resize/blur.

```bash
pip uninstall pillow
pip install pillow-simd
```

For high-volume image processing pipelines.

---

## Server-Side Image Pipeline

Full pattern for user avatar upload:

```python
@app.post("/avatar")
async def upload_avatar(file: UploadFile, user=Depends(get_user)):
    # 1. Validate
    if file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
        raise HTTPException(415)

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413)

    # 2. Open & validate it's actually an image
    try:
        img = Image.open(io.BytesIO(content))
        img.verify()  # ensures valid
    except Exception:
        raise HTTPException(400, "Invalid image")

    img = Image.open(io.BytesIO(content))
    img = ImageOps.exif_transpose(img)

    # 3. Generate sizes
    sizes = {"small": 128, "medium": 512, "large": 1024}
    for name, max_size in sizes.items():
        thumb = img.copy()
        thumb.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        if thumb.mode != "RGB":
            thumb = thumb.convert("RGB")

        buf = io.BytesIO()
        thumb.save(buf, "WEBP", quality=80, method=6)
        buf.seek(0)

        key = f"avatars/{user.id}/{name}.webp"
        await s3.upload_fileobj(buf, "my-bucket", key)

    # 4. Update DB
    await db.execute(
        "UPDATE users SET avatar_updated_at = now() WHERE id = $1",
        user.id
    )
    return {"url": f"https://cdn.example.com/avatars/{user.id}/medium.webp"}
```

---

## ImageMagick (Alternative)

For complex operations, ImageMagick CLI is sometimes better.

```bash
convert input.jpg -resize 800x800 -quality 85 output.jpg
convert input.jpg -auto-orient output.jpg
convert input.pdf[0] output.png   # PDF first page to image
```

Python wrapper: `Wand`.
```python
from wand.image import Image as WandImage

with WandImage(filename="input.jpg") as img:
    img.resize(800, 600)
    img.save(filename="output.jpg")
```

Use when:
- Need PDF rendering.
- Complex compositions.
- Color profile management.

---

## CDN On-The-Fly Resizing

Instead of pre-generating sizes, let CDN do it:

### Cloudflare Image Resizing
```
https://example.com/cdn-cgi/image/width=800,quality=85/photo.jpg
```

### Imgix / Cloudinary
```
https://imgix.net/photo.jpg?w=800&h=600&fit=crop
```

Trade-offs:
- ✓ Less storage (one master).
- ✓ Any size on demand.
- ✗ Cost per transformation.
- ✗ Tied to CDN provider.

Best for: SaaS with many image variants.

Pre-generated thumbnails: better for stable use cases.

---

## NSFW / Content Moderation

Use ML model:
- AWS Rekognition.
- Google Cloud Vision.
- OpenNSFW (Yahoo's open-source model).
- NudeNet.

```python
from nudenet import NudeDetector

detector = NudeDetector()
result = detector.detect("uploaded.jpg")
# Flags: BUTTOCKS_EXPOSED, FEMALE_GENITALIA_EXPOSED, etc.
```

Run on upload; reject if flagged.

---

## EXIF Stripping (Privacy)

Photos often include GPS coordinates, device info. Strip before public serving.

```python
from PIL import Image

img = Image.open("phone-photo.jpg")
data = list(img.getdata())
clean = Image.new(img.mode, img.size)
clean.putdata(data)
clean.save("public.jpg")
```

Or use:
```bash
exiftool -all= input.jpg
```

---

## Common Pitfalls

### 1. Loading huge images into memory
A 10000x10000 image is 300MB RAM. Resize on load:
```python
Image.MAX_IMAGE_PIXELS = 50000000   # safety limit
img = Image.open(path)
img.draft("RGB", (1024, 1024))   # ask decoder for smaller version
img.load()
```

### 2. Not converting modes
PNG with alpha → JPG → looks weird. Convert to RGB first.
```python
if img.mode in ("RGBA", "P"):
    bg = Image.new("RGB", img.size, (255, 255, 255))
    bg.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
    img = bg
```

### 3. Skipping EXIF transpose
Photos appear rotated.

### 4. Using JPG for screenshots / line art
PNG/WebP better. JPG creates artifacts on sharp edges.

### 5. Not stripping metadata for public images
Privacy leak.

### 6. Quality 95+ on JPG
Diminishing returns. 80-85 is sweet spot.

### 7. PIL in main async event loop
Blocks for seconds. Use ProcessPoolExecutor.

---

## File Format Cheat Sheet

| Format | When |
|---|---|
| JPG | Photos, social media |
| PNG | Screenshots, logos, transparency |
| WebP | Modern web (smaller than JPG/PNG) |
| AVIF | Future-proof (even smaller, less support) |
| GIF | Animation (or use MP4/WebM if not animated) |
| SVG | Icons, scalable graphics |
| HEIC | iPhone native (convert to JPG/WebP for web) |

---

## TL;DR

- Pillow is the workhorse for Python image processing.
- Always `ImageOps.exif_transpose` for user uploads.
- Pre-generate multiple sizes (thumbnails).
- WebP / AVIF for modern web.
- Strip EXIF for privacy.
- ProcessPoolExecutor for async pipelines.
- Pillow-SIMD for 4-6x speedup.
- CDN on-the-fly resize for variable sizes.
- NSFW detection mandatory for UGC platforms.
