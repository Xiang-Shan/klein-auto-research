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
  reads the PNG from ``<study_dir>``, decodes its IHDR to emit intrinsic
  ``width``/``height`` (no layout shift on load) and inlines the bytes as a
  ``data:`` URI. A missing file, or a file whose PNG signature/header does not
  decode, FAILS the build naming the file and the reason. Adding an optional
  ``data-caption="…"`` (entity-escaped) wraps the image in a numbered
  ``<figure class="fig" id="fig-N">`` with a caption and a CSS-``:target``
  enlargement that duplicates no image bytes; a bare ``data-fig`` keeps its
  authored surroundings untouched (fragments that already write their own
  ``<figure>``/``<figcaption>`` are never double-wrapped).
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
  winning entrypoint is included BY REFERENCE — ``<pre data-code="train.py"
  data-lang="python"></pre>`` reads the file from ``<study_dir>``, guaranteeing
  the page carries the actual bytes. Paths outside the study dir or a missing
  file FAIL the build. Every include is wrapped in a ``<details class="source">``
  whose summary states WHICH bytes these are:
  - ``data-run="E0009"`` reads the file at that run's ``candidate_commit``
    (``git show``), so the page shows the cell the notary executed rather than
    the working tree. A missing manifest, key, object or git FAILS the build.
  - a bare include of a file in the mutable surface (``entrypoint.mutable``;
    ``train.py`` below schema 3) FAILS: run-one RESTORES that surface, so the
    file on disk is the template, not any run's cell. Add ``data-run`` for the
    executed source, or ``data-role="template"`` to label it as the template.
  - anything outside the mutable surface (a verifier, ``lib/``, an analysis
    script) still includes bare and is labelled "current file at build".
  The three optional attributes may appear in any order after ``data-code``;
  anything else survives the pass and the leftover probe reports it.
- A ``<!--LEDGER-->`` marker (used in 04-journey) is replaced with an
  auto-generated ledger table read from ``results.tsv``: Exp · Track · Kind ·
  Metric · Status · Description, with Track dropped when the TSV has no such
  column and Kind (a manifest's ``evaluation_kind``) dropped when the study has
  no run manifests, over a ``<p class="ledger-key">`` naming each track's metric.
- An ``<!--EVIDENCE-->`` marker (used in 05-findings) is replaced with a block
  generated from the RECORDS — ``claims.lock`` and ``study_state.json`` — that
  copies strings and counts nothing else. A study that HAS a lock and carries the
  marker nowhere fails the acceptance guard: the findings section would otherwise
  claim things the receipts never state.
- Every ``<h3>`` without an ``id`` gets a stable page-unique slug id, and a
  section with two or more of them gets a ``<nav class="subnav">`` after its
  ``<h2>`` — deep links into a subsection survive a rebuild.

The head carries ``<meta name="generator" content="klein build_tutorial layout-N">``
(``LAYOUT_GENERATION``): ``scripts/check_shipped_reports.py`` enforces its phone and
print checks only on pages built at the current generation and reports older pages
as LEGACY, so a stylesheet fix never fails the reports shipped before it.

Acceptance guard (runs on the assembled page; non-zero exit lists violations):
- all seven section anchors present;
- the exact restrictive Content-Security-Policy is present (default/connect deny,
  data-only images, and a SHA-256-authorized fixed navigation script);
- ``href`` values are local fragments and ``src`` values are inlined PNGs only.
  Plain-text URLs inside <cite>/<code>/reference lists remain allowed.

Exit codes: 2 missing fragment(s) · 3 figure problem(s) · 4 acceptance guard ·
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
import itertools
import json
import re
import struct
import subprocess
import sys
from pathlib import Path
from typing import Any

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
#: The whole ``<img …>`` tag, so the inliner can ADD intrinsic width/height and
#: (with a caption) wrap the element — the attribute-only pass above still runs
#: afterwards over anything that carried ``data-fig`` outside an ``<img>``, so
#: no authoring form silently loses its inlining.
FIG_IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
FIG_CAPTION_RE = re.compile(r"""\s*data-caption\s*=\s*(["'])(.*?)\1""", re.IGNORECASE)
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
ATTR_URL_RE = re.compile(r"""(?:src|href)\s*=\s*(["'])(.*?)\1""", re.IGNORECASE)

# Math/code authoring idioms. The element forms are deliberately STRICT — the
# data attribute is the element's only attribute and the element is empty — so
# that an unescaped quote or stray content can never half-match: it simply
# fails to match, survives the pass, and the leftover probe turns it into a
# hard build error naming the fragment.
MATH_INLINE_RE = re.compile(r'<span\s+data-math="([^"]*)"\s*>\s*</span\s*>')
MATH_DISPLAY_RE = re.compile(r'<div\s+data-math-display="([^"]*)"\s*>\s*</div\s*>')
MATH_PROBE_RE = re.compile(r"data-math(?:-display)?\s*=")
# The include idiom: ``data-code`` first, then any of the three optional
# attributes in any order. Only the three are admitted by name, so a typo
# ("data-lan=") does not half-match into a silently wrong include — it fails to
# match, survives the pass, and CODE_PROBE_RE turns it into a build error.
CODE_INCLUDE_RE = re.compile(
    r'<pre\s+data-code="([^"]*)"'
    r'((?:\s+data-(?:lang|run|role)="[^"]*")*)'
    r"\s*>\s*</pre\s*>"
)
CODE_ATTR_RE = re.compile(r'\sdata-(lang|run|role)="([^"]*)"')
CODE_PROBE_RE = re.compile(r"data-code\s*=")
# An include that did NOT match sits inside a <pre> span, which every
# attribute-scanning pass masks — so probe_leftovers can never see it. This
# probe runs on the include pass's own output instead, where a surviving
# ``<pre … data-code=…>`` opening tag means the idiom was mistyped.
CODE_LEFTOVER_RE = re.compile(r"<pre[^>]*\sdata-code\s*=[^>]*>")
H3_RE = re.compile(r"<h3\b([^>]*)>(.*?)</h3\s*>", re.DOTALL | re.IGNORECASE)
ID_ATTR_RE = re.compile(r'\bid\s*=\s*"([^"]*)"')
SLUG_STRIP_RE = re.compile(r"[^a-z0-9]+")
TAG_RE = re.compile(r"<[^>]+>")
LANG_CLASS_RE = re.compile(
    r'<pre([^>]*)><code\s+class="language-([A-Za-z0-9_+-]+)"\s*>(.*?)</code></pre>',
    re.DOTALL,
)
PRE_SPAN_RE = re.compile(r"<pre\b.*?</pre\s*>", re.DOTALL | re.IGNORECASE)
SVG_VIEWBOX_RE = re.compile(r'viewBox="(-?[\d.]+) (-?[\d.]+) (-?[\d.]+) (-?[\d.]+)"')

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

#: The findings marker the records block replaces.
EVIDENCE_MARK = "<!--EVIDENCE-->"

#: The layout generation this builder emits, stamped into the page head as
#: ``<meta name="generator" content="klein build_tutorial layout-N">``. Bump it
#: when the stylesheet's phone/print guarantees change; a page built before the
#: current generation is measured but never failed by
#: ``scripts/check_shipped_reports.py`` — its layout is history, not a regression.
LAYOUT_GENERATION = 2
GENERATOR_META = (
    f'<meta name="generator" content="klein build_tutorial layout-{LAYOUT_GENERATION}">'
)

#: Strengths in the order a reader wants them (strongest first); any other value
#: the lock carries follows alphabetically, so a new strength is still shown.
STRENGTH_ORDER = ("confirmed", "exploratory")


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


def _flow_list(raw: str) -> list[str] | None:
    """``["a", "b"]`` → its items; ``None`` when the value is not a flow list.

    A study declares ``mutable`` either inline or as a block list; returning
    ``None`` (rather than an empty list) is what lets the caller tell "not a
    flow list, keep reading the following lines" from "declared, but empty".
    """
    s = raw.strip()
    if not (s.startswith("[") and s.endswith("]")):
        return None
    inner = s[1:-1].strip()
    if not inner:
        return []
    return [item for item in (_clean_scalar(part) for part in inner.split(",")) if item]


def _as_int(raw: str | None) -> int | None:
    try:
        return int(str(raw).strip())
    except (TypeError, ValueError):
        return None


def _pack_tracks(
    ordered: list[str],
    per_track: dict[str, dict[str, str | None]],
    top: dict[str, str | None],
) -> list[tuple[str | None, str, str | None]]:
    """``[(track or None, metric name, goal)]`` — the ledger key's raw material."""
    packed: list[tuple[str | None, str, str | None]] = []
    for name in ordered:
        metric = per_track.get(name, {}).get("name")
        if metric:
            packed.append((name, metric, per_track[name].get("goal")))
    if not packed and top.get("name"):
        packed.append((None, str(top["name"]), top.get("goal")))
    return packed


def _tiny_parse_meta(text: str, meta: dict[str, Any]) -> dict[str, Any]:
    """Stdlib fallback: goal/domain/target, the metric(s) and their goals,
    ``schema_version`` and ``entrypoint.mutable``.

    Deliberately a line walker, not a YAML subset: the skill directory has to
    stay copy-a-directory portable, so PyYAML may be absent, and every key the
    builder needs is top-level or two levels under one.
    """
    in_metric = in_tracks = in_entrypoint = in_mutable = False
    track_name: str | None = None
    in_track_metric = False
    ordered: list[str] = []
    per_track: dict[str, dict[str, str | None]] = {}
    top_metric: dict[str, str | None] = {}
    mutable: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip(" "))
        if in_mutable and stripped.startswith("- "):
            item = _clean_scalar(stripped[2:])
            if item:
                mutable.append(item)
            continue
        key, sep, value = stripped.partition(":")
        if not sep:
            continue
        key = key.strip()
        in_mutable = False
        if indent == 0:
            in_metric = key == "metric"
            in_tracks = key == "tracks"
            in_entrypoint = key == "entrypoint"
            track_name = None
            in_track_metric = False
            if key in ("goal", "domain", "target"):
                meta[key] = _clean_scalar(value)
            elif key == "schema_version":
                meta["schema_version"] = _as_int(_clean_scalar(value))
        elif in_metric and key in ("name", "goal"):
            top_metric[key] = _clean_scalar(value)
        elif in_entrypoint and key == "mutable":
            items = _flow_list(value)
            if items is None:
                in_mutable = True
            else:
                mutable.extend(items)
        elif in_tracks and indent == 2:
            track_name = key
            in_track_metric = False
            if track_name not in per_track:
                ordered.append(track_name)
                per_track[track_name] = {}
        elif in_tracks and indent == 4:
            in_track_metric = key == "metric"
        elif in_tracks and indent >= 6 and in_track_metric and key in ("name", "goal"):
            if track_name:
                per_track[track_name][key] = _clean_scalar(value)
    if top_metric.get("name"):
        meta["metric_name"] = top_metric["name"]
    tracks = _pack_tracks(ordered, per_track, top_metric)
    if ordered and tracks:
        meta["metric_name"] = ", ".join(f"{metric} ({name})" for name, metric, _g in tracks)
    meta["tracks"] = tracks
    meta["mutable"] = mutable
    return meta


def load_study_meta(study_dir: Path) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "goal": None,
        "metric_name": None,
        "domain": None,
        "target": None,
        "schema_version": None,
        "mutable": [],
        "tracks": [],
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
            meta["schema_version"] = _as_int(data.get("schema_version"))
            entrypoint = data.get("entrypoint")
            if isinstance(entrypoint, dict):
                declared = entrypoint.get("mutable")
                if isinstance(declared, (list, tuple)):
                    meta["mutable"] = [str(item) for item in declared]
            top_metric: dict[str, str | None] = {}
            metric = data.get("metric")
            if isinstance(metric, dict):
                top_metric = {"name": metric.get("name"), "goal": metric.get("goal")}
                meta["metric_name"] = metric.get("name")
            ordered: list[str] = []
            per_track: dict[str, dict[str, str | None]] = {}
            tracks = data.get("tracks")
            if isinstance(tracks, dict):
                for track_name, track_spec in tracks.items():
                    if not isinstance(track_spec, dict):
                        continue
                    track_metric = track_spec.get("metric")
                    if not isinstance(track_metric, dict) or not track_metric.get("name"):
                        continue
                    ordered.append(str(track_name))
                    per_track[str(track_name)] = {
                        "name": track_metric.get("name"),
                        "goal": track_metric.get("goal"),
                    }
            packed = _pack_tracks(ordered, per_track, top_metric)
            if ordered and packed:
                meta["metric_name"] = ", ".join(
                    f"{metric_name} ({name})" for name, metric_name, _g in packed
                )
            meta["tracks"] = packed
            return meta
    return _tiny_parse_meta(text, meta)


def mutable_surface(meta: dict[str, Any]) -> tuple[str, ...]:
    """The study-relative files ONE candidate may change.

    COPIED from ``kleinlib.contract.mutable_surface``, never imported: the skill
    directory must stay portable to a checkout that carries no kleinlib. Schema 2
    has exactly one mutable file by construction and forever.
    """
    if (meta.get("schema_version") or 0) < 3:
        return ("train.py",)
    declared = tuple(str(item) for item in (meta.get("mutable") or []))
    return declared or ("train.py",)


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


def git_show_prefix(study_dir: Path) -> str | None:
    """The study dir's path INSIDE its repository (``studies/11-…/``).

    ``git show <commit>:<path>`` resolves paths from the repo ROOT, so a
    study-relative include has to be re-rooted before it can be asked for.
    """
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-prefix"],
            cwd=str(study_dir),
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, ValueError):  # pragma: no cover - git missing entirely
        return None
    return r.stdout.strip() if r.returncode == 0 else None


def git_show_bytes(study_dir: Path, commit: str, repo_rel: str) -> tuple[bytes | None, str]:
    """``(blob bytes, error)`` for one path at one commit — read-only, no checkout."""
    try:
        r = subprocess.run(
            ["git", "show", f"{commit}:{repo_rel}"],
            cwd=str(study_dir),
            capture_output=True,
            check=False,
        )
    except (OSError, ValueError):  # pragma: no cover - git missing entirely
        return None, "git is not available"
    if r.returncode != 0:
        return None, r.stderr.decode("utf-8", "replace").strip() or "git show failed"
    return r.stdout, ""


# --------------------------------------------------------------------------
# Figure inlining + ledger
# --------------------------------------------------------------------------


def png_intrinsic_size(data: bytes) -> tuple[int, int]:
    """Width/height from a PNG's IHDR, or ValueError naming what did not decode.

    Fail closed rather than guess: a JPEG renamed ``.png`` (or a truncated
    write from an interrupted ``make_figures.py``) would otherwise ship as a
    broken image inside a self-contained artifact nobody can re-fetch.
    """
    if data[:8] != PNG_SIGNATURE:
        raise ValueError("not a PNG: bad signature")
    if len(data) < 24 or data[12:16] != b"IHDR":
        raise ValueError("not a PNG: truncated or missing IHDR header")
    width, height = struct.unpack(">II", data[16:24])
    if not width or not height:
        raise ValueError("not a PNG: IHDR declares a zero dimension")
    return width, height


def inline_figures(
    content: str,
    study_dir: Path,
    missing: list[str],
    figure_number: itertools.count | None = None,
) -> str:
    """Inline every ``data-fig="figures/x.png"`` as base64 with intrinsic size.

    ``figure_number`` is the PAGE-WIDE figure counter (``assemble`` threads one
    through every fragment) so ``id="fig-N"`` is document order and identical on
    every rebuild; it advances for every figure, captioned or not, so adding a
    caption to one figure cannot renumber its neighbours.

    Two passes, deliberately: whole ``<img>`` tags first (they gain
    ``width``/``height``, and a ``data-caption`` promotes them into a numbered
    ``<figure>`` with a ``:target`` enlargement), then the historic
    attribute-only substitution for any ``data-fig`` that was authored on
    something other than an ``<img>``.
    """
    counter = itertools.count(1) if figure_number is None else figure_number

    def read_figure(rel: str) -> tuple[str, int, int] | None:
        fig_path = study_dir / rel
        if not fig_path.exists():
            missing.append(f"{rel} — not found under {study_dir}")
            return None
        raw = fig_path.read_bytes()
        try:
            width, height = png_intrinsic_size(raw)
        except ValueError as exc:
            missing.append(f"{rel} — {exc}")
            return None
        return base64.b64encode(raw).decode("ascii"), width, height

    def repl_img(match: re.Match[str]) -> str:
        tag = match.group(0)
        if FIG_RE.search(tag) is None:
            return tag  # a plain <img src=…>: not ours to rewrite
        caption = FIG_CAPTION_RE.search(tag)
        if caption is not None:
            tag = tag[: caption.start()] + tag[caption.end() :]
        fig = FIG_RE.search(tag)
        if fig is None:  # pragma: no cover - a data-caption swallowing data-fig
            return match.group(0)
        loaded = read_figure(fig.group(2))
        if loaded is None:
            return match.group(0)  # leave untouched; the build fails downstream
        data, width, height = loaded
        # Rebuild the tag rather than append to it: the closing ">" (and an XHTML
        # "/>" author's slash) must stay last so width/height land inside the tag.
        rest = tag[fig.end() : -1].rstrip()
        if rest.endswith("/"):
            rest = rest[:-1].rstrip()
        img = (
            f'{tag[: fig.start()]}src="data:image/png;base64,{data}"{rest}'
            f' width="{width}" height="{height}">'
        )
        index = next(counter)
        if caption is None:
            return img
        text = html.escape(html.unescape(caption.group(2)))
        return (
            f'<figure class="fig" id="fig-{index}">'
            f'<a class="fig-zoom" href="#fig-{index}" aria-label="Enlarge figure">{img}</a>'
            f"<figcaption>{text} "
            f'<a class="fig-close" href="#fig-{index}-close">Close</a></figcaption>'
            "</figure>"
        )

    def repl_attr(match: re.Match[str]) -> str:
        loaded = read_figure(match.group(2))
        if loaded is None:
            return match.group(0)
        return f'src="data:image/png;base64,{loaded[0]}"'

    return FIG_RE.sub(repl_attr, FIG_IMG_RE.sub(repl_img, content))


def _read_json(path: Path) -> dict[str, Any] | None:
    """One JSON object, or ``None`` for absent/unreadable/not-an-object."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return value if isinstance(value, dict) else None


def ledger_key(tracks: list[tuple[str | None, str, str | None]]) -> str:
    """One line naming what each track's number means — a status column is
    unreadable without the direction its metric is judged in."""
    if not tracks:
        return ""
    bits: list[str] = []
    for name, metric, goal in tracks:
        direction = f" ({html.escape(str(goal))} is better)" if goal else ""
        metric_html = f"<strong>{html.escape(str(metric))}</strong>{direction}"
        bits.append(f"{html.escape(str(name))} — {metric_html}" if name else metric_html)
    label = "Tracks" if tracks[0][0] else "Metric"
    return f'<p class="ledger-key">{label}: ' + " · ".join(bits) + "</p>\n"


def build_ledger(study_dir: Path, meta: dict[str, Any] | None = None) -> str:
    """Auto-generate the experiment ledger table from results.tsv.

    Track and Kind are shown only when the study actually records them: a
    schema-2 results.tsv has no ``track`` column, and a v1 study has no run
    manifests to read ``evaluation_kind`` from. An empty column would read as
    missing data rather than as a schema that never had the field.
    """
    path = study_dir / "results.tsv"
    if not path.exists():
        return '<p class="note">results.tsv not found — ledger omitted.</p>'
    if meta is None:
        meta = load_study_meta(study_dir)
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        fields = reader.fieldnames or []
        metric_col = next(
            (c for c in ("primary_metric", "metric", "val_auc") if c in fields),
            None,
        )
        rows = list(reader)
    show_track = "track" in fields

    kinds: dict[str, str] = {}
    any_manifest = False
    for r in rows:
        exp = (r.get("experiment") or "").strip()
        if not exp:
            continue
        manifest_path = study_dir / "runs" / exp / "manifest.json"
        if not manifest_path.is_file():
            continue
        any_manifest = True
        kind = (_read_json(manifest_path) or {}).get("evaluation_kind")
        if kind:
            kinds[exp] = str(kind)

    columns = ["<th>Exp</th>"]
    if show_track:
        columns.append("<th>Track</th>")
    if any_manifest:
        columns.append("<th>Kind</th>")
    columns += ["<th>Metric</th>", "<th>Status</th>", "<th>Description</th>"]
    head = '<table class="ledger">\n<thead><tr>' + "".join(columns) + "</tr></thead>\n<tbody>\n"

    body: list[str] = []
    for r in rows:
        raw_exp = (r.get("experiment") or "").strip()
        exp = html.escape(raw_exp)
        metric = html.escape((r.get(metric_col) or "").strip()) if metric_col else ""
        status = (r.get("status") or "").strip().lower()
        desc = html.escape((r.get("description") or "").strip())
        kind = kinds.get(raw_exp, "—")
        classes = [f"st-{html.escape(status)}"]
        if kind == "final_test":
            classes.append("kind-final_test")
        cells = [f"<td>{exp}</td>"]
        if show_track:
            cells.append(f"<td>{html.escape((r.get('track') or '').strip())}</td>")
        if any_manifest:
            cells.append(f"<td>{html.escape(kind)}</td>")
        cells += [
            f'<td class="num">{metric}</td>',
            f'<td><span class="badge">{html.escape(status)}</span></td>',
            f"<td>{desc}</td>",
        ]
        body.append(f'<tr class="{" ".join(classes)}">' + "".join(cells) + "</tr>")
    return ledger_key(meta.get("tracks") or []) + head + "\n".join(body) + "\n</tbody>\n</table>"


# --------------------------------------------------------------------------
# The evidence block — generated from the RECORDS, never from prose
# --------------------------------------------------------------------------


def _counts(values: list[str], first: tuple[str, ...] = ()) -> list[tuple[str, int]]:
    """Value → count, ``first`` in the given order and the rest alphabetically."""
    tally: dict[str, int] = {}
    for value in values:
        tally[value] = tally.get(value, 0) + 1
    ranked = [k for k in first if k in tally] + sorted(k for k in tally if k not in first)
    return [(k, tally[k]) for k in ranked]


def _tally_html(pairs: list[tuple[str, int]]) -> str:
    """``confirmed <code>6</code> · exploratory <code>9</code>``.

    Every count lives inside ``<code>``: ``klein verify --numbers`` scans the
    page's text nodes and skips code spans, so a generated count can never be
    read as a claim numeral that no artifact pins.
    """
    return (
        " · ".join(f"{html.escape(name)} <code>{count}</code>" for name, count in pairs)
        or "none recorded"
    )


def build_evidence(study_dir: Path) -> str:
    """The findings section's receipts block, copied out of the study's records.

    Reads ``claims.lock`` and ``study_state.json`` and does ONE arithmetic
    operation on them — counting. Everything else is a verbatim string, and a
    record the study never wrote says so by name instead of being guessed at.
    """
    meta = load_study_meta(study_dir)
    schema = meta.get("schema_version") or 0
    rows: list[tuple[str, str]] = []

    lock = _read_json(study_dir / "claims.lock")
    claims = lock.get("claims") if isinstance(lock, dict) else None
    if lock is None or (lock.get("lock_schema") or 0) < 2 or not isinstance(claims, dict):
        rows.append(("claims.lock", "not recorded (schema 2)" if schema < 3 else "not recorded"))
    else:
        entries = [v for v in claims.values() if isinstance(v, dict)]
        total = len(entries)
        with_errata = sum(1 for entry in entries if entry.get("errata"))
        top_errata = lock.get("errata")
        top_count = len(top_errata) if isinstance(top_errata, (dict, list)) else 0
        rows.append(("claims", f"<code>{total}</code> locked in <code>claims.lock</code>"))
        rows.append(
            (
                "by strength",
                _tally_html(
                    _counts(
                        [str(e.get("strength") or "unstated") for e in entries],
                        STRENGTH_ORDER,
                    )
                ),
            )
        )
        rows.append(
            (
                "by class",
                _tally_html(_counts([str(e.get("class") or "unstated") for e in entries])),
            )
        )
        rows.append(
            (
                "errata",
                f"<code>{with_errata}</code> of <code>{total}</code> claims tagged · "
                f"<code>{top_count}</code> erratum record(s) in the lock",
            )
        )
        head = str(lock.get("git_head") or "")
        version = str(lock.get("klein_version") or "")
        locked_at = f"<code>{html.escape(head[:12])}</code>" if head else "not recorded"
        if version:
            locked_at += f" · klein <code>{html.escape(version)}</code>"
        rows.append(("locked at", locked_at))

    state = _read_json(study_dir / "study_state.json") or {}
    final = state.get("finalization")
    if not isinstance(final, dict):
        rows.append(("finalization", "not recorded"))
    else:
        rows.append(("label", html.escape(str(final.get("label") or "not recorded"))))
        referee = final.get("referee")
        if isinstance(referee, dict) and referee.get("status") == "unrefereed":
            # `klein finalize --no-referee --reason` writes exactly this shape;
            # the reason is the study's own disclosure, so it is copied verbatim.
            reason = html.escape(str(referee.get("reason") or "no reason recorded"))
            rows.append(("referee", f"unrefereed (finalized with --no-referee: {reason})"))
        elif not isinstance(referee, dict):
            rows.append(("referee", "not recorded (schema 2)" if schema < 3 else "not recorded"))
        else:
            independent = "yes" if referee.get("independent_of_experimenter") else "no"
            rows.append(
                (
                    "referee",
                    f"{html.escape(str(referee.get('verdict') or 'no verdict'))} — "
                    f"<code>{html.escape(str(referee.get('referee') or 'unnamed'))}</code> · "
                    f"independent of the experimenter: {independent}",
                )
            )
        gaps = final.get("confirmation_gaps")
        if isinstance(gaps, dict) and gaps:
            for track in sorted(gaps):
                reasons = gaps[track]
                listed = reasons if isinstance(reasons, list) else [reasons]
                rows.append(
                    (
                        f"confirmation gap · {track}",
                        "; ".join(html.escape(str(item)) for item in listed),
                    )
                )

    items = "\n".join(f"<dt>{html.escape(term)}</dt><dd>{value}</dd>" for term, value in rows)
    return (
        '<div class="evidence" data-generated="evidence">\n'
        '<dl class="evidence-list">\n' + items + "\n</dl>\n</div>"
    )


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
    mathml = latex2mathml_converter.convert(latex, display="block" if display else "inline")
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
        return f'<span class="kmath" data-latex="{source}"{_inline_math_style(svg)}>{svg}</span>'

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


def _run_source(
    study_dir: Path, run_id: str, rel: str, fragment: str
) -> tuple[bytes | None, dict[str, str], str]:
    """The bytes ONE run executed, plus that run's (commit, kind, track).

    ``run-one`` restores the mutable surface after a non-keep, so the file on
    disk is never proof of what a given cell ran; the candidate commit is. This
    reads the blob out of git rather than trusting the working tree.
    """
    manifest_rel = f"runs/{run_id}/manifest.json"
    manifest = _read_json(study_dir / manifest_rel)
    if manifest is None:
        return (
            None,
            {},
            f"{fragment}: data-run={run_id!r} for data-code={rel!r} has no readable "
            f"manifest at {manifest_rel}",
        )
    commit = str(manifest.get("candidate_commit") or "")
    if not commit:
        return (
            None,
            {},
            f"{fragment}: data-run={run_id!r} for data-code={rel!r}: {manifest_rel} "
            "records no 'candidate_commit'",
        )
    facts = {
        "commit": commit,
        "kind": str(manifest.get("evaluation_kind") or "unrecorded"),
        "track": str(manifest.get("track") or "unrecorded"),
    }
    prefix = git_show_prefix(study_dir)
    if prefix is None:
        return (
            None,
            facts,
            f"{fragment}: data-run={run_id!r} needs git to read {rel!r} at commit "
            f"{commit[:12]}, and git is not available here",
        )
    repo_rel = f"{prefix}{rel}"
    blob, error = git_show_bytes(study_dir, commit, repo_rel)
    if blob is None:
        return (
            None,
            facts,
            f"{fragment}: data-run={run_id!r}: git show {commit[:12]}:{repo_rel} failed — {error}",
        )
    return blob, facts, ""


def include_code(
    content: str,
    study_dir: Path,
    fragment: str,
    errors: list[str],
    meta: dict[str, Any] | None = None,
) -> str:
    """Resolve ``<pre data-code="…"></pre>`` includes against the study dir.

    This is what turns the spec's "the page carries the ACTUAL winning
    entrypoint" from a checklist promise into a build-time guarantee — and, with
    ``data-run``, names WHICH run's bytes those are instead of letting the reader
    assume the working tree is a cell.
    """
    surface = set(mutable_surface(meta if meta is not None else load_study_meta(study_dir)))

    def repl(match: re.Match[str]) -> str:
        rel = match.group(1)
        attrs = dict(CODE_ATTR_RE.findall(match.group(2)))
        lang, run, role = attrs.get("lang"), attrs.get("run"), attrs.get("role")
        if Path(rel).is_absolute() or ".." in Path(rel).parts:
            errors.append(
                f"{fragment}: data-code={rel!r} must be a relative path inside the study dir"
            )
            return ""
        if role is not None and role != "template":
            errors.append(f'{fragment}: data-role={role!r} is not a known role (only "template")')
            return ""
        norm = Path(rel).as_posix()
        if norm in surface and not run and role != "template":
            errors.append(
                f"{fragment}: data-code={norm!r} is the mutable surface, so the file "
                "on disk is the RESTORED template, not the cell a run executed; add "
                'data-run="E####" to include the executed source, or '
                'data-role="template" to label it'
            )
            return ""

        path = study_dir / rel
        if run:
            raw, facts, error = _run_source(study_dir, run, norm, fragment)
            if raw is None:
                errors.append(error)
                return ""
            try:
                source = raw.decode("utf-8")
            except UnicodeDecodeError:
                errors.append(
                    f"{fragment}: data-run={run!r}: {norm!r} at commit "
                    f"{facts['commit'][:12]} is not UTF-8 text"
                )
                return ""
        else:
            if not path.is_file():
                errors.append(f"{fragment}: data-code={rel!r} not found under {study_dir}")
                return ""
            raw, facts = path.read_bytes(), {}
            source = path.read_text(encoding="utf-8")

        resolved_lang = lang or LANG_BY_SUFFIX.get(path.suffix, "text")
        try:
            highlighted = _highlight_source(source, resolved_lang)
        except ClassNotFound:
            errors.append(f"{fragment}: data-lang={resolved_lang!r} is not a known lexer")
            return ""

        sha = hashlib.sha256(raw).hexdigest()[:12]
        if run:
            provenance = (
                f"executed by <code>{html.escape(run)}</code> "
                f"({html.escape(facts['kind'])}, track {html.escape(facts['track'])}) "
                f"at commit <code>{html.escape(facts['commit'][:12])}</code> · "
                f"sha256 <code>{sha}…</code>"
            )
        elif role == "template":
            provenance = f"restored template on disk, not a run's cell · sha256 <code>{sha}…</code>"
        else:
            provenance = (
                f"current file at build (outside the mutable surface) · sha256 <code>{sha}…</code>"
            )

        esc_rel = html.escape(norm, quote=True)
        wrapper = f' data-code-source="{esc_rel}"'
        if run:
            wrapper += f' data-run="{html.escape(run, quote=True)}"'
        if role == "template":
            wrapper += ' data-role="template"'
        return (
            f'<details class="source"{wrapper}>\n'
            f'<summary><span class="src-path"><code>{html.escape(norm)}</code></span> · '
            f'<span class="src-prov">{provenance}</span></summary>\n'
            f'<pre class="klein-code" data-code-source="{esc_rel}">'
            f'<code class="language-{html.escape(resolved_lang, quote=True)}">'
            f"{highlighted}</code></pre>\n"
            "</details>"
        )

    resolved = CODE_INCLUDE_RE.sub(repl, content)
    for leftover in CODE_LEFTOVER_RE.finditer(resolved):
        errors.append(
            f"{fragment}: unconsumed data-code (unknown attribute, unquoted value, or a "
            f"non-empty element?): {leftover.group(0)[:80]!r}"
        )
    return resolved


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


def slugify(text: str) -> str:
    """A heading's TEXT → a stable ASCII anchor slug."""
    plain = html.unescape(TAG_RE.sub(" ", text))
    return SLUG_STRIP_RE.sub("-", plain.lower()).strip("-") or "section"


def heading_text(inner: str) -> str:
    """A heading's rendered words: tags out, entities back, spaces collapsed."""
    return re.sub(r"\s+", " ", html.unescape(TAG_RE.sub(" ", inner))).strip()


def _insert_after_first_h2(section: str, block: str) -> str:
    """Put ``block`` right after the section's own heading, never inside a <pre>."""
    spans = [m.span() for m in PRE_SPAN_RE.finditer(section)]
    start = 0
    while True:
        idx = section.find("</h2>", start)
        if idx == -1:  # a fragment with no <h2> keeps its subnav-less shape
            return section
        if not any(begin <= idx < stop for begin, stop in spans):
            end = idx + len("</h2>")
            return f"{section[:end]}\n{block}{section[end:]}"
        start = idx + 1


def add_subsection_anchors(sections: list[str]) -> list[str]:
    """Give every ``<h3>`` a page-unique id, and every multi-h3 section a subnav.

    The slug depends only on the heading text and on the headings BEFORE it, so
    appending a subsection never renumbers an existing anchor — a tutorial that
    is cited by deep link has to survive its own rebuild. The seven section
    anchors are reserved up front so an ``<h3>Findings</h3>`` cannot steal
    ``#findings`` from the section it lives in.
    """
    seen: dict[str, int] = {anchor: 1 for _f, anchor, _t in SECTIONS}
    out: list[str] = []
    for section in sections:
        headings: list[tuple[str, str]] = []

        def annotate(segment: str, headings: list[tuple[str, str]] = headings) -> str:
            def repl(match: re.Match[str]) -> str:
                attrs, inner = match.group(1), match.group(2)
                existing = ID_ATTR_RE.search(attrs)
                if existing:
                    headings.append((existing.group(1), heading_text(inner)))
                    return match.group(0)
                base = slugify(inner)
                count = seen.get(base, 0) + 1
                seen[base] = count
                slug = base if count == 1 else f"{base}-{count}"
                headings.append((slug, heading_text(inner)))
                return f'<h3 id="{slug}"{attrs}>{inner}</h3>'

            return H3_RE.sub(repl, segment)

        section = outside_pre(section, annotate)
        if len(headings) >= 2:
            links = "".join(
                f'<a href="#{html.escape(slug, quote=True)}">{html.escape(text)}</a>'
                for slug, text in headings
            )
            section = _insert_after_first_h2(
                section,
                '<nav class="subnav" aria-label="In this section">' + links + "</nav>",
            )
        out.append(section)
    return out


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
        + "@media print{\n"
        # Re-assert the LIGHT token colours for print: without this a reader in
        # dark mode prints white-on-paper code from the dark block above.
        + light
        + "\n}\n"
        + "/* Build-time math (inline SVG glyph paths) */\n"
        # max-width + overflow-x let a formula wider than the column scroll on
        # its own instead of widening the page; the element's inline
        # vertical-align (computed from the viewBox) still sets the baseline,
        # and the box hugs the SVG height, so no descent is clipped.
        + ".kmath{display:inline-block;max-width:100%;overflow-x:auto}\n"
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
section{padding:34px 0;border-bottom:1px solid var(--rule);scroll-margin-top:76px}
h3[id]{scroll-margin-top:76px}
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
table.ledger td.num{font-variant-numeric:tabular-nums;white-space:nowrap}
table.ledger tr.kind-final_test td:first-child{font-weight:600}
table.ledger tr.kind-final_test td:first-child::after{content:" · sealed";font-weight:400;
font-size:11px;letter-spacing:.03em;color:var(--muted)}
.ledger-key{font-size:14px;color:var(--muted)}
.badge{display:inline-block;font-size:11px;letter-spacing:.03em;text-transform:uppercase;
background:var(--badge);color:var(--accent);border-radius:999px;padding:2px 9px}
tr.st-discard .badge{color:var(--muted)}tr.st-crash .badge{color:var(--accent2)}
blockquote{margin:0 0 16px;padding:2px 16px;border-left:3px solid var(--rule);color:var(--muted)}
.note{font-size:14px;color:var(--muted)}
.site-footer{border-top:1px solid var(--rule);padding:26px 0 48px;color:var(--muted);font-size:13px}
.site-footer .lineage{font-family:ui-monospace,Menlo,monospace;font-size:12px;margin-top:6px}
/* A long path, sha256, DOI or URL must reflow rather than widen the whole page —
   inside <code>/<a>/<cite> and as plain text in a reference list alike; the rule
   only fires on a token that cannot fit a line by itself, so prose is untouched.
   <pre> is exempt because it scrolls (breaking source lines misreads code). */
p,li,dd,td,th,figcaption,blockquote,code,a,cite{overflow-wrap:anywhere}
pre code{overflow-wrap:normal}
/* Section sub-navigation emitted after an <h2>. */
nav.subnav{display:flex;flex-wrap:wrap;gap:4px 14px;margin:0 0 16px;font-size:13px}
nav.subnav a{color:var(--muted);text-decoration:none;overflow-wrap:anywhere}
nav.subnav a:hover{color:var(--fg)}
/* Evidence blocks: a bordered key/value card that collapses to one column. */
.evidence{margin:16px 0;padding:12px 16px;border:1px solid var(--rule);border-radius:8px;
background:var(--card);font-size:15px;overflow-wrap:anywhere}
.evidence dl{margin:0;display:grid;grid-template-columns:minmax(0,auto) minmax(0,1fr);gap:4px 16px}
.evidence dt{color:var(--muted);font-size:14px}
.evidence dd{margin:0;min-width:0}
.evidence table{margin:0}
/* Source disclosure: the summary reads as the listing's caption, and the
   listing sits flush inside it (the <pre> drops its own border, never two). */
details.source{margin:0 0 16px;border:1px solid var(--rule);border-radius:8px;
background:var(--code-bg);overflow:hidden}
details.source>summary{cursor:pointer;padding:8px 14px;font-size:13px;line-height:1.5;
color:var(--muted);font-family:system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
overflow-wrap:anywhere}
/* Two rules, not one selector list: a browser that knows only one of these
   pseudo-elements would otherwise drop the whole declaration. */
details.source>summary::marker{color:var(--rule)}
details.source>summary::-webkit-details-marker{color:var(--rule)}
details.source>summary:focus-visible{outline:2px solid var(--accent);outline-offset:-3px}
details.source .src-path code{background:none;padding:0;font-size:13px;color:var(--fg)}
details.source .src-prov{color:var(--muted)}
details.source[open]>summary{border-bottom:1px solid var(--rule)}
details.source>pre,details.source>pre.klein-code{margin:0;border:0;border-radius:0;background:none}
/* Captioned figures: one image, two states. The enlargement is CSS :target on
   the SAME element, so the page never carries a second copy of the bytes. */
figure.fig{margin:20px 0}
figure.fig .fig-zoom{display:block;text-decoration:none}
figure.fig .fig-close{display:none}
figure.fig:target{position:fixed;inset:0;z-index:20;margin:0;padding:14px 16px 20px;
overflow:auto;background:var(--bg)}
figure.fig:target .fig-zoom{display:inline-block}
figure.fig:target img{max-width:none;width:auto;margin:0}
figure.fig:target figcaption{position:sticky;left:0;text-align:left;margin-top:10px}
figure.fig:target .fig-close{display:inline-block;margin-left:8px;color:var(--accent);
font-weight:600;text-decoration:underline}
/* 860px is the content column's own max-width: at or above it the nav provably
   fits one 52px row, below it the links would wrap and bury the anchor targets
   under a two-row bar. So below it the nav becomes ONE scrollable row instead,
   and scroll-margin gains the ~15px a non-overlay scrollbar adds to that row. */
@media (max-width:860px){
nav.topnav .wrap{flex-wrap:nowrap;overflow-x:auto;-webkit-overflow-scrolling:touch}
nav.topnav a{white-space:nowrap;flex:0 0 auto}
section{scroll-margin-top:84px}h3[id]{scroll-margin-top:84px}
.evidence dl{grid-template-columns:minmax(0,1fr)}
.evidence dt{margin-top:6px}}
@media print{
/* Re-declare the light palette: a dark-scheme reader must print on paper. */
:root{--bg:#fff;--fg:#111;--muted:#444;--rule:#ccc;--card:#fff;--accent:#0a5c55;
--accent2:#7f1d1d;--code-bg:#f6f6f6;--badge:#eee;--shadow:none}
nav.topnav{position:static;backdrop-filter:none;background:#fff}
body{font-size:12pt;background:#fff;color:#111}
/* break-inside:avoid on a SECTION pushed whole sections onto fresh pages and
   left the previous one near-empty; the atoms below are what must stay whole. */
section{border-color:#ccc;break-inside:auto}
h2,h3{break-after:avoid}
figure,img,table.ledger tr{break-inside:avoid}
a{color:inherit;text-decoration:none}img{border-color:#ccc}
pre{white-space:pre-wrap;overflow:visible;border-color:#ccc}
table{display:table;overflow:visible}
td,th{overflow-wrap:anywhere}
.kmath{overflow:visible;max-width:none}.kmath-display{overflow:visible}
details.source{display:block}details.source>summary{display:block}
figure.fig:target{position:static;inset:auto;overflow:visible;padding:0}
figure.fig:target img{max-width:100%}figure.fig .fig-close{display:none}}
"""

NAV_JS = """
(function(){
  var links=[].slice.call(document.querySelectorAll('nav.topnav a'));
  var map={};links.forEach(function(a){map[a.getAttribute('href').slice(1)]=a;});
  if('IntersectionObserver' in window){
    var obs=new IntersectionObserver(function(entries){
      entries.forEach(function(e){
        if(e.isIntersecting){
          links.forEach(function(a){a.classList.remove('active');});
          var a=map[e.target.id];if(a)a.classList.add('active');
        }
      });
    },{rootMargin:'-45% 0px -50% 0px'});
    document.querySelectorAll('main section[id]').forEach(function(s){obs.observe(s);});
  }
  /* A printout must not lose a listing that happens to be collapsed on screen.
     The pre-print state is restored, so printing never edits what is read. */
  var reopened=[];
  window.addEventListener('beforeprint',function(){
    reopened=[];
    document.querySelectorAll('details.source').forEach(function(d){
      reopened.push([d,d.open]);d.open=true;
    });
  });
  window.addEventListener('afterprint',function(){
    reopened.forEach(function(pair){pair[0].open=pair[1];});reopened=[];
  });
  /* Escape leaves a :target figure enlargement exactly the way the Close link
     does — move to a hash that matches no element, so nothing scrolls. */
  document.addEventListener('keydown',function(e){
    if(e.key!=='Escape')return;
    var h=location.hash;
    if(h.lastIndexOf('#fig-',0)!==0||h.slice(-6)==='-close')return;
    location.hash=h.slice(1)+'-close';
  });
})();
"""


def content_security_policy() -> str:
    """Return the restrictive policy for a generated, offline tutorial.

    Figures are data URIs and CSS is intentionally inlined.  The only script is
    this module's fixed navigation helper, authorized by its exact SHA-256 rather
    than by ``'unsafe-inline'``.  Everything capable of network activity is
    denied explicitly as well as by ``default-src 'none'``.
    """
    script_hash = base64.b64encode(hashlib.sha256(NAV_JS.encode("utf-8")).digest()).decode("ascii")
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
    return f'<meta http-equiv="Content-Security-Policy" content="{content_security_policy()}">'


def assemble(
    study_dir: Path,
    title: str,
    meta: dict[str, Any],
    missing: list[str],
    math_errors: list[str],
    code_errors: list[str],
) -> str:
    study_id = study_dir.name
    ledger = build_ledger(study_dir, meta)
    evidence = build_evidence(study_dir)
    # One counter for the whole page: figure ids are document order, not
    # per-fragment order, and a rebuild renumbers nothing.
    figure_number = itertools.count(1)

    body_sections: list[str] = []
    for filename, anchor, _title in SECTIONS:
        frag = (study_dir / "report" / "sections" / filename).read_text(encoding="utf-8")
        # Order matters: literal pastes are highlighted BEFORE includes are
        # resolved (an include target is an EMPTY <pre>, so the paste pass
        # cannot double-process it, and the include emits final form); math
        # and figures scan attributes, so both run masked outside <pre>.
        frag = highlight_code(frag, filename, code_errors)
        frag = include_code(frag, study_dir, filename, code_errors, meta)
        frag = outside_pre(
            frag,
            functools.partial(render_math, fragment=filename, errors=math_errors),
        )
        frag = outside_pre(
            frag,
            functools.partial(
                inline_figures,
                study_dir=study_dir,
                missing=missing,
                figure_number=figure_number,
            ),
        )
        probe_leftovers(frag, filename, math_errors, code_errors)
        frag = frag.replace("<!--LEDGER-->", ledger)
        frag = frag.replace(EVIDENCE_MARK, evidence)
        body_sections.append(f'<section id="{anchor}">\n{frag}\n</section>')

    # Last pass, deliberately: ids must be unique across the WHOLE page, and the
    # generated ledger/evidence blocks are part of the text an <h3> can precede.
    body_sections = add_subsection_anchors(body_sections)

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
        f"{GENERATOR_META}\n"
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
        '<main class="wrap">\n' + "\n".join(body_sections) + "\n</main>\n"
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
            "[build_tutorial] FAIL: the tutorial renderer needs pygments + ziamath + latex2mathml.",
            file=sys.stderr,
        )
        print("       In this repo:      uv sync --locked", file=sys.stderr)
        print(
            "       In a foreign repo: uv add "
            '"klein-auto-research @ git+https://github.com/Xiang-Shan/'
            'klein-auto-research@v2.0.0"',
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
        print("[build_tutorial] figure problem(s) referenced via data-fig:", file=sys.stderr)
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
    # A study with a lock has receipts; a findings section that never shows them
    # is asking the reader to take the verdicts on trust.
    if (study_dir / "claims.lock").is_file() and 'data-generated="evidence"' not in page:
        violations.append(
            f"claims.lock exists but no fragment carries {EVIDENCE_MARK}; "
            "add the marker to 05-findings.html"
        )
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
