"""``klein mcp`` — a read-only Model Context Protocol server over stdio (Klein 2.3).

Any MCP client — a Claude Science "Local command" connector, Claude Code,
Cursor — can ask a Klein repository where a study stands, what to do next and
whether it verifies, without a shell:

    klein mcp --root /path/to/klein-auto-research

Tools (every one read-only, annotated ``readOnlyHint: true``):

``list_studies`` · ``next`` · ``status`` · ``doctor`` · ``preflight`` ·
``verify`` (never writes a receipt) · ``predictions`` · ``claims_verify`` ·
``explain`` (a stage's protocol text).

There are deliberately **no gate, run, claims-writing or finalize tools**: a
gate acknowledgement belongs to a person and must never be clicked through by a
model, and an experiment outlives an MCP call's timeout.  Writes stay in the
shell, behind the host's own permission prompts.

The server is a small stdlib implementation of the stdio transport
(newline-delimited JSON-RPC 2.0: ``initialize``, ``ping``, ``tools/list``,
``tools/call``) so it adds no dependency to the engine.  Tool code runs with
``sys.stdout`` redirected to stderr, so nothing a check prints can corrupt the
protocol stream.
"""

from __future__ import annotations

import contextlib
import json
import sys
import traceback
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import IO, Any

from . import __version__
from .errors import WorkflowError

__all__ = ["PROTOCOL_VERSIONS", "KleinMCP", "serve"]

#: Newest first; an unknown requested version is answered with the newest.
PROTOCOL_VERSIONS = ("2025-11-25", "2025-06-18", "2025-03-26", "2024-11-05")

STAGE_PROTOCOLS = {
    "scaffold": "defaults-and-scaffolding.md",
    "consult": "consult-protocol.md",
    "inquiry": "inquiry-model.md",
    "data": "data-gate-protocol.md",
    "method": "method-gate-protocol.md",
    "experiment": "registered-mode.md",
    "sweep": "sweep-rules.md",
    "replicate": "replication-protocol.md",
    "calls": "model-calls-protocol.md",
    "compute": "compute-and-devices.md",
    "synthesize": "synthesis-protocol.md",
    "claims": "claims-protocol.md",
    "referee": "referee-protocol.md",
    "tutorial": "tutorial-spec.md",
    "phase": "phase-ritual.md",
    "war-stories": "war-stories.md",
}

_STUDY = {
    "type": "object",
    "properties": {
        "study": {
            "type": "string",
            "description": "study id (`NN-slug`) or path relative to the repository root",
        }
    },
    "required": ["study"],
    "additionalProperties": False,
}

TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_studies",
        "description": "List the studies under studies/ with their current stage and next action.",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "next",
        "description": "The ONE next action a study needs: stage, what is done, the exact command, "
        "the protocol section and why. Read-only (`klein next`).",
        "inputSchema": _STUDY,
    },
    {
        "name": "status",
        "description": "Machine-readable study status: gates, frontier per track, runs, predictions "
        "(`klein status --json`).",
        "inputSchema": _STUDY,
    },
    {
        "name": "doctor",
        "description": "What this machine can run: python, uv, git, extras, renderer, device, data hub; "
        "with a study, whether its pinned sources resolve. Never fetches (`klein doctor`).",
        "inputSchema": {
            "type": "object",
            "properties": {"study": _STUDY["properties"]["study"]},
            "additionalProperties": False,
        },
    },
    {
        "name": "preflight",
        "description": "The pre-run checks `klein run-one` enforces (gates, fingerprints, ledger, "
        "contract), reported without the clean-tree and branch requirements.",
        "inputSchema": _STUDY,
    },
    {
        "name": "verify",
        "description": "The full `klein verify` audit, without writing or committing a receipt.",
        "inputSchema": _STUDY,
    },
    {
        "name": "predictions",
        "description": "The registered predictions ledger with each verdict (`klein predict list`).",
        "inputSchema": _STUDY,
    },
    {
        "name": "claims_verify",
        "description": "The claims law over claims.lock (`klein claims verify`); empty before SYNTHESIZE.",
        "inputSchema": _STUDY,
    },
    {
        "name": "explain",
        "description": "Return a stage's protocol (the source of truth) as markdown. Topics: "
        + ", ".join(sorted(STAGE_PROTOCOLS)),
        "inputSchema": {
            "type": "object",
            "properties": {"topic": {"type": "string", "enum": sorted(STAGE_PROTOCOLS)}},
            "required": ["topic"],
            "additionalProperties": False,
        },
    },
]
for _tool in TOOLS:
    _tool["annotations"] = {"readOnlyHint": True, "destructiveHint": False, "openWorldHint": False}

INSTRUCTIONS = (
    "Klein keeps a notarized research ledger. These tools only read it. Start with `next` for a "
    "study; follow the command it names in a shell. Gate acknowledgements (consult, data, method, "
    "phase, referee) belong to the person — ask them; never record one on their behalf."
)


def _checks(rows: Any) -> dict[str, Any]:
    items = [{"name": c.name, "ok": bool(c.ok), "message": c.message} for c in rows]
    return {"ok": all(item["ok"] for item in items), "checks": items}


def _checks_text(result: Mapping[str, Any]) -> str:
    lines = [f"{'PASS' if result['ok'] else 'FAIL'} ({len(result['checks'])} checks)"]
    for item in result["checks"]:
        lines.append(f"[{'ok' if item['ok'] else 'FAIL'}] {item['name']}: {item['message']}")
    return "\n".join(lines)


class KleinMCP:
    """The tool implementations, bound to one repository root."""

    def __init__(self, root: str | Path = ".") -> None:
        self.root = Path(root).resolve()

    # ----------------------------------------------------------- resolution
    def study(self, value: Any) -> Path:
        if not isinstance(value, str) or not value.strip():
            raise WorkflowError("`study` is required: a study id like 23-lalonde or a path")
        raw = value.strip()
        candidates = [self.root / raw, self.root / "studies" / raw]
        for candidate in candidates:
            path = candidate.resolve()
            try:
                path.relative_to(self.root)
            except ValueError:
                continue
            if (path / "study.yaml").is_file():
                return path
        raise WorkflowError(f"no study {raw!r} under {self.root}")

    # ---------------------------------------------------------------- tools
    def list_studies(self, _: Mapping[str, Any]) -> tuple[str, Any]:
        from .next_step import next_step

        rows = []
        for path in sorted((self.root / "studies").glob("*/study.yaml")):
            study = path.parent
            try:
                result = next_step(study)
                nxt = result.get("next") or {}
                rows.append({"study": study.name, "stage": nxt.get("stage"), "next": nxt.get("action")})
            except (WorkflowError, OSError, ValueError) as exc:
                rows.append({"study": study.name, "stage": None, "next": f"unreadable: {exc}"})
        text = "\n".join(f"{r['study']}: {r['stage']} — {r['next']}" for r in rows) or "no studies"
        return text, {"studies": rows}

    def next(self, args: Mapping[str, Any]) -> tuple[str, Any]:
        from .next_step import format_next, next_step

        result = next_step(self.study(args.get("study")))
        return format_next(result), result

    def status(self, args: Mapping[str, Any]) -> tuple[str, Any]:
        from .next_step import status_data

        result = status_data(self.study(args.get("study")))
        return json.dumps(result, indent=2, default=str), result

    def doctor(self, args: Mapping[str, Any]) -> tuple[str, Any]:
        from .doctor import format_report, run_doctor

        study = self.study(args["study"]) if args.get("study") else None
        report = run_doctor(study)
        return format_report(report), report

    def preflight(self, args: Mapping[str, Any]) -> tuple[str, Any]:
        from .checks import preflight_checks

        result = _checks(
            preflight_checks(
                self.study(args.get("study")), require_clean=False, require_branch=False, require_local=False
            )
        )
        return _checks_text(result), result

    def verify(self, args: Mapping[str, Any]) -> tuple[str, Any]:
        from .checks import verify_study

        result = _checks(verify_study(self.study(args.get("study")), receipt=False))
        return _checks_text(result), result

    def predictions(self, args: Mapping[str, Any]) -> tuple[str, Any]:
        from .checks import _state_or_empty
        from .contract import load_contract
        from .predictions import format_ledger, ledger

        study = self.study(args.get("study"))
        contract = load_contract(study)
        rows = ledger(contract, _state_or_empty(study, contract))
        return format_ledger(rows), {"predictions": rows}

    def claims_verify(self, args: Mapping[str, Any]) -> tuple[str, Any]:
        from .claims import claims_checks
        from .contract import load_contract, schema_version

        study = self.study(args.get("study"))
        result = _checks(claims_checks(study, schema_version(load_contract(study))))
        if not result["checks"]:
            return "no claims.lock yet — the claims law starts at SYNTHESIZE", result
        return _checks_text(result), result

    def explain(self, args: Mapping[str, Any]) -> tuple[str, Any]:
        topic = str(args.get("topic") or "")
        if topic not in STAGE_PROTOCOLS:
            raise WorkflowError(f"unknown topic {topic!r}; one of: {', '.join(sorted(STAGE_PROTOCOLS))}")
        path = self.root / ".claude" / "skills" / "klein" / "references" / STAGE_PROTOCOLS[topic]
        if not path.is_file():
            raise WorkflowError(f"{path} not found — run the server with --root at a Klein repository")
        text = path.read_text(encoding="utf-8")
        return text, {"topic": topic, "path": str(path.relative_to(self.root))}

    # ------------------------------------------------------------- dispatch
    def call(self, name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        handler: Callable[[Mapping[str, Any]], tuple[str, Any]] | None = (
            getattr(self, name, None) if name in {t["name"] for t in TOOLS} else None
        )
        if handler is None:
            return {"content": [{"type": "text", "text": f"unknown tool {name!r}"}], "isError": True}
        try:
            with contextlib.redirect_stdout(sys.stderr):
                text, structured = handler(arguments or {})
        except (WorkflowError, FileNotFoundError, KeyError, ValueError) as exc:
            return {"content": [{"type": "text", "text": f"klein: {exc}"}], "isError": True}
        except Exception as exc:  # noqa: BLE001 — a tool failure must never kill the server
            traceback.print_exc(file=sys.stderr)
            return {"content": [{"type": "text", "text": f"klein: internal error: {exc}"}], "isError": True}
        result: dict[str, Any] = {"content": [{"type": "text", "text": text}], "isError": False}
        structured = json.loads(json.dumps(structured, default=str))
        if isinstance(structured, dict):
            result["structuredContent"] = structured
        return result

    def handle(self, message: Mapping[str, Any]) -> dict[str, Any] | None:
        """One JSON-RPC message in, one response (or None for a notification) out."""
        method = message.get("method")
        msg_id = message.get("id")
        params = message.get("params") or {}
        if msg_id is None:  # notification (initialized, cancelled, …): no reply
            return None

        def ok(result: Any) -> dict[str, Any]:
            return {"jsonrpc": "2.0", "id": msg_id, "result": result}

        def error(code: int, text: str) -> dict[str, Any]:
            return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": text}}

        if method == "initialize":
            requested = params.get("protocolVersion")
            version = requested if requested in PROTOCOL_VERSIONS else PROTOCOL_VERSIONS[0]
            return ok(
                {
                    "protocolVersion": version,
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "klein", "title": "Klein (read-only)", "version": __version__},
                    "instructions": INSTRUCTIONS,
                }
            )
        if method == "ping":
            return ok({})
        if method == "tools/list":
            return ok({"tools": TOOLS})
        if method == "tools/call":
            name = params.get("name")
            if not isinstance(name, str):
                return error(-32602, "tools/call needs a tool name")
            return ok(self.call(name, params.get("arguments") or {}))
        return error(-32601, f"method not found: {method}")


def serve(root: str | Path = ".", *, stdin: IO[str] | None = None, stdout: IO[str] | None = None) -> int:
    """Run the stdio loop until EOF."""
    reader = stdin or sys.stdin
    writer = stdout or sys.stdout
    server = KleinMCP(root)
    for line in reader:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except ValueError:
            reply: Any = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "parse error"}}
        else:
            if isinstance(message, list):  # a batch (2025-03-26)
                replies = [r for r in (server.handle(m) for m in message if isinstance(m, Mapping)) if r]
                reply = replies or None
            elif isinstance(message, Mapping):
                reply = server.handle(message)
            else:
                reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "invalid request"}}
        if reply is not None:
            writer.write(json.dumps(reply, ensure_ascii=False) + "\n")
            writer.flush()
    return 0
