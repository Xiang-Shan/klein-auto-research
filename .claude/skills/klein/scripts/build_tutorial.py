#!/usr/bin/env python3
"""build_tutorial.py — Route B assembler for the Klein TUTORIAL stage.

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
- A ``<!--LEDGER-->`` marker (used in 04-journey) is replaced with an
  auto-generated experiment ledger table read from ``results.tsv``.

Acceptance guard (runs on the assembled page; non-zero exit lists violations):
- all seven section anchors present;
- zero ``http://`` / ``https://`` inside ``src=``/``href=`` ATTRIBUTE values
  (plain-text URLs inside <cite>/<code>/reference lists are allowed — only
  attribute URLs are banned, since those are what trigger a network fetch).

Stdlib only. PyYAML is used opportunistically for study.yaml (same graceful
fallback pattern as summarize_results.py) but never required.

Usage:
    uv run python .claude/skills/klein/scripts/build_tutorial.py <study_dir> [--title "..."]
"""

from __future__ import annotations

import argparse
import base64
import csv
import html
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - exercised via the tiny fallback parser
    yaml = None  # type: ignore

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
            if key in ("goal", "domain", "target"):
                meta[key] = _clean_scalar(value)
        elif in_metric and key == "name":
            meta["metric_name"] = _clean_scalar(value)
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
pre code{background:none;padding:0;font-size:14px;line-height:1.55}
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


def assemble(study_dir: Path, title: str, meta: dict[str, str | None], missing: list[str]) -> str:
    study_id = study_dir.name
    ledger = build_ledger(study_dir)

    body_sections: list[str] = []
    for filename, anchor, _title in SECTIONS:
        frag = (study_dir / "report" / "sections" / filename).read_text(encoding="utf-8")
        frag = inline_figures(frag, study_dir, missing)
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
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n"
        f"<style>{CSS}</style>\n</head>\n<body>\n"
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
    for _f, anchor, _t in SECTIONS:
        if f'id="{anchor}"' not in page:
            violations.append(f"missing section anchor: id={anchor!r}")
    for match in ATTR_URL_RE.finditer(page):
        value = match.group(2)
        if "http://" in value or "https://" in value:
            violations.append(f"external URL in src/href attribute: {value[:70]!r}")
    return violations


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Assemble a Klein study tutorial (Route B).")
    p.add_argument("study_dir", type=Path, help="Path to studies/NN-<name>/")
    p.add_argument("--title", help="Page title (default: the study id).")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    study_dir = args.study_dir.resolve()
    sections_dir = study_dir / "report" / "sections"

    absent = [name for name, _a, _t in SECTIONS if not (sections_dir / name).exists()]
    if absent:
        print(f"[build_tutorial] missing fragment(s) in {sections_dir}:", file=sys.stderr)
        for name in absent:
            print(f"  - {name}", file=sys.stderr)
        return 2

    meta = load_study_meta(study_dir)
    title = args.title or study_dir.name
    missing_figs: list[str] = []
    page = assemble(study_dir, title, meta, missing_figs)

    if missing_figs:
        print("[build_tutorial] missing figure(s) referenced via data-fig:", file=sys.stderr)
        for rel in dict.fromkeys(missing_figs):  # dedupe, keep order
            print(f"  - {rel}", file=sys.stderr)
        return 3

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
