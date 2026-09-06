#!/usr/bin/env python3
"""Focused acceptance on the twelve SHIPPED tutorials, measured in a real browser.

``check_generated_tutorial_network.py`` proves a *freshly generated* tutorial
starts zero HTTP(S) requests.  This script asks the complementary question the
network job deliberately refuses: do the reports we already shipped actually
*read* on a phone, reveal their own anchors under the sticky nav, decode every
inlined figure, and survive ``Print to PDF``?  Nothing here rebuilds a study —
every report is opened read-only from its committed ``file://`` path.

Five checks per report:

1. ``network``  — zero page-initiated HTTP(S) requests, differenced against an
   ``about:blank`` baseline (the sibling script's netlog machinery, imported so
   the two jobs can never drift apart).
2. ``overflow`` — at 1440/768/390/320 px, ``scrollWidth <= innerWidth`` for the
   page, and no element outside the sanctioned local-scroll list overflows.
3. ``nav``      — every ``nav.topnav`` anchor (and every ``h3[id]``) lands BELOW
   the sticky nav's bottom edge at 390 and 320 px.  A sticky header with no
   ``scroll-margin-top`` swallows the heading you just clicked; that is the
   defect this check exists to name.
4. ``images``   — every ``img`` decoded (``naturalWidth > 0``) and, where the
   markup declares ``width``/``height``, they equal the natural size.
5. ``print``    — one report is printed to PDF and its text re-read.

Schema-2 studies (03, 05-09) are shipped history: they are measured and their
numbers reported, but their rows are labelled ``LEGACY`` and can never fail the
run.  Only a schema-3 report's FAIL sets the exit code.

Measurement mechanism -- why an iframe wrapper
----------------------------------------------
The reports ship a ``default-src 'none'`` CSP with a per-page ``script-src
'sha256-...'``, so no measurement script can be injected into the report itself.
Instead this script writes a WRAPPER page into a temp dir that ``<iframe>``s the
report and runs the measurement against ``iframe.contentDocument``.  Chrome's
``--allow-file-access-from-files`` makes ``file://`` documents same-origin, so
the parent may read the child's layout; the child's CSP is untouched because the
script never executes *in* the child realm.  The result is base64'd into the
wrapper's own ``<pre id="result">`` and read back out of ``--dump-dom``, so the
whole exchange is one bounded subprocess with no debugging port and no
websocket client.

Resizing the ``<iframe>`` element (rather than launching one Chrome per width)
re-evaluates the report's media queries against the frame's viewport, which is
what a narrower phone would do -- one browser per report instead of four, which
is what keeps a twelve-report run inside a few minutes.

Known browser defect (macOS): ``Google Chrome 152 --headless=new`` on macOS
never returns from ``--dump-dom`` when the page contains ANY ``<iframe>`` --
reproduced with a two-line frame and an empty child, with and without
``--allow-file-access-from-files``.  The same wrapper, the same flags and the
same Chromium engine complete in 0.2 s under ``chrome-headless-shell``, and
Linux CI's ``/usr/bin/google-chrome`` is unaffected.  Pass ``--chrome
/path/to/chrome-headless-shell`` on a Mac.  ``--chrome-timeout`` bounds the wait
either way, so a browser that hangs produces FAIL rows naming the report rather
than a job that runs until the runner kills it.

Usage::

    uv run --locked python scripts/check_shipped_reports.py
    uv run --locked python scripts/check_shipped_reports.py \\
        --studies 15-iris-90years-relaunch --evidence shipped-reports-evidence.json

Exit code is 1 if any schema-3 report fails a check, 2 on a usage error (e.g. an
unknown ``--studies`` name, or a browser that cannot be found), 0 otherwise.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import html
import importlib.util
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

REPO_ROOT = Path(__file__).resolve().parents[1]
STUDIES_DIR = REPO_ROOT / "studies"
NETWORK_SCRIPT = REPO_ROOT / "scripts" / "check_generated_tutorial_network.py"

DEFAULT_WIDTHS = (1440, 768, 390, 320)
# The nav-reveal assertion is a phone problem: at 1440/768 the nav is one line
# tall and nothing is ever swallowed, so asserting there only adds noise.  The
# measurement still runs at every width and lands in the evidence record.
NAV_REVEAL_WIDTHS = (390, 320)
DEFAULT_PRINT_STUDY = "15-iris-90years-relaunch"

# Elements allowed to scroll horizontally INSIDE themselves.  A wide code block,
# a wide ledger, a wide equation and the nav's own wrap are deliberate local
# scrollers; anything else that overflows is pushing the page sideways.
LOCAL_SCROLL_ALLOWED = "pre,table,.kmath,.kmath-display,nav.topnav .wrap,figure.fig:target"

# Sub-pixel layout rounding makes an exact `>` comparison chatter, so a box only
# counts as overflowing once it is a whole CSS pixel too wide.
OVERFLOW_TOLERANCE_PX = 1

# Top-level (column-0) key only -- nested contract keys are indented, so this
# never matches inside a mapping.  Same idiom as verify_shipped_studies.py.
SCHEMA_VERSION_RE = re.compile(r"^schema_version:\s*(\d+)", re.MULTILINE)
RESULT_RE = re.compile(r'<pre id="result">([^<]*)</pre>')
FIRST_CODE_BLOCK_RE = re.compile(r'<pre class="klein-code"[^>]*>(.*?)</pre>', re.DOTALL)
TAG_RE = re.compile(r"<[^>]*>")
# "/Type /Page" but never "/Type /Pages" -- the tree node is not a page.
PDF_PAGE_RE = re.compile(rb"/Type\s*/Page(?![s/\w])")

PASS = "PASS"
FAIL = "FAIL"
LEGACY = "LEGACY"
SKIP = "SKIP"

WRAPPER_TEMPLATE = """<!doctype html>
<meta charset="utf-8">
<title>klein shipped-report probe</title>
<style>
html,body{{margin:0;padding:0;overflow:hidden;background:#fff}}
#frame{{border:0;display:block;height:900px;width:{first_width}px}}
</style>
<pre id="result">PENDING</pre>
<iframe id="frame" src="{report_uri}"></iframe>
<script>
var WIDTHS = {widths};
var ALLOW = {allow};
var TOLERANCE = {tolerance};

function emit(payload) {{
  // base64 so the JSON survives DOM serialization byte-for-byte: --dump-dom
  // escapes &, < and > inside a text node, and a quoted JSON string is full of
  // characters we would then have to un-escape by guesswork.
  document.getElementById('result').textContent =
    btoa(unescape(encodeURIComponent(JSON.stringify(payload))));
}}

function classOf(el) {{
  var c = el.className;
  if (c && typeof c === 'object' && 'baseVal' in c) return c.baseVal;  // SVG
  return typeof c === 'string' ? c : '';
}}

function measure(frame, width) {{
  var doc = frame.contentDocument, win = frame.contentWindow;
  frame.style.width = width + 'px';
  doc.documentElement.getBoundingClientRect();  // force a synchronous relayout

  var overflow = [], all = doc.querySelectorAll('*');
  for (var i = 0; i < all.length; i++) {{
    var el = all[i];
    if (el.scrollWidth - el.clientWidth <= TOLERANCE) continue;
    if (el.matches(ALLOW)) continue;
    overflow.push({{
      tag: el.tagName.toLowerCase(),
      cls: classOf(el),
      scroll_width: el.scrollWidth,
      client_width: el.clientWidth,
      text: (el.textContent || '').replace(/\\s+/g, ' ').slice(0, 40)
    }});
  }}

  var nav = doc.querySelector('nav.topnav');
  var ids = [];
  if (nav) {{
    [].forEach.call(nav.querySelectorAll('a'), function (a) {{
      var href = a.getAttribute('href') || '';
      if (href.charAt(0) === '#' && href.length > 1) ids.push(href.slice(1));
    }});
  }}
  [].forEach.call(doc.querySelectorAll('h3[id]'), function (h) {{ ids.push(h.id); }});

  var reveal = [];
  ids.forEach(function (id) {{
    win.location.hash = '#' + id;
    var target = doc.getElementById(id);
    if (!target) {{ reveal.push({{id: id, missing: true}}); return; }}
    // Re-read the nav each time: it is position:sticky, so its bottom edge
    // moves with the scroll offset the hash jump just produced.
    var navBottom = nav ? nav.getBoundingClientRect().bottom : 0;
    reveal.push({{
      id: id,
      top: Math.round(target.getBoundingClientRect().top * 100) / 100,
      nav_bottom: Math.round(navBottom * 100) / 100
    }});
  }});
  win.location.hash = '';

  return {{
    width: width,
    inner_width: win.innerWidth,
    scroll_width: doc.scrollingElement.scrollWidth,
    overflow: overflow.slice(0, 40),
    overflow_count: overflow.length,
    reveal: reveal
  }};
}}

window.addEventListener('load', function () {{
  try {{
    var frame = document.getElementById('frame');
    var doc = frame.contentDocument;
    if (!doc) throw new Error('iframe contentDocument is null (same-origin file access denied?)');

    // Zero-width scrollbars make the measurement identical on macOS (overlay
    // scrollbars) and Linux CI (classic 15 px scrollbars), so `inner_width`
    // is the requested width on both.  style-src 'unsafe-inline' already
    // permits this; scroll-behavior:auto kills the smooth-scroll animation so
    // a hash jump has landed by the time we read the rect.
    var style = doc.createElement('style');
    style.textContent =
      '*::-webkit-scrollbar{{width:0!important;height:0!important}}' +
      'html{{scroll-behavior:auto!important}}';
    doc.head.appendChild(style);

    var images = [].map.call(doc.querySelectorAll('img'), function (img) {{
      return {{
        natural_width: img.naturalWidth,
        natural_height: img.naturalHeight,
        attr_width: img.getAttribute('width'),
        attr_height: img.getAttribute('height'),
        alt: (img.getAttribute('alt') || '').slice(0, 40)
      }};
    }});

    var widths = WIDTHS.map(function (w) {{ return measure(frame, w); }});
    emit({{ok: true, images: images, widths: widths}});
  }} catch (err) {{
    emit({{ok: false, error: String((err && err.stack) || err)}});
  }}
}});
</script>
"""


def load_network_module():
    """Import the sibling netlog checker by path.

    Same loader the sibling's own tests use.  Importing rather than copying is
    the point: ``started_http_urls`` reads Chrome's netlog at exactly one event
    boundary, and the two jobs must never disagree about where that boundary is.
    """
    spec = importlib.util.spec_from_file_location("klein_tutorial_network", NETWORK_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {NETWORK_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["klein_tutorial_network"] = module
    spec.loader.exec_module(module)
    return module


def discover_reports() -> list[Path]:
    """Every studies/<name> that ships a report/index.html, sorted by name."""
    return sorted(
        (
            path.parent
            for path in STUDIES_DIR.glob("*/study.yaml")
            if (path.parent / "report" / "index.html").is_file()
        ),
        key=lambda path: path.name,
    )


def schema_version(contract_text: str) -> int | None:
    """The contract's top-level schema_version, or None when the key is absent (v1)."""
    match = SCHEMA_VERSION_RE.search(contract_text)
    return int(match.group(1)) if match else None


def is_legacy(version: int | None) -> bool:
    """Schema-2 and schema-v1 reports are shipped history, never rebuilt."""
    return version is None or version < 3


def _repo_relative(path: Path) -> str:
    """``studies/<name>/report/index.html`` when we are inside the checkout.

    .as_posix(), not str(): on Windows a bare str() renders backslashes, and
    this string is what the evidence record (and anyone diffing two runs) keys
    off of.  A path outside the repo — a fixture under pytest's tmp_path — falls
    back to its absolute form rather than raising.
    """
    try:
        return path.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _normalize_selector(value: str) -> str:
    value = value.strip().rstrip("/")
    if value.startswith("studies/"):
        value = value[len("studies/") :]
    return value


def build_wrapper(report_uri: str, widths: tuple[int, ...] | list[int]) -> str:
    """The measurement wrapper page for one report at every requested width.

    ``report_uri`` lands in an HTML attribute, so it is escaped even though a
    file:// URI produced by ``Path.as_uri()`` is already percent-encoded — the
    rule in this repo is that every interpolated string is escaped, with no
    "but this one is safe" exceptions to audit later.
    """
    if not widths:
        raise ValueError("build_wrapper needs at least one width")
    return WRAPPER_TEMPLATE.format(
        report_uri=html.escape(report_uri, quote=True),
        first_width=int(widths[0]),
        widths=json.dumps([int(width) for width in widths]),
        allow=json.dumps(LOCAL_SCROLL_ALLOWED),
        tolerance=json.dumps(OVERFLOW_TOLERANCE_PX),
    )


def parse_wrapper_dom(dom: str) -> dict[str, Any]:
    """Decode the wrapper's ``<pre id="result">`` payload out of a dumped DOM.

    Fails closed: a missing pre, a still-``PENDING`` pre and undecodable base64
    are three different ways the page did not finish, and each names itself.
    """
    match = RESULT_RE.search(dom)
    if match is None:
        raise RuntimeError(
            'wrapper DOM has no <pre id="result"> element (did Chrome dump the wrapper?)'
        )
    payload = match.group(1).strip()
    if not payload or payload == "PENDING":
        raise RuntimeError("wrapper script did not finish before Chrome dumped the DOM")
    try:
        decoded = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise RuntimeError(f"wrapper result is not valid base64: {exc}") from exc
    result = json.loads(decoded.decode("utf-8"))
    if not result.get("ok"):
        raise RuntimeError(f"wrapper measurement failed in the browser: {result.get('error')}")
    return result


def run_chrome_dump(chrome: str, target: str, work_dir: Path, timeout: float) -> str:
    """One headless load of *target*, returning the dumped DOM.

    ``start_new_session`` + a process-group kill on timeout: Chrome spawns a
    helper tree, and a plain ``Popen.kill()`` leaves the renderers behind to
    contend with the next report's browser.
    """
    profile = work_dir / "wrapper-profile"
    command = [
        chrome,
        "--headless=new",
        "--allow-file-access-from-files",  # makes the file:// iframe same-origin for the wrapper
        "--disable-background-networking",
        "--disable-component-update",
        "--disable-default-apps",
        "--disable-dev-shm-usage",
        "--disable-domain-reliability",
        "--disable-gpu",
        "--disable-sync",
        "--metrics-recording-only",
        "--no-default-browser-check",
        "--no-first-run",
        f"--user-data-dir={profile}",
        "--window-size=1600,1000",  # the parent frame only; the iframe supplies the tested width
        "--virtual-time-budget=15000",
        "--dump-dom",
        target,
    ]
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_process_tree(process)
        raise RuntimeError(
            f"Chrome did not finish the measurement within {timeout:.0f} s"
        ) from None
    if process.returncode != 0:
        raise RuntimeError(
            f"Chrome failed ({process.returncode}):\n{stdout[-1000:]}\n{stderr[-1000:]}"
        )
    return stdout


def _kill_process_tree(process: subprocess.Popen[str]) -> None:
    """Kill a headless Chrome and its helpers, then reap it."""
    try:
        if hasattr(os, "killpg"):
            os.killpg(os.getpgid(process.pid), signal.SIGKILL)
        else:  # pragma: no cover - Windows has no process groups here
            process.kill()
    except (ProcessLookupError, PermissionError, OSError):
        process.kill()
    try:
        process.communicate(timeout=15)
    except subprocess.TimeoutExpired:  # pragma: no cover - the kill above already landed
        pass


def check_overflow(width_result: dict[str, Any]) -> tuple[bool, str]:
    """The page must not scroll sideways, and only sanctioned boxes may."""
    problems: list[str] = []
    inner = width_result["inner_width"]
    scroll = width_result["scroll_width"]
    if scroll - inner > OVERFLOW_TOLERANCE_PX:
        problems.append(f"page scrollWidth {scroll} > innerWidth {inner}")
    for element in width_result.get("overflow", []):
        selector = element["tag"] + (f".{element['cls'].split()[0]}" if element.get("cls") else "")
        problems.append(
            f"{selector} {element['scroll_width']}>{element['client_width']} {element['text']!r}"
        )
    extra = width_result.get("overflow_count", 0) - len(width_result.get("overflow", []))
    if extra > 0:
        problems.append(f"... and {extra} more overflowing element(s)")
    return (not problems), "; ".join(problems)


def check_nav_reveal(width_result: dict[str, Any]) -> tuple[bool, str]:
    """Every anchor must land at or below the sticky nav's bottom edge."""
    problems: list[str] = []
    for entry in width_result.get("reveal", []):
        if entry.get("missing"):
            problems.append(f"#{entry['id']} has no target element")
            continue
        top, nav_bottom = entry["top"], entry["nav_bottom"]
        if top < nav_bottom:
            problems.append(
                f"#{entry['id']} top {top} < nav bottom {nav_bottom} (hidden by {nav_bottom - top:.0f}px)"
            )
    return (not problems), "; ".join(problems)


def check_images(images: list[dict[str, Any]]) -> tuple[bool, str]:
    """Every inlined figure decoded, and any declared size is the real one."""
    problems: list[str] = []
    for index, image in enumerate(images):
        label = f"img[{index}]" + (f" ({image['alt']})" if image.get("alt") else "")
        if not image.get("natural_width"):
            problems.append(f"{label} did not decode (naturalWidth=0)")
            continue
        for axis, attribute, natural in (
            ("width", image.get("attr_width"), image["natural_width"]),
            ("height", image.get("attr_height"), image["natural_height"]),
        ):
            if attribute is None:
                continue
            try:
                declared = int(str(attribute).strip())
            except ValueError:
                problems.append(f"{label} has a non-integer {axis} attribute {attribute!r}")
                continue
            if declared != natural:
                problems.append(f"{label} declares {axis}={declared} but decoded {natural}")
    if not images:
        return True, "no <img> elements"
    return (not problems), "; ".join(problems)


def longest_code_line(report_html: str) -> str | None:
    """The longest source line of the report's FIRST highlighted code block.

    Pygments wraps every token in a span, so the text has to be recovered by
    stripping tags and unescaping — the resulting string is what must survive
    into the printed PDF unclipped.
    """
    match = FIRST_CODE_BLOCK_RE.search(report_html)
    if match is None:
        return None
    text = html.unescape(TAG_RE.sub("", match.group(1)))
    lines = [line.rstrip() for line in text.splitlines() if line.strip()]
    return max(lines, key=len) if lines else None


def _squash(text: str) -> str:
    """Whitespace-insensitive comparison: pdftotext re-spaces what it lays out."""
    return " ".join(text.split())


def pdf_page_count(pdf_bytes: bytes) -> int:
    """Pages counted from the PDF's own page objects, excluding the /Pages tree."""
    return len(PDF_PAGE_RE.findall(pdf_bytes))


def print_to_pdf(chrome: str, report: Path, pdf_path: Path, timeout: float) -> None:
    """Render *report* through Chrome's print pipeline, headers and footers off."""
    command = [
        chrome,
        "--headless=new",
        "--disable-gpu",
        "--disable-background-networking",
        "--disable-component-update",
        "--no-default-browser-check",
        "--no-first-run",
        f"--user-data-dir={pdf_path.parent / 'print-profile'}",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path}",
        "--virtual-time-budget=15000",
        report.resolve().as_uri(),
    ]
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True
    )
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_process_tree(process)
        raise RuntimeError(f"Chrome did not print the report within {timeout:.0f} s") from None
    if process.returncode != 0:
        raise RuntimeError(
            f"Chrome --print-to-pdf failed ({process.returncode}):\n{stdout[-800:]}\n{stderr[-800:]}"
        )
    if not pdf_path.is_file():
        raise RuntimeError("Chrome reported success without writing the PDF")


def evaluate_print(
    pdf_bytes: bytes,
    layout_text: str | None,
    report_html: str,
) -> tuple[bool, str, dict[str, Any]]:
    """Adjudicate the print check from the PDF bytes and (optional) extracted text.

    Split out from the browser and ``pdftotext`` subprocesses so the decision
    logic is testable without either binary on PATH.
    """
    details: dict[str, Any] = {"pdf_bytes": len(pdf_bytes), "pages": pdf_page_count(pdf_bytes)}
    problems: list[str] = []
    if details["pages"] < 2:
        problems.append(f"PDF has {details['pages']} page object(s), expected at least 2")

    if layout_text is None:
        details["text_assertions"] = "skipped"
        message = "print text assertions skipped: pdftotext absent"
        if problems:
            return False, f"{message}; {'; '.join(problems)}", details
        return True, f"{message}; PDF exists with {details['pages']} pages", details

    details["text_assertions"] = "run"
    haystack = _squash(layout_text)
    if "Description" not in layout_text:
        problems.append("printed text is missing the ledger's last column header 'Description'")
    code_line = longest_code_line(report_html)
    details["longest_code_line"] = code_line
    if code_line is None:
        problems.append('report has no <pre class="klein-code"> block to check against the print')
    elif _squash(code_line) not in haystack:
        problems.append(
            f"printed text is missing the longest code line: {code_line.strip()[:70]!r}"
        )

    pages = layout_text.split("\f")
    if pages and not pages[-1].strip():
        pages = pages[:-1]
    details["text_pages"] = len(pages)
    sparse = [
        index + 1
        for index, page in enumerate(pages)
        if len([line for line in page.splitlines() if line.strip()]) < 3
    ]
    details["sparse_pages"] = sparse

    note = f"{len(pages)} text pages"
    if sparse:
        # Reported, never failed: pdftotext sees no images, so a page carrying
        # only a figure is indistinguishable from a genuinely blank one.
        note += f"; near-empty text pages (likely figure-only): {sparse}"
    if problems:
        return False, "; ".join(problems) + f" [{note}]", details
    return True, note, details


def _row(study: str, check: str, status: str, message: str) -> dict[str, str]:
    return {"study": study, "check": check, "status": status, "detail": message}


def render_row(row: dict[str, str]) -> str:
    """One line per report per check, streamed as it is measured.

    Status first so a CI log can be scanned (or grepped) down the left edge
    without knowing how long any study slug happens to be.
    """
    return f"{row['status']:<6} {row['study']:<28} {row['check']:<14} {row['detail']}".rstrip()


def decide_exit(rows: list[dict[str, str]]) -> int:
    """1 when a schema-3 report failed anything; LEGACY rows never bite."""
    return 1 if any(row["status"] == FAIL for row in rows) else 0


def check_report(
    study: Path,
    chrome: str,
    network,
    noise_hosts: set[str],
    work_dir: Path,
    widths: tuple[int, ...],
    legacy: bool,
    max_load_seconds: float,
    chrome_timeout: float,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Run the four per-report checks and return (rows, evidence)."""
    name = study.name
    report = study / "report" / "index.html"
    status_for = (lambda ok: PASS if ok else FAIL) if not legacy else (lambda ok: LEGACY)
    rows: list[dict[str, str]] = []
    evidence: dict[str, Any] = {"study": name, "legacy": legacy, "report": _repo_relative(report)}

    # 1. network + load budget, on the report itself (not the wrapper).
    started = time.perf_counter()
    try:
        urls, _ = network._run_chrome(chrome, report.resolve().as_uri(), work_dir)
        load_seconds = time.perf_counter() - started
        offending = network.page_initiated_urls(urls, noise_hosts)
        evidence["load_seconds"] = round(load_seconds, 3)
        evidence["page_initiated_urls"] = offending
        if offending:
            rows.append(
                _row(
                    name,
                    "network",
                    status_for(False),
                    f"{len(offending)} page-initiated request(s): {offending[:3]}",
                )
            )
        elif load_seconds > max_load_seconds:
            rows.append(
                _row(
                    name,
                    "network",
                    status_for(False),
                    f"0 requests but load took {load_seconds:.2f} s (budget {max_load_seconds:.2f} s)",
                )
            )
        else:
            rows.append(
                _row(name, "network", status_for(True), f"0 requests, {load_seconds:.2f} s")
            )
    except (RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        evidence["network_error"] = str(exc)
        rows.append(_row(name, "network", status_for(False), f"could not measure: {exc}"))

    # 2-4. one wrapper load covers every width, plus the image decode census.
    wrapper = work_dir / f"wrapper-{name}.html"
    wrapper.write_text(build_wrapper(report.resolve().as_uri(), widths), encoding="utf-8")
    started = time.perf_counter()
    try:
        dom = run_chrome_dump(chrome, wrapper.as_uri(), work_dir, chrome_timeout)
        measurement = parse_wrapper_dom(dom)
    except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
        evidence["measure_error"] = str(exc)
        for check in ("overflow", "nav", "images"):
            rows.append(_row(name, check, status_for(False), f"could not measure: {exc}"))
        return rows, evidence
    evidence["measure_seconds"] = round(time.perf_counter() - started, 3)
    evidence["widths"] = measurement["widths"]
    evidence["images"] = measurement["images"]

    for width_result in measurement["widths"]:
        ok, message = check_overflow(width_result)
        rows.append(
            _row(name, f"overflow@{width_result['width']}", status_for(ok), message or "fits")
        )

    for width_result in measurement["widths"]:
        if width_result["width"] not in NAV_REVEAL_WIDTHS:
            continue
        ok, message = check_nav_reveal(width_result)
        anchors = len(width_result.get("reveal", []))
        rows.append(
            _row(
                name,
                f"nav@{width_result['width']}",
                status_for(ok),
                message or f"{anchors} anchors revealed",
            )
        )

    ok, message = check_images(measurement["images"])
    rows.append(
        _row(name, "images", status_for(ok), message or f"{len(measurement['images'])} decoded")
    )
    return rows, evidence


def check_print(
    study: Path,
    chrome: str,
    work_dir: Path,
    pdftotext: str | None,
    legacy: bool,
    chrome_timeout: float,
) -> tuple[dict[str, str], dict[str, Any]]:
    """Print one report to PDF and re-read it."""
    name = study.name
    report = study / "report" / "index.html"
    status_for = (lambda ok: PASS if ok else FAIL) if not legacy else (lambda ok: LEGACY)
    pdf_path = work_dir / f"{name}.pdf"
    try:
        print_to_pdf(chrome, report, pdf_path, chrome_timeout)
    except RuntimeError as exc:
        return _row(name, "print", status_for(False), str(exc)), {"error": str(exc)}

    layout_text: str | None = None
    if pdftotext:
        result = subprocess.run(
            [pdftotext, "-layout", str(pdf_path), "-"],
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        if result.returncode != 0:
            return (
                _row(
                    name,
                    "print",
                    status_for(False),
                    f"pdftotext failed ({result.returncode}): {result.stderr[-200:]}",
                ),
                {"error": result.stderr[-500:]},
            )
        layout_text = result.stdout

    ok, message, details = evaluate_print(
        pdf_path.read_bytes(), layout_text, report.read_text(encoding="utf-8", errors="replace")
    )
    details["study"] = name
    return _row(name, "print", status_for(ok), message), details


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Acceptance checks on the shipped studies' report/index.html."
    )
    parser.add_argument(
        "--studies",
        nargs="+",
        metavar="SLUG",
        help="restrict to these studies (directory name, e.g. 15-iris-90years-relaunch, or studies/<name>)",
    )
    parser.add_argument("--chrome", help="Chrome/Chromium executable (auto-detected by default)")
    parser.add_argument(
        "--pdftotext", help="pdftotext executable (auto-detected on PATH by default)"
    )
    parser.add_argument(
        "--print-study",
        default=DEFAULT_PRINT_STUDY,
        metavar="SLUG",
        help=f"which report to print to PDF and re-read (default: {DEFAULT_PRINT_STUDY})",
    )
    parser.add_argument(
        "--widths",
        nargs="+",
        type=int,
        default=list(DEFAULT_WIDTHS),
        metavar="PX",
        help=f"viewport widths to measure (default: {' '.join(str(w) for w in DEFAULT_WIDTHS)})",
    )
    parser.add_argument(
        "--max-load-seconds",
        type=float,
        default=5.0,
        help="fail when a headless file:// report load exceeds this budget (default: 5.0)",
    )
    parser.add_argument(
        "--chrome-timeout",
        type=float,
        default=90.0,
        # Twelve reports x this ceiling has to stay inside the CI job's own
        # timeout, or a hung browser costs a cancelled job instead of a report
        # that names itself.  A healthy run measures a report in well under a
        # second, so 90 s is a hang detector, not a budget.
        help="ceiling for one measurement or print browser subprocess (default: 90)",
    )
    parser.add_argument(
        "--evidence", type=Path, help="optional JSON path for the CI evidence record"
    )
    args = parser.parse_args(argv)

    if any(width <= 0 for width in args.widths):
        print("error: --widths must be positive", file=sys.stderr)
        return 2

    all_studies = discover_reports()
    if not all_studies:
        print(
            f"error: no reports discovered under {STUDIES_DIR}/*/report/index.html", file=sys.stderr
        )
        return 2
    if args.studies:
        wanted = {_normalize_selector(value) for value in args.studies}
        selected = [study for study in all_studies if study.name in wanted]
        missing = wanted - {study.name for study in selected}
        if missing:
            print(
                f"error: --studies named unknown studies: {', '.join(sorted(missing))}",
                file=sys.stderr,
            )
            return 2
    else:
        selected = all_studies

    print_study = _normalize_selector(args.print_study)
    if print_study not in {study.name for study in all_studies}:
        print(f"error: --print-study named an unknown study: {print_study}", file=sys.stderr)
        return 2

    network = load_network_module()
    try:
        chrome = network.find_chrome(args.chrome)
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    pdftotext = args.pdftotext or shutil.which("pdftotext")

    widths = tuple(args.widths)
    rows: list[dict[str, str]] = []
    evidence: dict[str, Any] = {
        "browser": chrome,
        "pdftotext": pdftotext,
        "widths": list(widths),
        "print_study": print_study,
        "reports": [],
    }

    started_run = time.perf_counter()
    with tempfile.TemporaryDirectory(
        prefix="klein-shipped-reports-", ignore_cleanup_errors=True
    ) as temp:
        work_dir = Path(temp)
        # The browser's own service traffic is measured once and differenced out
        # of every report -- exactly the sibling script's contract.
        baseline_urls, _ = network._run_chrome(chrome, "about:blank", work_dir)
        noise_hosts = {urlsplit(url).hostname for url in baseline_urls}
        evidence["baseline_hosts"] = sorted(host for host in noise_hosts if host)

        for study in selected:
            legacy = is_legacy(schema_version((study / "study.yaml").read_text(encoding="utf-8")))
            report_rows, report_evidence = check_report(
                study,
                chrome,
                network,
                noise_hosts,
                work_dir,
                widths,
                legacy,
                args.max_load_seconds,
                args.chrome_timeout,
            )
            if study.name == print_study:
                print_row, print_evidence = check_print(
                    study, chrome, work_dir, pdftotext, legacy, args.chrome_timeout
                )
                report_evidence["print"] = print_evidence
            else:
                print_row = _row(
                    study.name, "print", SKIP, f"not the --print-study ({print_study})"
                )
            report_rows.append(print_row)
            rows.extend(report_rows)
            evidence["reports"].append(report_evidence)
            for row in report_rows:
                print(render_row(row), flush=True)

    evidence["total_seconds"] = round(time.perf_counter() - started_run, 3)
    counts = {
        status: sum(1 for row in rows if row["status"] == status)
        for status in (PASS, FAIL, LEGACY, SKIP)
    }
    evidence["counts"] = counts
    exit_code = decide_exit(rows)

    print(
        f"\n[shipped-reports] {len(selected)} report(s), {len(rows)} checks: "
        f"{counts[PASS]} PASS, {counts[FAIL]} FAIL, {counts[LEGACY]} LEGACY (never fails), {counts[SKIP]} SKIP "
        f"in {evidence['total_seconds']:.1f} s"
    )
    if counts[FAIL]:
        print("[shipped-reports] failing checks:", file=sys.stderr)
        for row in rows:
            if row["status"] == FAIL:
                print(f"  | {row['study']} {row['check']}: {row['detail']}", file=sys.stderr)

    if args.evidence:
        args.evidence.write_text(
            json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
