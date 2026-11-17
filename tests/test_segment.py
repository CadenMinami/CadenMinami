"""Tests for cropping the cut-out person (no neural net needed)."""
from PIL import Image

from tools.ascii_header.segment import crop_around_head


def _person() -> Image.Image:
    """Transparent canvas: a 40px-wide 'head' on top of 200px-wide 'shoulders'."""
    img = Image.new("RGBA", (300, 400), (0, 0, 0, 0))
    img.paste((220, 190, 170, 255), (80, 50, 120, 150))  # head: x 80..120, centre x=100
    img.paste((20, 20, 30, 255), (0, 150, 200, 400))  # shoulders, much wider
    return img


def test_crop_is_centred_on_the_head_not_the_shoulders() -> None:
    out = crop_around_head(_person(), width_mult=2.0, height_ratio=1.0, pad=0.0)
    # Head is 40px wide -> 80px crop centred on x=100 -> columns 60..140.
    assert out.size == (80, 80)
    # The head sits in the middle of the crop, starting at its top edge.
    assert out.getpixel((40, 0))[3] == 255
    assert out.getpixel((0, 0))[3] == 0


def test_crop_of_empty_image_returns_it_unchanged() -> None:
    img = Image.new("RGBA", (30, 30), (0, 0, 0, 0))
    assert crop_around_head(img).size == (30, 30)
