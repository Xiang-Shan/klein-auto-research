"""Tests for build_tutorial.py — the bundled tutorial assembler (the route of
record; see tutorial-spec.md § Optional: an external renderer).

Scripts under ``.claude/skills/klein/scripts/`` are deliberately not a package
(the skill must stay copy-a-directory portable), so the module is loaded
directly via ``importlib.util`` rather than imported — same pattern as
conftest.py uses for summarize.
"""

from __future__ import annotations

import base64
import importlib.util
import sys
import types
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent

# A real 1x1 transparent PNG. Validity is irrelevant to the builder (it only
# base64-encodes the raw bytes), but a genuine PNG keeps the fixture honest.
PNG_1PX = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M8AAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
)

RESULTS_TSV = (
    "experiment\tprimary_metric\tstatus\tcommit\tdescription\n"
    "1\t0.625462\tkeep\t7c3a25b\tsplit-identity anchor LR+OHE\n"
    "2\t0.610000\tdiscard\t\tweaker family probe\n"
)

STUDY_YAML = (
    'goal: "Reproduce the campaign anchors"   # one sentence\n'
    'domain: "insurance"\n'
    'target: "claim_status"\n'
    "metric:\n"
    '  name: "val_auc"\n'
    "  goal: higher\n"
    "family: glm\n"
)

FRAGMENTS = {
    "01-question.html": "<h2>The Question</h2><p>Can we reproduce the anchors?</p>",
    "02-method.html": "<h2>The Method</h2><pre><code>model.fit(X, y)</code></pre>",
    "03-data.html": "<h2>The Data</h2><p>58,592 rows, 6.4% positive.</p>",
    "04-journey.html": (
        "<h2>The Journey</h2>\n<!--LEDGER-->\n"
        '<img data-fig="figures/plot_trajectory.png" alt="trajectory">'
    ),
    "05-findings.html": "<h2>Findings</h2><p>RQ1 confirmed via exp 1 and exp 3.</p>",
    "06-coding-advice.html": "<h2>Coding Advice</h2><p>Use OHE for linear models.</p>",
    "07-next-steps.html": "<h2>Next Steps</h2><p>Try elastic-net on the spline basis.</p>",
}


def _load_build_tutorial() -> types.ModuleType:
    path = SCRIPTS_DIR / "build_tutorial.py"
    spec = importlib.util.spec_from_file_location("klein_build_tutorial", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["klein_build_tutorial"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def build_module() -> types.ModuleType:
    return _load_build_tutorial()


def scaffold(
    study_dir: Path,
    *,
    fragments: dict[str, str] | None = None,
    with_figure: bool = True,
    with_results: bool = True,
) -> Path:
    """Create a minimal but complete study dir the builder can assemble."""
    frags = dict(FRAGMENTS if fragments is None else fragments)
    sections = study_dir / "report" / "sections"
    sections.mkdir(parents=True)
    for name, content in frags.items():
        (sections / name).write_text(content, encoding="utf-8")
    (study_dir / "study.yaml").write_text(STUDY_YAML, encoding="utf-8")
    if with_results:
        (study_dir / "results.tsv").write_text(RESULTS_TSV, encoding="utf-8")
    figures = study_dir / "figures"
    figures.mkdir()
    if with_figure:
        (figures / "plot_trajectory.png").write_bytes(PNG_1PX)
    return study_dir


def test_happy_path_builds(build_module, tmp_path, capsys):
    study = scaffold(tmp_path / "00-demo")
    rc = build_module.main([str(study)])
    assert rc == 0, capsys.readouterr().err

    out = study / "report" / "index.html"
    assert out.exists()
    page = out.read_text(encoding="utf-8")

    # figure base64-inlined, marker consumed, all seven anchors present
    assert "data:image/png;base64," in page
    assert "<!--LEDGER-->" not in page
    for anchor in ("question", "method", "data", "journey", "findings", "coding-advice", "next-steps"):
        assert f'id="{anchor}"' in page
    # header metadata surfaced from study.yaml
    assert "Reproduce the campaign anchors" in page
    assert "val_auc" in page
    # no external attribute URLs slipped through the guard
    assert build_module.acceptance_violations(page) == []
    assert build_module.csp_meta_tag() in page
    policy = build_module.content_security_policy()
    assert "default-src 'none'" in policy
    assert "connect-src 'none'" in policy
    assert "script-src 'sha256-" in policy
    assert "script-src 'unsafe-inline'" not in policy


def test_ledger_marker_replaced_with_results_rows(build_module, tmp_path):
    study = scaffold(tmp_path / "00-ledger")
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")

    assert 'class="ledger"' in page
    assert "split-identity anchor LR+OHE" in page  # exp 1 description
    assert "weaker family probe" in page  # exp 2 description
    assert "0.625462" in page  # exp 1 metric
    assert 'class="st-discard"' in page  # status styling hook


def test_v2_track_metrics_are_displayed(build_module, tmp_path):
    study = scaffold(tmp_path / "03-v2-meta")
    (study / "study.yaml").write_text(
        "schema_version: 2\n"
        'goal: "Compare two registered tracks"\n'
        'domain: "insurance"\n'
        "tracks:\n"
        "  primary:\n"
        "    metric:\n"
        '      name: "val_auc"\n'
        '      goal: "higher"\n'
        "  severity:\n"
        "    metric:\n"
        '      name: "rmse"\n'
        '      goal: "lower"\n',
        encoding="utf-8",
    )
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert "metric: val_auc (primary), rmse (severity)" in page

    original_yaml = build_module.yaml
    try:
        build_module.yaml = None
        meta = build_module.load_study_meta(study)
    finally:
        build_module.yaml = original_yaml
    assert meta["metric_name"] == "val_auc (primary), rmse (severity)"


def test_missing_figure_fails_listing_name(build_module, tmp_path, capsys):
    study = scaffold(tmp_path / "00-nofig", with_figure=False)
    rc = build_module.main([str(study)])
    assert rc == 3
    err = capsys.readouterr().err
    assert "figures/plot_trajectory.png" in err
    assert not (study / "report" / "index.html").exists()


def test_attribute_url_violation_fails(build_module, tmp_path, capsys):
    bad = dict(FRAGMENTS)
    bad["06-coding-advice.html"] = (
        '<h2>Coding Advice</h2><p><a href="https://cdn.example.com/app.js">grab it</a></p>'
    )
    study = scaffold(tmp_path / "00-badurl", fragments=bad)
    rc = build_module.main([str(study)])
    assert rc == 4
    err = capsys.readouterr().err
    assert "external URL" in err
    assert "cdn.example.com" in err


def test_non_network_resource_scheme_is_also_rejected(build_module, tmp_path, capsys):
    bad = dict(FRAGMENTS)
    bad["06-coding-advice.html"] = (
        '<h2>Coding Advice</h2><a href="javascript:alert(1)">unsafe</a>'
    )
    study = scaffold(tmp_path / "00-unsafe-scheme", fragments=bad)
    assert build_module.main([str(study)]) == 4
    assert "unsafe URL" in capsys.readouterr().err


def test_acceptance_rejects_missing_or_modified_csp(build_module, tmp_path):
    study = scaffold(tmp_path / "00-csp")
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")

    without_policy = page.replace(build_module.csp_meta_tag(), "")
    assert any("Content-Security-Policy" in item for item in build_module.acceptance_violations(without_policy))

    weakened = page.replace("connect-src 'none'", "connect-src https:")
    assert any("Content-Security-Policy" in item for item in build_module.acceptance_violations(weakened))


def test_plaintext_url_in_body_is_allowed(build_module, tmp_path):
    """A URL in <code>/<cite> body text (not a src/href attribute) must pass."""
    ok = dict(FRAGMENTS)
    ok["07-next-steps.html"] = (
        "<h2>Next Steps</h2><p>See <cite>https://arxiv.org/abs/2207.01848</cite> and "
        "<code>https://example.com/notes</code>.</p>"
    )
    study = scaffold(tmp_path / "00-plainurl", fragments=ok)
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert "arxiv.org/abs/2207.01848" in page
    assert build_module.acceptance_violations(page) == []


def test_missing_fragment_fails_listing_name(build_module, tmp_path, capsys):
    study = scaffold(tmp_path / "00-nofrag")
    (study / "report" / "sections" / "05-findings.html").unlink()
    rc = build_module.main([str(study)])
    assert rc == 2
    assert "05-findings.html" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# Build-time math (LaTeX -> inline SVG) — v1.2.0
# ---------------------------------------------------------------------------


def test_inline_math_renders_svg(build_module, tmp_path):
    frags = dict(FRAGMENTS)
    frags["02-method.html"] = (
        '<h2>The Method</h2><p>Minimize <span data-math="x^2 + y^2"></span> here.</p>'
    )
    study = scaffold(tmp_path / "00-mathinline", fragments=frags)
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert 'class="kmath"' in page
    assert "<svg" in page and 'd="' in page
    assert "vertical-align:" in page
    assert "data-math=" not in page  # consumed
    assert 'data-latex="x^2 + y^2"' in page  # the source survives, greppable


def test_display_math_renders_svg(build_module, tmp_path):
    frags = dict(FRAGMENTS)
    frags["02-method.html"] = (
        '<h2>The Method</h2><div data-math-display="\\sum_{i=1}^{n} x_i^2"></div>'
    )
    study = scaffold(tmp_path / "00-mathdisplay", fragments=frags)
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert 'class="kmath-display"' in page
    assert "data-math-display" not in page
    assert "<title>" in page  # accessible source


def test_math_attribute_escaping_round_trips(build_module, tmp_path):
    import html as html_mod
    import re as re_mod

    frags = dict(FRAGMENTS)
    frags["02-method.html"] = (
        '<h2>The Method</h2>'
        '<div data-math-display="F(x) &lt; \\tfrac{1}{2},\\quad y &gt; 0"></div>'
    )
    study = scaffold(tmp_path / "00-mathescape", fragments=frags)
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    m = re_mod.search(r'data-latex="([^"]*)"', page)
    assert m is not None
    assert html_mod.unescape(m.group(1)) == "F(x) < \\tfrac{1}{2},\\quad y > 0"


def test_latex_source_survives_into_the_artifact(build_module, tmp_path):
    """Digits typeset as SVG paths must stay greppable — the number-integrity
    property rides on data-latex carrying the verbatim source."""
    frags = dict(FRAGMENTS)
    frags["05-findings.html"] = (
        '<h2>Findings</h2><p>Anchor <span data-math="\\hat{\\mu} = 0.833868"></span>.</p>'
    )
    study = scaffold(tmp_path / "00-mathnumbers", fragments=frags)
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert "0.833868" in page


def test_unparseable_math_fails_with_exit_5(build_module, tmp_path, capsys):
    frags = dict(FRAGMENTS)
    frags["02-method.html"] = '<h2>M</h2><span data-math="\\frac{1}{"></span>'
    study = scaffold(tmp_path / "00-mathbad", fragments=frags)
    rc = build_module.main([str(study)])
    assert rc == 5
    err = capsys.readouterr().err
    assert "02-method.html" in err
    assert not (study / "report" / "index.html").exists()


def test_nonempty_math_element_fails(build_module, tmp_path, capsys):
    frags = dict(FRAGMENTS)
    frags["02-method.html"] = '<h2>M</h2><span data-math="x^2">fallback text</span>'
    study = scaffold(tmp_path / "00-mathnonempty", fragments=frags)
    rc = build_module.main([str(study)])
    assert rc == 5
    assert "unconsumed data-math" in capsys.readouterr().err


def test_unescaped_quote_in_math_is_caught(build_module, tmp_path, capsys):
    frags = dict(FRAGMENTS)
    frags["02-method.html"] = '<h2>M</h2><span data-math="a "b""></span>'
    study = scaffold(tmp_path / "00-mathquote", fragments=frags)
    rc = build_module.main([str(study)])
    assert rc == 5
    assert "unconsumed data-math" in capsys.readouterr().err


def test_math_inside_pre_is_left_alone(build_module, tmp_path):
    """A code block SHOWING the authoring convention must survive verbatim."""
    frags = dict(FRAGMENTS)
    frags["06-coding-advice.html"] = (
        "<h2>Coding Advice</h2>"
        '<pre><code>write &lt;span data-math="x^2"&gt;&lt;/span&gt; and '
        'data-fig="figures/x.png" in fragments</code></pre>'
    )
    study = scaffold(tmp_path / "00-mathmasked", fragments=frags)
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert 'data-math="x^2"' in page  # literal demo survived, un-rendered
    assert 'data-fig="figures/x.png"' in page  # inline_figures masked too


def test_math_svg_uses_currentcolor_and_no_xmlns(build_module, tmp_path):
    frags = dict(FRAGMENTS)
    frags["02-method.html"] = '<h2>M</h2><span data-math="\\sigma^2"></span>'
    study = scaffold(tmp_path / "00-mathcolor", fragments=frags)
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert 'fill="currentColor"' in page
    assert 'fill="black"' not in page
    assert "xmlns=" not in page
    assert 'id="g' not in page  # svg2=False: no symbol ids, no <use> refs
    assert "<use" not in page


# ---------------------------------------------------------------------------
# Build-time code highlighting + include-by-reference — v1.2.0
# ---------------------------------------------------------------------------

TRAIN_PY = (
    "import math\n"
    "\n"
    "\n"
    "def objective(x):\n"
    '    """Toy objective for the include test."""\n'
    "    return math.sqrt(x) - 0.5\n"
)


def test_language_class_paste_is_highlighted(build_module, tmp_path):
    frags = dict(FRAGMENTS)
    frags["06-coding-advice.html"] = (
        "<h2>Coding Advice</h2>"
        '<pre><code class="language-python">def f(x):\n    return x + 1</code></pre>'
    )
    study = scaffold(tmp_path / "00-highlight", fragments=frags)
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert 'class="klein-code"' in page
    assert '<span class="k">def</span>' in page  # a real Pygments token


def test_plain_pre_code_is_untouched(build_module, tmp_path):
    study = scaffold(tmp_path / "00-plainpre")  # 02-method has a plain paste
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert "<pre><code>model.fit(X, y)</code></pre>" in page  # byte-identical


def test_include_by_reference_matches_source_bytes(build_module, tmp_path):
    import html as html_mod
    import re as re_mod

    frags = dict(FRAGMENTS)
    frags["06-coding-advice.html"] = (
        '<h2>Coding Advice</h2><pre data-code="train.py" data-lang="python"></pre>'
    )
    study = scaffold(tmp_path / "00-include", fragments=frags)
    (study / "train.py").write_text(TRAIN_PY, encoding="utf-8")
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    m = re_mod.search(
        r'<pre class="klein-code" data-code-source="train\.py"><code[^>]*>(.*?)</code></pre>',
        page,
        re_mod.DOTALL,
    )
    assert m is not None
    recovered = html_mod.unescape(re_mod.sub(r"<[^>]+>", "", m.group(1)))
    assert recovered == TRAIN_PY  # the ACTUAL winning train.py, byte-for-byte


def test_missing_included_file_fails_with_exit_6(build_module, tmp_path, capsys):
    frags = dict(FRAGMENTS)
    frags["06-coding-advice.html"] = '<h2>C</h2><pre data-code="train.py"></pre>'
    study = scaffold(tmp_path / "00-includemissing", fragments=frags)
    rc = build_module.main([str(study)])
    assert rc == 6
    err = capsys.readouterr().err
    assert "train.py" in err
    assert not (study / "report" / "index.html").exists()


def test_included_path_escaping_study_dir_is_rejected(build_module, tmp_path, capsys):
    for index, bad in enumerate(("../../etc/passwd", "/etc/passwd")):
        frags = dict(FRAGMENTS)
        frags["06-coding-advice.html"] = f'<h2>C</h2><pre data-code="{bad}"></pre>'
        # Indexed, not hashed: `abs(hash(bad)) % 100` collided under some
        # PYTHONHASHSEED values and the second scaffold died on FileExistsError.
        study = scaffold(tmp_path / f"00-esc{index}", fragments=frags)
        rc = build_module.main([str(study)])
        assert rc == 6, bad
        assert "relative path inside the study dir" in capsys.readouterr().err


def test_language_inferred_from_suffix(build_module, tmp_path):
    frags = dict(FRAGMENTS)
    frags["06-coding-advice.html"] = '<h2>C</h2><pre data-code="run.sh"></pre>'
    study = scaffold(tmp_path / "00-suffix", fragments=frags)
    (study / "run.sh").write_text("echo done\n", encoding="utf-8")
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert 'class="language-bash"' in page


def test_pygments_css_is_dual_theme(build_module, tmp_path):
    study = scaffold(tmp_path / "00-css")
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert page.count("@media (prefers-color-scheme:dark)") >= 2  # base + pygments
    assert "pre.klein-code{background:var(--code-bg)" in page
    css = build_module.render_css()
    assert build_module.PYG_LIGHT_STYLE == "default"
    assert build_module.PYG_DARK_STYLE == "github-dark"
    assert ".kmath svg *,.kmath-display svg *{fill:currentColor}" in css


# ---------------------------------------------------------------------------
# Contract invariants with the new pipeline — v1.2.0
# ---------------------------------------------------------------------------


def test_csp_is_byte_identical_after_math_and_code(build_module, tmp_path):
    frags = dict(FRAGMENTS)
    frags["02-method.html"] = '<h2>M</h2><span data-math="e^{i\\pi} + 1 = 0"></span>'
    frags["06-coding-advice.html"] = (
        '<h2>C</h2><pre><code class="language-python">x = 1</code></pre>'
    )
    study = scaffold(tmp_path / "00-cspmath", fragments=frags)
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    policy = build_module.content_security_policy()
    assert "font-src 'none'" in policy  # engine D: no fonts, gate unchanged
    assert "script-src 'sha256-" in policy
    assert build_module.csp_meta_tag() in page


def test_acceptance_gates_still_pass_with_math_and_code(build_module, tmp_path):
    frags = dict(FRAGMENTS)
    frags["02-method.html"] = (
        '<h2>M</h2><div data-math-display="\\hat{\\beta} = (X\'X)^{-1}X\'y"></div>'
    )
    frags["06-coding-advice.html"] = (
        '<h2>C</h2><pre data-code="train.py" data-lang="python"></pre>'
    )
    study = scaffold(tmp_path / "00-gates", fragments=frags)
    (study / "train.py").write_text(TRAIN_PY, encoding="utf-8")
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")
    assert build_module.acceptance_violations(page) == []


def test_build_is_byte_deterministic(build_module, tmp_path):
    """Two builds of the same study must be byte-identical (same process,
    fixed git state — tmp studies have no git history, so no date either).
    NOTE: rebuilding a COMMITTED study is only byte-identical at a fixed git
    state (git_last_date embeds the last commit date); build-twice is the
    gate, rebuild-and-diff-the-checkout is not."""
    frags = dict(FRAGMENTS)
    frags["02-method.html"] = (
        '<h2>M</h2><span data-math="\\sigma_{ij}"></span>'
        '<pre><code class="language-python">y = f(x)</code></pre>'
    )
    study = scaffold(tmp_path / "00-determinism", fragments=frags)
    (study / "train.py").write_text(TRAIN_PY, encoding="utf-8")
    assert build_module.main([str(study)]) == 0
    first = (study / "report" / "index.html").read_bytes()
    assert build_module.main([str(study)]) == 0
    second = (study / "report" / "index.html").read_bytes()
    assert first == second


def test_missing_renderer_dependency_exits_7(build_module, tmp_path, capsys):
    study = scaffold(tmp_path / "00-nodeps")
    saved = build_module.ziamath
    try:
        build_module.ziamath = None
        rc = build_module.main([str(study)])
    finally:
        build_module.ziamath = saved
    assert rc == 7
    err = capsys.readouterr().err
    assert "uv sync --locked" in err
    assert not (study / "report" / "index.html").exists()
