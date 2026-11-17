"""Klein 3 judges schema 3 only; every other study is pointed at the engine that did.

Nothing is rewritten and nothing is judged under a rule set it was not written
for: one refusal, in ``load_contract``, naming the tag where the study verifies.
"""

from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path

import pytest
import yaml

from kleinlib import api, cli
from kleinlib.contract import (
    LEGACY_ENGINE_TAGS,
    SUPPORTED_SCHEMA_VERSIONS,
    load_contract,
    unsupported_schema_message,
    validate_contract,
)
from kleinlib.errors import WorkflowError
from kleinlib.scaffold import scaffold_study

REPO_ROOT = Path(__file__).resolve().parents[2]

#: label -> (study.yaml body, expected fragments of the refusal)
LEGACY = {
    "schema-2": ('schema_version: 2\nstudy_id: "02-old"\ngoal: "x"\n', ("schema 2", "tag v2.3.1", "studies/ARCHIVE.md")),
    "schema-1": ('study_id: "02-old"\ngoal: "x"\n', ("schema 1", "tag v1.3.0")),
    "schema-4": ('schema_version: 4\nstudy_id: "02-old"\ngoal: "x"\n', ("got 4", "a newer study needs a newer klein")),
}


@pytest.fixture(params=list(LEGACY))
def legacy_study(request, tmp_path: Path):
    body, fragments = LEGACY[request.param]
    study = tmp_path / "studies" / "02-old"
    study.mkdir(parents=True)
    (study / "study.yaml").write_text(body, encoding="utf-8")
    return study, body, fragments


@pytest.fixture
def schema2(tmp_path: Path) -> Path:
    study = tmp_path / "studies" / "02-old"
    study.mkdir(parents=True)
    (study / "study.yaml").write_text(LEGACY["schema-2"][0], encoding="utf-8")
    return study


def _tree(path: Path) -> dict[str, bytes]:
    return {p.relative_to(path).as_posix(): p.read_bytes() for p in sorted(path.rglob("*")) if p.is_file()}


def _run(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(argv)
    return code, out.getvalue(), err.getvalue()


# --------------------------------------------------------------------------
# the contract loader
# --------------------------------------------------------------------------


def test_only_schema_three_is_judged_and_two_engines_are_named() -> None:
    assert SUPPORTED_SCHEMA_VERSIONS == {3}
    assert LEGACY_ENGINE_TAGS == {1: "v1.3.0", 2: "v2.3.1"}
    assert unsupported_schema_message(3) is None


def test_load_contract_refuses_a_study_of_another_schema(legacy_study) -> None:
    study, _body, fragments = legacy_study
    with pytest.raises(WorkflowError) as exc:
        load_contract(study)
    for fragment in fragments:
        assert fragment in str(exc.value), fragment


def test_allow_legacy_returns_the_dict_for_the_verbs_that_only_say_so(legacy_study) -> None:
    study, body, _ = legacy_study
    assert load_contract(study, allow_legacy=True) == yaml.safe_load(body)


def test_validate_contract_returns_exactly_the_one_message(legacy_study) -> None:
    study, body, _ = legacy_study
    raw = yaml.safe_load(body)
    version = int(raw.get("schema_version", 1))
    assert validate_contract(raw, study) == [unsupported_schema_message(version)]


# --------------------------------------------------------------------------
# the command line
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "argv",
    [
        ["verify", "--study", "{S}"],
        ["status", "--study", "{S}"],
        ["run-one", "--study", "{S}", "--description", "x"],
        ["gate", "record", "consult", "--study", "{S}", "--acknowledged-by", "tester"],
        ["map", "--study", "{S}"],
        ["probe", "--study", "{S}", "--", "echo", "hi"],
    ],
)
def test_a_judging_verb_exits_two_and_writes_nothing(schema2: Path, argv: list[str]) -> None:
    before = _tree(schema2)
    code, _out, err = _run([str(schema2) if part == "{S}" else part for part in argv])
    assert code == 2, err
    assert "klein: error:" in err and "tag v2.3.1" in err
    assert _tree(schema2) == before  # not even a lock file or a study_state.json appeared


def test_preflight_reports_the_refusal_as_its_failed_study_contract_check(schema2: Path) -> None:
    before = _tree(schema2)
    code, out, _err = _run(["preflight", "--study", str(schema2)])
    assert code != 0  # exits as a failed check (1), not as an argparse-style refusal (2)
    assert "[FAIL] study contract" in out and "tag v2.3.1" in out
    assert _tree(schema2) == before


def test_next_on_a_legacy_study_exits_zero_and_points_at_the_archive(legacy_study) -> None:
    study, _body, fragments = legacy_study
    code, out, _err = _run(["next", "--study", str(study)])
    assert code == 0
    assert "stage: legacy" in out and "studies/ARCHIVE.md" in out
    code, out, _err = _run(["next", "--study", str(study), "--json"])
    env = json.loads(out)
    assert code == 0 and env["ok"] is True
    step = env["data"]["next"]
    assert step["stage_id"] == "legacy" and step["command"] is None and step["argv"] is None
    assert step["protocol"] == "studies/ARCHIVE.md"
    assert fragments[-1] in step["why"] or fragments[0] in step["why"]


def test_the_api_turns_the_refusal_into_an_envelope(schema2: Path) -> None:
    for call in (api.status, api.verify, api.study_map, api.predictions):
        env = call(schema2)
        assert env["ok"] is False and env["problems"][0]["code"] == "refused", call.__name__
        assert "tag v2.3.1" in env["problems"][0]["message"]
    assert api.next_action(schema2)["data"]["next"]["stage_id"] == "legacy"


# --------------------------------------------------------------------------
# scaffolding never writes an old schema
# --------------------------------------------------------------------------


def test_scaffold_refuses_to_write_schema_two(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        scaffold_study(tmp_path / "studies", "03-old", goal="g", schema_version=2)
    assert not (tmp_path / "studies" / "03-old").exists()


def test_klein_new_has_no_schema_version_option(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc:
        cli.main(["new", "x", "--schema-version", "2", "--root", str(tmp_path)])
    assert exc.value.code == 2
    assert not (tmp_path / "x").exists()


# --------------------------------------------------------------------------
# the archive
# --------------------------------------------------------------------------


def test_archived_schema_two_studies_are_indexed_and_gone_from_the_tree() -> None:
    index = yaml.safe_load((REPO_ROOT / "studies" / "archive.yaml").read_text(encoding="utf-8"))
    assert index["archive_tag"] == LEGACY_ENGINE_TAGS[2]
    rows = {row["id"]: row for row in index["studies"]}
    schema_two = {sid for sid, row in rows.items() if row["schema"] == 2}
    assert schema_two == {
        "03-noisy-rosenbrock-dfo", "05-fremtpl2-gap-forensics", "06-hurricane-gqls-returnlevels",
        "07-iris-90years", "08-iris-rematch", "09-iris-first-lesson",
    }
    for sid in rows:
        assert not (REPO_ROOT / "studies" / sid).exists(), sid
    assert (REPO_ROOT / "studies" / "ARCHIVE.md").is_file()


def test_every_study_left_in_the_tree_is_schema_three() -> None:
    studies = sorted(p for p in (REPO_ROOT / "studies").iterdir() if (p / "study.yaml").is_file())
    assert len(studies) >= 8
    for study in studies:
        assert load_contract(study)["schema_version"] == 3, study.name


def _git(*args: str) -> tuple[int, str]:
    import subprocess

    result = subprocess.run(["git", *args], cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    return result.returncode, result.stdout.strip()


def test_the_refusal_names_a_commit_as_well_as_a_tag() -> None:
    # A tag may not have been fetched (or pushed yet); a commit on main always resolves.
    from kleinlib.contract import LEGACY_ENGINE_COMMITS

    assert set(LEGACY_ENGINE_COMMITS) == set(LEGACY_ENGINE_TAGS)
    for version, commit in LEGACY_ENGINE_COMMITS.items():
        assert commit in unsupported_schema_message(version)
    index = yaml.safe_load((REPO_ROOT / "studies" / "archive.yaml").read_text(encoding="utf-8"))
    assert index["archive_commit"].startswith(LEGACY_ENGINE_COMMITS[2])


def test_the_legacy_commits_are_the_ones_the_tags_name() -> None:
    from kleinlib.contract import LEGACY_ENGINE_COMMITS

    code, shallow = _git("rev-parse", "--is-shallow-repository")
    if code != 0 or shallow == "true":
        pytest.skip("needs a full git history")
    for version, commit in LEGACY_ENGINE_COMMITS.items():
        code, full = _git("rev-parse", "--verify", "--quiet", f"{commit}^{{commit}}")
        assert code == 0, f"commit {commit} (schema {version}) is not in this repository"
        tag = LEGACY_ENGINE_TAGS[version]
        code, tagged = _git("rev-parse", "--verify", "--quiet", f"refs/tags/{tag}^{{commit}}")
        if code == 0:  # the tag is here: it must be the same engine
            assert tagged == full, f"{tag} points at {tagged}, the message names {full}"
