"""E14 — the consult gate hashes `scouting_ledger.md`, or records its absence.

The protocol has always said "committed before `klein gate record consult`; the
gate hashes it" (`assets/scouting-ledger-template.md`,
`references/consult-protocol.md`), but the engine hashed only the three REQUIRED
consult artifacts — so a study's pre-registration disclosure rested on a commit
order nobody checked. The ledger is OPTIONAL (a study may have scouted nothing),
so absence is recorded on the gate event rather than refused, and presence is
notarized like every other gate artifact.

Schema 3 only: a schema-2 study's consult record never mentions the ledger, even
when the file is sitting right there.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from kleinlib.checks import verify_study
from kleinlib.contract import GATE_OPTIONAL_ARTIFACTS
from kleinlib.errors import WorkflowError
from kleinlib.scaffold import scaffold_study
from kleinlib.workflow import load_contract, load_state, read_events, record_gate

LEDGER = "scouting_ledger.md"

COMMON = dict(
    goal="compare a candidate",
    domain="test",
    target="y",
    family="linear",
    metric_name="val_auc",
    metric_goal="higher",
    data_source="csv:fixture.csv",
    data_path="data/prepared/fixture.csv",
)


def _resolve_placeholders(study: Path) -> None:
    """Fill what CONSULT owns, so the gate's placeholder refusal is not the story."""
    for name in ("study.yaml", "program.md", "research_plan.md"):
        path = study / name
        path.write_text(
            re.sub(r"\{\{[^{}]+\}\}", "filled", path.read_text(encoding="utf-8")),
            encoding="utf-8",
        )


def _study(tmp_path: Path, *, schema_version: int, ledger: bool = True) -> Path:
    """A scaffolded study with the consult gate's prerequisites resolved.

    ``ledger=False`` deletes the scaffolded ledger BEFORE any gate is recorded —
    the "nothing was scouted, and the study says so" case.
    """
    kwargs = dict(COMMON)
    if schema_version >= 3:
        kwargs.update(kind="predict", modality="tabular", profile="generic", audience="testers")
    study = scaffold_study(
        tmp_path / f"studies{schema_version}", "03-demo",
        schema_version=schema_version, **kwargs,
    )
    _resolve_placeholders(study)
    if not ledger:
        (study / LEDGER).unlink(missing_ok=True)
    return study


def _consult_events(study: Path) -> list[dict]:
    return [
        event
        for event in read_events(study)
        if event.get("type") in {"gate_recorded", "gate_overridden"}
        and event.get("gate") == "consult"
    ]


def _named(checks, name: str):
    return next(check for check in checks if check.name == name)


def _hash_check(study: Path):
    return _named(verify_study(study), "gate artifact hashes")


# -- the registry -----------------------------------------------------------


def test_the_ledger_is_the_consult_gate_s_one_optional_artifact() -> None:
    assert GATE_OPTIONAL_ARTIFACTS == {"consult": (LEDGER,)}


# -- (a) present: hashed, then guarded --------------------------------------


def test_a_present_ledger_is_hashed_into_the_consult_record(tmp_path: Path) -> None:
    study = _study(tmp_path, schema_version=3)
    state = record_gate(study, "consult", acknowledged_by="tester")

    recorded = state["gates"]["consult"]["artifacts"]
    assert set(recorded) == {"study.yaml", "research_plan.md", "program.md", LEDGER}
    # The enforced map is what `klein verify` re-checks on every run; program.md
    # is excluded there because the journal is REQUIRED to change, the ledger is not.
    assert LEDGER in state["artifact_hashes"]
    assert "program.md" not in state["artifact_hashes"]
    assert _consult_events(study)[-1]["artifact_hashes"][LEDGER] == state["artifact_hashes"][LEDGER]
    assert "scouting_ledger" not in _consult_events(study)[-1]


def test_editing_the_ledger_after_the_gate_fails_verify(tmp_path: Path) -> None:
    study = _study(tmp_path, schema_version=3)
    record_gate(study, "consult", acknowledged_by="tester")
    assert _hash_check(study).ok

    ledger = study / LEDGER
    ledger.write_text(
        ledger.read_text(encoding="utf-8") + "\n| S1 | 2026-09-03 | a peek | 0.94 | … | … |\n",
        encoding="utf-8",
    )
    check = _hash_check(study)
    assert not check.ok
    assert check.message == f"recorded gate artifact changed after acknowledgement: {LEDGER}"


def test_deleting_the_ledger_after_the_gate_fails_verify(tmp_path: Path) -> None:
    """A disclosure cannot be un-disclosed by deleting the file."""
    study = _study(tmp_path, schema_version=3)
    record_gate(study, "consult", acknowledged_by="tester")
    (study / LEDGER).unlink()
    check = _hash_check(study)
    assert not check.ok
    assert check.message == f"recorded gate artifact is missing: {LEDGER}"


def test_a_consult_re_record_re_hashes_the_amended_ledger(tmp_path: Path) -> None:
    study = _study(tmp_path, schema_version=3)
    first = dict(record_gate(study, "consult", acknowledged_by="tester")["artifact_hashes"])

    ledger = study / LEDGER
    ledger.write_text(
        ledger.read_text(encoding="utf-8").replace(
            "nothing scouted before the gate", "an OLS fit on the public table"
        ),
        encoding="utf-8",
    )
    state = record_gate(
        study, "consult", acknowledged_by="tester", note="scouting disclosed before Gate 1"
    )
    assert state["artifact_hashes"][LEDGER] != first[LEDGER]
    assert _hash_check(study).ok
    # The amendment is on the append-only trail, with its reason.
    events = _consult_events(study)
    assert len(events) == 2
    assert events[-1]["note"] == "scouting disclosed before Gate 1"


def test_an_unresolved_placeholder_in_the_ledger_is_refused(tmp_path: Path) -> None:
    """A half-written disclosure is not a disclosure — same rule as the three."""
    study = _study(tmp_path, schema_version=3)
    (study / LEDGER).write_text("# Scouting ledger\n\n{{one paragraph}}\n", encoding="utf-8")
    with pytest.raises(WorkflowError) as exc:
        record_gate(study, "consult", acknowledged_by="tester")
    assert f"unresolved placeholder in {LEDGER}" in str(exc.value)


# -- (b) absent: recorded, and verify stays clean ----------------------------


def test_an_absent_ledger_is_recorded_as_absent(tmp_path: Path) -> None:
    study = _study(tmp_path, schema_version=3, ledger=False)
    state = record_gate(study, "consult", acknowledged_by="tester")

    assert set(state["gates"]["consult"]["artifacts"]) == {
        "study.yaml", "research_plan.md", "program.md",
    }
    assert LEDGER not in state["artifact_hashes"]
    assert _consult_events(study)[-1]["scouting_ledger"] == "absent"
    # Nothing was hashed, so nothing can drift: the audit stays clean.
    assert _hash_check(study).ok


def test_an_absent_ledger_does_not_block_an_override_either(tmp_path: Path) -> None:
    study = _study(tmp_path, schema_version=3, ledger=False)
    state = record_gate(
        study, "consult", acknowledged_by="tester", override_reason="contract accepted as-is"
    )
    assert state["gates"]["consult"]["status"] == "overridden"
    assert _consult_events(study)[-1]["scouting_ledger"] == "absent"


def test_a_ledger_written_after_an_absent_record_is_hashed_by_the_re_record(
    tmp_path: Path,
) -> None:
    study = _study(tmp_path, schema_version=3, ledger=False)
    record_gate(study, "consult", acknowledged_by="tester")
    (study / LEDGER).write_text("# Scouting ledger\n\nOne OLS fit, disclosed.\n", encoding="utf-8")
    state = record_gate(study, "consult", acknowledged_by="tester", note="ledger opened")
    assert LEDGER in state["artifact_hashes"]
    assert "scouting_ledger" not in _consult_events(study)[-1]


# -- (c) schema 2: byte-identical, ledger or no ledger -----------------------


def test_schema_2_never_mentions_the_ledger_even_when_one_exists(tmp_path: Path) -> None:
    study = _study(tmp_path, schema_version=2)
    assert not (study / LEDGER).exists(), "schema 2 does not scaffold a ledger"
    (study / LEDGER).write_text("# Scouting ledger\n\nkept by hand, as 07/08/09 did.\n", encoding="utf-8")

    state = record_gate(study, "consult", acknowledged_by="tester")
    assert set(state["gates"]["consult"]["artifacts"]) == {
        "study.yaml", "research_plan.md", "program.md",
    }
    assert LEDGER not in state["artifact_hashes"]
    event = _consult_events(study)[-1]
    assert LEDGER not in event["artifact_hashes"]
    assert "scouting_ledger" not in event
    assert LEDGER not in json.dumps(state)


def test_schema_2_does_not_record_an_absence_either(tmp_path: Path) -> None:
    study = _study(tmp_path, schema_version=2)
    record_gate(study, "consult", acknowledged_by="tester")
    assert "scouting_ledger" not in _consult_events(study)[-1]


# -- (d) the scaffold ships the ledger, and the fixture path hashes it -------


def test_the_schema_3_scaffold_writes_a_placeholder_free_ledger(tmp_path: Path) -> None:
    study = _study(tmp_path, schema_version=3)
    text = (study / LEDGER).read_text(encoding="utf-8")
    assert re.search(r"\{\{[^{}]+\}\}", text) is None
    assert 'study: "03-demo"' in text
    assert "nothing scouted before the gate" in text
    assert "## §0 Disclosure" in text


def test_the_standard_schema_3_fixture_hashes_its_scaffolded_ledger(ready_study_v3) -> None:
    """The canonical fixture path — `klein new` then the three gates — notarizes it."""
    _repo, study = ready_study_v3
    state = load_state(study, load_contract(study))
    assert LEDGER in state["gates"]["consult"]["artifacts"]
    assert LEDGER in state["artifact_hashes"]
    assert _hash_check(study).ok


# -- Defect 2: the scaffolded program.md carries a roster --------------------


def test_the_schema_3_program_carries_a_roster_naming_the_experimenter(
    tmp_path: Path,
) -> None:
    study = _study(tmp_path, schema_version=3)
    program = (study / "program.md").read_text(encoding="utf-8")
    heading, _, rest = program.partition("## Roster")
    assert heading.strip() == "# Program — 03-demo", "the roster sits right after the title"
    rows = [line for line in rest.split("\n\n## ")[0].splitlines() if line.startswith("| ")]
    assert [row.split("|")[1].strip() for row in rows] == [
        "Role", "---", "experimenter", "data-gate auditor", "referee", "lead",
    ]
    # The first three are the study's to fill; a blank experimenter row is what
    # caps the referee's independence rung.
    assert [row.split("|")[2].strip() for row in rows[2:5]] == ["", "", ""]
    assert "fresh session" in rest


def test_the_schema_2_program_has_no_roster(tmp_path: Path) -> None:
    study = _study(tmp_path, schema_version=2)
    program = (study / "program.md").read_text(encoding="utf-8")
    assert "## Roster" not in program
    assert program.startswith("# Program — 03-demo\n\nThis is the living lab notebook.")
