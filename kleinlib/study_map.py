"""``klein map`` — a study as a map, not a metric.

A finished run leaves a number; a finished study should leave an understanding:
which question was asked, what was predicted before the evidence, which runs
bear on which prediction, which claims the evidence earned and how strongly,
what was decided along the way — and what is still open.  Every one of those
facts is already on the record (the contract, the predictions ledger, the run
manifests, ``claims.lock``, the dated ``Decision:`` lines of ``program.md``);
this module only joins them.

Read-only and derived: it writes nothing unless asked for an HTML file, it adds
no record of its own, and nothing the engine judges depends on it.
"""

from __future__ import annotations

import html
import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .contract import load_contract, normalize_tracks, rigor
from .errors import WorkflowError

__all__ = ["build_map", "format_map", "render_html"]

_RUN_RE = re.compile(r"\bE\d{4}\b")
_ID_RE = re.compile(r"\b(?:E\d{4}|P\d+|C\d+|RQ\d+|X\d{4})\b")
_DECISION_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\b.{0,12}?Decision:\s*(.*)")
_CLAIM_QUESTION_RE = re.compile(r"\*\*\[(C\d+)\]\*\*\s*\|\s*(RQ\d+)")


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _short(text: Any, limit: int = 160) -> str:
    flat = " ".join(str(text or "").split())
    return flat if len(flat) <= limit else flat[: limit - 1].rsplit(" ", 1)[0] + "…"


def _natural(identifier: str) -> tuple[str, int]:
    """``C10`` sorts after ``C9``."""
    match = re.match(r"([A-Za-z:]*)(\d+)", identifier)
    return (match.group(1), int(match.group(2))) if match else (identifier, 0)


def _decisions(program: str) -> list[dict[str, Any]]:
    """Dated ``Decision:`` entries of ``program.md``, each with the ids it names."""
    lines = program.splitlines()
    found: list[dict[str, Any]] = []
    for index, line in enumerate(lines):
        match = _DECISION_RE.search(line)
        if not match:
            continue
        body = [match.group(2)]
        for following in lines[index + 1 :]:
            if not following.strip() or re.match(r"^\s{0,3}([-*]|\d+\.|#|\|)", following):
                break
            body.append(following.strip())
        text = " ".join(body).replace("**", "")
        found.append(
            {
                "id": f"D{len(found) + 1}",
                "date": match.group(1),
                "text": _short(text, 240),
                "mentions": sorted(set(_ID_RE.findall(" ".join(body)))),
            }
        )
    return found


def _probes(study: Path) -> list[dict[str, Any]]:
    rows = []
    for line in _read(study / "probes.jsonl").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict) and row.get("id"):
            rows.append(row)
    return rows


def build_map(study_dir: str | Path) -> dict[str, Any]:
    """The study's evidence graph: nodes, edges, and what is still open."""
    from .checks import _state_or_empty
    from .manifest import load_manifests
    from .predictions import ledger

    study = Path(study_dir)
    contract = load_contract(study)
    state = _state_or_empty(study, contract)
    manifests = load_manifests(study)
    lock = _json(study / "claims.lock")
    claims = lock.get("claims") if isinstance(lock, Mapping) else None
    claims = claims if isinstance(claims, Mapping) else {}
    findings = _read(study / "findings.md")
    claim_question = dict(_CLAIM_QUESTION_RE.findall(findings))

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    known: set[str] = set()

    def add(node_id: str, kind: str, label: str, **attrs: Any) -> None:
        known.add(node_id)
        nodes.append({"id": node_id, "type": kind, "label": label, **attrs})

    def link(source: str, target: str, kind: str) -> None:
        edge = {"from": source, "to": target, "type": kind}
        if edge not in edges:
            edges.append(edge)

    # --- questions -----------------------------------------------------------
    questions = contract.get("research_questions")
    for row in questions if isinstance(questions, list) else []:
        if isinstance(row, Mapping) and row.get("id"):
            add(str(row["id"]), "question", _short(row.get("question")), prior=_short(row.get("prior")))

    # --- runs ----------------------------------------------------------------
    for manifest in manifests:
        run_id = str(manifest.get("experiment"))
        add(
            run_id,
            "run",
            _short(manifest.get("description"), 120),
            track=manifest.get("track"),
            disposition=manifest.get("disposition"),
            metric=manifest.get("primary_metric"),
            metric_name=manifest.get("metric_name"),
            sealed=manifest.get("evaluation_kind") == "final_test",
        )
    for probe in _probes(study):
        add(str(probe["id"]), "probe", _short(probe.get("note") or " ".join(probe.get("command", [])), 120))

    # --- predictions ---------------------------------------------------------
    predictions = ledger(contract, state)
    for row in predictions:
        pid = str(row["id"])
        add(
            pid,
            "prediction",
            _short(row.get("statement")),
            verdict=row.get("verdict"),
            rule=row.get("rule"),
            track=row.get("track"),
        )
        for evidence in row.get("evidence") or []:
            run = _RUN_RE.search(str(evidence))
            if run and run.group(0) in known:
                link(run.group(0), pid, str(row.get("verdict") or "tests"))

    # --- claims --------------------------------------------------------------
    for claim_id, entry in sorted(claims.items(), key=lambda item: _natural(str(item[0]))):
        if not isinstance(entry, Mapping):
            continue
        add(
            str(claim_id),
            "claim",
            _short(entry.get("claim")),
            strength=entry.get("strength"),
            claim_class=entry.get("class"),
            evidence=list(entry.get("evidence") or []),
            errata=list(entry.get("errata") or []),
        )
        for evidence in entry.get("evidence") or []:
            run = _RUN_RE.search(str(evidence))
            if run and run.group(0) in known:
                link(run.group(0), str(claim_id), "supports")
        question = claim_question.get(str(claim_id))
        if question in known:
            link(str(claim_id), question, "answers")

    # A prediction bears on a question when a claim answering that question
    # rests on a run that also adjudicated the prediction (derived, not declared).
    runs_of_prediction = {
        str(row["id"]): {e["from"] for e in edges if e["to"] == str(row["id"])} for row in predictions
    }
    for claim_id, question in claim_question.items():
        if question not in known:
            continue
        claim_runs = {e["from"] for e in edges if e["to"] == claim_id and e["type"] == "supports"}
        for pid, runs in runs_of_prediction.items():
            if runs & claim_runs:
                link(question, pid, "predicts")

    # Before any claim exists the link has to come from the contract: a
    # prediction that names its question (`question: RQ1`, or the id in its
    # statement), or a study with one question, which every prediction bears on.
    from .contract import registered_predictions

    declared = registered_predictions(contract)
    question_ids = [node["id"] for node in nodes if node["type"] == "question"]
    for row in predictions:
        pid = str(row["id"])
        entry = declared.get(pid) if isinstance(declared.get(pid), Mapping) else {}
        named = entry.get("question")
        mentioned = [q for q in question_ids if re.search(rf"\b{re.escape(q)}\b", str(row.get("statement") or ""))]
        if isinstance(named, str) and named in known:
            link(named, pid, "predicts")
        elif mentioned:
            for question in mentioned:
                link(question, pid, "predicts")
        elif len(question_ids) == 1 and not any(e["to"] == pid and e["type"] == "predicts" for e in edges):
            link(question_ids[0], pid, "predicts")

    # --- decisions -----------------------------------------------------------
    decisions = _decisions(_read(study / "program.md"))
    for decision in decisions:
        add(decision["id"], "decision", decision["text"], date=decision["date"])
        for mention in decision["mentions"]:
            if mention in known and mention != decision["id"]:
                link(decision["id"], mention, "decides")

    # --- what is still open, and what could be pursued next -------------------
    # `open` must be resolved before the study can close honestly; `leads` are
    # legitimate final states that say where a follow-up study would start.
    open_items: list[dict[str, str]] = []
    leads: list[dict[str, str]] = []

    def still(kind: str, node_id: str, message: str) -> None:
        open_items.append({"kind": kind, "id": node_id, "message": message})

    def lead(kind: str, node_id: str, message: str) -> None:
        leads.append({"kind": kind, "id": node_id, "message": message})

    decided = {m for d in decisions for m in d["mentions"]}
    for row in predictions:
        pid, verdict = str(row["id"]), str(row.get("verdict"))
        if verdict == "open":
            still("prediction-open", pid, "registered, not yet adjudicated by any run")
        elif verdict == "inconclusive":
            lead("prediction-inconclusive", pid, "inconclusive — this evidence could not decide it")
        elif verdict == "refuted" and pid not in decided:
            still("refutation-undecided", pid, "refuted, and no dated Decision: line says what changed")
    answered = set(claim_question.values())
    for node in nodes:
        if node["type"] == "question" and node["id"] not in answered:
            still("question-unanswered", node["id"], "no claim answers this question yet")
        if node["type"] == "claim" and node.get("strength") not in {"confirmed", None}:
            lead("claim-unconfirmed", node["id"], f"{node.get('strength')} — not confirmed by this study")
        if node["type"] == "claim" and node.get("strength") is None:
            still("claim-unclassified", node["id"], "the claim has no strength yet")
        if node["type"] == "run" and node.get("disposition") == "crash":
            cited = any(e["from"] == node["id"] or e["to"] == node["id"] for e in edges)
            if not cited:
                still("crash-unexplained", node["id"], "a crash no prediction, claim or decision mentions")

    gates = state.get("gates") if isinstance(state.get("gates"), Mapping) else {}
    finalization = state.get("finalization") if isinstance(state.get("finalization"), Mapping) else {}
    data = contract.get("data")
    counts = {
        kind: sum(node["type"] == kind for node in nodes)
        for kind in ("question", "prediction", "run", "probe", "claim", "decision")
    }
    return {
        "study": str(contract.get("study_id") or study.name),
        "goal": _short(contract.get("goal"), 400),
        "kind": contract.get("kind"),
        "modality": data.get("modality") if isinstance(data, Mapping) else None,
        "profile": contract.get("profile"),
        "status": state.get("status"),
        "label": finalization.get("label"),
        "rigor": rigor(contract),
        "gates": {name: value.get("status") for name, value in gates.items() if isinstance(value, Mapping)},
        "tracks": sorted(normalize_tracks(contract)),
        "counts": counts,
        "nodes": nodes,
        "edges": edges,
        "open": open_items,
        "leads": leads,
    }


# --------------------------------------------------------------------------
# Text
# --------------------------------------------------------------------------

_VERDICT_MARK = {"supported": "+", "refuted": "x", "inconclusive": "?", "open": "·"}


def format_map(data: Mapping[str, Any]) -> str:
    """The map as plain text: one block per question, then what is open."""
    nodes = {node["id"]: node for node in data["nodes"]}
    edges = data["edges"]

    def targets(source: str, kind: str | None = None) -> list[str]:
        return [e["to"] for e in edges if e["from"] == source and (kind is None or e["type"] == kind)]

    def sources(target: str, kind: str | None = None) -> list[str]:
        return [e["from"] for e in edges if e["to"] == target and (kind is None or e["type"] == kind)]

    def runs_into(target: str) -> list[str]:
        return [s for s in sources(target) if nodes.get(s, {}).get("type") == "run"]

    counts = data["counts"]
    out = [
        f"study: {data['study']}  ({data.get('kind')} · {data.get('modality')} · {data.get('profile')})",
        f"status: {data.get('status')}"
        + (f" — {data['label']}" if data.get("label") else "")
        + (" · quick look" if data.get("rigor") == "quick" else ""),
        "",
        f"{counts['question']} question(s) · {counts['prediction']} prediction(s) · {counts['run']} run(s) · "
        f"{counts['claim']} claim(s) · {counts['decision']} decision(s)"
        + (f" · {counts['probe']} probe(s)" if counts.get("probe") else ""),
        "",
    ]
    placed: set[str] = set()

    def prediction_line(pid: str) -> str:
        node = nodes[pid]
        runs = ", ".join(runs_into(pid)) or "no run yet"
        mark = _VERDICT_MARK.get(str(node.get("verdict")), "·")
        return f"    [{mark}] {pid} {node.get('verdict')}: {node['label']}  ← {runs}"

    def claim_line(cid: str) -> str:
        node = nodes[cid]
        runs = ", ".join(runs_into(cid)) or "no run cited"
        return f"    => {cid} ({node.get('strength')}, {node.get('claim_class')}): {node['label']}  ← {runs}"

    for node in data["nodes"]:
        if node["type"] != "question":
            continue
        out.append(f"{node['id']}  {node['label']}")
        for pid in targets(node["id"], "predicts"):
            out.append(prediction_line(pid))
            placed.add(pid)
        for cid in sources(node["id"], "answers"):
            out.append(claim_line(cid))
            placed.add(cid)
        out.append("")
    loose_predictions = [n["id"] for n in data["nodes"] if n["type"] == "prediction" and n["id"] not in placed]
    loose_claims = [n["id"] for n in data["nodes"] if n["type"] == "claim" and n["id"] not in placed]
    if loose_predictions:
        out.append("predictions not yet tied to a question:")
        out.extend(prediction_line(pid) for pid in loose_predictions)
        out.append("")
    if loose_claims:
        out.append("claims not tied to a question:")
        out.extend(claim_line(cid) for cid in loose_claims)
        out.append("")
    if data["open"]:
        out.append(f"still open ({len(data['open'])}):")
        out.extend(f"  - {item['id']}: {item['message']}" for item in data["open"])
    else:
        out.append("still open: nothing — every prediction is decided and every question has a claim")
    if data.get("leads"):
        out.append("")
        out.append(f"leads for a follow-up study ({len(data['leads'])}):")
        out.extend(f"  - {item['id']}: {item['message']}" for item in data["leads"])
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# HTML — one self-contained file, no script, no network
# --------------------------------------------------------------------------

_COLUMNS = (
    ("question", "Questions"),
    ("prediction", "Predictions"),
    ("run", "Evidence"),
    ("claim", "Claims"),
)
_CSS = """
:root{--bg:#fbfaf7;--ink:#1d1c1a;--mute:#6b6862;--line:#d9d5cc;--card:#fff;
--q:#3b5b8c;--p:#7a5c1e;--r:#4a4a48;--c:#2f6b4f;--bad:#a3392e;--warn:#9a6a12}
@media (prefers-color-scheme:dark){:root{--bg:#161614;--ink:#ecebe6;--mute:#a09c94;--line:#3a3833;
--card:#1f1f1c;--q:#8fb0e0;--p:#d9b56a;--r:#b9b6ae;--c:#7fc7a2;--bad:#e58a7f;--warn:#e0b458}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:15px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1280px;margin:0 auto;padding:28px 16px 48px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:15px;margin:28px 0 8px;letter-spacing:.02em}
.meta{color:var(--mute);margin:0 0 6px}.goal{max-width:70ch;margin:8px 0 0}
.scroll{overflow-x:auto;border:1px solid var(--line);border-radius:10px;background:var(--card)}
svg{display:block}svg text{font:12px ui-sans-serif,system-ui,sans-serif;fill:var(--ink)}
.box{fill:var(--card);stroke-width:1.5}.col{font-weight:600;fill:var(--mute)}
.id{font-weight:700}.edge{fill:none;stroke:var(--line);stroke-width:1.3}
.edge.refuted{stroke:var(--bad)}.edge.supported,.edge.supports,.edge.answers{stroke:var(--c)}
ul{padding-left:20px;margin:6px 0}li{margin:3px 0}code{font:13px ui-monospace,monospace}
.chip{display:inline-block;padding:0 7px;border-radius:9px;border:1px solid var(--line);font-size:12px;color:var(--mute)}
table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:5px 8px;border-top:1px solid var(--line);vertical-align:top}
th{color:var(--mute);font-weight:600;border-top:0}
"""
_STROKE = {"question": "var(--q)", "prediction": "var(--p)", "run": "var(--r)", "claim": "var(--c)"}


def _wrap(text: str, width: int, lines: int) -> list[str]:
    words, out, current = text.split(), [], ""
    for word in words:
        if len(current) + len(word) + 1 > width and current:
            out.append(current)
            current = word
            if len(out) == lines:
                break
        else:
            current = f"{current} {word}".strip()
    if len(out) < lines and current:
        out.append(current)
    if len(out) == lines and " ".join(out) != " ".join(words):
        out[-1] = out[-1][: width - 1].rstrip() + "…"
    return out


def render_html(data: Mapping[str, Any]) -> str:
    """The map as one self-contained HTML page (inline CSS and SVG, no script)."""
    esc = html.escape
    box_w, gap_x, row_h, top = 250, 70, 74, 44
    columns = {kind: [n for n in data["nodes"] if n["type"] == kind] for kind, _ in _COLUMNS}
    position: dict[str, tuple[int, int]] = {}
    for index, (kind, _title) in enumerate(_COLUMNS):
        for row, node in enumerate(columns[kind]):
            position[node["id"]] = (16 + index * (box_w + gap_x), top + row * row_h)
    height = top + max((len(v) for v in columns.values()), default=1) * row_h + 10
    width = 16 * 2 + len(_COLUMNS) * box_w + (len(_COLUMNS) - 1) * gap_x
    parts = [f'<svg viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" '
             f'aria-label="Evidence map of study {esc(data["study"])}">']
    for index, (_kind, title) in enumerate(_COLUMNS):
        parts.append(f'<text class="col" x="{16 + index * (box_w + gap_x)}" y="22">{esc(title)}</text>')
    order = {kind: index for index, (kind, _t) in enumerate(_COLUMNS)}
    kinds = {n["id"]: n["type"] for n in data["nodes"]}
    for edge in data["edges"]:
        a, b = edge["from"], edge["to"]
        if a not in position or b not in position:
            continue
        if order[kinds[a]] > order[kinds[b]]:
            a, b = b, a
        (x1, y1), (x2, y2) = position[a], position[b]
        x1, y1, y2 = x1 + box_w, y1 + 28, y2 + 28
        mid = (x1 + x2) / 2
        parts.append(f'<path class="edge {esc(edge["type"])}" d="M{x1},{y1} C{mid},{y1} {mid},{y2} {x2},{y2}"/>')
    for kind, _title in _COLUMNS:
        for node in columns[kind]:
            x, y = position[node["id"]]
            tag = {
                "prediction": str(node.get("verdict") or ""),
                "run": " · ".join(str(v) for v in (node.get("disposition"), node.get("metric")) if v is not None),
                "claim": str(node.get("strength") or ""),
            }.get(kind, "")
            parts.append(f'<rect class="box" x="{x}" y="{y}" width="{box_w}" height="60" rx="8" stroke="{_STROKE[kind]}"/>')
            parts.append(f'<text x="{x + 10}" y="{y + 18}"><tspan class="id">{esc(node["id"])}</tspan>'
                         f'<tspan dx="8" fill="var(--mute)">{esc(tag)}</tspan></text>')
            for offset, line in enumerate(_wrap(node["label"], 38, 2)):
                parts.append(f'<text x="{x + 10}" y="{y + 35 + offset * 15}">{esc(line)}</text>')
    parts.append("</svg>")
    decisions = [n for n in data["nodes"] if n["type"] == "decision"]
    probes = [n for n in data["nodes"] if n["type"] == "probe"]
    counts = data["counts"]
    body = [
        f"<h1>{esc(data['study'])}</h1>",
        f'<p class="meta">{esc(str(data.get("kind")))} · {esc(str(data.get("modality")))} · '
        f'{esc(str(data.get("profile")))} — status: {esc(str(data.get("status")))}'
        + (f" ({esc(str(data['label']))})" if data.get("label") else "")
        + (" · quick look" if data.get("rigor") == "quick" else "") + "</p>",
        f'<p class="goal">{esc(data.get("goal") or "")}</p>',
        f'<h2>The map — {counts["question"]} questions, {counts["prediction"]} predictions, '
        f'{counts["run"]} runs, {counts["claim"]} claims</h2>',
        '<div class="scroll">' + "".join(parts) + "</div>",
        "<h2>Still open</h2>",
    ]
    if data["open"]:
        body.append("<ul>" + "".join(
            f'<li><code>{esc(i["id"])}</code> — {esc(i["message"])} <span class="chip">{esc(i["kind"])}</span></li>'
            for i in data["open"]) + "</ul>")
    else:
        body.append("<p>Nothing: every prediction is decided and every question has a claim.</p>")
    if data.get("leads"):
        body.append("<h2>Leads for a follow-up study</h2><ul>" + "".join(
            f'<li><code>{esc(i["id"])}</code> — {esc(i["message"])} <span class="chip">{esc(i["kind"])}</span></li>'
            for i in data["leads"]) + "</ul>")
    if decisions:
        body.append("<h2>Decisions along the way</h2><table><tr><th>When</th><th>Decision</th></tr>" + "".join(
            f'<tr><td>{esc(str(d.get("date")))}</td><td>{esc(d["label"])}</td></tr>' for d in decisions) + "</table>")
    if probes:
        body.append("<h2>Exploratory probes (never evidence for a claim)</h2><ul>" + "".join(
            f'<li><code>{esc(p["id"])}</code> — {esc(p["label"])}</li>' for p in probes) + "</ul>")
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{esc(data['study'])} — evidence map</title><style>{_CSS}</style></head>"
        f"<body><main>{''.join(body)}</main></body></html>\n"
    )


def write_html(study_dir: str | Path, out: str | Path | None = None) -> Path:
    """Write the HTML map and return its path.

    The default is ``./<study>-map.html`` in the working directory — outside the
    study, like ``klein notebook``: a derived reading copy must not leave an
    untracked file that the next ``run-one`` would refuse as a dirty tree.
    """
    study = Path(study_dir)
    target = Path(out) if out is not None else Path.cwd() / f"{study.resolve().name}-map.html"
    if target.exists() and target.is_dir():
        raise WorkflowError(f"{target} is a directory")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_html(build_map(study)), encoding="utf-8")
    return target
