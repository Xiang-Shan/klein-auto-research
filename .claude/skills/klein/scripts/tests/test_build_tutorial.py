"""Tests for build_tutorial.py — the Route B tutorial assembler.

Scripts under ``.claude/skills/klein/scripts/`` are deliberately not a package
(the skill must stay copy-a-directory portable), so the module is loaded
directly via ``importlib.util`` rather than imported — same pattern as
conftest.py uses for preflight/summarize.
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


def test_ledger_marker_replaced_with_results_rows(build_module, tmp_path):
    study = scaffold(tmp_path / "00-ledger")
    assert build_module.main([str(study)]) == 0
    page = (study / "report" / "index.html").read_text(encoding="utf-8")

    assert 'class="ledger"' in page
    assert "split-identity anchor LR+OHE" in page  # exp 1 description
    assert "weaker family probe" in page  # exp 2 description
    assert "0.625462" in page  # exp 1 metric
    assert 'class="st-discard"' in page  # status styling hook


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
