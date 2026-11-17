"""Turn a cut-out portrait (RGBA image) into rows of ASCII characters."""
from PIL import Image, ImageFilter
import numpy as np

# Characters ordered from "light ink" to "heavy ink". The header is drawn as
# light text on a dark panel, so brighter pixels get heavier characters.
# There is deliberately no space here: every pixel that belongs to the person
# must stay visible, even the darkest parts of the suit.
FOREGROUND_RAMP = ".:-=+*#%@"

# A monospace character cell is roughly twice as tall as it is wide, so we
# use about half as many rows as columns to keep the face from stretching.
DEFAULT_CHAR_ASPECT = 0.5

# A pixel counts as "part of the person" once it is at least this opaque.
ALPHA_THRESHOLD = 128


def image_to_grid(
    img: Image.Image,
    cols: int,
    char_aspect: float = DEFAULT_CHAR_ASPECT,
    ramp: str = FOREGROUND_RAMP,
    gamma: float = 1.0,
) -> list[str]:
    """Convert an RGBA image to `rows` strings of exactly `cols` characters.

    Transparent pixels (the removed background) become spaces. Opaque pixels
    are mapped to `ramp` by brightness, after stretching the person's own
    brightness range to use the full ramp. `gamma` < 1 brightens midtones.
    """
    rgba = img.convert("RGBA")
    rows = max(1, round(rgba.height / rgba.width * cols * char_aspect))
    small = rgba.resize((cols, rows), Image.Resampling.LANCZOS)

    pixels = np.asarray(small, dtype=np.float64)
    luminance = pixels[..., :3] @ np.array([0.299, 0.587, 0.114])
    opaque = pixels[..., 3] >= ALPHA_THRESHOLD

    levels = _stretch_contrast(luminance, opaque)
    levels = levels**gamma
    indices = np.clip((levels * len(ramp)).astype(int), 0, len(ramp) - 1)

    return [
        "".join(ramp[indices[r, c]] if opaque[r, c] else " " for c in range(cols))
        for r in range(rows)
    ]


def _stretch_contrast(luminance: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Rescale luminance to 0..1 using only the person's pixels.

    Using the 2nd-98th percentile (instead of min/max) stops one shiny pixel
    from flattening everything else. If the person is one flat colour there is
    no range to stretch, so we fall back to plain 0..255 brightness.
    """
    if not mask.any():
        return np.zeros_like(luminance)
    lo, hi = np.percentile(luminance[mask], [2, 98])
    if hi - lo < 1e-6:
        return np.clip(luminance / 255.0, 0.0, 1.0)
    return np.clip((luminance - lo) / (hi - lo), 0.0, 1.0)


def boost_local_contrast(img: Image.Image, strength: float = 2.5, radius_frac: float = 0.03) -> Image.Image:
    """Exaggerate small details (eyes, brows, lips) relative to their surroundings.

    We blur the image to get its broad shading, subtract that to isolate the
    fine detail, then add the detail back `strength` times over. This is the
    "clarity" slider in photo editors. Without it, features that differ from
    the surrounding skin by only a few shades of grey all collapse into the
    same character. Returns a greyscale RGBA image with the original alpha.
    """
    rgba = img.convert("RGBA")
    grey = rgba.convert("L")
    radius = float(max(1.0, rgba.width * radius_frac))
    lum = np.asarray(grey, dtype=np.float64)
    blurred = np.asarray(grey.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float64)
    boosted = np.clip(lum + strength * (lum - blurred), 0, 255).astype(np.uint8)
    out = Image.fromarray(boosted, mode="L").convert("RGBA")
    out.putalpha(rgba.getchannel("A"))
    return out
