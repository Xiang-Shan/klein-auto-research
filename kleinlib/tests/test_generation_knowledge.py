"""The ``knowledge`` capability: promote, contest, resolve, consult.

The smallest exercise runs end to end in ONE temporary
repository with three studies, because the whole point of a cross-study store is
that it is not inside a study:

    A promotes one scoped claim → B retrieves it, tests it outside that regime,
    and files a scoped contest → C's consultation returns BOTH and has to record
    what it did about them → and A, untouched, still verifies.

The invalid controls are the ways the store could be made to lie: a receipt with
the contest edited out, a failed transfer filed as a refutation, a promotion off
a lock that does not verify, a strengthened copy, and a deleted transaction.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from test_workflow_v3 import _fill, commit_all, git

from kleinlib import cli
from kleinlib.claims import add_claim, add_number, init_lock, pin_artifact
from kleinlib.generation import knowledge as gk
from kleinlib.scaffold import scaffold_study
from kleinlib.workflow import record_gate

REPO_ROOT = Path(__file__).resolve().parents[2]


def _gen(*argv: str) -> int:
    return cli.main(["generation", *argv])


# --------------------------------------------------------------------------
# fixtures — three studies, one repository
# --------------------------------------------------------------------------


def _repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    (repo / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    commit_all(repo, "repository")
    return repo


def _scaffold(repo: Path, slug: str) -> Path:
    """One schema-3 study, committed, with the three gates still UNRECORDED."""
    study = scaffold_study(
        repo / "studies",
        slug,
        goal="compare a candidate",
        domain="test",
        target="y",
        task_type="classification",
        method_depth="brief",
        family="linear",
        metric_name="val_auc",
        metric_goal="higher",
        data_source="csv:fixture.csv",
        data_path="data/prepared/fixture.csv",
        max_run_seconds=5,
        schema_version=3,
        kind="predict",
        modality="tabular",
        profile="generic",
        audience="the maintainers of this test suite",
    )
    _fill(study)
    data = study / "data" / "prepared"
    data.mkdir(parents=True)
    (data / "fixture.csv").write_text("x,y\n1,0\n2,1\n", encoding="utf-8")
    (study / "data_card.md").write_text("# Data card\n\n> **Decision:** **GO**\n", encoding="utf-8")
    (study / "method_card.md").write_text("# Method card\n\nBrief method.\n", encoding="utf-8")
    commit_all(repo, f"scaffolded {slug}")
    return study


def _gates(repo: Path, study: Path) -> None:
    record_gate(study, "consult", acknowledged_by="tester")
    record_gate(study, "data", acknowledged_by="tester")
    record_gate(study, "method", acknowledged_by="tester")
    commit_all(repo, f"gates recorded for {study.name}")


def _lock(
    repo: Path,
    study: Path,
    sentence: str,
    *,
    claim_class: str = "empirical-description",
    strength: str = "exploratory",
) -> None:
    """A findings file, a pinned table and a claims lock that verifies."""
    (study / "findings.md").write_text(
        f"# Findings\n\n- **[C1]** {sentence}\n", encoding="utf-8"
    )
    tables = study / "tables"
    tables.mkdir(exist_ok=True)
    (tables / "result.tsv").write_text("metric\tvalue\nval_auc\t0.812345\n", encoding="utf-8")
    commit_all(repo, f"{study.name}: findings and table")
    init_lock(study)
    pin_artifact(study, "result", "tables/result.tsv")
    add_number(study, "val_auc", value=0.812345, art="result", claim="C1", precision=6)
    add_claim(
        study,
        "C1",
        claim_class=claim_class,
        strength=strength,
        claim=sentence,
        numbers=["val_auc"],
        evidence=["art:result"],
    )


A_SENTENCE = "Isotonic calibration beats class weights on weak-signal tabular data."
B_SENTENCE = "On imbalanced tabular data the same calibration recipe loses to raw scores."
C_QUESTION = "does calibration transfer to imbalanced tabular data"


def _enable(study: Path, *capabilities: str) -> None:
    argv = ["init", "--study", str(study)]
    for name in capabilities or ("knowledge",):
        argv += ["--capability", name]
    assert _gen(*argv) == 0


@pytest.fixture
def store(tmp_path: Path) -> dict[str, Any]:
    """A promotes; B contests; C consults.  One repo, three studies."""
    repo = _repo(tmp_path)

    alpha = _scaffold(repo, "03-alpha")
    _enable(alpha)
    assert (
        _gen(
            "knowledge",
            "query",
            "--study",
            str(alpha),
            "--tags",
            "calibration",
            "--text",
            "how should weak-signal tabular scores be calibrated",
            "--actor",
            "tester",
        )
        == 0
    )
    _gates(repo, alpha)
    _lock(repo, alpha, A_SENTENCE)
    assert (
        _gen(
            "knowledge",
            "promote",
            "--study",
            str(alpha),
            "--claim",
            "C1",
            "--tags",
            "calibration",
            "tabular",
            "--scope",
            "population=weak-signal insurance-like tables",
            "--scope",
            "measurement_regime=held-out AUC at a tuned threshold",
            "--scope",
            "assumptions=the positive rate stays under five percent",
            "--rationale",
            "the recipe generalised across three phases here",
        )
        == 0
    )

    beta = _scaffold(repo, "04-beta")
    _enable(beta)
    assert (
        _gen(
            "knowledge",
            "query",
            "--study",
            str(beta),
            "--tags",
            "calibration",
            "--text",
            C_QUESTION,
            "--use",
            "K1=the recipe is the thing this study is testing",
        )
        == 0
    )
    _gates(repo, beta)
    _lock(repo, beta, B_SENTENCE)
    return {"repo": repo, "alpha": alpha, "beta": beta}


def _contest(store: dict[str, Any]) -> int:
    return _gen(
        "knowledge",
        "contest",
        "--study",
        str(store["beta"]),
        "--target",
        "K1",
        "--evidence",
        "04-beta#C1",
        "--rationale",
        "the claim's scope names weak-signal tables; this measured an imbalanced one and it lost",
    )


def _receipt(study: Path) -> dict[str, Any]:
    return json.loads((study / "generation" / "verify_receipt.json").read_text(encoding="utf-8"))


def _details(receipt: dict[str, Any], name: str) -> str:
    return " ".join(check["detail"] for check in receipt["checks"] if check["name"] == name)


def _statuses(receipt: dict[str, Any], name: str) -> list[str]:
    return [check["status"] for check in receipt["checks"] if check["name"] == name]


def _query_object(study: Path) -> tuple[Path, dict[str, Any]]:
    """The study's first ``knowledge_queried`` receipt: its file and its content."""
    from kleinlib.generation.ledger import read_events

    rows = gk.queries(study, read_events(study), gk.QUERY_TYPE)
    assert rows, "no knowledge_queried receipt"
    event, obj = rows[0]
    path = study / "generation" / "objects" / f"{event['payload_sha256']}.json"
    return path, obj


# --------------------------------------------------------------------------
# The valid control: the smallest exercise
# --------------------------------------------------------------------------


def test_v20_a_promotes_b_contests_c_consults_and_a_still_verifies(store) -> None:
    """The smallest exercise, end to end in one repo."""
    repo, alpha, beta = store["repo"], store["alpha"], store["beta"]
    assert _contest(store) == 0

    gamma = _scaffold(repo, "05-gamma")
    _enable(gamma)
    # C's consultation must return A's object AND B's contest, and must decide.
    assert (
        _gen(
            "knowledge",
            "query",
            "--study",
            str(gamma),
            "--tags",
            "calibration",
            "--text",
            C_QUESTION,
            "--reject",
            "K1=contested outside our regime; we re-measure rather than inherit",
        )
        == 0
    )
    _gates(repo, gamma)

    _path, receipt = _query_object(gamma)
    assert receipt["hits"] and receipt["hits"][0]["id"] == "K1"
    assert receipt["hits"][0]["contests"] == ["KE0002"], receipt["hits"][0]
    assert receipt["no_match"] is False
    assert receipt["retriever_version"] == gk.RETRIEVER_VERSION
    assert receipt["decision"] == [
        {
            "id": "K1",
            "decision": "reject",
            "reason": "contested outside our regime; we re-measure rather than inherit",
        }
    ]

    for study in (alpha, beta, gamma):
        assert _gen("verify", "--study", str(study)) == 0, study.name
        assert _receipt(study)["summary"]["failed"] == 0

    # The capability outcome is reported beside the integrity, never conflated.
    assert _receipt(alpha)["capabilities"]["knowledge"] == {
        "integrity": "PASS",
        "outcome": "no-match",
        "hits": 0,
        "used": 0,
        "rejected": 0,
    }
    assert _receipt(gamma)["capabilities"]["knowledge"]["outcome"] == "consulted"
    assert _receipt(gamma)["capabilities"]["knowledge"]["rejected"] == 1


def test_the_empty_store_answers_with_an_explicit_no_match_receipt(store) -> None:
    """The bootstrap case: an empty store is consulted, and says so on the record."""
    _path, receipt = _query_object(store["alpha"])
    assert receipt["no_match"] is True
    assert receipt["hits"] == []
    assert receipt["store_head"]
    assert receipt["contract_draft_sha256"]


def test_a_promotion_copies_class_strength_and_roots_verbatim(store) -> None:
    """Promotion creates availability, not stronger evidence."""
    snapshot = gk.snapshot_on_disk(store["repo"])
    obj = snapshot.objects["K1"]
    assert obj["class"] == "empirical-description"
    assert obj["strength"] == "exploratory"
    assert obj["evidence_roots"] == ["art:result"]
    assert obj["claim_id"] == "03-alpha#C1"
    assert obj["text"] == A_SENTENCE
    assert obj["scope"]["population"] == "weak-signal insurance-like tables"
    assert obj["scope"]["assumptions"] == ["the positive rate stays under five percent"]
    assert obj["type"] == "claim"


def test_a_knowledge_commit_files_the_store_and_nothing_else(store) -> None:
    """The promotion transaction touches `knowledge/**` only — never `git add -A`."""
    repo = store["repo"]
    commit = git(repo, "log", "--format=%H", "-1", "--grep=knowledge promote")
    assert commit, "the promotion filed no commit"
    names = [
        name
        for name in git(repo, "show", "--name-only", "--format=", commit).splitlines()
        if name
    ]
    assert names and all(name.startswith("knowledge/") for name in names), names


# --------------------------------------------------------------------------
# Invalid controls
# --------------------------------------------------------------------------


def test_v20_a_receipt_with_the_contest_removed_by_hand_fails_replay(store) -> None:
    """Suppressing the closure is exactly what replay detects."""
    repo, beta = store["repo"], store["beta"]
    assert _contest(store) == 0

    gamma = _scaffold(repo, "05-gamma")
    _enable(gamma)
    assert (
        _gen(
            "knowledge",
            "query",
            "--study",
            str(gamma),
            "--text",
            C_QUESTION,
            "--use",
            "K1=inherited as-is",
        )
        == 0
    )
    _gates(repo, gamma)
    assert _gen("verify", "--study", str(gamma)) == 0

    path, receipt = _query_object(gamma)
    assert receipt["hits"][0]["contests"] == ["KE0002"]
    receipt["hits"][0]["contests"] = []
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    assert _gen("verify", "--study", str(gamma)) == 2
    detail = _details(_receipt(gamma), "knowledge replay")
    assert "suppressed hit or contest" in detail
    assert "FAIL" in _statuses(_receipt(gamma), "knowledge replay")
    assert beta.is_dir()


def test_v20_a_failed_transfer_is_a_prediction_verdict_not_a_contest(store) -> None:
    """A contest needs a CLAIM that contradicts, not a refuted P#."""
    beta = store["beta"]
    rc = _gen(
        "knowledge",
        "contest",
        "--study",
        str(beta),
        "--target",
        "K1",
        "--evidence",
        "P1",
        "--rationale",
        "the transfer prediction was refuted here",
    )
    assert rc == 2
    assert not gk.closure(gk.snapshot_on_disk(store["repo"]), "K1")[0]


def test_a_contest_citing_a_claim_of_another_study_is_refused(store) -> None:
    """A contest rests on evidence THIS study earned."""
    assert (
        _gen(
            "knowledge",
            "contest",
            "--study",
            str(store["beta"]),
            "--target",
            "K1",
            "--evidence",
            "03-alpha#C1",
            "--rationale",
            "borrowing someone else's claim to contest with",
        )
        == 2
    )


def test_a_promotion_off_a_lock_that_does_not_verify_is_refused(tmp_path: Path) -> None:
    """`klein claims verify` must PASS on the source study NOW."""
    repo = _repo(tmp_path)
    study = _scaffold(repo, "03-alpha")
    _enable(study)
    assert _gen("knowledge", "query", "--study", str(study), "--text", "anything") == 0
    _gates(repo, study)
    _lock(repo, study, A_SENTENCE)

    # Break check 5: the pinned table no longer spells the number out.
    (study / "tables" / "result.tsv").write_text("metric\tvalue\nval_auc\t0.9\n", encoding="utf-8")
    commit_all(repo, "table edited after the lock")
    assert (
        _gen(
            "knowledge",
            "promote",
            "--study",
            str(study),
            "--claim",
            "C1",
            "--tags",
            "calibration",
        )
        == 2
    )
    assert not gk.snapshot_on_disk(repo).objects


def test_a_promotion_of_a_claim_that_is_not_in_the_lock_is_refused(store) -> None:
    # exit 1: `--claim C9` names a claim the lock does not carry, so the
    # promotion question was never asked — nothing is recorded either way.
    assert (
        _gen("knowledge", "promote", "--study", str(store["alpha"]), "--claim", "C9") == 1
    )


def test_v20_a_strengthened_copy_fails_verification(store) -> None:
    """A promotion never strengthens, and an edit says so."""
    repo, alpha = store["repo"], store["alpha"]
    assert _gen("verify", "--study", str(alpha)) == 0

    snapshot = gk.snapshot_on_disk(repo)
    path = gk.objects_dir(repo) / f"{snapshot.shas['K1']}.json"
    obj = json.loads(path.read_text(encoding="utf-8"))
    obj["strength"] = "confirmed"
    path.write_text(json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")

    assert _gen("verify", "--study", str(alpha)) == 2
    receipt = _receipt(alpha)
    assert "never strengthens it" in _details(receipt, "knowledge promotions")
    assert "FAIL" in _statuses(receipt, "knowledge store")


def test_v20_a_deleted_transaction_fails_the_store_check(store) -> None:
    """Transactions are append-only; a deleted object is detected."""
    repo, alpha = store["repo"], store["alpha"]
    snapshot = gk.snapshot_on_disk(repo)
    (gk.objects_dir(repo) / f"{snapshot.shas['K1']}.json").unlink()

    assert _gen("verify", "--study", str(alpha)) == 2
    assert "is not in the store" in _details(_receipt(alpha), "knowledge store")


def test_an_edited_store_event_breaks_the_chain(store) -> None:
    """The store carries its own hash chain; a rewritten rationale is caught."""
    repo, alpha = store["repo"], store["alpha"]
    assert _contest(store) == 0
    path = gk.events_path(repo)
    lines = path.read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[-1])
    tampered["rationale"] = "on second thought, never mind"
    lines[-1] = json.dumps(tampered, sort_keys=True, separators=(",", ":"))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    assert _gen("verify", "--study", str(alpha)) == 2
    assert "event_hash does not match" in _details(_receipt(alpha), "knowledge store")


# --------------------------------------------------------------------------
# the consultation obligation and its bootstrap
# --------------------------------------------------------------------------


def test_a_declaring_study_with_no_query_receipt_fails(tmp_path: Path) -> None:
    """A missing consultation on a knowledge-enabled study is a FAIL."""
    repo = _repo(tmp_path)
    study = _scaffold(repo, "03-alpha")
    _enable(study)
    _gates(repo, study)

    assert _gen("verify", "--study", str(study)) == 2
    receipt = _receipt(study)
    assert "no knowledge_queried receipt" in _details(receipt, "knowledge query")
    assert receipt["capabilities"]["knowledge"]["outcome"] == "unconsulted"


def test_a_consultation_after_the_consult_ack_fails(tmp_path: Path) -> None:
    """A store read after the ack is a bibliography, not a consultation."""
    repo = _repo(tmp_path)
    study = _scaffold(repo, "03-alpha")
    _enable(study)
    _gates(repo, study)
    assert _gen("knowledge", "query", "--study", str(study), "--text", "late") == 0

    assert _gen("verify", "--study", str(study)) == 2
    assert "at or after the consult gate record" in _details(_receipt(study), "knowledge query")


def test_an_undecided_hit_fails_until_decide_closes_it(store) -> None:
    """CONSULT records a use/reject reason for every hit it saw."""
    repo = store["repo"]
    gamma = _scaffold(repo, "05-gamma")
    _enable(gamma)
    assert _gen("knowledge", "query", "--study", str(gamma), "--text", C_QUESTION) == 0
    _gates(repo, gamma)

    assert _gen("verify", "--study", str(gamma)) == 2
    assert "hits nobody decided: K1" in _details(_receipt(gamma), "knowledge decisions")

    assert (
        _gen(
            "knowledge",
            "decide",
            "--study",
            str(gamma),
            "--reject",
            "K1=measured regime does not match ours",
        )
        == 0
    )
    assert _gen("verify", "--study", str(gamma)) == 0
    assert _receipt(gamma)["capabilities"]["knowledge"]["rejected"] == 1


def test_a_decision_without_a_reason_is_refused(store) -> None:
    repo = store["repo"]
    gamma = _scaffold(repo, "05-gamma")
    _enable(gamma)
    assert (
        _gen(
            "knowledge",
            "query",
            "--study",
            str(gamma),
            "--text",
            C_QUESTION,
            "--use",
            "K1",
        )
        == 1
    )


# --------------------------------------------------------------------------
# dedupe, resolution, retrieval determinism
# --------------------------------------------------------------------------


def test_the_store_dedupes_by_evidence_roots(store) -> None:
    """Repeating a lesson is not a second piece of evidence."""
    alpha = store["alpha"]
    add_claim(
        alpha,
        "C2",
        claim_class="empirical-description",
        strength="exploratory",
        claim="A second sentence resting on exactly the same evidence.",
        evidence=["art:result"],
    )
    findings = alpha / "findings.md"
    findings.write_text(
        findings.read_text(encoding="utf-8")
        + "- **[C2]** A second sentence resting on exactly the same evidence.\n",
        encoding="utf-8",
    )
    commit_all(store["repo"], "alpha: a second claim on the same evidence")

    assert _gen("knowledge", "promote", "--study", str(alpha), "--claim", "C2") == 2
    assert list(gk.snapshot_on_disk(store["repo"]).objects) == ["K1"]


def test_resolve_appends_and_deletes_nothing(store) -> None:
    """`withdrawn` keeps the object with the resolution attached."""
    repo, beta = store["repo"], store["beta"]
    assert _contest(store) == 0
    assert (
        _gen(
            "knowledge",
            "resolve",
            "--study",
            str(beta),
            "--target",
            "K1",
            "--outcome",
            "scoped",
            "--rationale",
            "the claim holds inside its stated regime and is narrowed, not withdrawn",
        )
        == 0
    )
    snapshot = gk.snapshot_on_disk(repo)
    assert "K1" in snapshot.objects
    contests, resolutions = gk.closure(snapshot, "K1")
    assert contests == ["KE0002"] and resolutions == ["KE0003"]
    assert [event["operation"] for event in snapshot.events] == ["promote", "contest", "resolve"]


def test_retrieval_is_deterministic_and_complete(store) -> None:
    """`lex-1` is token overlap, ordered by score then id, with no top-k."""
    snapshot = gk.snapshot_on_disk(store["repo"])
    first, truncated = gk.hits_for(snapshot, tags=["calibration"], text=C_QUESTION)
    second, _ = gk.hits_for(snapshot, tags=["calibration"], text=C_QUESTION)
    assert first == second and not truncated
    assert [hit["id"] for hit in first] == ["K1"]
    assert gk.hits_for(snapshot, text="unrelated words entirely")[0] == []
    limited, truncated = gk.hits_for(snapshot, tags=["calibration"], text=C_QUESTION, limit=0)
    assert limited == [] and truncated is True


def test_a_limit_is_recorded_in_the_receipt(store) -> None:
    """Truncation is visible, never convenient."""
    repo = store["repo"]
    gamma = _scaffold(repo, "05-gamma")
    _enable(gamma)
    assert (
        _gen(
            "knowledge",
            "query",
            "--study",
            str(gamma),
            "--text",
            C_QUESTION,
            "--limit",
            "1",
            "--use",
            "K1=the only hit we kept",
        )
        == 0
    )
    _path, receipt = _query_object(gamma)
    assert receipt["limit"] == 1 and receipt["truncated"] is False


# --------------------------------------------------------------------------
# method promotion, and the capability gate
# --------------------------------------------------------------------------


def test_a_method_promotion_pins_its_reference_records(tmp_path: Path) -> None:
    """Method objects pin their card and their reference-store entries."""
    repo = _repo(tmp_path)
    study = _scaffold(repo, "03-alpha")
    _enable(study, "expertise", "knowledge")
    assert _gen("knowledge", "query", "--study", str(study), "--text", "methods for tables") == 0

    # No record yet: the promotion is refused rather than filed unpinned.
    assert _gen("knowledge", "promote", "--study", str(study), "--method") == 2

    assert (
        _gen(
            "reference",
            "record",
            "--study",
            str(study),
            "--id",
            "collins2010",
            "--title",
            "Tacit and Explicit Knowledge",
            "--year",
            "2010",
            "--identifier",
            "isbn:9780226113807",
            "--locator",
            "isbn:9780226113807",
            "--statement",
            "reproducing a recipe is not holding the tacit knowledge behind it",
            "--basis",
            "bibliography",
        )
        == 0
    )
    (study / "references.yaml").write_text(
        "references:\n"
        "  collins2010:\n"
        "    title: 'Tacit and Explicit Knowledge'\n"
        "    isbn: '9780226113807'\n"
        "    verified: true\n"
        "    record_id: collins2010\n",
        encoding="utf-8",
    )
    commit_all(repo, "alpha: references")

    assert (
        _gen(
            "knowledge",
            "promote",
            "--study",
            str(study),
            "--method",
            "--tags",
            "tabular",
        )
        == 0
    )
    obj = gk.snapshot_on_disk(repo).objects["K1"]
    assert obj["type"] == "method"
    assert obj["evidence_roots"] == ["ref:collins2010"]
    assert obj["source_path"].endswith("method_card.md")
    assert obj["class"] is None and obj["strength"] is None


def test_the_knowledge_verbs_refuse_a_study_that_did_not_declare_it(tmp_path: Path) -> None:
    """The opt-in is immutable: a study that wants the store declares it at init."""
    repo = _repo(tmp_path)
    study = _scaffold(repo, "03-alpha")
    assert _gen("init", "--study", str(study)) == 0
    assert _gen("knowledge", "query", "--study", str(study), "--text", "anything") == 1
    assert _gen("knowledge", "show", "--study", str(study)) == 0


def test_the_capability_is_registered_and_declarable() -> None:
    """The spine reaches this package by REGISTRATION, not by a branch."""
    from kleinlib.generation.capabilities import load
    from kleinlib.generation.manifest import KNOWN_CAPABILITIES, SUPPORTED_CAPABILITIES

    assert "knowledge" in KNOWN_CAPABILITIES
    assert "knowledge" in SUPPORTED_CAPABILITIES
    assert load()["knowledge"] is gk.CAPABILITY
    assert gk.CAPABILITY.verify_family is not None
    # Consulting the store is a CONSULT-time obligation, not a per-action one.
    assert gk.CAPABILITY.admission_rules == ()


def test_the_store_is_repo_level_and_never_rewrites_the_markdown(store) -> None:
    """The markdown convention stays the human surface, untouched by every verb."""
    repo = store["repo"]
    assert (repo / "knowledge" / "objects").is_dir()
    assert (repo / "knowledge" / "events.jsonl").is_file()
    assert not list((repo / "knowledge").glob("*.md"))
    # and the package never reaches for a model or the network
    source = (REPO_ROOT / "kleinlib" / "generation" / "knowledge.py").read_text(encoding="utf-8")
    for forbidden in ("requests", "httpx", "urllib.request", "anthropic", "openai", "socket"):
        assert forbidden not in source, forbidden


# --------------------------------------------------------------------------
# the fix pass: the tip is anchored, and a promotion resolves or fails
# --------------------------------------------------------------------------


def test_c3_an_event_removed_from_the_tip_is_caught_by_the_stores_own_history(
    store,
) -> None:
    """The hash chain cannot see a deleted LAST line — every event still verifies.

    Valid control: the store after a contest verifies.  Invalid control: the
    same store with that contest's line dropped.  Nothing inside the file
    objects; the previous state of the file, in git, does.
    """
    repo, alpha = store["repo"], store["alpha"]
    assert _contest(store) == 0
    assert _gen("verify", "--study", str(alpha)) == 0

    path = gk.events_path(repo)
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    # the truncated chain is internally perfect
    assert gk.store_chain_problems(gk.snapshot_on_disk(repo).events) == []

    assert _gen("verify", "--study", str(alpha)) == 2
    assert "events removed from the tip" in _details(_receipt(alpha), "knowledge store")


def test_c5_a_promotion_whose_commit_does_not_resolve_is_checked_on_disk(store) -> None:
    """`commit: null` used to buy a WARN and skip the strengthening check."""
    repo, alpha = store["repo"], store["alpha"]
    snapshot = gk.snapshot_on_disk(repo)
    obj = dict(snapshot.objects["K1"])
    obj["commit"] = None

    def _rewrite(payload: dict[str, Any]) -> None:
        # content-addressed: the store keeps exactly ONE K1 file, named after its
        # own bytes, and the transaction that references it is repointed by
        # target — so only the promotion check has anything to say
        from kleinlib.primitives import canonical_json, sha256_bytes

        text = canonical_json(payload) + "\n"
        sha = sha256_bytes(text.encode())
        for existing in gk.objects_dir(repo).glob("*.json"):
            if json.loads(existing.read_text(encoding="utf-8")).get("id") == "K1":
                existing.unlink()
        (gk.objects_dir(repo) / f"{sha}.json").write_text(text, encoding="utf-8")
        events = gk.events_path(repo)
        rows = [json.loads(line) for line in events.read_text(encoding="utf-8").splitlines() if line.strip()]
        for row in rows:
            if row.get("target") == "K1":
                row["object_sha"] = sha
        events.write_text(
            "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
            encoding="utf-8",
        )

    _rewrite(obj)
    # valid control: no commit to resolve, so the source lock ON DISK is read
    # and the promotion still checks out (the store's own chain complains about
    # the hand edit, as it does for every rewritten object; the promotion does not)
    _gen("verify", "--study", str(alpha))
    assert "in the working tree" in _details(_receipt(alpha), "knowledge promotions")
    assert "PASS" in _statuses(_receipt(alpha), "knowledge promotions")

    # invalid control: the same unresolvable commit, now with a strengthened copy
    obj["strength"] = "confirmed"
    _rewrite(obj)
    assert _gen("verify", "--study", str(alpha)) == 2
    assert "never strengthens it" in _details(_receipt(alpha), "knowledge promotions")


def test_c7_an_unreplayable_receipt_fails_when_the_store_is_in_this_repo(store) -> None:
    """WARN is for a reader in the wrong clone, not for a receipt that lies."""
    repo, alpha = store["repo"], store["alpha"]
    assert gk.store_is_local(repo)

    path, obj = _query_object(alpha)
    obj["store_head"] = "0" * 40
    path.write_text(json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")

    assert _gen("verify", "--study", str(alpha)) == 2
    assert "FAIL" in _statuses(_receipt(alpha), "knowledge replay")
    assert "does not resolve here" in _details(_receipt(alpha), "knowledge replay")


def test_c7_a_checkout_without_the_store_only_warns(store, tmp_path: Path) -> None:
    """The same symptom in a clone that has no knowledge/ tree stays a WARN."""
    repo, alpha = store["repo"], store["alpha"]
    path, obj = _query_object(alpha)
    obj["retriever_version"] = "lex-99"
    path.write_text(json.dumps(obj, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    assert _gen("verify", "--study", str(alpha)) == 2
    assert "FAIL" in _statuses(_receipt(alpha), "knowledge replay")

    import shutil

    shutil.rmtree(repo / "knowledge")
    assert not gk.store_is_local(repo)
    assert _gen("verify", "--study", str(alpha)) in (0, 2)
    assert "WARN" in _statuses(_receipt(alpha), "knowledge replay")
    assert "carries no knowledge/ store" in _details(_receipt(alpha), "knowledge replay")
