#!/usr/bin/env python3
"""build_tutorial.py — the assembler for the Klein TUTORIAL stage.

Design split: the tutor agent authors CONTENT (seven HTML fragments); this
script does deterministic ASSEMBLY into one self-contained ``report/index.html``
that opens from ``file://`` with zero network requests.

Fragment contract
-----------------
``<study_dir>/report/sections/`` MUST contain exactly seven HTML *fragments*
(no ``<html>``/``<head>``/``<body>`` wrappers), in this order:

    01-question.html  02-method.html  03-data.html  04-journey.html
    05-findings.html  06-coding-advice.html  07-next-steps.html

- Figures are referenced as ``<img data-fig="figures/<name>.png">``; the builder
  reads the PNG from ``<study_dir>`` and inlines it as a ``data:`` URI. A missing
  figure FAILS the build (listing the name).
- Math is authored as LaTeX in EMPTY elements — ``<span data-math="…"></span>``
  (inline) / ``<div data-math-display="…"></div>`` (display) — and rendered at
  BUILD time to inline SVG glyph paths (ziamath; no fonts, no runtime script).
  Inside the attribute, escape exactly ``& " < >`` as entities; backslashes are
  literal. The LaTeX source survives into the page as ``data-latex`` (greppable
  numbers, copyable source) and as the SVG ``<title>``. An unparseable formula,
  a non-empty element, or a leftover ``data-math`` FAILS the build.
- Code is highlighted at build time (Pygments, dual-theme CSS classes):
  ``<pre><code class="language-python">…escaped…</code></pre>`` is highlighted
  in place; a ``<pre><code>`` with no language class is left untouched. The
  winning train.py is included BY REFERENCE — ``<pre data-code="train.py"
  data-lang="python"></pre>`` reads the file from ``<study_dir>``, guaranteeing
  the page carries the actual bytes. Paths outside the study dir or a missing
  file FAIL the build.
- A ``<!--LEDGER-->`` marker (used in 04-journey) is replaced with an
  auto-generated experiment ledger table read from ``results.tsv``.

Acceptance guard (runs on the assembled page; non-zero exit lists violations):
- all seven section anchors present;
- the exact restrictive Content-Security-Policy is present (default/connect deny,
  data-only images, and a SHA-256-authorized fixed navigation script);
- ``href`` values are local fragments and ``src`` values are inlined PNGs only.
  Plain-text URLs inside <cite>/<code>/reference lists remain allowed.

Exit codes: 2 missing fragment(s) · 3 missing figure(s) · 4 acceptance guard ·
5 math render failure · 6 code include failure · 7 renderer dependency missing.
(argparse itself also exits 2 on a usage error — pre-existing collision, kept.)

Dependencies: pygments + ziamath + latex2mathml (declared in pyproject.toml).
PyYAML is used opportunistically for study.yaml (same graceful fallback pattern
as summarize_results.py) but never required.

Usage:
    uv run --locked python .claude/skills/klein/scripts/build_tutorial.py <study_dir> [--title "..."]
"""

from __future__ import annotations

import argparse
import base64
import csv
import functools
import hashlib
import html
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - exercised via the tiny fallback parser
    yaml = None  # type: ignore

# The renderer dependencies are REQUIRED (exit 7 with instructions when absent):
# a builder that silently degrades would emit different bytes on different
# machines, and determinism is part of the tutorial contract.
try:
    import latex2mathml.converter as latex2mathml_converter
    import ziamath
    from pygments import highlight as pygments_highlight
    from pygments.formatters import HtmlFormatter
    from pygments.lexers import get_lexer_by_name
    from pygments.util import ClassNotFound
except ImportError as exc:  # pragma: no cover - exercised via a monkeypatched sentinel
    _RENDERER_IMPORT_ERROR: Exception | None = exc
    ziamath = None  # type: ignore
else:
    _RENDERER_IMPORT_ERROR = None
    # svg2=False is MANDATORY, not cosmetic: the default emits <symbol id=…> +
    # <use href=…> whose glyph ids collide across the many formulas of one
    # page; plain per-glyph <path> output has no ids and no hrefs.
    ziamath.config.svg2 = False

# (fragment filename, anchor id, nav title) — the fixed seven-section arc.
SECTIONS: tuple[tuple[str, str, str], ...] = (
    ("01-question.html", "question", "The Question"),
    ("02-method.html", "method", "The Method"),
    ("03-data.html", "data", "The Data"),
    ("04-journey.html", "journey", "The Journey"),
    ("05-findings.html", "findings", "Findings"),
    ("06-coding-advice.html", "coding-advice", "Coding Advice"),
    ("07-next-steps.html", "next-steps", "Next Steps"),
)

FIG_RE = re.compile(r"""data-fig\s*=\s*(["'])(.*?)\1""")
ATTR_URL_RE = re.compile(r"""(?:src|href)\s*=\s*(["'])(.*?)\1""", re.IGNORECASE)

# Math/code authoring idioms. The element forms are deliberately STRICT — the
# data attribute is the element's only attribute and the element is empty — so
# that an unescaped quote or stray content can never half-match: it simply
# fails to match, survives the pass, and the leftover probe turns it into a
# hard build error naming the fragment.
MATH_INLINE_RE = re.compile(r'<span\s+data-math="([^"]*)"\s*>\s*</span\s*>')
MATH_DISPLAY_RE = re.compile(r'<div\s+data-math-display="([^"]*)"\s*>\s*</div\s*>')
MATH_PROBE_RE = re.compile(r"data-math(?:-display)?\s*=")
CODE_INCLUDE_RE = re.compile(
    r'<pre\s+data-code="([^"]*)"(?:\s+data-lang="([^"]*)")?\s*>\s*</pre\s*>'
)
CODE_PROBE_RE = re.compile(r"data-code\s*=")
LANG_CLASS_RE = re.compile(
    r'<pre([^>]*)><code\s+class="language-([A-Za-z0-9_+-]+)"\s*>(.*?)</code></pre>',
    re.DOTALL,
)
PRE_SPAN_RE = re.compile(r"<pre\b.*?</pre\s*>", re.DOTALL | re.IGNORECASE)
SVG_VIEWBOX_RE = re.compile(
    r'viewBox="(-?[\d.]+) (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)"'
)

#: Pinned Pygments styles — named constants so a Pygments upgrade cannot
#: silently reskin every shipped report (the pair is also what the dual-theme
#: CSS test asserts).
PYG_LIGHT_STYLE = "default"
PYG_DARK_STYLE = "github-dark"

LANG_BY_SUFFIX = {
    ".py": "python",
    ".sh": "bash",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
}


# --------------------------------------------------------------------------
# study.yaml metadata (pyyaml when present; tiny top-level fallback otherwise)
# --------------------------------------------------------------------------


def _clean_scalar(raw: str) -> str | None:
    s = raw.strip()
    if not s:
        return None
    if s[0] in "\"'":
        q = s[0]
        end = s.find(q, 1)
        return s[1:end] if end != -1 else s[1:]
    if "#" in s:  # strip an inline comment from an unquoted scalar
        s = s.split("#", 1)[0].strip()
    return s or None


def _tiny_parse_meta(text: str, meta: dict[str, str | None]) -> dict[str, str | None]:
    """Stdlib fallback: harvest top-level goal/domain/target + nested metric.name."""
    in_metric = False
    in_tracks = False
    track_name: str | None = None
    in_track_metric = False
    track_metrics: list[str] = []
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        key, sep, value = line.strip().partition(":")
        if not sep:
            continue
        key = key.strip()
        if indent == 0:
            in_metric = key == "metric"
            in_tracks = key == "tracks"
            track_name = None
            in_track_metric = False
            if key in ("goal", "domain", "target"):
                meta[key] = _clean_scalar(value)
        elif in_metric and key == "name":
            meta["metric_name"] = _clean_scalar(value)
        elif in_tracks and indent == 2:
            track_name = key
            in_track_metric = False
        elif in_tracks and indent == 4:
            in_track_metric = key == "metric"
        elif in_tracks and indent >= 6 and in_track_metric and key == "name":
            metric_name = _clean_scalar(value)
            if track_name and metric_name:
                track_metrics.append(f"{metric_name} ({track_name})")
    if track_metrics:
        meta["metric_name"] = ", ".join(track_metrics)
    return meta


def load_study_meta(study_dir: Path) -> dict[str, str | None]:
    meta: dict[str, str | None] = {
        "goal": None,
        "metric_name": None,
        "domain": None,
        "target": None,
    }
    path = study_dir / "study.yaml"
    if not path.exists():
        return meta
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        try:
            data = yaml.safe_load(text)
        except Exception:
            data = None
        if isinstance(data, dict):
            for k in ("goal", "domain", "target"):
                meta[k] = data.get(k)
            metric = data.get("metric")
            if isinstance(metric, dict):
                meta["metric_name"] = metric.get("name")
            tracks = data.get("tracks")
            if isinstance(tracks, dict):
                names: list[str] = []
                for track_name, track_spec in tracks.items():
                    if not isinstance(track_spec, dict):
                        continue
                    track_metric = track_spec.get("metric")
                    if not isinstance(track_metric, dict) or not track_metric.get("name"):
                        continue
                    names.append(f"{track_metric['name']} ({track_name})")
                if names:
                    meta["metric_name"] = ", ".join(names)
            return meta
    return _tiny_parse_meta(text, meta)


def git_last_date(study_dir: Path) -> str | None:
    """Last commit date touching the study dir (YYYY-MM-DD); None if git absent."""
    try:
        r = subprocess.run(
            ["git", "log", "-1", "--format=%ad", "--date=short", "--", "."],
            cwd=str(study_dir),
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, ValueError):  # pragma: no cover - git missing entirely
        return None
    out = r.stdout.strip()
    return out if r.returncode == 0 and out else None


# --------------------------------------------------------------------------
# Figure inlining + ledger
# --------------------------------------------------------------------------


def inline_figures(content: str, study_dir: Path, missing: list[str]) -> str:
    """Replace every ``data-fig="figures/x.png"`` with an inline base64 ``src=``."""

    def repl(match: re.Match[str]) -> str:
        rel = match.group(2)
        fig_path = study_dir / rel
        if not fig_path.exists():
            missing.append(rel)
            return match.group(0)  # leave untouched; the build fails downstream
        data = base64.b64encode(fig_path.read_bytes()).decode("ascii")
        return f'src="data:image/png;base64,{data}"'

    return FIG_RE.sub(repl, content)


def build_ledger(study_dir: Path) -> str:
    """Auto-generate the experiment ledger table from results.tsv."""
    path = study_dir / "results.tsv"
    if not path.exists():
        return '<p class="note">results.tsv not found — ledger omitted.</p>'
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        fields = reader.fieldnames or []
        metric_col = next(
            (c for c in ("primary_metric", "metric", "val_auc") if c in fields),
            None,
        )
        rows = list(reader)
    head = (
        '<table class="ledger">\n<thead><tr>'
        "<th>Exp</th><th>Metric</th><th>Status</th><th>Description</th>"
        "</tr></thead>\n<tbody>\n"
    )
    body: list[str] = []
    for r in rows:
        exp = html.escape((r.get("experiment") or "").strip())
        metric = html.escape((r.get(metric_col) or "").strip()) if metric_col else ""
        status = (r.get("status") or "").strip().lower()
        desc = html.escape((r.get("description") or "").strip())
        body.append(
            f'<tr class="st-{html.escape(status)}"><td>{exp}</td>'
            f"<td>{metric}</td>"
            f'<td><span class="badge">{html.escape(status)}</span></td>'
            f"<td>{desc}</td></tr>"
        )
    return head + "\n".join(body) + "\n</tbody>\n</table>"


# --------------------------------------------------------------------------
# Build-time rendering: math (LaTeX → inline SVG) and code (Pygments)
# --------------------------------------------------------------------------


def outside_pre(text: str, fn) -> str:
    """Apply ``fn`` to every region OUTSIDE ``<pre>…</pre>`` spans.

    Fragments legitimately contain raw quotes inside code blocks, and a code
    block SHOWING an authoring idiom (``data-math=``, ``data-fig=``) must
    survive verbatim — so every attribute-scanning pass masks pre spans first.
    """
    parts: list[str] = []
    last = 0
    for m in PRE_SPAN_RE.finditer(text):
        parts.append(fn(text[last : m.start()]))
        parts.append(m.group(0))
        last = m.end()
    parts.append(fn(text[last:]))
    return "".join(parts)


def _render_one_math(latex: str, display: bool) -> str:
    """One LaTeX expression → theme-aware inline SVG with the source as <title>."""
    mathml = latex2mathml_converter.convert(
        latex, display="block" if display else "inline"
    )
    svg = ziamath.Math(mathml).svg()
    # ziamath hard-codes black; currentColor follows the page's --fg in both
    # colour schemes (the CSS re-asserts it for every child as well).
    svg = svg.replace('fill="black"', 'fill="currentColor"')
    svg = svg.replace('stroke="black"', 'stroke="currentColor"')
    # Inline SVG in an HTML document needs no namespace declarations, and
    # stripping them keeps the built page free of ``http://`` strings.
    svg = svg.replace(' xmlns="http://www.w3.org/2000/svg"', "", 1)
    svg = svg.replace(' xmlns:xlink="http://www.w3.org/1999/xlink"', "", 1)
    return svg.replace(">", f' role="img"><title>{html.escape(latex)}</title>', 1)


def _inline_math_style(svg: str) -> str:
    """Baseline alignment for inline math, computed from the viewBox.

    ziamath puts the baseline at y=0, so the descent (box below the baseline)
    is ``min_y + height``; width/height attributes are emitted 1:1 with
    viewBox units, so the CSS pixel shift equals the unit count.
    """
    m = SVG_VIEWBOX_RE.search(svg)
    if not m:
        return ""
    descent = float(m.group(2)) + float(m.group(4))
    return f' style="vertical-align:{-descent:.3f}px"'


def render_math(content: str, fragment: str, errors: list[str]) -> str:
    """Replace the two strict math idioms with rendered SVG.

    A render failure records the error and DROPS the element — safe because
    any recorded error aborts the build before ``index.html`` is written.
    Non-matching uses (unescaped quote, non-empty element) simply survive the
    pass and are turned into hard errors by the leftover probe.
    """

    def repl_inline(match: re.Match[str]) -> str:
        return _emit(match.group(1), display=False)

    def repl_display(match: re.Match[str]) -> str:
        return _emit(match.group(1), display=True)

    def _emit(raw: str, *, display: bool) -> str:
        latex = html.unescape(raw)
        try:
            svg = _render_one_math(latex, display)
        except Exception as exc:  # noqa: BLE001 - any renderer failure is a build error
            errors.append(f"{fragment}: {latex!r} → {type(exc).__name__}: {exc}")
            return ""
        source = html.escape(latex, quote=True)
        if display:
            return f'<div class="kmath-display" data-latex="{source}">{svg}</div>'
        return (
            f'<span class="kmath" data-latex="{source}"{_inline_math_style(svg)}>'
            f"{svg}</span>"
        )

    content = MATH_INLINE_RE.sub(repl_inline, content)
    return MATH_DISPLAY_RE.sub(repl_display, content)


def _highlight_source(source: str, lang: str) -> str:
    lexer = get_lexer_by_name(lang)
    highlighted = pygments_highlight(source, lexer, HtmlFormatter(nowrap=True))
    # Pygments guarantees a trailing newline; keep the byte-for-byte round trip.
    if highlighted.endswith("\n") and not source.endswith("\n"):
        highlighted = highlighted[:-1]
    return highlighted


def highlight_code(content: str, fragment: str, errors: list[str]) -> str:
    """Highlight literal ``<pre><code class="language-…">`` pastes in place.

    A ``<pre><code>`` with no language class is untouched — the escape hatch
    for console dumps and not-code monospace blocks.
    """

    def repl(match: re.Match[str]) -> str:
        pre_attrs, lang, body = match.group(1), match.group(2), match.group(3)
        try:
            highlighted = _highlight_source(html.unescape(body), lang)
        except ClassNotFound:
            errors.append(f"{fragment}: unknown language class 'language-{lang}'")
            return match.group(0)
        # An author-supplied class on the <pre> would produce a duplicate
        # class attribute beside ours; fold it out (klein-code wins).
        pre_attrs = re.sub(r'\sclass="[^"]*"', "", pre_attrs)
        return (
            f'<pre class="klein-code"{pre_attrs}><code class="language-{lang}">'
            f"{highlighted}</code></pre>"
        )

    return LANG_CLASS_RE.sub(repl, content)


def include_code(content: str, study_dir: Path, fragment: str, errors: list[str]) -> str:
    """Resolve ``<pre data-code="…"></pre>`` includes against the study dir.

    This is what turns the spec's "the page carries the ACTUAL winning
    train.py" from a checklist promise into a build-time guarantee.
    """

    def repl(match: re.Match[str]) -> str:
        rel, lang = match.group(1), match.group(2)
        if Path(rel).is_absolute() or ".." in Path(rel).parts:
            errors.append(
                f"{fragment}: data-code={rel!r} must be a relative path inside the study dir"
            )
            return ""
        path = study_dir / rel
        if not path.is_file():
            errors.append(f"{fragment}: data-code={rel!r} not found under {study_dir}")
            return ""
        source = path.read_text(encoding="utf-8")
        resolved_lang = lang or LANG_BY_SUFFIX.get(path.suffix, "text")
        try:
            highlighted = _highlight_source(source, resolved_lang)
        except ClassNotFound:
            errors.append(f"{fragment}: data-lang={resolved_lang!r} is not a known lexer")
            return ""
        return (
            f'<pre class="klein-code" data-code-source="{html.escape(rel, quote=True)}">'
            f'<code class="language-{html.escape(resolved_lang, quote=True)}">'
            f"{highlighted}</code></pre>"
        )

    return CODE_INCLUDE_RE.sub(repl, content)


def probe_leftovers(
    content: str,
    fragment: str,
    math_errors: list[str],
    code_errors: list[str],
) -> None:
    """Any ``data-math``/``data-code`` surviving outside <pre> is an authoring
    error (unescaped quote, non-empty element, malformed attributes)."""

    def scan(segment: str) -> str:
        for probe, hint, sink in (
            (MATH_PROBE_RE, "data-math", math_errors),
            (CODE_PROBE_RE, "data-code", code_errors),
        ):
            for m in probe.finditer(segment):
                snippet = segment[m.start() : m.start() + 80].splitlines()[0]
                sink.append(
                    f"{fragment}: unconsumed {hint} (unescaped quote or non-empty "
                    f"element?): {snippet!r}"
                )
        return segment

    outside_pre(content, scan)


def render_css() -> str:
    """Pygments dual-theme classes + math styling, appended to the base CSS."""
    light = HtmlFormatter(style=PYG_LIGHT_STYLE).get_style_defs("pre.klein-code")
    dark = HtmlFormatter(style=PYG_DARK_STYLE).get_style_defs("pre.klein-code")
    return (
        "\n/* Pygments (build-time highlighting; styles pinned in-module) */\n"
        + light
        + "\n@media (prefers-color-scheme:dark){\n"
        + dark
        + "\n}\n"
        # get_style_defs emits its own container background; the theme wins:
        + "pre.klein-code{background:var(--code-bg);border:1px solid var(--rule)}\n"
        + "@media (prefers-color-scheme:dark){pre.klein-code{background:var(--code-bg)}}\n"
        + "/* Build-time math (inline SVG glyph paths) */\n"
        + ".kmath{display:inline-block}\n"
        + ".kmath svg{display:block;margin:0;border:0;background:none}\n"
        + ".kmath-display{margin:18px 0;text-align:center;overflow-x:auto}\n"
        + ".kmath-display svg{display:inline-block;margin:0;border:0;background:none;max-width:none}\n"
        + ".kmath svg *,.kmath-display svg *{fill:currentColor}\n"
    )


# --------------------------------------------------------------------------
# Page assembly
# --------------------------------------------------------------------------

CSS = """
:root{--bg:#fbfaf6;--fg:#1f2430;--muted:#5c6472;--rule:#e3e0d6;--card:#fff;
--accent:#0f766e;--accent2:#991b1b;--code-bg:#f4f2ec;--badge:#e7ede9;--shadow:0 1px 3px rgba(0,0,0,.06)}
@media (prefers-color-scheme:dark){:root{--bg:#14161a;--fg:#e6e8ec;--muted:#9aa3b2;
--rule:#2a2e37;--card:#1b1e24;--accent:#5eead4;--accent2:#fca5a5;--code-bg:#1f232b;
--badge:#243029;--shadow:0 1px 3px rgba(0,0,0,.5)}}
*{box-sizing:border-box}html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--fg);
font-family:Georgia,Cambria,"Times New Roman",serif;font-size:18px;line-height:1.65}
.wrap{max-width:860px;margin:0 auto;padding:0 24px}
h1,h2,h3,nav,.kicker,.badge,.meta,th{font-family:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.site-header{border-bottom:1px solid var(--rule);padding:34px 0 26px}
.kicker{font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);font-weight:600;margin:0 0 8px}
.site-header h1{font-size:30px;line-height:1.2;margin:0 0 10px}
.goal{font-size:19px;color:var(--fg);margin:0 0 12px}
.meta{font-size:13px;color:var(--muted);margin:0}
nav.topnav{position:sticky;top:0;z-index:10;background:color-mix(in srgb,var(--bg) 92%,transparent);
backdrop-filter:blur(6px);border-bottom:1px solid var(--rule)}
nav.topnav .wrap{display:flex;flex-wrap:wrap;gap:4px 14px;padding:10px 24px}
nav.topnav a{font-size:13px;color:var(--muted);text-decoration:none;padding:4px 2px;border-bottom:2px solid transparent}
nav.topnav a:hover{color:var(--fg)}
nav.topnav a.active{color:var(--accent);border-bottom-color:var(--accent)}
main{padding:8px 0 40px}
section{padding:34px 0;border-bottom:1px solid var(--rule);scroll-margin-top:64px}
section:last-child{border-bottom:0}
section h2{font-size:23px;margin:0 0 14px;padding-left:12px;border-left:4px solid var(--accent)}
h3{font-size:18px;margin:26px 0 8px}
p{margin:0 0 14px}
a{color:var(--accent)}
ul,ol{padding-left:26px;margin:0 0 14px}li{margin:6px 0}
strong{font-weight:700}
code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.86em;
background:var(--code-bg);padding:1px 5px;border-radius:4px}
pre{background:var(--code-bg);border:1px solid var(--rule);border-radius:8px;
padding:14px 16px;overflow-x:auto;margin:0 0 16px}
pre code{background:none;padding:0;font-size:13.5px;line-height:1.4;tab-size:4}
img{max-width:100%;height:auto;display:block;margin:16px auto;border:1px solid var(--rule);
border-radius:8px;background:var(--card)}
figure{margin:20px 0}figcaption{font-size:14px;color:var(--muted);text-align:center;margin-top:6px}
table{border-collapse:collapse;width:100%;margin:16px 0;font-size:14px;display:block;overflow-x:auto}
th,td{border:1px solid var(--rule);padding:7px 10px;text-align:left;vertical-align:top}
th{background:var(--code-bg);font-weight:600}
table.ledger td:nth-child(2){font-variant-numeric:tabular-nums;white-space:nowrap}
.badge{display:inline-block;font-size:11px;letter-spacing:.03em;text-transform:uppercase;
background:var(--badge);color:var(--accent);border-radius:999px;padding:2px 9px}
tr.st-discard .badge{color:var(--muted)}tr.st-crash .badge{color:var(--accent2)}
blockquote{margin:0 0 16px;padding:2px 16px;border-left:3px solid var(--rule);color:var(--muted)}
.note{font-size:14px;color:var(--muted)}
.site-footer{border-top:1px solid var(--rule);padding:26px 0 48px;color:var(--muted);font-size:13px}
.site-footer .lineage{font-family:ui-monospace,Menlo,monospace;font-size:12px;margin-top:6px}
@media print{nav.topnav{position:static;backdrop-filter:none}
body{font-size:12pt}section{border-color:#ccc;page-break-inside:avoid}
a{color:inherit;text-decoration:none}img{border-color:#ccc}}
"""

NAV_JS = """
(function(){
  var links=[].slice.call(document.querySelectorAll('nav.topnav a'));
  var map={};links.forEach(function(a){map[a.getAttribute('href').slice(1)]=a;});
  if(!('IntersectionObserver' in window))return;
  var obs=new IntersectionObserver(function(entries){
    entries.forEach(function(e){
      if(e.isIntersecting){
        links.forEach(function(a){a.classList.remove('active');});
        var a=map[e.target.id];if(a)a.classList.add('active');
      }
    });
  },{rootMargin:'-45% 0px -50% 0px'});
  document.querySelectorAll('main section[id]').forEach(function(s){obs.observe(s);});
})();
"""


def content_security_policy() -> str:
    """Return the restrictive policy for a generated, offline tutorial.

    Figures are data URIs and CSS is intentionally inlined.  The only script is
    this module's fixed navigation helper, authorized by its exact SHA-256 rather
    than by ``'unsafe-inline'``.  Everything capable of network activity is
    denied explicitly as well as by ``default-src 'none'``.
    """
    script_hash = base64.b64encode(hashlib.sha256(NAV_JS.encode("utf-8")).digest()).decode(
        "ascii"
    )
    return "; ".join(
        (
            "default-src 'none'",
            "img-src data:",
            "style-src 'unsafe-inline'",
            f"script-src 'sha256-{script_hash}'",
            "connect-src 'none'",
            "font-src 'none'",
            "media-src 'none'",
            "object-src 'none'",
            "frame-src 'none'",
            "worker-src 'none'",
            "manifest-src 'none'",
            "base-uri 'none'",
            "form-action 'none'",
        )
    )


def csp_meta_tag() -> str:
    return (
        '<meta http-equiv="Content-Security-Policy" '
        f'content="{content_security_policy()}">'
    )


def assemble(
    study_dir: Path,
    title: str,
    meta: dict[str, str | None],
    missing: list[str],
    math_errors: list[str],
    code_errors: list[str],
) -> str:
    study_id = study_dir.name
    ledger = build_ledger(study_dir)

    body_sections: list[str] = []
    for filename, anchor, _title in SECTIONS:
        frag = (study_dir / "report" / "sections" / filename).read_text(encoding="utf-8")
        # Order matters: literal pastes are highlighted BEFORE includes are
        # resolved (an include target is an EMPTY <pre>, so the paste pass
        # cannot double-process it, and the include emits final form); math
        # and figures scan attributes, so both run masked outside <pre>.
        frag = highlight_code(frag, filename, code_errors)
        frag = include_code(frag, study_dir, filename, code_errors)
        frag = outside_pre(
            frag,
            functools.partial(render_math, fragment=filename, errors=math_errors),
        )
        frag = outside_pre(
            frag,
            functools.partial(inline_figures, study_dir=study_dir, missing=missing),
        )
        probe_leftovers(frag, filename, math_errors, code_errors)
        frag = frag.replace("<!--LEDGER-->", ledger)
        body_sections.append(f'<section id="{anchor}">\n{frag}\n</section>')

    nav_links = "\n".join(
        f'<a href="#{anchor}">{i}. {html.escape(nav)}</a>'
        for i, (_f, anchor, nav) in enumerate(SECTIONS, start=1)
    )

    date = git_last_date(study_dir)
    meta_bits = [f"study: {html.escape(study_id)}"]
    if meta.get("metric_name"):
        meta_bits.append(f"metric: {html.escape(str(meta['metric_name']))}")
    if meta.get("domain"):
        meta_bits.append(f"domain: {html.escape(str(meta['domain']))}")
    if date:
        meta_bits.append(html.escape(date))
    goal = html.escape(str(meta.get("goal") or ""))

    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        f"{csp_meta_tag()}\n"
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n"
        f"<style>{CSS}{render_css()}</style>\n</head>\n<body>\n"
        '<header class="site-header"><div class="wrap">\n'
        '<p class="kicker">Klein Auto Research · Tutorial</p>\n'
        f"<h1>{html.escape(title)}</h1>\n"
        f'<p class="goal">{goal}</p>\n'
        f'<p class="meta">{" · ".join(meta_bits)}</p>\n'
        "</div></header>\n"
        '<nav class="topnav"><div class="wrap">\n'
        f"{nav_links}\n</div></nav>\n"
        '<main class="wrap">\n'
        + "\n".join(body_sections)
        + "\n</main>\n"
        '<footer class="site-footer"><div class="wrap">\n'
        "<p>Generated by Klein Auto Research — the SYNTHESIZE→TUTORIAL loop. "
        "Self-contained: every figure is a base64-inlined PNG, no network required.</p>\n"
        '<p class="lineage">lineage: Karpathy autoresearch → Elan agent-smith → Klein Auto Research</p>\n'
        "</div></footer>\n"
        f"<script>{NAV_JS}</script>\n"
        "</body>\n</html>\n"
    )


# --------------------------------------------------------------------------
# Acceptance guard
# --------------------------------------------------------------------------


def acceptance_violations(page: str) -> list[str]:
    violations: list[str] = []
    if csp_meta_tag() not in page:
        violations.append("missing or modified restrictive Content-Security-Policy")
    for _f, anchor, _t in SECTIONS:
        if f'id="{anchor}"' not in page:
            violations.append(f"missing section anchor: id={anchor!r}")
    for match in ATTR_URL_RE.finditer(page):
        value = match.group(2).strip()
        lowered = value.lower()
        if lowered.startswith(("http://", "https://", "//")):
            violations.append(f"external URL in src/href attribute: {value[:70]!r}")
        elif not (value.startswith("#") or lowered.startswith("data:image/png;base64,")):
            violations.append(f"unsafe URL in src/href attribute: {value[:70]!r}")
    return violations


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Assemble a Klein study tutorial.")
    p.add_argument("study_dir", type=Path, help="Path to studies/NN-<name>/")
    p.add_argument("--title", help="Page title (default: the study id).")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    study_dir = args.study_dir.resolve()
    sections_dir = study_dir / "report" / "sections"

    if ziamath is None:
        print(
            "[build_tutorial] FAIL: the tutorial renderer needs pygments + "
            "ziamath + latex2mathml.",
            file=sys.stderr,
        )
        print("       In this repo:      uv sync --locked", file=sys.stderr)
        print(
            "       In a foreign repo: uv add "
            '"klein-auto-research @ git+https://github.com/Xiang-Shan/'
            'klein-auto-research@v1.2.0"',
            file=sys.stderr,
        )
        print("       Or directly:       uv add pygments ziamath latex2mathml", file=sys.stderr)
        print(f"       ({_RENDERER_IMPORT_ERROR})", file=sys.stderr)
        return 7

    absent = [name for name, _a, _t in SECTIONS if not (sections_dir / name).exists()]
    if absent:
        print(f"[build_tutorial] missing fragment(s) in {sections_dir}:", file=sys.stderr)
        for name in absent:
            print(f"  - {name}", file=sys.stderr)
        return 2

    meta = load_study_meta(study_dir)
    title = args.title or study_dir.name
    missing_figs: list[str] = []
    math_errors: list[str] = []
    code_errors: list[str] = []
    page = assemble(study_dir, title, meta, missing_figs, math_errors, code_errors)

    if missing_figs:
        print("[build_tutorial] missing figure(s) referenced via data-fig:", file=sys.stderr)
        for rel in dict.fromkeys(missing_figs):  # dedupe, keep order
            print(f"  - {rel}", file=sys.stderr)
        return 3

    if math_errors:
        print("[build_tutorial] math render FAILED:", file=sys.stderr)
        for err in math_errors:
            print(f"  - {err}", file=sys.stderr)
        return 5

    if code_errors:
        print("[build_tutorial] code include/highlight FAILED:", file=sys.stderr)
        for err in code_errors:
            print(f"  - {err}", file=sys.stderr)
        return 6

    violations = acceptance_violations(page)
    if violations:
        print("[build_tutorial] acceptance guard FAILED:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 4

    out = study_dir / "report" / "index.html"
    out.write_text(page, encoding="utf-8")
    n_figs = page.count("data:image/png;base64")
    print(f"[build_tutorial] wrote {out} ({len(page):,} bytes, {n_figs} inlined figure(s))")
    return 0


if __name__ == "__main__":
    sys.exit(main())
