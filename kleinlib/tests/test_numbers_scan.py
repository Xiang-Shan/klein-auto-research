"""E9 — the numbers law over a whole document.

``references/claims-protocol.md`` states it once: every numeral in
``findings.md``, ``claims.lock`` and ``report/index.html`` is a copy of a value
in a pinned artifact.  :mod:`kleinlib.claims` mechanizes the claim-sentence half;
:mod:`kleinlib.numbers` mechanizes the document half, reusing that module's
``NUMERAL_RE``/``SENTENCE_EXEMPT_RE``/``NUMBERS_OK_RE`` rather than restating
them.

Pinned here: the exemption list (each class of the protocol's own list), the
extraction rules (frontmatter, code, table separators, headings, the marker), a
planted unsourced numeral being caught, and the three shipped iris findings
passing at the tuned allowlist.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from kleinlib.claims import NUMERAL_RE, SENTENCE_EXEMPT_RE
from kleinlib.numbers import (
    DOCUMENT_EXEMPT_RE,
    Literal,
    LiteralIndex,
    extract_literals,
    html_text,
    literal_precision,
    unsourced_literals,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def tokens(markdown: str) -> list[str]:
    return [item.token for item in extract_literals(markdown)]


# ---------------------------------------------------------------------------
# 1. what the scan skips whole
# ---------------------------------------------------------------------------


def test_frontmatter_is_skipped_and_line_numbers_survive_it() -> None:
    text = "---\nseed: 12345\nvalue: 6789\n---\nthe delta is 0.042\n"
    found = extract_literals(text)
    assert [item.token for item in found] == ["0.042"]
    # blanked, not deleted: the offender still reports its real line
    assert found[0].line == 5


def test_fenced_code_and_inline_code_are_exempt() -> None:
    text = (
        "prose says 0.5\n"
        "```python\n"
        "threshold = 0.99999\n"
        "```\n"
        "and `alpha = 0.123456` is code too\n"
    )
    assert tokens(text) == ["0.5"]


def test_a_longer_fence_closes_only_on_its_own_marker() -> None:
    text = "````\n```\n0.7777\n````\n0.25\n"
    assert tokens(text) == ["0.25"]


def test_table_separator_rows_are_punctuation_never_data() -> None:
    text = "| a | b |\n|---|--:|\n| 0.5 | 0.25 |\n"
    assert tokens(text) == ["0.5", "0.25"]


def test_headings_carry_section_numbering_not_evidence() -> None:
    assert tokens("## 3.2 The 0.05 threshold\n\nbody 0.31\n") == ["0.31"]


def test_the_law_s_escape_hatch_exempts_its_whole_line() -> None:
    text = "the constant 6.02214076 <!-- klein:numbers-ok: Avogadro, a definition -->\n"
    assert tokens(text) == []


# ---------------------------------------------------------------------------
# 2. the exemption list, class by class (claims-protocol.md, "The numbers law")
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "line",
    [
        "the 1936 anchor and the 2026-08-25 citations pass",  # years and dates
        "Serfling (2002a) and Serfling (2002b) both apply",  # disambiguated years
        "E0004 discarded, P3 refuted, C7 stands, RQ2 answered, S10 retired",  # ids
        "see Section 4, Figure 2, Table 1 and step 3",  # structural numbering
        "§VI and §7.2 of the profile",  # section marks
        "n = 24 objects and k = 5 seeds",  # small counts naming their source
        "0 of 42 cells cleared the guard",  # N of M
        "68% of the 2026 papers",  # percentages
        "the declared split seed 20260912 and the range (20260829..20260848)",
        "numpy requires a seed below 2**32",  # powers
        "schema 3, klein v2.0, Python 3.13",  # versions
        "the full 150x4 printed table",  # shapes
        "Fisher's 4:1:-5 allopolyploidy contrast",  # ratios
        "*Annals of Eugenics* 7(2):179-188 (DOI 10.1111/j.1469-1809.1936.tb02137.x)",
        "open access via Rothamsted, eprint 33079, changelog #11082, p. 182",
        "arXiv:2503.11651 is the preprint",
        "the timestamp 20260912T101500Z",
    ],
)
def test_every_exempt_class_leaves_no_numeral_behind(line: str) -> None:
    assert tokens(line + "\n") == []


def test_a_bare_reference_value_is_not_exempt() -> None:
    """The law's own counter-example: "not 465" needs a pinned home."""
    assert tokens("the coefficient is 465.12, not 454.16\n") == ["465.12", "454.16"]


def test_the_document_exemptions_are_layered_on_the_claims_law_not_a_copy() -> None:
    # The sentence law owns ids/years/small counts; the document law owns the
    # classes a one-sentence claim never carries.  Neither restates the other.
    assert SENTENCE_EXEMPT_RE.search("E0004") is not None
    assert DOCUMENT_EXEMPT_RE.search("E0004") is None
    assert DOCUMENT_EXEMPT_RE.search("Table 1") is not None
    assert SENTENCE_EXEMPT_RE.search("Table 1") is None


# ---------------------------------------------------------------------------
# 3. extraction details that produce false positives when they go wrong
# ---------------------------------------------------------------------------


def test_a_unicode_minus_keeps_its_sign() -> None:
    """`−` is what prose writes; NUMERAL_RE only knows ASCII `-`.

    Without normalisation `−0.0595` extracts as `+0.0595` and a real,
    measured value is reported unsourced because its sign flipped.
    """
    assert tokens("hgbt −0.0595 on average\n") == ["-0.0595"]
    assert NUMERAL_RE.match("−0.0595") is None  # the reason the fix is needed


def test_a_hyphenated_compound_is_not_read_as_a_negative_number() -> None:
    """"depth-2 tree", "top-10 lift", "5-fold CV" are English, not arithmetic.

    Taking the hyphen as a minus reports `-2` for a sentence that says two: a
    false positive with a plausible value that the author cannot find anywhere,
    which is exactly the class this module refuses to produce. A sign the author
    really wrote still survives.
    """
    assert tokens("the depth-2 tree, a top-10 lift and 5-fold CV\n") == ["2", "10", "5"]
    assert tokens("delta -0.07 against +0.08, x=-5, (-0.5), 5e-3\n") == [
        "-0.07",
        "+0.08",
        "-5",
        "-0.5",
        "5e-3",
    ]


def test_an_exempt_span_drops_the_numeral_it_touches_rather_than_splitting_it() -> None:
    """Substituting an exempt span away can invent a number that was never written.

    Study 07 writes "within ±0.008 of 0.023445".  The claims law's "N of M"
    exemption covers "8 of 0"; blanking it leaves the fragments "0.00" and
    ".023445" — a plausible-looking numeral nobody wrote.
    """
    found = tokens("stays within ±0.008 of 0.023445 across the draws\n")
    assert ".023445" not in found
    assert "0.00" not in found


def test_precision_is_the_precision_as_written() -> None:
    assert literal_precision("0.330") == 3
    assert literal_precision("2.22") == 2
    assert literal_precision("42") == 0
    assert literal_precision("-0.0595") == 4
    assert literal_precision("1.2e-5") == 3  # no meaningful written precision


# ---------------------------------------------------------------------------
# 4. the index, and a planted offender
# ---------------------------------------------------------------------------


@pytest.fixture
def measured(tmp_path: Path) -> Path:
    study = tmp_path / "10-demo"
    (study / "runs" / "E0001").mkdir(parents=True)
    (study / "results.tsv").write_text(
        "experiment\tprimary_metric\nE0001\t0.026409\n", encoding="utf-8"
    )
    (study / "aux_metrics.tsv").write_text(
        "experiment\tmetric\tvalue\nE0001\twall_seconds\t1.25\n", encoding="utf-8"
    )
    (study / "study.yaml").write_text("schema_version: 3\n", encoding="utf-8")
    (study / "runs" / "E0001" / "manifest.json").write_text(
        json.dumps({"experiment": "E0001", "primary_metric": 0.026409}), encoding="utf-8"
    )
    return study


def test_the_index_reads_the_sources_the_protocol_names(measured: Path) -> None:
    index = LiteralIndex.for_study(measured, {})
    assert set(index.sources) == {
        "results.tsv",
        "aux_metrics.tsv",
        "study.yaml",
        "runs/E0001/manifest.json",
    }
    assert index.covers(Literal(0.026409, 1, "0.026409", ""))
    assert index.covers(Literal(1.25, 1, "1.25", ""))


def test_a_value_matches_at_its_own_precision_not_the_artifact_s(measured: Path) -> None:
    index = LiteralIndex.for_study(measured, {})
    assert index.covers(Literal(0.0264, 1, "0.0264", ""))  # rounds to the stored value
    assert not index.covers(Literal(0.0265, 1, "0.0265", ""))


def test_a_planted_unsourced_numeral_is_caught(measured: Path) -> None:
    findings = measured / "findings.md"
    findings.write_text(
        "# Findings\n\nThe anchor scored 0.026409 on the declared split,\n"
        "an improvement of 0.004733 over the previous incumbent.\n",
        encoding="utf-8",
    )
    index = LiteralIndex.for_study(measured, {}, exclude=[findings])
    caught = unsourced_literals(findings.read_text(encoding="utf-8"), index)
    assert [item.token for item in caught] == ["0.004733"]
    assert caught[0].line == 4
    assert "0.004733" in caught[0].describe()


def test_the_scanned_document_is_kept_out_of_its_own_index(measured: Path) -> None:
    """Study 09's lock pins findings.md as an artifact of itself.

    Without the exclusion every findings numeral would trivially trace to
    findings, and the scan would be vacuous.
    """
    findings = measured / "findings.md"
    findings.write_text("the number 0.987654 comes from nowhere\n", encoding="utf-8")
    (measured / "claims.lock").write_text(
        json.dumps({"artifacts": {"findings": {"path": "findings.md"}}}), encoding="utf-8"
    )
    index = LiteralIndex.for_study(measured, {}, exclude=[findings])
    assert unsourced_literals(findings.read_text(encoding="utf-8"), index)


def test_a_registered_sweep_sidecar_is_a_source(measured: Path) -> None:
    (measured / "sweeps").mkdir()
    (measured / "sweeps" / "floor.sidecar.tsv").write_text(
        "trial\tvalue\n1\t0.0163144\n", encoding="utf-8"
    )
    (measured / "sweeps" / "floor.py").write_text("# frozen\n", encoding="utf-8")
    state = {
        "sweeps": {
            "floor": {"sidecar": "sweeps/floor.sidecar.tsv", "script": "sweeps/floor.py"}
        }
    }
    assert not LiteralIndex.for_study(measured, {}).covers(
        Literal(0.0163144, 1, "0.0163144", "")
    )
    assert LiteralIndex.for_study(measured, state).covers(
        Literal(0.0163144, 1, "0.0163144", "")
    )


# ---------------------------------------------------------------------------
# 5. the tutorial pass — text nodes only
# ---------------------------------------------------------------------------


def test_html_text_reads_text_nodes_and_skips_code_svg_and_script() -> None:
    page = (
        "<style>.a{width:12.5px}</style>"
        "<script>var x = 3.14159;</script>"
        "<svg><path d='M 4.44 -8.568'/></svg>"
        "<pre><code>alpha = 0.98765</code></pre>"
        "<p>the anchor scored 0.026409</p>"
    )
    text = html_text(page)
    assert tokens(text) == ["0.026409"]


def test_adjacent_table_cells_never_concatenate_into_a_number_nobody_wrote() -> None:
    """`<td>E0001</td><td>0.029442</td>` must not read as `00010.029442`."""
    text = html_text("<tr><td>E0001</td><td>0.029442</td></tr>")
    assert tokens(text) == ["0.029442"]


# ---------------------------------------------------------------------------
# 6. the shipped studies, at the tuned allowlist
# ---------------------------------------------------------------------------

#: Measured on the real documents at the tuned exemption list (E9 report).  The
#: iris studies are the tuning set: 08 and 09 pin every number they quote, so a
#: clean scan is the correct answer and any regression in the exemptions or the
#: index shows up here as a non-zero count.  07 predates the practice of pinning
#: derived quantities: each of its 39 hits is a real derived value (a delta, a
#: multiple of delta, an aggregate wall time) with no pinned home — no false
#: positives, which is what the ceiling below asserts.
SHIPPED_FINDINGS_CEILING = {
    "07-iris-90years": 39,
    "08-iris-rematch": 0,
    "09-iris-first-lesson": 0,
}


@pytest.mark.parametrize("slug", sorted(SHIPPED_FINDINGS_CEILING))
def test_the_shipped_iris_findings_scan_at_the_reported_rate(slug: str) -> None:
    study = REPO_ROOT / "studies" / slug
    findings = study / "findings.md"
    if not findings.is_file():  # pragma: no cover - a trimmed checkout
        pytest.skip(f"{slug} is not in this checkout")
    state = json.loads((study / "study_state.json").read_text(encoding="utf-8"))
    index = LiteralIndex.for_study(study, state, exclude=[findings])
    caught = unsourced_literals(findings.read_text(encoding="utf-8"), index)
    assert len(caught) <= SHIPPED_FINDINGS_CEILING[slug], [
        item.describe() for item in caught
    ]


def test_the_bibliographic_classes_that_made_07_s_reference_section_noisy() -> None:
    """The FP class the tuning pass removed: a references section's identifiers.

    Order matters — the document exemptions run BEFORE the sentence exemptions,
    or the year inside a DOI is stripped first and breaks the DOI's span.
    """
    line = (
        "- **Fisher (1936), *Annals of Eugenics* 7(2):179-188 — VERIFIED 2026-08-25** "
        "(DOI 10.1111/j.1469-1809.1936.tb02137.x; eprint 33079)\n"
    )
    assert tokens(line) == []
