"""Unit tests for scripts/check_shipped_reports.py — no browser, no PDF tools.

The script's whole job is to launch Chrome, so everything testable is the layer
either side of that subprocess: the wrapper page it writes, the JSON it reads
back out of a dumped DOM, and the arithmetic that turns a measurement into
PASS / FAIL / LEGACY / SKIP.  Mirrors the mocking style of
``test_tutorial_network.py`` (load by path, monkeypatch at the module).
"""

from __future__ import annotations

import base64
import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = REPO_ROOT / "scripts" / "check_shipped_reports.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("klein_shipped_reports", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["klein_shipped_reports"] = module
    spec.loader.exec_module(module)
    return module


def _dumped_dom(payload: dict) -> str:
    """What Chrome's --dump-dom looks like once the wrapper has emitted."""
    encoded = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("ascii")
    return (
        f'<!DOCTYPE html><html><head></head><body><pre id="result">{encoded}</pre>'
        '<iframe id="frame"></iframe></body></html>'
    )


def _width_result(**overrides) -> dict:
    result = {
        "width": 390,
        "inner_width": 390,
        "scroll_width": 390,
        "overflow": [],
        "overflow_count": 0,
        "reveal": [{"id": "question", "top": 44.0, "nav_bottom": 41.0}],
    }
    result.update(overrides)
    return result


# --- the wrapper page -------------------------------------------------------


def test_build_wrapper_carries_the_report_uri_and_every_width() -> None:
    module = _load_module()
    page = module.build_wrapper(
        "file:///repo/studies/15-x/report/index.html", [1440, 768, 390, 320]
    )
    assert 'src="file:///repo/studies/15-x/report/index.html"' in page
    assert "var WIDTHS = [1440, 768, 390, 320];" in page
    # The frame starts at the first requested width so the very first measure()
    # is not measuring a relayout in progress.
    assert "width:1440px" in page
    assert 'id="result">PENDING<' in page
    assert module.LOCAL_SCROLL_ALLOWED in page


def test_build_wrapper_escapes_the_report_uri() -> None:
    module = _load_module()
    page = module.build_wrapper('file:///tmp/a"><script>x</script>.html', [390])
    assert "<script>x</script>.html" not in page
    assert "&quot;&gt;&lt;script&gt;" in page


def test_build_wrapper_refuses_an_empty_width_list() -> None:
    module = _load_module()
    try:
        module.build_wrapper("file:///x.html", [])
    except ValueError as exc:
        assert "width" in str(exc)
    else:  # pragma: no cover - the raise above is the contract
        raise AssertionError("build_wrapper accepted an empty width list")


# --- reading the measurement back out of a dumped DOM -----------------------


def test_parse_wrapper_dom_decodes_the_base64_payload() -> None:
    module = _load_module()
    payload = {"ok": True, "images": [], "widths": [_width_result()]}
    assert module.parse_wrapper_dom(_dumped_dom(payload)) == payload


def test_parse_wrapper_dom_fails_closed_on_a_page_that_never_finished() -> None:
    module = _load_module()
    for dom, expected in (
        ("<html><body>no pre here</body></html>", "no <pre"),
        ('<pre id="result">PENDING</pre>', "did not finish"),
        ('<pre id="result">not base64!!</pre>', "not valid base64"),
    ):
        try:
            module.parse_wrapper_dom(dom)
        except RuntimeError as exc:
            assert expected in str(exc), (dom, exc)
        else:  # pragma: no cover
            raise AssertionError(f"parse_wrapper_dom accepted {dom!r}")


def test_parse_wrapper_dom_surfaces_an_in_browser_error() -> None:
    module = _load_module()
    dom = _dumped_dom({"ok": False, "error": "TypeError: contentDocument is null"})
    try:
        module.parse_wrapper_dom(dom)
    except RuntimeError as exc:
        assert "contentDocument is null" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("parse_wrapper_dom accepted a failed measurement")


# --- LEGACY classification --------------------------------------------------


def test_schema_version_reads_only_the_top_level_key() -> None:
    module = _load_module()
    contract = "study: 09-iris\nschema_version: 2\ntracks:\n  primary:\n    schema_version: 99\n"
    assert module.schema_version(contract) == 2
    assert module.schema_version("study: old\n") is None
    assert module.schema_version("schema_version: 3\n") == 3


CURRENT_PAGE = '<!doctype html>\n<html><head><meta charset="utf-8">\n<meta name="generator" content="klein build_tutorial layout-2">\n<title>t</title></head><body></body></html>\n'


def test_schema_two_and_v1_are_legacy_and_a_current_schema_three_page_is_not() -> None:
    module = _load_module()
    assert module.is_legacy(None, CURRENT_PAGE) is True
    assert module.is_legacy(2, CURRENT_PAGE) is True
    assert module.is_legacy(3, CURRENT_PAGE) is False
    assert module.legacy_reason(2, CURRENT_PAGE) == "schema 2 study"
    assert module.legacy_reason(None, CURRENT_PAGE) == "schema v1 study"
    assert module.legacy_reason(3, CURRENT_PAGE) is None


def test_a_schema_three_page_built_before_the_layout_generation_is_legacy() -> None:
    """The shipped schema-3 reports predate the phone/print stylesheet; a CSS fix
    must not turn them red, so the check keys off the builder's generator tag."""
    module = _load_module()
    untagged = CURRENT_PAGE.replace(
        '<meta name="generator" content="klein build_tutorial layout-2">\n', ""
    )
    assert module.layout_generation(untagged) is None
    assert module.is_legacy(3, untagged) is True
    assert "no generator tag" in module.legacy_reason(3, untagged)
    older = CURRENT_PAGE.replace("layout-2", "layout-1")
    assert module.layout_generation(older) == 1
    assert module.legacy_reason(3, older) == "built at layout generation 1, check asserts 2"
    assert module.layout_generation(CURRENT_PAGE) == 2


# --- the check arithmetic ---------------------------------------------------


def test_check_overflow_passes_a_page_that_fits() -> None:
    module = _load_module()
    ok, message = module.check_overflow(_width_result())
    assert ok and message == ""


def test_check_overflow_names_the_page_and_every_offending_element() -> None:
    module = _load_module()
    ok, message = module.check_overflow(
        _width_result(
            scroll_width=520,
            overflow=[
                {
                    "tag": "div",
                    "cls": "callout wide",
                    "scroll_width": 480,
                    "client_width": 358,
                    "text": "A very wide callout",
                }
            ],
            overflow_count=1,
        )
    )
    assert not ok
    assert "page scrollWidth 520 > innerWidth 390" in message
    assert "div.callout 480>358" in message
    assert "A very wide callout" in message


def test_check_overflow_reports_elements_beyond_the_capped_list() -> None:
    module = _load_module()
    ok, message = module.check_overflow(_width_result(overflow=[], overflow_count=7))
    assert not ok
    assert "and 7 more overflowing element(s)" in message


def test_check_nav_reveal_fails_an_anchor_swallowed_by_the_sticky_nav() -> None:
    module = _load_module()
    ok, message = module.check_nav_reveal(
        _width_result(reveal=[{"id": "method", "top": 12.0, "nav_bottom": 41.0}])
    )
    assert not ok
    assert "#method top 12.0 < nav bottom 41.0" in message
    assert "hidden by 29px" in message


def test_check_nav_reveal_passes_when_every_target_clears_the_nav() -> None:
    module = _load_module()
    ok, message = module.check_nav_reveal(
        _width_result(
            reveal=[
                {"id": "a", "top": 41.0, "nav_bottom": 41.0},
                {"id": "b", "top": 90.0, "nav_bottom": 41.0},
            ]
        )
    )
    assert ok and message == ""


def test_check_images_requires_a_decode_and_honest_size_attributes() -> None:
    module = _load_module()
    ok, message = module.check_images(
        [
            {
                "natural_width": 800,
                "natural_height": 600,
                "attr_width": None,
                "attr_height": None,
                "alt": "fig",
            }
        ]
    )
    assert ok and message == ""

    ok, message = module.check_images(
        [
            {
                "natural_width": 0,
                "natural_height": 0,
                "attr_width": None,
                "attr_height": None,
                "alt": "broken",
            }
        ]
    )
    assert not ok and "did not decode" in message

    ok, message = module.check_images(
        [
            {
                "natural_width": 800,
                "natural_height": 600,
                "attr_width": "640",
                "attr_height": "600",
                "alt": "",
            }
        ]
    )
    assert not ok and "declares width=640 but decoded 800" in message

    ok, message = module.check_images([])
    assert ok and message == "no <img> elements"


# --- print ------------------------------------------------------------------


def test_pdf_page_count_ignores_the_pages_tree_node() -> None:
    module = _load_module()
    pdf = b"<< /Type /Pages /Count 3 >> << /Type /Page >> << /Type/Page >> <</Type /Page>>"
    assert module.pdf_page_count(pdf) == 3


def test_longest_code_line_unescapes_the_first_highlighted_block() -> None:
    module = _load_module()
    report = (
        '<pre class="klein-code"><span class="k">def</span> f():\n'
        '    <span class="n">x</span> = a &amp; b &lt;&lt; 2  # the long one\n</pre>'
        '<pre class="klein-code">short</pre>'
    )
    assert module.longest_code_line(report) == "    x = a & b << 2  # the long one"
    assert module.longest_code_line("<p>no code here</p>") is None


def test_evaluate_print_skips_text_assertions_when_pdftotext_is_absent() -> None:
    module = _load_module()
    pdf = b"<< /Type /Page >> << /Type /Page >>"
    ok, message, details = module.evaluate_print(pdf, None, "<html></html>")
    assert ok
    assert message.startswith("print text assertions skipped: pdftotext absent")
    assert details["pages"] == 2
    assert details["text_assertions"] == "skipped"


def test_evaluate_print_still_requires_two_pages_without_pdftotext() -> None:
    module = _load_module()
    ok, message, _ = module.evaluate_print(b"<< /Type /Page >>", None, "<html></html>")
    assert not ok
    assert "1 page object(s), expected at least 2" in message


def test_evaluate_print_asserts_the_ledger_header_and_longest_code_line() -> None:
    module = _load_module()
    report = '<pre class="klein-code">uv run --locked klein verify --numbers --evidence-use</pre>'
    pdf = b"<< /Type /Page >> << /Type /Page >>"
    text = (
        "Experiment  Metric  Description\nkeep    0.97   the winner\n\n"
        "uv    run   --locked    klein   verify   --numbers   --evidence-use\n"
    )
    ok, message, details = module.evaluate_print(pdf, text, report)
    assert ok, message
    assert details["longest_code_line"] == "uv run --locked klein verify --numbers --evidence-use"

    ok, message, _ = module.evaluate_print(pdf, "Experiment Metric Description\n", report)
    assert not ok
    assert "missing the longest code line" in message

    ok, message, _ = module.evaluate_print(
        pdf, "uv run --locked klein verify --numbers --evidence-use\n", report
    )
    assert not ok
    assert "missing the ledger's last column header 'Description'" in message


def test_evaluate_print_reports_but_never_fails_near_empty_pages() -> None:
    module = _load_module()
    report = '<pre class="klein-code">x = 1</pre>'
    pdf = b"<< /Type /Page >> << /Type /Page >>"
    text = "Description\nx = 1\nline three\n\f\n\n\f Description again\nx = 1\nthree\n"
    ok, message, details = module.evaluate_print(pdf, text, report)
    assert ok, message
    assert details["text_pages"] == 3
    assert details["sparse_pages"] == [2]
    assert "near-empty text pages (likely figure-only): [2]" in message


# --- statuses and exit codes ------------------------------------------------


def test_decide_exit_ignores_legacy_and_skip_rows() -> None:
    module = _load_module()
    rows = [
        {
            "study": "09",
            "check": "overflow@390",
            "status": module.LEGACY,
            "detail": "page scrollWidth 700 > innerWidth 390",
        },
        {"study": "09", "check": "print", "status": module.SKIP, "detail": ""},
        {"study": "15", "check": "overflow@390", "status": module.PASS, "detail": "fits"},
    ]
    assert module.decide_exit(rows) == 0
    rows.append(
        {"study": "15", "check": "nav@320", "status": module.FAIL, "detail": "#method hidden"}
    )
    assert module.decide_exit(rows) == 1


def test_render_row_leads_with_the_status() -> None:
    module = _load_module()
    line = module.render_row(
        {"study": "15-iris", "check": "nav@320", "status": module.FAIL, "detail": "#method hidden"}
    )
    assert line.startswith("FAIL   15-iris")
    assert line.endswith("#method hidden")


def test_check_report_labels_every_row_legacy_for_a_schema_two_study(tmp_path, monkeypatch) -> None:
    """A schema-2 report is still measured — its numbers just cannot fail the run."""
    module = _load_module()
    study = tmp_path / "09-iris-first-lesson"
    (study / "report").mkdir(parents=True)
    (study / "report" / "index.html").write_text("<html></html>", encoding="utf-8")

    class _FakeNetwork:
        @staticmethod
        def _run_chrome(chrome, target, work_dir):
            return [], None

        @staticmethod
        def page_initiated_urls(urls, noise_hosts):
            return []

    measurement = {
        "ok": True,
        "images": [
            {
                "natural_width": 0,
                "natural_height": 0,
                "attr_width": None,
                "attr_height": None,
                "alt": "broken",
            }
        ],
        "widths": [
            _width_result(
                width=390,
                scroll_width=900,
                reveal=[{"id": "method", "top": 2.0, "nav_bottom": 41.0}],
            )
        ],
    }
    monkeypatch.setattr(module, "run_chrome_dump", lambda *args, **kwargs: _dumped_dom(measurement))

    rows, evidence = module.check_report(
        study, "/fake/chrome", _FakeNetwork, set(), tmp_path, (390,), True, 5.0, 60.0
    )
    assert evidence["legacy"] is True
    assert {row["status"] for row in rows} == {module.LEGACY}
    assert module.decide_exit(rows) == 0
    # The measurement itself is preserved verbatim, defects and all.
    assert any("page scrollWidth 900 > innerWidth 390" in row["detail"] for row in rows)
    assert any("did not decode" in row["detail"] for row in rows)


def test_check_report_fails_the_same_defects_on_a_schema_three_study(tmp_path, monkeypatch) -> None:
    module = _load_module()
    study = tmp_path / "15-iris-90years-relaunch"
    (study / "report").mkdir(parents=True)
    (study / "report" / "index.html").write_text("<html></html>", encoding="utf-8")

    class _FakeNetwork:
        @staticmethod
        def _run_chrome(chrome, target, work_dir):
            return ["https://cdn.example.invalid/leak.js"], None

        @staticmethod
        def page_initiated_urls(urls, noise_hosts):
            return list(urls)

    measurement = {
        "ok": True,
        "images": [],
        "widths": [_width_result(width=320, scroll_width=900, inner_width=320)],
    }
    monkeypatch.setattr(module, "run_chrome_dump", lambda *args, **kwargs: _dumped_dom(measurement))

    rows, _ = module.check_report(
        study, "/fake/chrome", _FakeNetwork, set(), tmp_path, (320,), False, 5.0, 60.0
    )
    statuses = {row["check"]: row["status"] for row in rows}
    assert statuses["network"] == module.FAIL
    assert statuses["overflow@320"] == module.FAIL
    assert statuses["nav@320"] == module.PASS
    assert module.decide_exit(rows) == 1


def test_check_report_reports_an_unmeasurable_report_as_a_failure(tmp_path, monkeypatch) -> None:
    module = _load_module()
    study = tmp_path / "12-insurance-claims-frequency"
    (study / "report").mkdir(parents=True)
    (study / "report" / "index.html").write_text("<html></html>", encoding="utf-8")

    class _FakeNetwork:
        @staticmethod
        def _run_chrome(chrome, target, work_dir):
            return [], None

        @staticmethod
        def page_initiated_urls(urls, noise_hosts):
            return []

    def _boom(*args, **kwargs):
        raise RuntimeError("Chrome did not finish the measurement within 180 s")

    monkeypatch.setattr(module, "run_chrome_dump", _boom)
    rows, evidence = module.check_report(
        study, "/fake/chrome", _FakeNetwork, set(), tmp_path, (390,), False, 5.0, 60.0
    )
    assert [row["check"] for row in rows] == ["network", "overflow", "nav", "images"]
    assert {row["status"] for row in rows[1:]} == {module.FAIL}
    assert "did not finish" in evidence["measure_error"]


# --- CLI --------------------------------------------------------------------


def test_unknown_studies_selector_is_a_usage_error(capsys) -> None:
    module = _load_module()
    assert module.main(["--studies", "99-not-a-study"]) == 2
    assert "unknown studies: 99-not-a-study" in capsys.readouterr().err


def test_unknown_print_study_is_a_usage_error(capsys) -> None:
    module = _load_module()
    assert module.main(["--print-study", "99-not-a-study"]) == 2
    assert "--print-study named an unknown study" in capsys.readouterr().err


def test_non_positive_width_is_a_usage_error(capsys) -> None:
    module = _load_module()
    assert module.main(["--widths", "390", "0"]) == 2
    assert "--widths must be positive" in capsys.readouterr().err


def test_studies_selector_accepts_the_studies_prefix() -> None:
    module = _load_module()
    assert (
        module._normalize_selector("studies/15-iris-90years-relaunch/")
        == "15-iris-90years-relaunch"
    )
    assert module._normalize_selector(" 09-iris-first-lesson ") == "09-iris-first-lesson"
