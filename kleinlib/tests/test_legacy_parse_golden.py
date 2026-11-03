"""Golden test: the whole-log metric parser reproduces every shipped manifest.

Klein 2.3 adds a block-scoped metric channel (``entrypoint.printed: block``).  The
legacy channel — every ``key: value`` line of the whole run log — must keep
producing EXACTLY the numbers each shipped run was judged on, forever.  This test
freezes that: for every shipped manifest that exited 0, was not a crash, and whose
track declares no verifier (a verifier's block is merged into ``metrics``),
``parse_metric_log(run.log)`` must equal the manifest's recorded ``metrics`` and
``primary_metric``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from kleinlib.decision import parse_metric_log

ROOT = Path(__file__).resolve().parents[2]


def _cases() -> list[tuple[str, Path]]:
    cases: list[tuple[str, Path]] = []
    for manifest_path in sorted(ROOT.glob("studies/*/runs/E*/manifest.json")):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        log = manifest_path.parent / "run.log"
        if manifest.get("exit_code") != 0 or manifest.get("disposition") == "crash":
            continue
        if not log.is_file():
            continue
        if manifest.get("printed_scope"):
            # a 2.3 block-scoped run is judged by the block channel, not this one
            continue
        study = manifest_path.parents[2]
        contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
        tracks = contract.get("tracks")
        track = tracks.get(manifest.get("track"), {}) if isinstance(tracks, dict) else {}
        if isinstance(track, dict) and track.get("verifier"):
            continue
        cases.append((manifest_path.relative_to(ROOT).as_posix(), manifest_path))
    return cases


CASES = _cases()


def test_golden_corpus_is_not_empty() -> None:
    # The shipped exhibits carry well over a hundred eligible runs; an empty
    # corpus would mean this guard silently stopped guarding.
    assert len(CASES) >= 50


@pytest.mark.parametrize("manifest_path", [path for _, path in CASES], ids=[rel for rel, _ in CASES])
def test_whole_log_parse_reproduces_manifest(manifest_path: Path) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    primary, _name, _goal, metrics = parse_metric_log(manifest_path.parent / "run.log")
    assert primary == manifest["primary_metric"]
    assert metrics == manifest["metrics"]
