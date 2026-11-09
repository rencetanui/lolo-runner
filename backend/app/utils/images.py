import io

from PIL import Image, ImageOps

MAX_PIXELS = 40_000_000
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
MIN_WIDTH, MIN_HEIGHT = 600, 300


class ImageError(Exception):
    pass


def _jpeg(im: Image.Image, quality: int) -> bytes:
    out = io.BytesIO()
    im.save(out, "JPEG", quality=quality, optimize=True, progressive=True)
    return out.getvalue()


def _flatten(im: Image.Image) -> Image.Image:
    """Transparent PNGs get a white background instead of black."""
    if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
        rgba = im.convert("RGBA")
        base = Image.new("RGB", rgba.size, (255, 255, 255))
        base.paste(rgba, mask=rgba.split()[-1])
        return base
    return im.convert("RGB")


def process_banner(data: bytes) -> tuple[bytes, bytes]:
    """Return (banner, share image) as JPEGs. Raises ImageError for anything that isn't a usable photo."""
    try:
        Image.open(io.BytesIO(data)).verify()
        im = Image.open(io.BytesIO(data))               # verify() leaves the image unusable, so reopen
        if im.format not in ALLOWED_FORMATS:
            raise ImageError("Please upload a JPEG, PNG or WebP image.")
        if im.width * im.height > MAX_PIXELS:
            raise ImageError("That image has too many pixels. Please resize it first.")
        im = ImageOps.exif_transpose(im)                # honour the phone's rotation, then drop every bit of metadata
        im = _flatten(im)
    except ImageError:
        raise
    except Exception:
        raise ImageError("That file isn't a valid image.")
    if im.width < MIN_WIDTH or im.height < MIN_HEIGHT:
        raise ImageError(f"The image is too small. Use at least {MIN_WIDTH}×{MIN_HEIGHT} pixels.")
    banner = im.copy()
    banner.thumbnail((1600, 1600), Image.LANCZOS)
    share = ImageOps.fit(im, (1200, 630), Image.LANCZOS, centering=(0.5, 0.5))
    return _jpeg(banner, 85), _jpeg(share, 80)