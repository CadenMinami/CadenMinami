"""Cut the person out of a photo and crop to a portrait framed around the head."""
from PIL import Image
import numpy as np

# rembg ships several models; this one is trained specifically to separate
# people from busy backgrounds (like the library arches in my photo).
DEFAULT_MODEL = "u2net_human_seg"

# The top ~22% of the person (from the crown down) is treated as "the head".
# That band is used only to find where the head is and how wide it is.
HEAD_BAND = 0.22


def cut_out_person(photo: Image.Image, model_name: str = DEFAULT_MODEL) -> Image.Image:
    """Return an RGBA copy of `photo` where everything except the person is transparent.

    rembg is imported here rather than at the top of the file because it loads
    a ~170 MB neural network. Tests and CI never need it, so they never pay that cost.
    """
    from rembg import new_session, remove  # heavy, optional dependency

    session = new_session(model_name)
    result = remove(photo.convert("RGB"), session=session)
    assert isinstance(result, Image.Image)
    return result.convert("RGBA")


def crop_around_head(
    cutout: Image.Image,
    width_mult: float = 1.6,
    height_ratio: float = 1.2,
    pad: float = 0.03,
) -> Image.Image:
    """Crop a portrait centred on the head.

    The crop is `width_mult` times the head's width (so the face fills most of
    the frame instead of being dwarfed by the shoulders), and `height_ratio`
    times as tall as it is wide, starting just above the top of the hair.
    """
    opaque = np.asarray(cutout.getchannel("A")) >= 128
    rows = np.nonzero(opaque.any(axis=1))[0]
    if rows.size == 0:
        return cutout
    top, bottom = int(rows[0]), int(rows[-1])

    band = opaque[top : top + max(1, round((bottom - top + 1) * HEAD_BAND))]
    head_cols = np.nonzero(band.any(axis=0))[0]
    head_left, head_right = int(head_cols[0]), int(head_cols[-1]) + 1
    centre = (head_left + head_right) / 2
    width = (head_right - head_left) * width_mult
    margin = round(width * pad)

    box = (
        round(centre - width / 2),
        top - margin,
        round(centre + width / 2),
        top - margin + round(width * height_ratio),
    )
    # Image.crop pads anything outside the photo with transparent pixels,
    # which become spaces in the ASCII, so going past an edge is harmless.
    return cutout.crop(box)
