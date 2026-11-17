# ascii_header

Generates the animated header at the top of my profile: an ASCII-art portrait that "decodes" into place next to my name.

```
photo ──► segment.py ──► ascii.py ──► render_svg.py ──► assets/header.svg
          cut out the     pixels to     animated SVG
          person (rembg)  characters    (CSS + SMIL, no JS)
```

GitHub strips JavaScript from READMEs but still plays CSS and SMIL animations inside SVG images, so the whole effect lives in a single SVG file. Each text row is drawn a few times: scrambled copies flash briefly, then the real row locks in. Staggering those timings row by row produces the decode effect.

## Regenerate

```bash
python -m venv .venv && .venv/bin/pip install pillow numpy pyfiglet "rembg[cpu]" pytest
.venv/bin/python -m tools.ascii_header --photo path/to/photo.png --out assets/header.svg
.venv/bin/python -m pytest -q
```

The photo is only read, never committed. The first run downloads rembg's ~170 MB person-segmentation model. After that, the cut-out is cached next to the photo, so tweaking options like `--cols`, `--clarity` or `--name-font` is instant.
