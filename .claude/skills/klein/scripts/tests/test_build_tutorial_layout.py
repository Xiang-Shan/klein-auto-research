"""Layout, print and figure-presentation contracts of build_tutorial.py.

A separate file from ``test_build_tutorial.py`` on purpose: this suite owns the
CSS/JS surface (mobile navigation, print completeness, source disclosure) and
the figure pipeline (PNG header decode, captions, ``:target`` enlargement),
which are edited independently of the assembler's fragment/math/code contracts.

The rules asserted here were accepted against headless Chrome at 1440/768/390/
320 px and a ``--print-to-pdf`` extraction; these tests are the cheap standing
guard that the accepted strings do not silently disappear.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import struct
import sys
import types
import zlib
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent


def _png(width: int, height: int) -> bytes:
    """A minimal but genuine greyscale PNG of the requested intrinsic size."""

    def chunk(kind: bytes, payload: bytes) -> bytes:
        body = kind + payload
        return struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    raw = b"".join(b"\x00" + b"\x80" * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


PNG_WIDE = _png(320, 96)
JPEG_BYTES = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEB"
    "AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEB/8AAEQgAAQABAwEiAAIRAQMRAf/E"
    "ABQAAQAAAAAAAAAAAAAAAAAAAAr/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFAEBAAAAAAAA"
    "AAAAAAAAAAAAAP/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/AKpgAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/9k="
)

STUDY_YAML = 'goal: "Accept the layout"\ndomain: "framework"\nmetric:\n  name: "val_auc"\n'

BASE_FRAGMENTS = {
    "01-question.html": "<h2>The Question</h2><p>Can the page read on a phone?</p>",
    "02-method.html": "<h2>The Method</h2><p>Measure it.</p>",
    "03-data.html": "<h2>The Data</h2><p>One wide PNG.</p>",
    "04-journey.html": "<h2>The Journey</h2>\n<!--LEDGER-->",
    "05-findings.html": "<h2>Findings</h2><p>It reads.</p>",
    "06-coding-advice.html": "<h2>Coding Advice</h2><p>Style the disclosure.</p>",
    "07-next-steps.html": "<h2>Next Steps</h2><p>Ship it.</p>",
}

RESULTS_TSV = (
    "experiment\tprimary_metric\tstatus\tcommit\tdescription\n"
    "E0001\t0.625462\tkeep\t7c3a25b\tanchor\n"
)


def _load_build_tutorial() -> types.ModuleType:
    path = SCRIPTS_DIR / "build_tutorial.py"
    spec = importlib.util.spec_from_file_location("klein_build_tutorial_layout", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["klein_build_tutorial_layout"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def build_module() -> types.ModuleType:
    return _load_build_tutorial()


def scaffold(
    study_dir: Path,
    *,
    fragments: dict[str, str] | None = None,
    figures: dict[str, bytes] | None = None,
) -> Path:
    frags = dict(BASE_FRAGMENTS if fragments is None else fragments)
    sections = study_dir / "report" / "sections"
    sections.mkdir(parents=True)
    for name, content in frags.items():
        (sections / name).write_text(content, encoding="utf-8")
    (study_dir / "study.yaml").write_text(STUDY_YAML, encoding="utf-8")
    (study_dir / "results.tsv").write_text(RESULTS_TSV, encoding="utf-8")
    figures_dir = study_dir / "figures"
    figures_dir.mkdir()
    for name, payload in (figures or {"wide.png": PNG_WIDE}).items():
        (figures_dir / name).write_bytes(payload)
    return study_dir


def build(build_module, study: Path) -> str:
    assert build_module.main([str(study)]) == 0
    return (study / "report" / "index.html").read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# R-4 — mobile navigation and overflow
# ---------------------------------------------------------------------------


def test_mobile_nav_is_one_scrollable_row(build_module):
    css = build_module.CSS
    mobile = css.split("@media (max-width:860px){", 1)[1].split("@media print{", 1)[0]
    assert "nav.topnav .wrap{flex-wrap:nowrap;overflow-x:auto" in mobile
    assert "nav.topnav a{white-space:nowrap;flex:0 0 auto}" in mobile
    # The anchor targets must clear that row: the nav measures 52.4 px tall in
    # Chrome, plus ~15 px where the scrolling row draws a non-overlay scrollbar.
    assert "section{scroll-margin-top:84px}h3[id]{scroll-margin-top:84px}" in mobile


def test_scroll_margin_covers_h3_anchors_at_desktop(build_module):
    css = build_module.CSS
    assert "scroll-margin-top:76px}" in css  # section
    assert "h3[id]{scroll-margin-top:76px}" in css


def test_long_tokens_wrap_but_code_blocks_still_scroll(build_module):
    css = build_module.CSS
    assert "p,li,dd,td,th,figcaption,blockquote,code,a,cite{overflow-wrap:anywhere}" in css
    assert "pre code{overflow-wrap:normal}" in css
    assert "pre{background:var(--code-bg)" in css and "overflow-x:auto" in css


def test_inline_math_scrolls_instead_of_widening_the_page(build_module):
    assert ".kmath{display:inline-block;max-width:100%;overflow-x:auto}" in (
        build_module.render_css()
    )


def test_ledger_numeric_column_is_class_driven(build_module):
    css = build_module.CSS
    assert "table.ledger td.num{font-variant-numeric:tabular-nums;white-space:nowrap}" in css
    # nth-child(2) broke the moment a column was inserted; the class does not.
    assert "table.ledger td:nth-child(2)" not in css
    assert "table.ledger tr.kind-final_test td:first-child{font-weight:600}" in css
    assert "sealed" in css  # the quiet mark on a sealed row
    assert ".ledger-key{font-size:14px;color:var(--muted)}" in css


def test_wide_blocks_have_wrapping_rules(build_module):
    css = build_module.CSS
    assert ".evidence{" in css and "overflow-wrap:anywhere}" in css
    assert "details.source>summary{" in css
    assert "nav.subnav{display:flex;flex-wrap:wrap" in css
    mobile = css.split("@media (max-width:860px){", 1)[1].split("@media print{", 1)[0]
    assert ".evidence dl{grid-template-columns:minmax(0,1fr)}" in mobile


# ---------------------------------------------------------------------------
# R-5 — complete printed tables, code, equations
# ---------------------------------------------------------------------------


def test_print_rules_keep_everything_on_paper(build_module):
    print_css = build_module.CSS.split("@media print{", 1)[1]
    for rule in (
        "pre{white-space:pre-wrap;overflow:visible",
        "table{display:table;overflow:visible}",
        "td,th{overflow-wrap:anywhere}",
        ".kmath-display{overflow:visible}",
        "section{border-color:#ccc;break-inside:auto}",
        "h2,h3{break-after:avoid}",
        "figure,img,table.ledger tr{break-inside:avoid}",
        "details.source{display:block}",
        "details.source>summary{display:block}",
        "nav.topnav{position:static",
    ):
        assert rule in print_css, rule
    # A whole section pinned to one page produced near-empty pages; that is
    # exactly the rule this print block must NOT reintroduce.
    assert "page-break-inside:avoid" not in build_module.CSS
    # An explicit light palette so a dark-scheme reader prints on paper.
    assert "--bg:#fff" in print_css and "--fg:#111" in print_css
    assert "@media print{" in build_module.render_css()  # pygments light for print


def test_nav_js_opens_and_restores_source_disclosures_for_print(build_module):
    js = build_module.NAV_JS
    assert "'beforeprint'" in js and "'afterprint'" in js
    assert "document.querySelectorAll('details.source')" in js
    assert "d.open=true" in js
    assert "pair[0].open=pair[1]" in js  # the previous state is restored


def test_nav_js_clears_a_figure_enlargement_on_escape(build_module):
    js = build_module.NAV_JS
    assert "'keydown'" in js
    assert "e.key!=='Escape'" in js
    assert "h.lastIndexOf('#fig-',0)!==0" in js
    assert "location.hash=h.slice(1)+'-close'" in js


def test_csp_authorizes_the_new_nav_script_and_the_page_still_passes(build_module, tmp_path):
    digest = base64.b64encode(hashlib.sha256(build_module.NAV_JS.encode("utf-8")).digest()).decode(
        "ascii"
    )
    policy = build_module.content_security_policy()
    assert f"script-src 'sha256-{digest}'" in policy
    assert "'unsafe-inline'" not in policy.split("script-src", 1)[1]

    study = scaffold(tmp_path / "00-csp-nav")
    page = build(build_module, study)
    assert build_module.csp_meta_tag() in page
    assert build_module.acceptance_violations(page) == []


# ---------------------------------------------------------------------------
# R-6 — source disclosure styling
# ---------------------------------------------------------------------------


def test_open_disclosure_has_no_double_border(build_module):
    css = build_module.CSS
    assert "details.source{margin:0 0 16px;border:1px solid var(--rule)" in css
    assert "details.source>pre,details.source>pre.klein-code{margin:0;border:0" in css
    assert "details.source>summary:focus-visible{outline:2px solid var(--accent)" in css
    # Two rules, so a browser that knows only one pseudo-element keeps the other.
    assert "details.source>summary::marker{color:var(--rule)}" in css
    assert "details.source>summary::-webkit-details-marker{color:var(--rule)}" in css


# ---------------------------------------------------------------------------
# R-7 — figures: intrinsic size, captions, enlargement
# ---------------------------------------------------------------------------


def test_png_header_decode_emits_intrinsic_size(build_module, tmp_path):
    frags = dict(BASE_FRAGMENTS)
    frags["03-data.html"] = '<h2>The Data</h2><img data-fig="figures/wide.png" alt="wide">'
    study = scaffold(tmp_path / "00-figsize", fragments=frags)
    page = build(build_module, study)
    assert 'width="320" height="96">' in page
    assert build_module.png_intrinsic_size(PNG_WIDE) == (320, 96)


def test_non_png_figure_fails_with_exit_3_naming_file_and_reason(build_module, tmp_path, capsys):
    for index, (name, payload) in enumerate(
        (("shot.png", JPEG_BYTES), ("trunc.png", b"\x89PNG\r\n\x1a\n\x00\x00"))
    ):
        frags = dict(BASE_FRAGMENTS)
        frags["03-data.html"] = f'<h2>The Data</h2><img data-fig="figures/{name}">'
        study = scaffold(tmp_path / f"00-notpng{index}", fragments=frags, figures={name: payload})
        assert build_module.main([str(study)]) == 3, name
        err = capsys.readouterr().err
        assert "figure problem(s)" in err
        assert f"figures/{name}" in err
        assert "not a PNG" in err
        assert not (study / "report" / "index.html").exists()


def test_caption_wraps_the_image_in_a_numbered_figure(build_module, tmp_path):
    frags = dict(BASE_FRAGMENTS)
    frags["03-data.html"] = (
        '<h2>The Data</h2><img data-fig="figures/wide.png" alt="wide" '
        'data-caption="The frontier &amp; its sealed test.">'
    )
    study = scaffold(tmp_path / "00-figcaption", fragments=frags)
    page = build(build_module, study)
    assert '<figure class="fig" id="fig-1">' in page
    assert '<a class="fig-zoom" href="#fig-1" aria-label="Enlarge figure">' in page
    assert '<a class="fig-close" href="#fig-1-close">Close</a>' in page
    assert "The frontier &amp; its sealed test." in page
    assert 'width="320" height="96">' in page
    assert "data-caption" not in page  # consumed, not leaked into the <img>
    # The enlargement is CSS :target on the SAME element — never a second copy.
    assert page.count("data:image/png;base64,") == 1
    assert "figure.fig:target{position:fixed" in page
    assert build_module.acceptance_violations(page) == []


def test_bare_data_fig_keeps_its_authored_wrapping(build_module, tmp_path):
    """Shipped studies wrap their own <figure>/<figcaption>; never double-wrap."""
    frags = dict(BASE_FRAGMENTS)
    frags["03-data.html"] = (
        "<h2>The Data</h2><figure><img data-fig=\"figures/wide.png\" alt='wide'>"
        "<figcaption>Authored caption</figcaption></figure>"
    )
    study = scaffold(tmp_path / "00-figbare", fragments=frags)
    page = build(build_module, study)
    assert '<figure class="fig"' not in page
    assert '<a class="fig-zoom"' not in page
    assert "<figcaption>Authored caption</figcaption>" in page
    assert '<figure><img src="data:image/png;base64,' in page
    assert 'alt=\'wide\' width="320" height="96">' in page


def test_two_captioned_figures_number_in_document_order_and_are_deterministic(
    build_module, tmp_path
):
    frags = dict(BASE_FRAGMENTS)
    frags["03-data.html"] = (
        '<h2>The Data</h2><img data-fig="figures/wide.png" data-caption="First">'
    )
    frags["05-findings.html"] = (
        '<h2>Findings</h2><img data-fig="figures/tall.png" data-caption="Second">'
    )
    study = scaffold(
        tmp_path / "00-fignumber",
        fragments=frags,
        figures={"wide.png": PNG_WIDE, "tall.png": _png(64, 128)},
    )
    page = build(build_module, study)
    assert page.index('id="fig-1"') < page.index('id="fig-2"')
    assert '<figcaption>First <a class="fig-close" href="#fig-1-close">' in page
    assert '<figcaption>Second <a class="fig-close" href="#fig-2-close">' in page
    assert 'width="64" height="128">' in page
    first = (study / "report" / "index.html").read_bytes()
    assert build_module.main([str(study)]) == 0
    assert (study / "report" / "index.html").read_bytes() == first


def test_page_head_names_its_layout_generation(build_module, tmp_path):
    """The shipped-report check keys its LEGACY classification off this tag."""
    from test_build_tutorial import scaffold

    study = scaffold(tmp_path / "00-generator")
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert build_module.GENERATOR_META in page
    assert build_module.LAYOUT_GENERATION == 2
    assert f'content="klein build_tutorial layout-{build_module.LAYOUT_GENERATION}"' in page
