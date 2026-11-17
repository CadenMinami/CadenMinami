"""Tests for the animated SVG header renderer."""
import xml.etree.ElementTree as ET

from tools.ascii_header.render_svg import HeaderText, render_header

SVG_NS = "{http://www.w3.org/2000/svg}"
FACE = ["  .:-=+  ", " =#@&@#= ", "  <*%*>  "]  # includes XML-special characters on purpose
TEXT = HeaderText(name_lines=["CADEN", "MINAMI"], taglines=["UCLA CS", "MLOps"])


def _parse(svg: str) -> ET.Element:
    return ET.fromstring(svg)


def test_output_is_valid_xml_with_svg_root() -> None:
    root = _parse(render_header(FACE, TEXT, seed=1))
    assert root.tag == f"{SVG_NS}svg"
    assert root.get("viewBox")


def test_every_face_row_has_a_final_frame() -> None:
    root = _parse(render_header(FACE, TEXT, seed=1))
    finals = [t for t in root.iter(f"{SVG_NS}text") if "face-final" in (t.get("class") or "")]
    assert ["".join(t.itertext()) for t in finals] == FACE


def test_scramble_frames_keep_the_silhouette() -> None:
    # Scrambled rows put random characters only where the face has characters,
    # so the outline of the head is visible while it "decodes".
    root = _parse(render_header(FACE, TEXT, seed=1, scramble_frames=3))
    scrambles = [t for t in root.iter(f"{SVG_NS}text") if "face-scramble" in (t.get("class") or "")]
    assert len(scrambles) == len(FACE) * 3
    for t in scrambles:
        row = FACE[int(t.get("data-row"))]
        text = "".join(t.itertext())
        assert [c == " " for c in text] == [c == " " for c in row]


def test_rows_decode_top_to_bottom() -> None:
    root = _parse(render_header(FACE, TEXT, seed=1))
    finals = [t for t in root.iter(f"{SVG_NS}text") if "face-final" in (t.get("class") or "")]
    delays = [float(t.get("style").split("animation-delay:")[1].rstrip("s;")) for t in finals]
    assert delays == sorted(delays) and delays[0] < delays[-1]


def test_name_and_taglines_are_present() -> None:
    svg = render_header(FACE, TEXT, seed=1)
    for s in ["CADEN", "MINAMI", "UCLA CS", "MLOps"]:
        assert s in svg


def test_same_seed_gives_identical_output() -> None:
    # Deterministic output means regenerating the header doesn't create noisy git diffs.
    assert render_header(FACE, TEXT, seed=7) == render_header(FACE, TEXT, seed=7)


def test_respects_reduced_motion() -> None:
    assert "prefers-reduced-motion" in render_header(FACE, TEXT, seed=1)


def test_name_uses_gradient_glow_and_shimmer() -> None:
    svg = render_header(FACE, TEXT, seed=1)
    root = _parse(svg)
    ids = {el.get("id") for el in root.iter() if el.get("id")}
    assert {"nameGrad", "glow", "shine"} <= ids
    finals = [t for t in root.iter(f"{SVG_NS}text") if "name-final" in (t.get("class") or "")]
    assert finals  # the decoded name exists...
    assert "url(#nameGrad)" in svg  # ...and is painted with the gradient


def test_shimmer_overlay_appears_only_after_the_name_decodes() -> None:
    root = _parse(render_header(FACE, TEXT, seed=1))
    texts = list(root.iter(f"{SVG_NS}text"))

    def delay(t: ET.Element) -> float:
        return float(t.get("style").split("animation-delay:")[1].rstrip("s;"))

    last_final = max(delay(t) for t in texts if "name-final" in (t.get("class") or ""))
    shines = [t for t in texts if "name-shine" in (t.get("class") or "")]
    assert len(shines) == len(TEXT.name_lines)
    assert all(delay(t) >= last_final for t in shines)
