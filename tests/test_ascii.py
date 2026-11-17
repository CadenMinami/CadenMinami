"""Tests for turning a cut-out portrait into a grid of characters."""
from PIL import Image

from tools.ascii_header.ascii import FOREGROUND_RAMP, image_to_grid


def _solid(width: int, height: int, rgba: tuple[int, int, int, int]) -> Image.Image:
    return Image.new("RGBA", (width, height), rgba)


def test_transparent_pixels_become_spaces() -> None:
    grid = image_to_grid(_solid(40, 40, (255, 255, 255, 0)), cols=10)
    assert all(set(row) <= {" "} for row in grid)


def test_opaque_pixels_never_become_spaces() -> None:
    # Even a pure-black opaque area (a dark suit) must stay visible.
    grid = image_to_grid(_solid(40, 40, (0, 0, 0, 255)), cols=10)
    assert all(" " not in row for row in grid)


def test_row_count_corrects_for_tall_characters() -> None:
    # A square image with 20 columns should get ~10 rows, because a monospace
    # character cell is about twice as tall as it is wide.
    grid = image_to_grid(_solid(100, 100, (128, 128, 128, 255)), cols=20)
    assert len(grid) == 10
    assert all(len(row) == 20 for row in grid)


def test_brighter_pixels_get_denser_characters() -> None:
    # Left half dark, right half bright -> right side uses later ramp characters.
    img = Image.new("RGBA", (40, 20), (20, 20, 20, 255))
    img.paste((235, 235, 235, 255), (20, 0, 40, 20))
    row = image_to_grid(img, cols=8)[0]
    left, right = row[:4], row[4:]
    assert max(FOREGROUND_RAMP.index(c) for c in left) < min(FOREGROUND_RAMP.index(c) for c in right)


def test_local_contrast_boost_exaggerates_small_details() -> None:
    from tools.ascii_header.ascii import boost_local_contrast

    # A faint dark spot (an "eye") on a bright face: the boost should widen the gap.
    img = Image.new("RGBA", (100, 100), (200, 200, 200, 255))
    img.paste((180, 180, 180, 255), (45, 45, 55, 55))
    before = img.getpixel((10, 10))[0] - img.getpixel((50, 50))[0]
    out = boost_local_contrast(img, strength=2.0, radius_frac=0.05)
    after = out.getpixel((10, 10))[0] - out.getpixel((50, 50))[0]
    assert after > before
    assert out.getchannel("A").getextrema() == (255, 255)  # transparency untouched
