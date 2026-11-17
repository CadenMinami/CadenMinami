"""Render the ASCII face + name as a self-contained, animated SVG.

How the animation works (no JavaScript, because GitHub strips it):
every row of text is drawn several times on top of itself. A few copies are
"scrambled" (random characters in the same shape) and flash on for a split
second each; then the real row switches on and stays. Staggering the start
time row by row makes the picture "decode" from top to bottom. A faint
scanline then sweeps over the face forever.
"""
from dataclasses import dataclass
import random
from typing import Sequence
from xml.sax.saxutils import escape

# Characters used while a row is still "decoding".
FACE_SCRAMBLE_CHARS = "!#$%&*+-=?@^~<>/\\|01"
NAME_SCRAMBLE_CHARS = "█▓▒░╔╗╚╝═║"


@dataclass(frozen=True)
class HeaderText:
    """Everything on the right-hand side of the header."""

    name_lines: Sequence[str]  # pre-rendered block-letter art, one string per line
    taglines: Sequence[str]  # short lines shown after a "> " prompt
    title: str = "Caden Minami"  # read by screen readers instead of the ASCII art
    window_title: str = "caden@ucla: ~"


@dataclass(frozen=True)
class Theme:
    """Colours and sizes. Pixel values are in SVG user units."""

    panel: str = "#0d1117"
    border: str = "#30363d"
    face: str = "#e6edf3"
    scramble: str = "#3fb950"
    # The name is painted with a left-to-right gradient (UCLA blue -> gold).
    name_gradient: tuple[str, ...] = ("#4fa3ff", "#8f7bff", "#ffd100")
    name_glow: float = 2.2  # blur radius of the neon glow; 0 turns it off
    shine_period: float = 3.5  # seconds per shimmer sweep across the name
    prompt: str = "#d29922"
    tagline: str = "#8b949e"
    face_font: float = 8.0
    face_char_w: float = 4.8  # monospace glyphs are ~0.6em wide
    face_line_h: float = 8.8
    name_font: float = 11.0
    name_char_w: float = 6.6
    name_line_h: float = 11.0  # equal to the font size so block letters have no gaps
    tag_font: float = 14.0
    tag_char_w: float = 8.4
    tag_line_h: float = 24.0
    pad: float = 28.0
    titlebar_h: float = 30.0
    gap: float = 40.0


@dataclass(frozen=True)
class Timing:
    """Seconds. Tuned so the whole header settles in about 3 seconds."""

    row_stagger: float = 0.03  # delay between consecutive face rows starting
    flicker: float = 0.08  # how long each scrambled frame is visible
    name_start: float = 0.4
    name_stagger: float = 0.07
    tagline_gap: float = 0.35
    scan_period: float = 4.0


FONT_STACK = "ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace"


def render_header(
    face: Sequence[str],
    text: HeaderText,
    *,
    seed: int = 0,
    scramble_frames: int = 3,
    theme: Theme | None = None,
    timing: Timing | None = None,
) -> str:
    """Return the full SVG document as a string."""
    th = theme or Theme()
    tm = timing or Timing()
    rng = random.Random(seed)

    face_cols = max((len(r) for r in face), default=0)
    face_w = face_cols * th.face_char_w
    face_h = len(face) * th.face_line_h

    name_cols = max((len(r) for r in text.name_lines), default=0)
    name_w = name_cols * th.name_char_w
    name_h = len(text.name_lines) * th.name_line_h
    tag_cols = max((len(t) + 2 for t in text.taglines), default=0)
    tag_w = tag_cols * th.tag_char_w
    right_w = max(name_w, tag_w)
    right_h = name_h + th.tag_line_h * (len(text.taglines) + 1)

    body_h = max(face_h, right_h)
    width = th.pad * 2 + face_w + th.gap + right_w
    height = th.titlebar_h + th.pad * 2 + body_h

    face_x = th.pad
    face_y = th.titlebar_h + th.pad + (body_h - face_h) / 2
    right_x = face_x + face_w + th.gap
    right_y = th.titlebar_h + th.pad + (body_h - right_h) / 2

    parts: list[str] = []

    # --- Face: decode rows top to bottom ----------------------------------
    for i, row in enumerate(face):
        y = face_y + (i + 1) * th.face_line_h
        start = i * tm.row_stagger
        parts += _decoding_row(
            row, i, face_x, y, start, scramble_frames, tm.flicker,
            th.face_char_w, FACE_SCRAMBLE_CHARS, rng, "face",
        )
    face_done = (len(face) - 1) * tm.row_stagger + scramble_frames * tm.flicker if face else 0.0

    # --- Name (block letters) ---------------------------------------------
    for i, row in enumerate(text.name_lines):
        y = right_y + (i + 1) * th.name_line_h
        start = tm.name_start + i * tm.name_stagger
        parts += _decoding_row(
            row, i, right_x, y, start, scramble_frames, tm.flicker,
            th.name_char_w, NAME_SCRAMBLE_CHARS, rng, "name",
        )
    name_done = tm.name_start + len(text.name_lines) * tm.name_stagger + scramble_frames * tm.flicker

    # Shimmer: a copy of each name line painted with a moving white highlight,
    # switched on only once the name has fully decoded.
    for i, row in enumerate(text.name_lines):
        y = right_y + (i + 1) * th.name_line_h
        length = f'textLength="{len(row) * th.name_char_w:.1f}" lengthAdjust="spacingAndGlyphs"' if row.strip() else ""
        parts.append(
            f'<text class="name name-shine f" x="{right_x:.1f}" y="{y:.1f}" {length} fill="url(#shine)" '
            f'style="animation-delay:{name_done:.2f}s">{escape(row)}</text>'
        )

    # --- Taglines: "> text", each decoding after the previous -------------
    tag_y0 = right_y + name_h + th.tag_line_h
    last_tag_start = name_done
    for i, line in enumerate(text.taglines):
        y = tag_y0 + (i + 1) * th.tag_line_h - th.tag_line_h / 2
        start = name_done + i * tm.tagline_gap
        last_tag_start = start
        parts.append(
            f'<text class="p" x="{right_x:.1f}" y="{y:.1f}" style="animation-delay:{start:.2f}s">&gt;</text>'
        )
        parts += _decoding_row(
            line, i, right_x + 2 * th.tag_char_w, y, start, scramble_frames, tm.flicker,
            th.tag_char_w, FACE_SCRAMBLE_CHARS, rng, "tag",
        )
    all_done = max(face_done, last_tag_start + scramble_frames * tm.flicker)

    # Blinking cursor after the last tagline.
    if text.taglines:
        last = text.taglines[-1]
        cx = right_x + (len(last) + 3) * th.tag_char_w
        cy = tag_y0 + len(text.taglines) * th.tag_line_h - th.tag_line_h / 2
        parts.append(
            f'<rect class="cursor" x="{cx:.1f}" y="{cy - th.tag_font * 0.8:.1f}" '
            f'width="{th.tag_char_w:.1f}" height="{th.tag_font:.1f}" '
            f'style="animation-delay:{all_done:.2f}s"/>'
        )

    # Scanline sweeping over the face once everything has settled (SMIL, so
    # it runs inside GitHub's <img> sandbox without any script).
    scan = (
        f'<rect class="scan" x="{face_x:.1f}" y="{face_y:.1f}" width="{face_w:.1f}" height="14" '
        f'fill="url(#scan)" opacity="0">'
        f'<set attributeName="opacity" to="1" begin="{all_done:.2f}s"/>'
        f'<animate attributeName="y" from="{face_y - 14:.1f}" to="{face_y + face_h:.1f}" '
        f'dur="{tm.scan_period}s" begin="{all_done:.2f}s" repeatCount="indefinite"/>'
        f"</rect>"
    )

    css = _css(th, tm.flicker)
    defs = _name_defs(th, right_x, name_w, name_done)
    titlebar = _titlebar(width, th, text.window_title)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" '
        f'width="{width:.0f}" height="{height:.0f}" role="img" aria-label="{escape(text.title)}" '
        f'xml:space="preserve">'
        f"<title>{escape(text.title)}</title>"
        f"<defs>{defs}<linearGradient id=\"scan\" x1=\"0\" y1=\"0\" x2=\"0\" y2=\"1\">"
        f'<stop offset="0" stop-color="{th.scramble}" stop-opacity="0"/>'
        f'<stop offset="0.5" stop-color="{th.scramble}" stop-opacity="0.18"/>'
        f'<stop offset="1" stop-color="{th.scramble}" stop-opacity="0"/>'
        f"</linearGradient></defs>"
        f"<style>{css}</style>"
        f'<rect x="0.5" y="0.5" width="{width - 1:.0f}" height="{height - 1:.0f}" rx="12" '
        f'fill="{th.panel}" stroke="{th.border}"/>'
        f"{titlebar}"
        + "".join(parts)
        + scan
        + "</svg>"
    )


def _decoding_row(
    row: str,
    index: int,
    x: float,
    y: float,
    start: float,
    frames: int,
    flicker: float,
    char_w: float,
    charset: str,
    rng: random.Random,
    kind: str,
) -> list[str]:
    """One row = `frames` scrambled copies that flash briefly, then the real text."""
    out: list[str] = []
    # textLength pins each row to an exact width, so columns line up even if
    # the viewer's monospace font is slightly wider or narrower than ours.
    length = f'textLength="{len(row) * char_w:.1f}" lengthAdjust="spacingAndGlyphs"' if row.strip() else ""
    for f in range(frames):
        scrambled = "".join(" " if c == " " else rng.choice(charset) for c in row)
        delay = start + f * flicker
        out.append(
            f'<text class="{kind} {kind}-scramble s" data-row="{index}" x="{x:.1f}" y="{y:.1f}" {length} '
            f'style="animation-delay:{delay:.2f}s">{escape(scrambled)}</text>'
        )
    final_delay = start + frames * flicker
    out.append(
        f'<text class="{kind} {kind}-final f" data-row="{index}" x="{x:.1f}" y="{y:.1f}" {length} '
        f'style="animation-delay:{final_delay:.2f}s">{escape(row)}</text>'
    )
    return out


def _name_defs(th: Theme, x: float, width: float, start: float) -> str:
    """Gradient, glow filter and shimmer highlight used by the name."""
    n = len(th.name_gradient)
    stops = "".join(
        f'<stop offset="{i / max(1, n - 1):.2f}" stop-color="{c}"/>' for i, c in enumerate(th.name_gradient)
    )
    # userSpaceOnUse = the gradient spans the whole name block, not each line
    # separately, so the colours flow continuously from C to the last I.
    grad = (
        f'<linearGradient id="nameGrad" gradientUnits="userSpaceOnUse" '
        f'x1="{x:.1f}" y1="0" x2="{x + width:.1f}" y2="0">{stops}</linearGradient>'
    )
    # Glow = blurred copy of the letters drawn underneath the sharp ones.
    glow = (
        f'<filter id="glow" x="-10%" y="-30%" width="120%" height="160%">'
        f'<feGaussianBlur stdDeviation="{th.name_glow}" result="b"/>'
        f'<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
    )
    # A narrow white band that slides from left of the name to past its right edge.
    shine = (
        f'<linearGradient id="shine" gradientUnits="userSpaceOnUse" '
        f'x1="{x - 120:.1f}" y1="0" x2="{x:.1f}" y2="0">'
        f'<stop offset="0" stop-color="#fff" stop-opacity="0"/>'
        f'<stop offset="0.5" stop-color="#fff" stop-opacity="0.85"/>'
        f'<stop offset="1" stop-color="#fff" stop-opacity="0"/>'
        f'<animateTransform attributeName="gradientTransform" type="translate" '
        f'from="0 0" to="{width + 240:.1f} 0" dur="{th.shine_period}s" begin="{start:.2f}s" '
        f'repeatCount="indefinite"/></linearGradient>'
    )
    return grad + (glow if th.name_glow > 0 else "") + shine


def _titlebar(width: float, th: Theme, title: str) -> str:
    """A small terminal-window title bar with the three traffic-light dots."""
    dots = "".join(
        f'<circle cx="{20 + i * 18}" cy="{th.titlebar_h / 2 + 2:.1f}" r="5.5" fill="{c}"/>'
        for i, c in enumerate(["#ff5f56", "#ffbd2e", "#27c93f"])
    )
    return (
        f'{dots}<text class="wt" x="{width / 2:.1f}" y="{th.titlebar_h / 2 + 6:.1f}" '
        f'text-anchor="middle">{escape(title)}</text>'
        f'<line x1="0" x2="{width:.0f}" y1="{th.titlebar_h + 4:.1f}" y2="{th.titlebar_h + 4:.1f}" '
        f'stroke="{th.border}"/>'
    )


def _css(th: Theme, flicker: float) -> str:
    return (
        f"text{{font-family:{FONT_STACK};white-space:pre}}"
        f".face{{font-size:{th.face_font}px;fill:{th.face}}}"
        f".name{{font-size:{th.name_font}px;fill:url(#nameGrad)}}"
        + (".name-final{filter:url(#glow)}" if th.name_glow > 0 else "")
        + ".name-shine{fill:url(#shine)}"
        f".tag{{font-size:{th.tag_font}px;fill:{th.tagline}}}"
        f".p{{font-size:{th.tag_font}px;fill:{th.prompt};opacity:0;animation:on .01s linear forwards}}"
        f".wt{{font-size:12px;fill:{th.tagline}}}"
        f".s{{fill:{th.scramble};opacity:0;animation:flash {flicker}s linear}}"
        f".f{{opacity:0;animation:on .01s linear forwards}}"
        f".cursor{{fill:{th.prompt};opacity:0;animation:blink 1.1s steps(1) infinite}}"
        "@keyframes flash{from,to{opacity:1}}"
        "@keyframes on{to{opacity:1}}"
        "@keyframes blink{0%{opacity:1}50%{opacity:0}}"
        # People who ask their OS for less motion get the finished picture instantly.
        "@media (prefers-reduced-motion:reduce){.s,.scan,.name-shine{display:none}"
        ".f,.p{animation:none;opacity:1}.cursor{animation:none;opacity:1}}"
    )
