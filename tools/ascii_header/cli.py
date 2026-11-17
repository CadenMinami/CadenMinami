"""Command-line entry point: photo in, animated header SVG out.

Example:
    python -m tools.ascii_header --photo ~/Downloads/pfp.png --out assets/header.svg

The photo is only read, never copied into the repo. The cut-out is cached
next to it (as a .png, which .gitignore excludes) so re-running to tweak the
look skips the slow neural-network step.
"""
import argparse
from dataclasses import replace
from pathlib import Path
from typing import Sequence

from PIL import Image
import pyfiglet

from .ascii import boost_local_contrast, image_to_grid
from .render_svg import HeaderText, Theme, render_header
from .segment import crop_around_head, cut_out_person

# The block-letter name is scaled down if needed so it never gets wider than this.
MAX_NAME_WIDTH = 400.0

DEFAULT_TAGLINES = [
    "CS @ UCLA",
    "tech lead @ Practice Potential",
    "constantly building",
]


def block_letters(words: Sequence[str], font: str = "ansi_regular") -> list[str]:
    """Render each word as big block letters, stacked, with blank trailing rows removed."""
    lines: list[str] = []
    for word in words:
        art = pyfiglet.figlet_format(word, font=font, width=200).rstrip("\n").split("\n")
        while art and not art[-1].strip():
            art.pop()
        if lines:
            lines.append("")
        lines += [line.rstrip() for line in art]
    return lines


def fit_name(theme: Theme, name_cols: int) -> Theme:
    """Shrink the name's font so `name_cols` characters fit in MAX_NAME_WIDTH.

    Line height equals font size so solid block characters touch vertically.
    """
    char_w = min(theme.name_char_w, MAX_NAME_WIDTH / max(1, name_cols))
    font = char_w / 0.6
    return replace(theme, name_char_w=char_w, name_font=font, name_line_h=font)


def load_cutout(photo: Path, cache: Path) -> Image.Image:
    """Return the background-removed photo, computing it only if not cached."""
    if cache.exists() and cache.stat().st_mtime >= photo.stat().st_mtime:
        return Image.open(cache).convert("RGBA")
    cutout = cut_out_person(Image.open(photo))
    cutout.save(cache)
    return cutout


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--photo", type=Path, required=True, help="portrait photo (stays local)")
    parser.add_argument("--out", type=Path, default=Path("assets/header.svg"))
    parser.add_argument("--cols", type=int, default=100, help="width of the face in characters")
    parser.add_argument("--width-mult", type=float, default=1.6, help="crop width / head width")
    parser.add_argument("--height-ratio", type=float, default=1.2, help="crop height / crop width")
    parser.add_argument("--clarity", type=float, default=2.5, help="local contrast boost (0 = off)")
    parser.add_argument("--gamma", type=float, default=0.8, help="<1 brightens midtones")
    parser.add_argument("--seed", type=int, default=7, help="fixed seed = identical output each run")
    parser.add_argument("--tagline", action="append", help="repeatable; replaces the defaults")
    parser.add_argument("--name-font", default="dos_rebel", help="any pyfiglet font name")
    args = parser.parse_args(argv)

    photo: Path = args.photo.expanduser()
    cache = photo.with_name(photo.stem + ".cutout.png")
    portrait = crop_around_head(load_cutout(photo, cache), width_mult=args.width_mult, height_ratio=args.height_ratio)
    portrait = boost_local_contrast(portrait, strength=args.clarity)
    name_lines = block_letters(["CADEN", "MINAMI"], font=args.name_font)
    theme = fit_name(Theme(), max(len(line) for line in name_lines))
    # Match the grid's proportions to the SVG's character cell so nothing stretches.
    face = image_to_grid(portrait, cols=args.cols, gamma=args.gamma, char_aspect=theme.face_char_w / theme.face_line_h)

    text = HeaderText(name_lines=name_lines, taglines=args.tagline or DEFAULT_TAGLINES)
    svg = render_header(face, text, seed=args.seed, theme=theme)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(svg, encoding="utf-8")
    print(f"wrote {args.out} ({len(svg) / 1024:.0f} KB, face {args.cols}x{len(face)})")
