"""`klein doctor` — environment and (optionally) study source-readiness report.

Normative text: `.claude/skills/klein/references/data-sources.md` (the
`klein doctor` paragraph: "python, uv and git versions; which extras are
installed; the tutorial renderer dependencies; the device `pick_device` would
choose; whether `$DATA_HUB` is set and importable; and, with `--study`,
whether that study's source tag resolves on this machine and what the pin
says") and `references/compute-and-devices.md` (the device choice it echoes).

Every probe here is a version query, an import-spec lookup (or, for
`$DATA_HUB`, a real import of LOCAL code only), or a filesystem stat — NEVER a
network request, NEVER a study mutation. `run_doctor` is pure and returns a
plain, JSON-friendly dict (`klein doctor --json` serializes it directly);
`format_report` renders the same dict as the text `klein doctor` prints by
default. The CLI (`cli_doctor.py`) owns the `--strict` exit-code decision —
this module always reports honestly (`ok=False` when something genuinely
is not ready) without deciding whether that should fail a process.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from . import sources

#: extra name -> representative module(s) to probe (kept in sync with
#: `[project.optional-dependencies]` by hand; doctor does not parse
#: pyproject.toml itself so it never needs the packaging machinery).
_EXTRA_PROBES: dict[str, tuple[str, ...]] = {
    "encoders": ("category_encoders",),
    "parquet": ("pyarrow",),
    "gbdt": ("lightgbm", "xgboost", "catboost"),
    "deep": ("torch",),
    "foundation": ("tabpfn",),
}

#: the TUTORIAL stage's build-time renderer — main dependencies today, but
#: still worth probing (an editable/partial install can still be missing one).
_RENDERER_MODULES = ("pygments", "ziamath", "latex2mathml")


#: ``klein doctor --host`` (Klein 2.3): the driving host's own constraints.
HOSTS = ("claude-science", "claude-code", "generic")


def run_doctor(study_dir: Path | None = None, *, host: str | None = None) -> dict[str, Any]:
    """The full report: environment checks, plus study-source checks with `study_dir`.

    ``host`` (Klein 2.3) appends that host's probes — still read-only, still no
    network: a read-only uv environment, a missing uv, GPUs, the skill and agents
    a host loads, and the read-only MCP server.
    """
    checks: list[dict[str, Any]] = [
        _probe_python(),
        _probe_uv(),
        _probe_git(),
        *_probe_extras(),
        _probe_renderer(),
        _probe_device(),
        _probe_data_hub(),
    ]
    if study_dir is not None:
        checks.extend(_probe_study_source(Path(study_dir)))
    if host is not None:
        checks.extend(_probe_host(host, Path(study_dir) if study_dir is not None else None))
    return {"ok": all(check["ok"] for check in checks), "checks": checks}


def format_report(report: dict[str, Any]) -> str:
    """Render a `run_doctor()` report the way `klein doctor` prints it by default."""
    lines: list[str] = []
    not_ok = 0
    for check in report["checks"]:
        marker = "OK" if check["ok"] else "WARN"
        not_ok += not check["ok"]
        lines.append(f"[{marker}] {check['name']}: {check['message']}")
    lines.append(
        f"summary: {len(report['checks'])} checks, {not_ok} not-ok "
        "(never fetches; exit code reflects --strict only)"
    )
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# Individual probes
# --------------------------------------------------------------------------


def _probe_python() -> dict[str, Any]:
    ok = sys.version_info >= (3, 11)
    suffix = "" if ok else " — this project requires-python >=3.11"
    return {
        "name": "python",
        "ok": ok,
        "message": f"{platform.python_version()} at {sys.executable}{suffix}",
    }


def _probe_cli_tool(name: str, command: list[str]) -> dict[str, Any]:
    exe = shutil.which(command[0])
    if exe is None:
        return {"name": name, "ok": False, "message": f"{command[0]!r} not found on PATH"}
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    except OSError as exc:
        return {"name": name, "ok": False, "message": f"found at {exe} but failed to run: {exc}"}
    output = (result.stdout or result.stderr or "(no output)").strip().splitlines()
    version = output[0] if output else "(no output)"
    return {"name": name, "ok": result.returncode == 0, "message": f"{version} ({exe})"}


def _probe_uv() -> dict[str, Any]:
    return _probe_cli_tool("uv", ["uv", "--version"])


def _probe_git() -> dict[str, Any]:
    return _probe_cli_tool("git", ["git", "--version"])


def _probe_extras() -> list[dict[str, Any]]:
    checks = []
    for extra, modules in _EXTRA_PROBES.items():
        missing = [module for module in modules if importlib.util.find_spec(module) is None]
        ok = not missing
        message = (
            "installed"
            if ok
            else f"missing {', '.join(missing)} — uv sync --locked --extra {extra}"
        )
        checks.append({"name": f"extra: {extra}", "ok": ok, "message": message})
    return checks


def _probe_renderer() -> dict[str, Any]:
    missing = [module for module in _RENDERER_MODULES if importlib.util.find_spec(module) is None]
    ok = not missing
    message = (
        f"installed ({', '.join(_RENDERER_MODULES)})"
        if ok
        else f"missing {', '.join(missing)} — the TUTORIAL stage cannot build report/index.html"
    )
    return {"name": "tutorial renderer", "ok": ok, "message": message}


def _probe_device() -> dict[str, Any]:
    if importlib.util.find_spec("torch") is None:
        return {
            "name": "device",
            "ok": True,
            "message": "torch not installed (extra 'deep') — pick_device() unavailable",
        }
    from .torch_device import device_name, pick_device

    try:
        device = pick_device()
    except Exception as exc:  # torch's own backends can raise oddly on exotic builds
        return {"name": "device", "ok": False, "message": f"pick_device() raised: {exc}"}
    override = os.environ.get("KLEIN_DEVICE")
    note = f" (KLEIN_DEVICE={override!r} override)" if override else " (auto: mps -> cuda -> cpu)"
    return {"name": "device", "ok": True, "message": f"{device_name(device)}{note}"}


def _probe_data_hub() -> dict[str, Any]:
    hub_root = os.environ.get("DATA_HUB")
    if not hub_root:
        return {
            "name": "DATA_HUB",
            "ok": True,
            "message": "not set — bundled datasets and hub: tags fall back to datasets/",
        }
    hub_path = Path(hub_root)
    if not hub_path.is_dir():
        return {
            "name": "DATA_HUB",
            "ok": False,
            "message": f"set to {hub_root!r} but that is not a directory",
        }
    if str(hub_path) not in sys.path:
        sys.path.insert(0, str(hub_path))
    try:
        importlib.import_module("loaders.python.hub")
    except ImportError as exc:
        return {
            "name": "DATA_HUB",
            "ok": True,
            "message": (
                f"{hub_path} exists but loaders.python.hub is not importable ({exc}) — "
                "hub: tags fall back to a plain <name>/*.csv directory, then the bundled copy"
            ),
        }
    return {"name": "DATA_HUB", "ok": True, "message": f"{hub_path}; loaders.python.hub is importable"}


def _probe_study_source(study_dir: Path) -> list[dict[str, Any]]:
    contract_path = study_dir / "study.yaml"
    if not contract_path.is_file():
        return [{"name": "study contract", "ok": False, "message": f"no study.yaml at {study_dir}"}]
    try:
        contract = yaml.safe_load(contract_path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        return [{"name": "study contract", "ok": False, "message": f"study.yaml does not parse: {exc}"}]
    data_block = contract.get("data") if isinstance(contract, dict) else None
    source = data_block.get("source") if isinstance(data_block, dict) else None
    if not source:
        return [{"name": "data source", "ok": True, "message": "no data.source declared in study.yaml"}]
    entries = [(source, data_block.get("sha256") if isinstance(data_block, dict) else None)]
    inputs = data_block.get("inputs") if isinstance(data_block, dict) else None
    for entry in inputs if isinstance(inputs, list) else []:
        if isinstance(entry, dict) and entry.get("source"):
            entries.append((entry["source"], entry.get("sha256")))
    checks: list[dict[str, Any]] = []
    for tag, expected_sha256 in entries:
        report = sources.describe(tag, study_dir=study_dir, expected_sha256=expected_sha256)
        pin_note = f"; pin present={report['pin_present']}" if report["pin_required"] else ""
        scheme = report["scheme"] or "unparsed"
        checks.append(
            {
                "name": "data source",
                "ok": bool(report["resolvable"]),
                "message": f"{tag!r} ({scheme}): {report['detail']}{pin_note}",
            }
        )
    return checks


# --------------------------------------------------------------------------
# Host probes (Klein 2.3) — `klein doctor --host claude-science|claude-code|generic`
# --------------------------------------------------------------------------


def _repo_root(start: Path) -> Path | None:
    for candidate in (start, *start.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _probe_uv_environment(repo: Path | None) -> dict[str, Any]:
    override = os.environ.get("UV_PROJECT_ENVIRONMENT")
    if override:
        target = Path(override).expanduser()
        writable = os.access(target if target.exists() else target.parent, os.W_OK)
        return {
            "name": "uv environment",
            "ok": writable,
            "message": f"UV_PROJECT_ENVIRONMENT={override}"
            + ("" if writable else " — not writable; point it at a directory you own"),
        }
    if shutil.which("uv") is None:
        return {
            "name": "uv environment",
            "ok": True,
            "message": "no uv on PATH — scaffold with `klein new … --runner python` and install the "
            "engine from PyPI into the host's environment (integrations/claude-science/README.md §1)",
        }
    venv = (repo or Path.cwd()) / ".venv"
    if venv.exists() and not os.access(venv, os.W_OK):
        return {
            "name": "uv environment",
            "ok": False,
            "message": f"{venv} is read-only to this process — export "
            "UV_PROJECT_ENVIRONMENT=$HOME/.cache/klein-venv, then `uv sync --locked`",
        }
    return {"name": "uv environment", "ok": True, "message": f"{venv} {'writable' if venv.exists() else 'not created yet (uv sync --locked)'}"}


def _probe_gpu() -> dict[str, Any]:
    exe = shutil.which("nvidia-smi")
    if exe is None:
        return {"name": "gpu", "ok": True, "message": "no nvidia-smi — CPU here; use a detached run for GPU work"}
    try:
        result = subprocess.run([exe, "-L"], capture_output=True, text=True, timeout=10, check=False)
    except OSError as exc:
        return {"name": "gpu", "ok": True, "message": f"nvidia-smi failed to run: {exc}"}
    gpus = [line for line in result.stdout.splitlines() if line.strip()]
    return {"name": "gpu", "ok": True, "message": "; ".join(gpus) if gpus else "nvidia-smi lists no GPU"}


def _probe_skill(repo: Path | None) -> dict[str, Any]:
    root = repo or Path.cwd()
    skill = root / ".claude" / "skills" / "klein" / "SKILL.md"
    if skill.is_file():
        return {"name": "klein skill", "ok": True, "message": f"{skill.relative_to(root)} present"}
    return {
        "name": "klein skill",
        "ok": False,
        "message": "no .claude/skills/klein/SKILL.md here — import the skill from GitHub, or run from a clone",
    }


def _probe_host(host: str, study_dir: Path | None) -> list[dict[str, Any]]:
    if host not in HOSTS:
        return [{"name": "host", "ok": False, "message": f"unknown host {host!r}; one of {', '.join(HOSTS)}"}]
    repo = _repo_root((study_dir or Path.cwd()).resolve())
    checks: list[dict[str, Any]] = [
        {"name": "host", "ok": True, "message": host},
        {
            "name": "mcp server",
            "ok": True,
            "message": "built in (stdlib, read-only): `klein mcp --root "
            f"{repo or '<repository>'}`",
        },
        _probe_gpu(),
    ]
    if host == "claude-science":
        checks.append(_probe_uv_environment(repo))
        checks.append(_probe_skill(repo))
        kit = (repo or Path.cwd()) / "integrations" / "claude-science" / "README.md"
        checks.append(
            {
                "name": "claude-science kit",
                "ok": kit.is_file(),
                "message": str(kit.relative_to(repo)) if kit.is_file() and repo else "integrations/claude-science/ not found",
            }
        )
    elif host == "claude-code":
        checks.append(_probe_skill(repo))
        agents = sorted(p.stem for p in ((repo or Path.cwd()) / ".claude" / "agents").glob("klein-*.md"))
        checks.append(
            {
                "name": "klein agents",
                "ok": bool(agents),
                "message": ", ".join(agents) if agents else "no .claude/agents/klein-*.md — roles run solo",
            }
        )
    return checks
