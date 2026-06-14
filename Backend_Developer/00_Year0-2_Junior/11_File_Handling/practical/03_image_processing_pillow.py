"""
Image Processing with Pillow — Production Patterns for Backend Developers
==========================================================================

Covers every technique from the theory doc:
  - Open / save / format conversion
  - Resize (thumbnail + forced), crop, rotate
  - EXIF orientation fix  (critical for user uploads)
  - Multi-size thumbnail generation
  - Compression optimisation (JPEG / PNG / WebP)
  - Text watermarks
  - Filters & colour enhancements
  - EXIF stripping (privacy)
  - Mode-conversion pitfall guard (RGBA → RGB)
  - Memory-safety guard (MAX_IMAGE_PIXELS)
  - Async pipeline via ProcessPoolExecutor
  - FastAPI avatar-upload pattern (illustrative — requires FastAPI + aiobotocore)

Dependencies
------------
# pip install Pillow

Optional extras (illustrative — guarded by try/except):
# pip install pillow-simd      # 4-6x faster drop-in replacement
# pip install rembg             # ML background removal
# pip install pytesseract       # OCR  (also: brew/apt install tesseract)
# pip install imagehash         # Perceptual hashing / deduplication

Run
---
    python 03_image_processing_pillow.py

The __main__ demo creates a synthetic in-memory test image so no file on disk
is required.  Every section that touches the filesystem writes to a temp
directory and cleans up afterwards.
"""

# ==========================================================================
# IMPORTS
# ==========================================================================

import asyncio
import io
import logging
import os
import tempfile
from concurrent.futures import ProcessPoolExecutor
from functools import wraps
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# pip install Pillow
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

log = logging.getLogger(__name__)

# ==========================================================================
# 1. CONSTANTS & CONFIGURATION
# ==========================================================================

# Prevent decompression-bomb attacks — images larger than this are rejected.
# (10000 x 10000 ≈ 300 MB RAM; 50 MP is generous for user uploads.)
Image.MAX_IMAGE_PIXELS = 50_000_000

# Thumbnail size profiles used throughout the module.
THUMBNAIL_SIZES: Dict[str, Tuple[int, int]] = {
    "small":  (128, 128),
    "medium": (512, 512),
    "large":  (1024, 1024),
}

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB


# ==========================================================================
# 2. BASIC OPERATIONS — open, inspect, save, convert
# ==========================================================================

def open_image(path: str) -> Image.Image:
    """
    Open an image from disk and print its basic metadata.

    Always call ``ImageOps.exif_transpose`` on user-supplied images
    before any further processing so that phone photos appear upright.
    """
    img = Image.open(path)
    log.info(
        "Opened image: size=%s  format=%s  mode=%s",
        img.size, img.format, img.mode,
    )
    return img


def save_jpeg(img: Image.Image, path: str, quality: int = 85) -> None:
    """
    Save an image as a JPEG with sensible production defaults.

    quality=85  — sweet spot; 70-90 is the typical production range.
    optimize    — extra encoding pass shaves a few extra bytes.
    progressive — browser can render a low-res version while loading.
    """
    img.save(
        path,
        format="JPEG",
        quality=quality,
        optimize=True,
        progressive=True,
    )


def save_png(img: Image.Image, path: str) -> None:
    """Save a PNG with maximum lossless compression."""
    img.save(path, format="PNG", optimize=True, compress_level=9)


def save_webp(img: Image.Image, path: str, quality: int = 80) -> None:
    """
    Save as WebP — typically 25-35% smaller than an equivalent JPEG.

    method=6 is the slowest encoder setting but produces the smallest file.
    For real-time thumbnail generation, method=4 is a reasonable trade-off.
    """
    img.save(path, format="WEBP", quality=quality, method=6)


def convert_png_to_jpeg(png_path: str, jpeg_path: str) -> None:
    """
    Convert a PNG to JPEG.

    PNG may have an alpha channel; JPEG does not.  Compositing onto a white
    background before saving prevents a black-fill artifact.
    """
    img = Image.open(png_path)
    img = _ensure_rgb(img)
    save_jpeg(img, jpeg_path)


# ==========================================================================
# 3. MODE-CONVERSION GUARD  (pitfall #2 from theory doc)
# ==========================================================================

def _ensure_rgb(img: Image.Image) -> Image.Image:
    """
    Composite a transparent image onto a white background and return an RGB
    image.  This must be called before saving as JPEG or any format that
    does not support an alpha channel.

    Handles both RGBA (per-pixel transparency) and paletted P images.
    """
    if img.mode in ("RGBA", "P"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        mask = img.split()[-1] if img.mode == "RGBA" else None
        background.paste(img, mask=mask)
        return background
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


# ==========================================================================
# 4. EXIF ORIENTATION FIX  (critical for user uploads)
# ==========================================================================

def fix_exif_orientation(img: Image.Image) -> Image.Image:
    """
    Rotate an image according to its EXIF orientation tag.

    Phones embed rotation metadata.  Web browsers honour it automatically,
    but Pillow (and most server-side renderers) do not — so a portrait photo
    often arrives as landscape when processed raw.

    Call this as the very first step after opening any user-supplied image.
    """
    return ImageOps.exif_transpose(img)


# ==========================================================================
# 5. RESIZE OPERATIONS
# ==========================================================================

def resize_thumbnail(img: Image.Image, max_size: Tuple[int, int]) -> Image.Image:
    """
    Resize in-place so that the longest side is <= max_size, preserving the
    original aspect ratio.  Uses LANCZOS (Sinc-based) resampling, which
    gives the best quality for downscaling.

    Note: ``thumbnail`` modifies the image in-place.  Work on a copy if
    the original is still needed.
    """
    thumb = img.copy()
    thumb.thumbnail(max_size, Image.Resampling.LANCZOS)
    return thumb


def resize_force(img: Image.Image, size: Tuple[int, int]) -> Image.Image:
    """
    Force an exact output size.  This will distort the image if the aspect
    ratio does not match.  Prefer ``resize_thumbnail`` or ``center_crop``
    for public-facing assets.
    """
    return img.resize(size, Image.Resampling.LANCZOS)


def smart_crop(img: Image.Image, size: Tuple[int, int]) -> Image.Image:
    """
    Crop and resize to an exact size, centering the subject.

    ``ImageOps.fit`` picks the largest rectangle with the target aspect ratio
    from the centre of the source image, then scales to the requested size.
    Useful for user avatars and product thumbnails.
    """
    return ImageOps.fit(img, size, Image.Resampling.LANCZOS)


def center_crop_square(img: Image.Image) -> Image.Image:
    """
    Crop to a square using the centre of the image.

    Equivalent to the manual bounding-box calculation from the theory doc.
    """
    w, h = img.size
    crop_size = min(w, h)
    left  = (w - crop_size) // 2
    top   = (h - crop_size) // 2
    return img.crop((left, top, left + crop_size, top + crop_size))


def rotate_image(img: Image.Image, degrees: int, expand: bool = True) -> Image.Image:
    """
    Rotate an image by the given number of degrees counter-clockwise.

    ``expand=True`` resizes the canvas so no content is clipped.
    """
    return img.rotate(degrees, expand=expand)


# ==========================================================================
# 6. MULTI-SIZE THUMBNAIL GENERATION
# ==========================================================================

def make_thumbnails(
    input_path: str,
    output_dir: str,
    sizes: Optional[Dict[str, Tuple[int, int]]] = None,
    output_format: str = "WEBP",
) -> List[str]:
    """
    Generate multiple size variants from a source image.

    This is the standard pattern for user avatars, product images, and
    blog cover photos.  Each variant is saved as WebP for optimal web
    delivery.

    Parameters
    ----------
    input_path:    Path to the source image.
    output_dir:    Directory where variants will be written.
    sizes:         Name-to-pixel-size mapping.  Defaults to THUMBNAIL_SIZES.
    output_format: Pillow format string (WEBP, JPEG, PNG).

    Returns
    -------
    List of absolute paths to the generated files.
    """
    if sizes is None:
        sizes = THUMBNAIL_SIZES

    img = Image.open(input_path)
    img = fix_exif_orientation(img)      # must come first

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ext = output_format.lower()
    generated: List[str] = []

    for name, size in sizes.items():
        thumb = img.copy()
        thumb.thumbnail(size, Image.Resampling.LANCZOS)

        if output_format == "JPEG":
            thumb = _ensure_rgb(thumb)

        dest = str(out_dir / f"{name}.{ext}")
        if output_format == "WEBP":
            thumb.save(dest, format="WEBP", quality=80, method=6)
        elif output_format == "JPEG":
            save_jpeg(thumb, dest)
        else:
            thumb.save(dest, format=output_format)

        generated.append(dest)
        log.info("Saved thumbnail: %s  size=%s", dest, thumb.size)

    return generated


# ==========================================================================
# 7. WATERMARK
# ==========================================================================

def add_text_watermark(
    img: Image.Image,
    text: str = "© MyApp",
    opacity: int = 128,
    font_size: int = 24,
) -> Image.Image:
    """
    Composite a semi-transparent text watermark in the bottom-right corner.

    Uses the default bitmap font when a TrueType font is not available so
    the function works without any extra font files on disk.

    Parameters
    ----------
    img:       Source image (will not be mutated).
    text:      Watermark string.
    opacity:   Alpha value 0-255 (128 = 50% transparent).
    font_size: Point size when a TrueType font can be loaded.

    Returns
    -------
    A new RGBA image with the watermark composited in.
    """
    base = img.convert("RGBA")
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Prefer a system TrueType font; fall back to Pillow's built-in bitmap.
    font: ImageFont.ImageFont
    try:
        font = ImageFont.truetype("Arial.ttf", font_size)
    except IOError:
        try:
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", font_size)
        except IOError:
            font = ImageFont.load_default()

    # textbbox returns (left, top, right, bottom) relative to position (0, 0).
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    margin = 20
    pos = (base.width - text_w - margin, base.height - text_h - margin)
    draw.text(pos, text, fill=(255, 255, 255, opacity), font=font)

    watermarked = Image.alpha_composite(base, overlay)
    return watermarked


# ==========================================================================
# 8. FILTERS & COLOUR ENHANCEMENTS
# ==========================================================================

def apply_gaussian_blur(img: Image.Image, radius: float = 5.0) -> Image.Image:
    """Apply a Gaussian blur.  Common for background / depth-of-field effects."""
    return img.filter(ImageFilter.GaussianBlur(radius=radius))


def apply_sharpen(img: Image.Image) -> Image.Image:
    """Sharpen an image using the built-in kernel."""
    return img.filter(ImageFilter.SHARPEN)


def apply_edge_enhance(img: Image.Image) -> Image.Image:
    """Enhance edges — useful for scanned document processing."""
    return img.filter(ImageFilter.EDGE_ENHANCE)


def to_grayscale(img: Image.Image) -> Image.Image:
    """Convert to single-channel luminance (L mode)."""
    return img.convert("L")


def adjust_brightness(img: Image.Image, factor: float = 1.5) -> Image.Image:
    """
    Adjust brightness.

    factor < 1.0 darkens; factor > 1.0 brightens; 1.0 = no change.
    """
    return ImageEnhance.Brightness(img).enhance(factor)


def adjust_contrast(img: Image.Image, factor: float = 1.2) -> Image.Image:
    """Adjust contrast.  Useful after scanning to boost legibility."""
    return ImageEnhance.Contrast(img).enhance(factor)


def adjust_saturation(img: Image.Image, factor: float = 0.5) -> Image.Image:
    """
    Adjust colour saturation.

    factor=0.0 → grayscale; factor=1.0 → original; factor>1.0 → vivid.
    """
    return ImageEnhance.Color(img).enhance(factor)


def adjust_sharpness(img: Image.Image, factor: float = 2.0) -> Image.Image:
    """Enhance overall image sharpness."""
    return ImageEnhance.Sharpness(img).enhance(factor)


# ==========================================================================
# 9. EXIF STRIPPING  (privacy — strip before public serving)
# ==========================================================================

def strip_exif(img: Image.Image) -> Image.Image:
    """
    Return a new image with all metadata (including GPS coordinates) removed.

    Phones embed location, device model, and timestamp in EXIF.  Always strip
    this data before serving images publicly to protect user privacy.

    The technique copies raw pixel data into a brand-new Image object that
    carries no metadata at all.
    """
    data = list(img.getdata())
    clean = Image.new(img.mode, img.size)
    clean.putdata(data)
    return clean


# ==========================================================================
# 10. IN-MEMORY PIPELINE  (BytesIO — avoids disk I/O in API handlers)
# ==========================================================================

def process_upload_to_bytes(
    raw_bytes: bytes,
    output_format: str = "WEBP",
    max_size: Tuple[int, int] = (800, 800),
    quality: int = 80,
) -> bytes:
    """
    Accept raw image bytes (e.g. from an HTTP request body), validate, fix
    orientation, resize, strip EXIF, and return the processed bytes — all in
    memory with no filesystem I/O.

    Parameters
    ----------
    raw_bytes:     Bytes from ``await file.read()`` in a FastAPI handler.
    output_format: "WEBP", "JPEG", or "PNG".
    max_size:      Maximum width/height (thumbnail, preserves aspect ratio).
    quality:       Compression quality for WEBP/JPEG (ignored for PNG).

    Returns
    -------
    Processed image as raw bytes.

    Raises
    ------
    ValueError: If the bytes do not represent a valid image.
    """
    try:
        # img.verify() consumes the stream; re-open on a fresh BytesIO.
        probe = Image.open(io.BytesIO(raw_bytes))
        probe.verify()
    except Exception as exc:
        raise ValueError("Invalid or corrupt image data") from exc

    img = Image.open(io.BytesIO(raw_bytes))
    img = fix_exif_orientation(img)
    img = strip_exif(img)
    img.thumbnail(max_size, Image.Resampling.LANCZOS)

    if output_format == "JPEG":
        img = _ensure_rgb(img)

    buf = io.BytesIO()
    if output_format == "WEBP":
        img.save(buf, format="WEBP", quality=quality, method=6)
    elif output_format == "JPEG":
        img.save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
    else:
        img.save(buf, format=output_format)

    buf.seek(0)
    return buf.read()


# ==========================================================================
# 11. ASYNC PIPELINE — ProcessPoolExecutor for CPU-bound operations
# ==========================================================================

# Pillow operations are CPU-bound.  Running them in the asyncio event loop
# blocks the loop and kills throughput under concurrent requests.
# ProcessPoolExecutor is preferred over ThreadPoolExecutor because Pillow
# holds the GIL during pure-Python operations; processes bypass the GIL
# entirely and get true parallelism.

_process_pool = ProcessPoolExecutor(max_workers=min(4, (os.cpu_count() or 2)))


def _resize_sync(input_path: str, output_path: str, max_size: Tuple[int, int]) -> str:
    """
    Synchronous resize worker — intended to run inside a ProcessPoolExecutor.

    This function must be defined at module level (not as a lambda or nested
    function) so that it is picklable.
    """
    img = Image.open(input_path)
    img = ImageOps.exif_transpose(img)
    img.thumbnail(max_size, Image.Resampling.LANCZOS)
    img = _ensure_rgb(img)
    img.save(output_path, format="JPEG", quality=85, optimize=True)
    return output_path


async def resize_async(
    input_path: str,
    output_path: str,
    max_size: Tuple[int, int] = (800, 800),
) -> str:
    """
    Resize an image asynchronously without blocking the event loop.

    Offloads the CPU-bound Pillow work to a process pool so that the asyncio
    event loop remains free to serve other requests during the resize.

    Returns the output path once the resize is complete.
    """
    loop = asyncio.get_running_loop()
    result: str = await loop.run_in_executor(
        _process_pool, _resize_sync, input_path, output_path, max_size
    )
    return result


# ==========================================================================
# 12. MEMORY-SAFETY GUARD  (pitfall #1 — huge images)
# ==========================================================================

def safe_open_large(path: str, target_mode: str = "RGB") -> Image.Image:
    """
    Open a potentially very large image efficiently.

    ``Image.draft`` hints to the JPEG decoder that we want a smaller version,
    so the decoder performs only one (or two) downscale passes during decode
    rather than loading the full 300 MB and then shrinking.  This is a
    significant memory and CPU saving for high-resolution source files.

    Note: ``draft`` is a hint only — the actual decoded size may differ.
    Always call ``img.load()`` to materialise the pixel data.
    """
    img = Image.open(path)
    img.draft(target_mode, (1024, 1024))  # request ≤ 1024 px from the decoder
    img.load()
    log.info("Loaded (via draft): size=%s  mode=%s", img.size, img.mode)
    return img


# ==========================================================================
# 13. ILLUSTRATIVE PATTERNS — external libraries (guarded by try/except)
# ==========================================================================

def background_removal_example(img: Image.Image) -> Optional[Image.Image]:
    """
    Remove the background from an image using the ``rembg`` ML model.

    # pip install rembg

    Returns None if rembg is not installed.
    """
    try:
        from rembg import remove  # type: ignore[import]
        return remove(img)
    except ImportError:
        log.warning("rembg not installed — skipping background removal demo")
        return None


def ocr_example(img: Image.Image) -> Optional[str]:
    """
    Extract text from an image using Tesseract via ``pytesseract``.

    # pip install pytesseract
    # brew install tesseract   (macOS)
    # apt install tesseract-ocr  (Ubuntu)

    Returns None if pytesseract is not installed.
    """
    try:
        import pytesseract  # type: ignore[import]
        return pytesseract.image_to_string(img, lang="eng")
    except ImportError:
        log.warning("pytesseract not installed — skipping OCR demo")
        return None


def perceptual_hash_example(img: Image.Image) -> Optional[str]:
    """
    Compute a perceptual hash for duplicate / near-duplicate detection.

    # pip install imagehash

    Perceptual hashing is used for:
      - Duplicate upload detection.
      - Reverse image search.
      - NSFW filtering (compare against known-bad hash sets).

    Returns the hex hash string, or None if imagehash is not installed.
    """
    try:
        import imagehash  # type: ignore[import]
        h = imagehash.average_hash(img)
        return str(h)
    except ImportError:
        log.warning("imagehash not installed — skipping hash demo")
        return None


# ==========================================================================
# 14. FASTAPI AVATAR UPLOAD PATTERN  (illustrative — not executable here)
# ==========================================================================

FASTAPI_AVATAR_PATTERN = '''
# pip install fastapi python-multipart aiobotocore Pillow

from fastapi import Depends, FastAPI, HTTPException, UploadFile
from PIL import Image, ImageOps
import io

app = FastAPI()

AVATAR_SIZES = {"small": 128, "medium": 512, "large": 1024}

@app.post("/avatar")
async def upload_avatar(file: UploadFile, user=Depends(get_current_user)):
    # --- 1. Validate content type and size -----------------------------------
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(415, "Unsupported media type")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 10 MB)")

    # --- 2. Verify the bytes are actually a valid image ---------------------
    try:
        probe = Image.open(io.BytesIO(content))
        probe.verify()
    except Exception:
        raise HTTPException(400, "Invalid image")

    img = Image.open(io.BytesIO(content))
    img = ImageOps.exif_transpose(img)        # fix phone orientation

    # --- 3. Generate size variants ------------------------------------------
    for name, max_px in AVATAR_SIZES.items():
        thumb = img.copy()
        thumb.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)

        if thumb.mode != "RGB":
            thumb = thumb.convert("RGB")

        buf = io.BytesIO()
        thumb.save(buf, "WEBP", quality=80, method=6)
        buf.seek(0)

        key = f"avatars/{user.id}/{name}.webp"
        await s3_client.upload_fileobj(buf, "my-bucket", key)

    # --- 4. Update database -------------------------------------------------
    await db.execute(
        "UPDATE users SET avatar_updated_at = now() WHERE id = $1", user.id
    )
    return {"url": f"https://cdn.example.com/avatars/{user.id}/medium.webp"}
'''


# ==========================================================================
# 15. SELF-CONTAINED __main__ DEMO
# ==========================================================================

def _make_synthetic_image(width: int = 640, height: int = 480) -> Image.Image:
    """
    Create a synthetic RGB test image without any file on disk.

    Draws a colour gradient and a simple grid so the various resize / crop /
    filter operations produce visually distinct results.
    """
    img = Image.new("RGB", (width, height), color=(30, 30, 30))
    draw = ImageDraw.Draw(img)

    # Colour bands
    band_height = height // 6
    colours = [
        (220, 50,  50),   # red
        (50,  180, 50),   # green
        (50,  50,  220),  # blue
        (200, 180, 0),    # yellow
        (0,   180, 200),  # cyan
        (180, 0,   200),  # magenta
    ]
    for idx, colour in enumerate(colours):
        y0 = idx * band_height
        y1 = y0 + band_height
        draw.rectangle([0, y0, width, y1], fill=colour)

    # Grid overlay to make distortion visible
    for x in range(0, width, 40):
        draw.line([(x, 0), (x, height)], fill=(0, 0, 0), width=1)
    for y in range(0, height, 40):
        draw.line([(0, y), (width, y)], fill=(0, 0, 0), width=1)

    return img


def _run_demo() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # ------------------------------------------------------------------ #
        print("\n=== SECTION 1 — Synthetic test image ===")
        src = _make_synthetic_image()
        src_path = str(tmp_path / "source.png")
        src.save(src_path, format="PNG")
        print(f"  Created synthetic image: size={src.size}  mode={src.mode}")

        # ------------------------------------------------------------------ #
        print("\n=== SECTION 2 — Open & inspect ===")
        img = open_image(src_path)
        print(f"  size={img.size}  format={img.format}  mode={img.mode}")

        # ------------------------------------------------------------------ #
        print("\n=== SECTION 3 — EXIF orientation fix ===")
        img_fixed = fix_exif_orientation(img)
        print(f"  After exif_transpose: size={img_fixed.size}  (no change on synthetic image)")

        # ------------------------------------------------------------------ #
        print("\n=== SECTION 4 — Resize (thumbnail, preserving aspect ratio) ===")
        thumb = resize_thumbnail(img_fixed, (200, 200))
        print(f"  Thumbnail size: {thumb.size}")

        print("\n=== SECTION 4b — Resize (forced, may distort) ===")
        forced = resize_force(img_fixed, (300, 300))
        print(f"  Forced size: {forced.size}")

        # ------------------------------------------------------------------ #
        print("\n=== SECTION 5 — Crop operations ===")
        square = center_crop_square(img_fixed)
        print(f"  Center crop square: {square.size}")
        smart = smart_crop(img_fixed, (200, 200))
        print(f"  Smart crop (ImageOps.fit): {smart.size}")

        # ------------------------------------------------------------------ #
        print("\n=== SECTION 6 — Rotate ===")
        rotated = rotate_image(img_fixed, 90)
        print(f"  After 90° rotation: size={rotated.size}")

        # ------------------------------------------------------------------ #
        print("\n=== SECTION 7 — Format conversion (PNG → JPEG) ===")
        jpeg_path = str(tmp_path / "converted.jpg")
        convert_png_to_jpeg(src_path, jpeg_path)
        converted = Image.open(jpeg_path)
        print(f"  Saved JPEG: size={converted.size}  format={converted.format}")

        # ------------------------------------------------------------------ #
        print("\n=== SECTION 8 — Save variants (JPEG / WebP) ===")
        jpeg_out = str(tmp_path / "out.jpg")
        webp_out = str(tmp_path / "out.webp")
        save_jpeg(img_fixed, jpeg_out)
        save_webp(img_fixed, webp_out)
        print(f"  JPEG bytes: {Path(jpeg_out).stat().st_size:,}")
        print(f"  WebP bytes: {Path(webp_out).stat().st_size:,}")

        # ------------------------------------------------------------------ #
        print("\n=== SECTION 9 — Multi-size thumbnail generation ===")
        small_sizes: Dict[str, Tuple[int, int]] = {
            "small":  (64, 64),
            "medium": (200, 200),
        }
        generated = make_thumbnails(src_path, str(tmp_path / "thumbs"), sizes=small_sizes)
        for p in generated:
            info = Image.open(p)
            print(f"  {Path(p).name}: {info.size}  {Path(p).stat().st_size:,} bytes")

        # ------------------------------------------------------------------ #
        print("\n=== SECTION 10 — Watermark ===")
        watermarked = add_text_watermark(img_fixed, text="(c) DemoApp", opacity=180)
        wm_path = str(tmp_path / "watermarked.png")
        watermarked.save(wm_path, format="PNG")
        print(f"  Watermarked image mode: {watermarked.mode}  size: {watermarked.size}")

        # ------------------------------------------------------------------ #
        print("\n=== SECTION 11 — Filters & enhancements ===")
        blurred   = apply_gaussian_blur(img_fixed, radius=3)
        sharpened = apply_sharpen(img_fixed)
        gray      = to_grayscale(img_fixed)
        bright    = adjust_brightness(img_fixed, 1.4)
        contrast  = adjust_contrast(img_fixed, 1.3)
        print(f"  Blur mode={blurred.mode}  Sharpen mode={sharpened.mode}")
        print(f"  Grayscale mode={gray.mode}  Brightness mode={bright.mode}")
        print(f"  Contrast mode={contrast.mode}")

        # ------------------------------------------------------------------ #
        print("\n=== SECTION 12 — EXIF stripping (privacy) ===")
        stripped = strip_exif(img_fixed)
        print(f"  Stripped image size={stripped.size}  mode={stripped.mode}")
        print("  (EXIF / GPS metadata removed — safe for public serving)")

        # ------------------------------------------------------------------ #
        print("\n=== SECTION 13 — Mode-conversion guard (RGBA → RGB) ===")
        rgba_img = img_fixed.convert("RGBA")
        print(f"  Input mode: {rgba_img.mode}")
        rgb_img = _ensure_rgb(rgba_img)
        print(f"  After _ensure_rgb: {rgb_img.mode}")

        # ------------------------------------------------------------------ #
        print("\n=== SECTION 14 — In-memory pipeline (BytesIO) ===")
        with open(src_path, "rb") as fh:
            raw = fh.read()
        out_bytes = process_upload_to_bytes(raw, output_format="WEBP", max_size=(200, 200))
        print(f"  Input bytes: {len(raw):,}  →  Output WebP bytes: {len(out_bytes):,}")

        # ------------------------------------------------------------------ #
        print("\n=== SECTION 15 — Async resize via ProcessPoolExecutor ===")
        async_src = str(tmp_path / "async_source.jpg")
        async_dst = str(tmp_path / "async_output.jpg")
        save_jpeg(img_fixed, async_src)

        async def _demo_async() -> None:
            result = await resize_async(async_src, async_dst, max_size=(150, 150))
            info = Image.open(result)
            print(f"  Async resize output: {info.size}  {Path(result).stat().st_size:,} bytes")

        asyncio.run(_demo_async())

        # ------------------------------------------------------------------ #
        print("\n=== SECTION 16 — Optional-library demos (graceful degradation) ===")
        bg_result   = background_removal_example(img_fixed)
        ocr_result  = ocr_example(img_fixed)
        hash_result = perceptual_hash_example(img_fixed)
        print(f"  background removal: {'ok' if bg_result else 'skipped (rembg not installed)'}")
        print(f"  OCR:                {'ok' if ocr_result else 'skipped (pytesseract not installed)'}")
        print(f"  perceptual hash:    {hash_result if hash_result else 'skipped (imagehash not installed)'}")

        # ------------------------------------------------------------------ #
        print("\n=== SECTION 17 — Common pitfalls summary ===")
        pitfalls = [
            "1. Loading huge images into memory  → use Image.MAX_IMAGE_PIXELS + img.draft()",
            "2. Not converting RGBA/P to RGB before JPEG save  → use _ensure_rgb()",
            "3. Skipping EXIF transpose  → photos appear sideways on server",
            "4. Using JPEG for screenshots/line art  → artifacts; prefer PNG/WebP",
            "5. Not stripping metadata for public images  → GPS privacy leak",
            "6. quality=95+ on JPEG  → diminishing returns; 80-85 is the sweet spot",
            "7. Pillow in main async event loop  → blocks; use ProcessPoolExecutor",
        ]
        for p in pitfalls:
            print(f"  {p}")

    print("\nAll sections completed successfully.  Temp files cleaned up.")


if __name__ == "__main__":
    _run_demo()
