"""The stable Python surface of Klein, for a host that embeds it.

Every function here returns one **envelope** — a plain, JSON-able dict with a
format version — and never prints.  ``klein <verb> --json`` prints the same
envelope, and the read-only MCP server (``klein mcp``) serves the same ``data``,
so a host has three equivalent seams and one shape to parse::

    {
      "klein": "3.0.0",          # engine version
      "format": 1,               # envelope format; bumped only on a breaking change
      "verb": "verify",
      "ok": true,                # the verb succeeded (exit code 0)
      "data": {...},             # verb-specific, documented per function below
      "problems": [              # why not, or what to look at; empty when clean
        {"level": "error" | "warn", "code": "refused" | "check" | ..., "message": "..."}
      ]
    }

Reading is free and safe (``next_action``, ``status``, ``preflight``, ``verify``
with ``receipt=False``, ``claims_verify``, ``predictions``, ``study_map``,
``explain``).  Writing goes through the same notary the command line uses
(``run_one``, ``sealed_dry_run``, ``gate``, ``finalize``, ``probe``): nothing here
bypasses a gate, and a refusal comes back as ``ok: false`` with the reason, never
as a traceback.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

from . import __version__
from .errors import WorkflowError

__all__ = [
    "FORMAT",
    "checks_data",
    "claims_verify",
    "emit",
    "emit_checks",
    "envelope",
    "explain",
    "finalize",
    "gate",
    "next_action",
    "predictions",
    "preflight",
    "probe",
    "refusal",
    "run_one",
    "sealed_dry_run",
    "status",
    "study_map",
    "verify",
]

#: The envelope format.  A field is only ever ADDED within a format.
FORMAT = 1

#: Exceptions that mean "the engine refused", as opposed to a bug.
REFUSALS: tuple[type[Exception], ...] = (WorkflowError, FileExistsError, ValueError)


def envelope(
    verb: str,
    data: Mapping[str, Any] | None = None,
    *,
    ok: bool = True,
    problems: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    return {
        "klein": __version__,
        "format": FORMAT,
        "verb": verb,
        "ok": bool(ok),
        "data": dict(data or {}),
        "problems": [dict(problem) for problem in problems],
    }


def refusal(verb: str, exc: BaseException, *, data: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """The envelope of a verb the engine refused."""
    return envelope(
        verb,
        data,
        ok=False,
        problems=[{"level": "error", "code": "refused", "message": str(exc)}],
    )


def _guard(verb: str, body: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Run one API call the way the command line runs a verb, minus the printing.

    Anything the engine prints while it works (a notice that an unrelated edit was
    left uncommitted, a warning) comes back as a ``warn`` problem instead of
    reaching the host's standard output.  The probe variables are cleared for the
    duration: set in THIS process they would empty the sealed partition a gate
    fingerprints (they belong to a probe's child only).
    """
    import contextlib
    import io
    import os

    from .probe import PROBE_ENV_KEYS

    saved = {key: os.environ.pop(key) for key in PROBE_ENV_KEYS if key in os.environ}
    printed = io.StringIO()
    try:
        with contextlib.redirect_stdout(printed):
            reply = body()
    except REFUSALS as exc:
        reply = refusal(verb, exc)
    finally:
        os.environ.update(saved)
    for line in printed.getvalue().splitlines():
        if line.strip():
            reply["problems"].append({"level": "warn", "code": "notice", "message": line.strip()})
    return reply


# --------------------------------------------------------------------------
# The command line's structured channel
# --------------------------------------------------------------------------

#: When ``klein <verb> --json`` runs, the verb's handler leaves its structured
#: result here (``emit``) and ``kleinlib.cli`` wraps it in the envelope.  None
#: outside ``--json`` mode, so ``emit`` costs a text-mode run nothing.
_SINK: dict[str, Any] | None = None


def emit(data: Mapping[str, Any]) -> None:
    """Hand the running verb's structured result to ``--json`` mode (a no-op otherwise)."""
    if _SINK is not None:
        _SINK.update(data)


def emit_checks(checks: Sequence[Any]) -> None:
    emit(checks_data(checks))


def checks_data(checks: Sequence[Any]) -> dict[str, Any]:
    """A list of ``Check`` as data: one row per check and a summary."""
    rows = []
    for check in checks:
        message = str(check.message)
        level = "fail" if not check.ok else ("warn" if message.startswith("[WARN]") else "ok")
        rows.append({"name": check.name, "ok": bool(check.ok), "level": level, "message": message})
    return {
        "checks": rows,
        "summary": {
            "total": len(rows),
            "failed": sum(row["level"] == "fail" for row in rows),
            "warned": sum(row["level"] == "warn" for row in rows),
        },
    }


def _checks_envelope(verb: str, checks: Sequence[Any]) -> dict[str, Any]:
    data = checks_data(checks)
    problems = [
        {
            "level": "error" if row["level"] == "fail" else "warn",
            "code": "check",
            "name": row["name"],
            "message": row["message"],
        }
        for row in data["checks"]
        if row["level"] != "ok"
    ]
    return envelope(verb, data, ok=data["summary"]["failed"] == 0, problems=problems)


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------


def next_action(study: str | Path) -> dict[str, Any]:
    """``klein next``: the one action this study needs.  ``data`` is :func:`kleinlib.next_step.next_step`."""
    from .next_step import next_step

    return _guard("next", lambda: envelope("next", next_step(Path(study))))


def status(study: str | Path) -> dict[str, Any]:
    """``klein status``: gates, tracks, incumbents, predictions and the next action."""
    from .next_step import status_data

    return _guard("status", lambda: envelope("status", status_data(Path(study))))


def preflight(study: str | Path, *, allow_dirty: bool = False) -> dict[str, Any]:
    """``klein preflight``: would a run be admitted right now?"""
    from .checks import preflight_checks

    return _guard(
        "preflight",
        lambda: _checks_envelope(
            "preflight", preflight_checks(Path(study), require_clean=not allow_dirty)
        ),
    )


def verify(
    study: str | Path,
    *,
    receipt: bool = False,
    strict: bool = False,
    require_local: bool = False,
) -> dict[str, Any]:
    """``klein verify``: the whole audit.

    ``receipt=False`` (the default HERE, unlike the command line) only reads; pass
    ``True`` to write and commit ``verify_receipt.json`` as the study's owner.
    """
    from .checks import verify_study

    return _guard(
        "verify",
        lambda: _checks_envelope(
            "verify",
            verify_study(Path(study), receipt=receipt, strict=strict, require_local=require_local),
        ),
    )


def claims_verify(study: str | Path, *, strict: bool = False) -> dict[str, Any]:
    """``klein claims verify``: the seven-check claims law over ``claims.lock``."""
    from .claims import verify_lock

    return _guard(
        "claims verify",
        lambda: _checks_envelope("claims verify", verify_lock(Path(study), strict=strict)),
    )


def predictions(study: str | Path) -> dict[str, Any]:
    """``klein predict list``: every registered prediction and its verdict."""
    from .checks import _state_or_empty
    from .contract import load_contract
    from .predictions import counts as prediction_counts
    from .predictions import ledger as prediction_ledger

    def body() -> dict[str, Any]:
        contract = load_contract(Path(study))
        rows = prediction_ledger(contract, _state_or_empty(Path(study), contract))
        return envelope("predict list", {"predictions": rows, "counts": prediction_counts(rows)})

    return _guard("predict list", body)


def study_map(study: str | Path) -> dict[str, Any]:
    """``klein map``: question → predictions → evidence → claims → decisions, as a graph."""
    from .study_map import build_map

    return _guard("map", lambda: envelope("map", build_map(Path(study))))


def explain(topic: str) -> dict[str, Any]:
    """``klein explain``: a protocol or a glossary term, from the installed package."""
    from .resources import explain_topic

    return _guard("explain", lambda: envelope("explain", explain_topic(topic)))


# --------------------------------------------------------------------------
# Writing — through the notary
# --------------------------------------------------------------------------


def run_summary(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """The fields of a run manifest a host usually needs (the full manifest is on disk)."""
    keys = (
        "experiment",
        "track",
        "disposition",
        "primary_metric",
        "metric_name",
        "evaluation_kind",
        "exit_code",
        "candidate_commit",
        "base_commit",
        "incumbent",
        "description",
    )
    summary = {key: manifest.get(key) for key in keys if key in manifest}
    for key in ("predictions", "tests"):
        if key in manifest:
            summary[key] = manifest[key]
    return summary


def run_one(
    study: str | Path,
    *,
    description: str,
    track: str | None = None,
    tests: str | Sequence[str] | None = None,
    final_test: bool = False,
    allow_rerun: bool = False,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    """``klein run-one``: one candidate transaction.  ``ok`` is false for a crash.

    The caller edits the mutable surface first; this commits the candidate, runs
    it, decides by the contract's arithmetic, and files the evidence — exactly as
    the command line does, without echoing the child's output.
    """
    from .workflow import run_one as _run_one

    def body() -> dict[str, Any]:
        manifest = _run_one(
            Path(study),
            track=track,
            description=description,
            timeout_seconds=timeout_seconds,
            final_test=final_test,
            echo=False,
            allow_rerun=allow_rerun,
            tests=tests,
        )
        return envelope(
            "run-one", {"run": run_summary(manifest)}, ok=manifest.get("disposition") != "crash"
        )

    return _guard("run-one", body)


def sealed_dry_run(
    study: str | Path,
    *,
    track: str | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    """``klein run-one --final-test --dry-run``: rehearse the sealed run; spends nothing.

    Mandatory before ``run_one(final_test=True)``: the rehearsal runs the real
    entrypoint on development data and proves it would have reached the sealed
    read.  ``ok`` is true only when it did.
    """
    from .workflow import sealed_dry_run as _sealed_dry_run

    def body() -> dict[str, Any]:
        code = _sealed_dry_run(Path(study), track=track, timeout_seconds=timeout_seconds, echo=False)
        return envelope("run-one --final-test --dry-run", {"exit_code": code}, ok=code == 0)

    return _guard("run-one --final-test --dry-run", body)


def gate(
    study: str | Path,
    name: str,
    *,
    acknowledged_by: str,
    note: str = "",
    override_reason: str | None = None,
    phase: str | None = None,
) -> dict[str, Any]:
    """``klein gate record|override``.  ``acknowledged_by`` must name who decided — a
    host must never acknowledge a gate on a person's behalf without their say."""
    from .state import record_gate

    def body() -> dict[str, Any]:
        state = record_gate(
            Path(study),
            name,
            acknowledged_by=acknowledged_by,
            note=note,
            override_reason=override_reason,
            phase=phase,
        )
        return envelope(
            "gate",
            {
                "gate": name,
                "status": "overridden" if override_reason is not None else "recorded",
                "gates": {
                    key: value.get("status")
                    for key, value in (state.get("gates") or {}).items()
                    if isinstance(value, Mapping)
                },
            },
        )

    return _guard("gate", body)


def finalize(
    study: str | Path,
    *,
    allow_exploratory: bool = False,
    allow_open_predictions: bool = False,
    no_referee: bool = False,
    reason: str = "",
) -> dict[str, Any]:
    """``klein finalize``: close the study; ``data.label`` is confirmed / exploratory."""
    from .workflow import finalize as _finalize

    def body() -> dict[str, Any]:
        label = _finalize(
            Path(study),
            allow_exploratory=allow_exploratory,
            allow_open_predictions=allow_open_predictions,
            open_predictions_reason=reason,
            no_referee=no_referee,
            referee_reason=reason,
        )
        return envelope("finalize", {"label": label})

    return _guard("finalize", body)


def probe(
    study: str | Path,
    command: Sequence[str],
    *,
    note: str = "",
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    """``klein probe``: one exploratory look, on the record, never at sealed data."""
    from .probe import run_probe

    def body() -> dict[str, Any]:
        record = run_probe(
            Path(study), list(command), note=note, timeout_seconds=timeout_seconds, echo=False
        )
        return envelope("probe", {"probe": record}, ok=record.get("exit_code") == 0)

    return _guard("probe", body)
