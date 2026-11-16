"""``klein generation benchmark …`` (the ``benchmark`` capability): the planted-truth benchmark verbs.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from ...errors import WorkflowError
from ._shared import (
    _error,
    _load,
    _refuse,
    _require_capability,
    _require_clean,
    _require_healthy_ledger,
    _study,
    _study_relative_file,
    _testimony,
    _testimony_fields,
)


def register(actions: argparse._SubParsersAction) -> None:
    """``klein generation benchmark commit|submit|reveal|retire|show``.

    Argparse only, like every other group here: the handlers import
    ``kleinlib.generation.benchmark`` lazily, so a study that never declares
    ``benchmark`` never loads a line of it.  Every verb runs in the CUSTODIAN's
    study; a participant's study declares no benchmark capability at all.
    """
    benchmark = actions.add_parser(
        "benchmark",
        help="the custodian's planted-truth benchmark: commit, import, reveal",
        description=(
            "Commit to a salted private bundle before any participant sees the public "
            "one; import each arm's frozen submission; reveal the bundle once every arm "
            "has submitted or has a recorded missing trial; score all arms in ONE sealed "
            "registered cell. A hash is not secrecy: isolation is accounts, containers or "
            "machines, and the only record of it is `klein generation custody attest`. See "
            ".claude/skills/klein/references/planted-truth-protocol.md."
        ),
    )
    benchmark_actions = benchmark.add_subparsers(dest="benchmark_action", required=True)

    commit = benchmark_actions.add_parser(
        "commit", help="freeze benchmark.yaml and record the salted commitment"
    )
    _study(commit)
    _testimony(commit)
    commit.add_argument(
        "--private",
        required=True,
        metavar="PATH",
        help="the private bundle (file or directory) — normally OUTSIDE this repository",
    )
    commit.add_argument(
        "--salt-file",
        required=True,
        metavar="PATH",
        help="the salt; its bytes are hashed into the commitment and never stored here",
    )
    commit.set_defaults(handler=_run_benchmark_commit)

    submit = benchmark_actions.add_parser(
        "submit", help="import one arm's frozen submission (before the reveal)"
    )
    _study(submit)
    _testimony(submit)
    submit.add_argument("--arm", required=True, help="the arm id declared in benchmark.yaml")
    submit.add_argument(
        "--file", required=True, metavar="PATH", help="the participant's frozen submission JSON"
    )
    submit.set_defaults(handler=_run_benchmark_submit)

    reveal = benchmark_actions.add_parser(
        "reveal", help="disclose the private bundle and recompute the commitment"
    )
    _study(reveal)
    _testimony(reveal)
    reveal.add_argument(
        "--private",
        required=True,
        metavar="PATH",
        help="the disclosed bundle, now INSIDE the study and committed to git",
    )
    reveal.add_argument(
        "--salt-file", required=True, metavar="PATH", help="the same salt the commitment used"
    )
    reveal.add_argument(
        "--missing-arm",
        nargs=2,
        action="append",
        default=[],
        metavar=("ARM", "REASON"),
        help="record an arm that never submitted as a missing trial (repeatable); it stays "
        "in the denominator",
    )
    reveal.set_defaults(handler=_run_benchmark_reveal)

    retire = benchmark_actions.add_parser(
        "retire", help="retire a leaked benchmark from hidden evaluation; results are retained"
    )
    _study(retire)
    _testimony(retire)
    retire.add_argument(
        "--reason", required=True, help="what leaked, to whom, and how it was discovered"
    )
    retire.set_defaults(handler=_run_benchmark_retire)

    show = benchmark_actions.add_parser(
        "show", help="read-only: the commitment, the submissions, the reveal"
    )
    _study(show)
    show.set_defaults(handler=_run_benchmark_show)


def _benchmark_setup(
    args: argparse.Namespace, *, extra: tuple[str, ...] = ()
) -> tuple[Path, dict[str, Any], Path, list[dict[str, Any]]]:
    """Preconditions shared by every benchmark verb.  Raises ``WorkflowError``."""
    from ..chronology import repo_for
    from ..ledger import read_events

    study, contract = _load(args)
    _require_capability(study, "benchmark")
    _require_healthy_ledger(study)
    _require_clean(study, contract, *extra)
    repo = repo_for(study)
    assert repo is not None  # _require_clean already refused a non-repo
    return study, contract, repo, read_events(study)


def _outside_bundle(raw: str) -> Path:
    """A bundle path anywhere on disk — the private one usually is not in the repo."""
    path = Path(raw).expanduser()
    if not path.exists():
        raise WorkflowError(f"{raw!r} does not exist")
    return path


def _run_benchmark_commit(args: argparse.Namespace) -> int:
    from ...primitives import sha256_bytes, sha256_file
    from .. import benchmark as gb
    from .. import manifest as gm
    from ..admission import core_anchor
    from ..chronology import gate_events, git_head, read_core_events
    from ..ledger import append_event, commit_artifacts, write_object

    try:
        study, contract, repo, events = _benchmark_setup(
            args, extra=(gb.BENCHMARK_NAME, gb.SCHEMA_NAME)
        )
        payload = gb.read_benchmark_file(study)
    except WorkflowError as exc:
        return _error(str(exc))

    if gb.commits(study, events):
        return _error(
            f"{gb.BENCHMARK_NAME} is already committed — a benchmark commits ONCE, and the "
            "terms are frozen from that moment"
        )
    filed = sorted((study / gb.SUBMISSIONS_DIR).glob("*.json"))
    if filed:
        return _error(
            "submission file(s) already exist ("
            + ", ".join(path.name for path in filed)
            + f"): {gb.SUBMISSIONS_DIR}/ is written by `benchmark submit`, and a commitment "
            "recorded after an answer arrived commits to nothing"
        )
    if not gate_events(read_core_events(study), "method"):
        return _refuse(
            "the METHOD gate is not recorded: the matching rule and the scorer are frozen "
            "at METHOD, before any arm sees the data, so committing first would "
            "pin a checker the gate never hashed"
        )

    study_name = gm.study_id(study, contract)
    problems = gb.validation_problems(payload, study=study_name, contract=contract)
    if problems:
        print("benchmark commit refused:")
        for problem in problems:
            print(f"  - {problem}")
        return 2

    try:
        # Reading the bundles: `--salt-file`, `--private` and the paths
        # benchmark.yaml names.  A file that cannot be read is exit 1 — the
        # commitment question was never asked, so nothing was answered.
        public = dict(payload["public_bundle"])
        public_sha = sha256_bytes(gb.bundle_bytes(study / str(public["path"])))
        salt = gb.read_salt(_outside_bundle(args.salt_file))
        commitment = gb.commitment_of(salt, gb.bundle_bytes(_outside_bundle(args.private)))
        scorer_path, scorer_sha = _study_relative_file(
            study, str(payload["scorer"]["path"]), label="scorer.path"
        )
    except (WorkflowError, KeyError, TypeError) as exc:
        return _error(str(exc))
    salt_sha = sha256_bytes(salt)

    declared = public.get("sha256")
    if isinstance(declared, str) and declared != public_sha:
        return _refuse(
            f"public_bundle.sha256 declares {declared[:12]}… but {public['path']} hashes to "
            f"{public_sha[:12]}… — leave it null and let the commitment compute it"
        )
    pinned = payload.get("private_commitment")
    if isinstance(pinned, dict):
        for key, actual in (("sha256", commitment), ("salt_sha256", salt_sha)):
            told = pinned.get(key)
            if isinstance(told, str) and told != actual:
                return _refuse(
                    f"private_commitment.{key} declares {told[:12]}… but the salt and the "
                    f"bundle give {actual[:12]}…"
                )

    schema_rel = str(payload["submission_schema"])
    schema_file = study / schema_rel
    copied = False
    if not schema_file.is_file():
        source = gb.packaged_schema(repo)
        if source is None:
            return _error(
                f"{schema_rel} does not exist and this install carries no packaged "
                f"{gb.SCHEMA_NAME}; copy the participant-facing schema into the study first"
            )
        schema_file.parent.mkdir(parents=True, exist_ok=True)
        schema_file.write_bytes(source.read_bytes())
        copied = True
    schema_sha = sha256_file(schema_file)
    file_sha = sha256_file(gb.benchmark_path(study))

    obj = gb.commit_object(
        study=study_name,
        payload=payload,
        file_sha256=file_sha,
        public_bundle={"path": str(public["path"]), "sha256": public_sha},
        private_commitment={"sha256": commitment, "salt_sha256": salt_sha},
        scorer={"path": scorer_path, "sha256": scorer_sha},
        submission_schema={"path": schema_rel, "sha256": schema_sha},
    )
    sha = write_object(study, obj)
    event = append_event(
        study,
        gb.COMMIT_TYPE,
        study=study_name,
        core_anchor=core_anchor(study),
        git_head=git_head(repo),
        payload_sha256=sha,
        testimony_fields=_testimony_fields(args),
        file_sha256=file_sha,
        commitment=commitment,
        arms=len(gb.arm_ids(payload)),
    )
    commit_artifacts(
        study,
        f"klein: benchmark commit ({study_name}, {len(gb.arm_ids(payload))} arm(s))",
        paths=[gb.BENCHMARK_NAME, schema_rel, "generation/events.jsonl", "generation/objects"],
    )
    print(
        f"{event['id']} benchmark commit: {gb.BENCHMARK_NAME} {file_sha[:12]}…, "
        f"object {sha[:12]}…"
    )
    print(f"  public bundle {public['path']}: {public_sha[:12]}…")
    print(f"  private commitment: {commitment[:12]}… (salt {salt_sha[:12]}…)")
    print(f"  scorer {scorer_path}: {scorer_sha[:12]}…")
    print(f"  submission schema {schema_rel}: {schema_sha[:12]}…" + (" (copied)" if copied else ""))
    for arm in gb.arm_ids(payload):
        print(f"  - arm {arm}")
    print(
        "the salt is NOT in this repository; `benchmark reveal` needs it again. A hash is "
        "not secrecy: record custody with `klein generation custody attest`."
    )
    return 0


def _run_benchmark_submit(args: argparse.Namespace) -> int:
    from ...primitives import sha256_bytes
    from .. import benchmark as gb
    from .. import manifest as gm
    from ..admission import core_anchor
    from ..chronology import git_head
    from ..ledger import append_event, commit_artifacts, write_object

    arm = str(args.arm)
    destination = f"{gb.SUBMISSIONS_DIR}/{arm}.json"
    try:
        study, contract, repo, events = _benchmark_setup(args, extra=(destination,))
    except WorkflowError as exc:
        return _error(str(exc))

    locked = gb.commits(study, events)
    if not locked:
        return _error(
            "there is no commitment yet: `klein generation benchmark commit` records the "
            "terms before any arm's answer is imported"
        )
    if gb.reveals(study, events):
        return _refuse(
            f"the bundle is already revealed — importing {arm!r} now would import an answer "
            "written after the truth was disclosed"
        )
    payload = locked[-1][1].get("payload") or {}
    if arm not in gb.arm_ids(payload):
        return _error(
            f"the benchmark declares no arm {arm!r} (declared: "
            + (", ".join(gb.arm_ids(payload)) or "none")
            + ")"
        )
    existing = [
        str(obj.get("arm")) for _event, obj in gb.submissions(study, events)
    ]
    if arm in existing:
        return _error(
            f"arm {arm!r} has already submitted; a submission is frozen and is never replaced"
        )

    source = Path(args.file).expanduser()
    if not source.is_file():
        return _error(f"--file {args.file!r} does not exist")
    try:
        submission = gb.read_submission(source)
    except WorkflowError as exc:
        return _error(str(exc))
    cap = payload.get("hypothesis_cap")
    problems = gb.submission_problems(
        submission, arm=arm, cap=cap if isinstance(cap, int) and not isinstance(cap, bool) else 0
    )
    if problems:
        print(f"benchmark submit refused for arm {arm}:")
        for problem in problems:
            print(f"  - {problem}")
        return 2

    raw = source.read_bytes()
    target = study / destination
    target.parent.mkdir(parents=True, exist_ok=True)
    # The participant's OWN bytes, not a re-serialization: the hash the custodian
    # records has to be the hash the participant can compute on their own file.
    target.write_bytes(raw)
    file_sha = sha256_bytes(raw)

    study_name = gm.study_id(study, contract)
    count = len(submission.get("structures") or [])
    obj = gb.submission_object(
        study=study_name,
        arm=arm,
        commit_sha=str(locked[-1][0].get("payload_sha256")),
        file_path=destination,
        file_sha256=file_sha,
        structures=count,
        participant=str(submission.get("study")) if submission.get("study") else None,
    )
    sha = write_object(study, obj)
    event = append_event(
        study,
        gb.SUBMIT_TYPE,
        study=study_name,
        core_anchor=core_anchor(study),
        git_head=git_head(repo),
        payload_sha256=sha,
        parent_ids=[str(locked[-1][0].get("id"))],
        testimony_fields=_testimony_fields(args),
        arm=arm,
        file_sha256=file_sha,
        structures=count,
    )
    commit_artifacts(
        study,
        f"klein: benchmark submit {arm} ({study_name}, {count} structure(s))",
        paths=[destination, "generation/events.jsonl", "generation/objects"],
    )
    print(
        f"{event['id']} benchmark submit {arm}: {destination} {file_sha[:12]}…, "
        f"{count} structure(s) of at most {cap}, object {sha[:12]}…"
    )
    outstanding = [name for name in gb.arm_ids(payload) if name not in {*existing, arm}]
    print(
        "outstanding arms: " + (", ".join(outstanding) if outstanding else "none — reveal next")
    )
    return 0


def _run_benchmark_reveal(args: argparse.Namespace) -> int:
    from ...primitives import sha256_bytes, sha256_file
    from .. import benchmark as gb
    from .. import manifest as gm
    from ..admission import core_anchor
    from ..chronology import git_head
    from ..ledger import append_event, commit_generation, write_object

    try:
        study, contract, repo, events = _benchmark_setup(args)
    except WorkflowError as exc:
        return _error(str(exc))

    locked = gb.commits(study, events)
    if not locked:
        return _error("there is no commitment to reveal against")
    if gb.reveals(study, events):
        return _error("the bundle is already revealed; disclosure happens once")
    commit_event, commit_obj = locked[-1]
    payload = commit_obj.get("payload") or {}

    declared = gb.arm_ids(payload)
    submitted = [str(obj.get("arm")) for _event, obj in gb.submissions(study, events)]
    missing = {str(arm): str(reason) for arm, reason in args.missing_arm}
    for arm in missing:
        if arm not in declared:
            return _error(f"--missing-arm names {arm!r}, which the benchmark does not declare")
        if arm in submitted:
            return _error(f"--missing-arm names {arm!r}, which HAS submitted")
    gap = [arm for arm in declared if arm not in submitted and arm not in missing]
    if gap:
        return _refuse(
            "arm(s) "
            + ", ".join(gap)
            + " have not submitted: every arm submits before the reveal, or its missing "
            "trial is recorded with `--missing-arm <arm> <reason>` and stays in the "
            "denominator (reveal_policy: after-all-arms)"
        )

    try:
        salt = gb.read_salt(_outside_bundle(args.salt_file))
        bundle = Path(args.private).expanduser()
        bundle_rel = _inside_study(study, bundle, label="--private")
        commitment = gb.commitment_of(salt, gb.bundle_bytes(bundle))
    except WorkflowError as exc:
        return _error(str(exc))
    salt_sha = sha256_bytes(salt)
    pinned = commit_obj.get("private_commitment") or {}
    matched = commitment == pinned.get("sha256") and salt_sha == pinned.get("salt_sha256")

    study_name = gm.study_id(study, contract)
    missing_rows = [{"arm": arm, "reason": reason} for arm, reason in sorted(missing.items())]
    truth: dict[str, Any] = {}
    if matched:
        truth_rel = str(payload.get("truth_file"))
        truth_path = study / truth_rel
        if not truth_path.is_file():
            return _error(
                f"the revealed bundle does not carry {truth_rel} — benchmark.yaml's "
                "truth_file names the structural truth INSIDE the private bundle, and the "
                "scoring cell reads exactly those bytes"
            )
        if not _within(truth_path, bundle):
            return _refuse(
                f"{truth_rel} is not inside the revealed bundle {bundle_rel} — a truth file "
                "outside the commitment is a truth file the commitment never covered"
            )
        truth = {"path": truth_rel, "sha256": sha256_file(truth_path)}

    obj = gb.reveal_object(
        study=study_name,
        commit_sha=str(commit_event.get("payload_sha256")),
        commitment=commitment,
        salt_sha256=salt_sha,
        private_bundle={"path": bundle_rel, "sha256": sha256_bytes(gb.bundle_bytes(bundle))},
        truth=truth,
        missing_arms=missing_rows,
        matched=matched,
    )
    sha = write_object(study, obj)
    event = append_event(
        study,
        gb.REVEAL_TYPE if matched else gb.REVEAL_FAILED_TYPE,
        study=study_name,
        core_anchor=core_anchor(study),
        git_head=git_head(repo),
        payload_sha256=sha,
        parent_ids=[str(commit_event.get("id"))],
        testimony_fields=_testimony_fields(args),
        commitment=commitment,
        matched=matched,
        arms=len(submitted),
        missing=len(missing_rows),
    )
    commit_generation(
        study,
        f"klein: benchmark reveal ({study_name}, {'matched' if matched else 'MISMATCH'})",
        paths=("generation/events.jsonl", "generation/objects"),
    )
    if not matched:
        print(
            f"{event['id']} benchmark reveal REFUSED and RECORDED: the bundle hashes to "
            f"{commitment[:12]}… under this salt, but the commitment is "
            f"{str(pinned.get('sha256'))[:12]}… — the bundle disclosed is not the bundle "
            "committed to, and `generation verify` will FAIL `benchmark commitment` from "
            "here on"
        )
        return 2
    print(
        f"{event['id']} benchmark reveal: {bundle_rel} recomputes to the commitment "
        f"{commitment[:12]}…, object {sha[:12]}…"
    )
    print(f"  truth: {truth['path']} {truth['sha256'][:12]}…")
    print(f"  submitted arms: {', '.join(sorted(submitted)) or 'none'}")
    for row in missing_rows:
        print(f"  missing trial {row['arm']}: {row['reason']}")
    print(
        "the scoring track's seal is now admissible: one sealed registered cell scores "
        "every arm"
    )
    return 0


def _inside_study(study: Path, path: Path, *, label: str) -> str:
    """The study-relative POSIX path of something that must live in the study."""
    if not path.exists():
        raise WorkflowError(f"{label} {str(path)!r} does not exist")
    try:
        return path.resolve().relative_to(study.resolve()).as_posix()
    except ValueError as exc:
        raise WorkflowError(
            f"{label} {str(path)!r} is outside the study — a reveal DISCLOSES the bundle "
            "into the record, so the bytes the scoring cell reads are the bytes a reader "
            "can hash"
        ) from exc


def _within(path: Path, bundle: Path) -> bool:
    resolved, root = path.resolve(), bundle.resolve()
    return resolved == root or root in resolved.parents


def _run_benchmark_retire(args: argparse.Namespace) -> int:
    from .. import benchmark as gb
    from .. import manifest as gm
    from ..admission import core_anchor
    from ..chronology import git_head
    from ..ledger import append_event, commit_generation, write_object

    try:
        study, contract, repo, events = _benchmark_setup(args)
    except WorkflowError as exc:
        return _error(str(exc))
    locked = gb.commits(study, events)
    if not locked:
        return _error("there is no committed benchmark to retire")
    if gb.joined(study, events, gb.RETIRE_TYPE):
        return _error("this benchmark is already retired")
    if not str(args.reason).strip():
        return _error("--reason is required: what leaked, to whom, and how it was discovered")

    study_name = gm.study_id(study, contract)
    obj = gb.retire_object(
        study=study_name,
        commit_sha=str(locked[-1][0].get("payload_sha256")),
        reason=str(args.reason).strip(),
    )
    sha = write_object(study, obj)
    event = append_event(
        study,
        gb.RETIRE_TYPE,
        study=study_name,
        core_anchor=core_anchor(study),
        git_head=git_head(repo),
        payload_sha256=sha,
        parent_ids=[str(locked[-1][0].get("id"))],
        testimony_fields=_testimony_fields(args),
        reason=str(args.reason).strip(),
    )
    commit_generation(
        study,
        f"klein: benchmark retire ({study_name})",
        paths=("generation/events.jsonl", "generation/objects"),
    )
    print(f"{event['id']} benchmark retired: {args.reason}")
    print(
        "the results are RETAINED and stay readable; the benchmark is simply never used as "
        "a hidden benchmark again"
    )
    return 0


def _run_benchmark_show(args: argparse.Namespace) -> int:
    from .. import benchmark as gb
    from .. import custody as gc
    from ..ledger import read_events

    try:
        study, _contract = _load(args)
        _require_capability(study, "benchmark")
        events = read_events(study)
    except WorkflowError as exc:
        return _error(str(exc))

    locked = gb.commits(study, events)
    if not locked:
        print("benchmark: nothing committed")
        return 0
    event, obj = locked[-1]
    payload = obj.get("payload") or {}
    print(
        f"{event.get('id')} commitment {str((obj.get('private_commitment') or {}).get('sha256'))[:12]}…"
        f" ({gb.BENCHMARK_NAME} {str(obj.get('file_sha256'))[:12]}…)"
    )
    print(f"  scoring track: {payload.get('scoring_track')}")
    print(f"  cap: {payload.get('hypothesis_cap')}, penalty: {payload.get('false_positive_penalty')}")
    blocks = payload.get("seed_blocks") or {}
    print(f"  seed blocks: development {blocks.get('development')} / sealed {blocks.get('sealed')}")
    for row in gb.submissions(study, events):
        print(
            f"  {row[0].get('id')} submit {row[1].get('arm')}: "
            f"{row[1].get('structures')} structure(s), {str(row[1].get('file_sha256'))[:12]}…"
        )
    for name in gb.arm_ids(payload):
        if name not in {str(obj.get("arm")) for _e, obj in gb.submissions(study, events)}:
            print(f"  {name}: not submitted")
    for row in gb.reveals(study, events):
        print(f"  {row[0].get('id')} revealed: truth {(row[1].get('truth') or {}).get('path')}")
        for missing in row[1].get("missing_arms") or ():
            print(f"    missing trial {missing.get('arm')}: {missing.get('reason')}")
    for row in gb.joined(study, events, gb.REVEAL_FAILED_TYPE):
        print(f"  {row[0].get('id')} reveal FAILED: the bundle is not the one committed to")
    for row in gb.joined(study, events, gb.RETIRE_TYPE):
        print(f"  {row[0].get('id')} retired: {row[1].get('reason')}")
    attested = gc.attestations(study, events)
    print(f"  custody: {gc.custody_state(attested)} ({', '.join(gc.holders(attested)) or 'nobody attested'})")
    return 0
