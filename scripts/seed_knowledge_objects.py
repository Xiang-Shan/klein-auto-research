#!/usr/bin/env python3
"""One-off: seed ``knowledge/objects/`` from the markdown that is already there.

`knowledge/` has carried typed claim citations since v1 — ``(supports
09-iris-first-lesson#C3)`` in the prose, and an optional ``claims:`` list in the
frontmatter.  Those citations already say which claims the framework's durable
lessons lean on; this script turns each of them into a store object so a later
study's ``klein generation knowledge query`` can find them.

Three promises, in order of importance:

1. **No markdown is ever written.**  Every ``knowledge/**/*.md`` file is opened
   read-only.  The markdown convention stays the human surface; the store is a
   second surface beside it, not a replacement for it.
2. **Dry-run by default.**  With no ``--apply`` the script prints exactly what it
   would write and exits 0 having touched nothing.
3. **Only verified claims are seeded.**  Each cited study's ``claims.lock`` must
   pass ``klein claims verify`` NOW; a study whose lock does not verify is
   reported and skipped, never seeded on the strength of its own citation.

``class``, ``strength`` and the claim's ``evidence`` are copied verbatim — a
seeded object is exactly as strong as the claim it names — and objects are
deduplicated by EVIDENCE ROOTS, so one lesson repeated across three documents
seeds one object, not three.

**Scope tags are a human curation step and are deliberately left empty.**  A3 §5
scopes an object by population, measurement regime, intervention, assumptions and
exclusions; nothing in a markdown citation says any of those, and inventing them
is precisely the failure the store exists to prevent.  Fill them by hand
afterwards (a corrected object is a NEW promotion, not an edit).

Usage::

    uv run --locked python scripts/seed_knowledge_objects.py            # dry run
    uv run --locked python scripts/seed_knowledge_objects.py --apply    # writes

``--apply`` writes ``knowledge/objects/<sha>.json`` and appends one ``promote``
transaction each to ``knowledge/events.jsonl``.  It does NOT commit: it prints
the exact ``git add -- …`` command, because a one-off ops script should not be
the thing that decides what enters the history.  Each object records the HEAD it
read its source lock at, which is what lets ``klein generation verify`` resolve
the promotion later and check that nothing was strengthened on the way in.

Exit codes: 0 ok (including a dry run), 1 nothing to seed or a usage problem.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from kleinlib.claims import (  # noqa: E402
    claims_map,
    detect_lock_schema,
    load_lock,
    verify_lock,
)
from kleinlib.errors import WorkflowError  # noqa: E402
from kleinlib.generation import knowledge as gk  # noqa: E402
from kleinlib.generation.chronology import git_head  # noqa: E402
from kleinlib.primitives import sha256_file  # noqa: E402

CITATION_RE = re.compile(r"\((?:supports|refutes) (?P<study>[0-9a-z][0-9a-z-]*)#(?P<claim>C\d+)\)")
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)


def frontmatter(text: str) -> dict[str, Any]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return {}
    try:
        value = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return {}
    return value if isinstance(value, dict) else {}


def citations(doc: Path) -> tuple[dict[str, Any], list[tuple[str, str]]]:
    """``(frontmatter, [(study, claim id)])`` for one knowledge document.

    Both surfaces are read: the inline typed citations the promotion rule
    already requires, and the optional ``claims:`` frontmatter list.
    """
    text = doc.read_text(encoding="utf-8")
    front = frontmatter(text)
    found: list[tuple[str, str]] = []
    for match in CITATION_RE.finditer(text):
        found.append((match.group("study"), match.group("claim")))
    for entry in front.get("claims") or ():
        if isinstance(entry, str) and "#" in entry:
            study, _, claim = entry.partition("#")
            if re.fullmatch(r"C\d+", claim):
                found.append((study, claim))
    ordered: list[tuple[str, str]] = []
    for pair in found:
        if pair not in ordered:
            ordered.append(pair)
    return front, ordered


def tags_for(doc: Path, front: dict[str, Any]) -> list[str]:
    """Retrieval tags from what the document already declares about itself."""
    tags = {str(item) for item in (front.get("concepts") or []) if isinstance(item, str)}
    for key in ("domain", "type"):
        value = front.get(key)
        if isinstance(value, str) and value.strip():
            tags.add(value.strip())
    tags.add(doc.parent.name)
    return sorted(tag.casefold() for tag in tags if tag)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--apply",
        action="store_true",
        help="write the objects and transactions (default: print them and exit)",
    )
    parser.add_argument(
        "--repo", default=str(REPO_ROOT), help="repository root (default: this checkout)"
    )
    parser.add_argument("--actor", help="who ran the seeding (testimony, not authenticated)")
    args = parser.parse_args(argv)

    repo = Path(args.repo).resolve()
    docs = sorted((repo / "knowledge").rglob("*.md"))
    if not docs:
        print(f"no markdown under {repo / 'knowledge'}", file=sys.stderr)
        return 1

    snapshot = gk.snapshot_on_disk(repo)
    # Every object names the commit its source lock was read at.  Without one,
    # `klein generation verify` has nothing to resolve the promotion against and
    # a seeded object would be exempt from the strengthening check forever.
    head = git_head(repo)
    if head is None:
        print(f"{repo} is not a git repository with a resolvable HEAD", file=sys.stderr)
        return 1
    planned: list[tuple[dict[str, Any], Path]] = []
    skipped: list[str] = []
    verified: dict[str, bool] = {}

    for doc in docs:
        front, pairs = citations(doc)
        for study_name, claim_id in pairs:
            study_dir = repo / "studies" / study_name
            if not (study_dir / "claims.lock").is_file():
                skipped.append(f"{doc.name}: {study_name}#{claim_id} — no claims.lock")
                continue
            if study_name not in verified:
                try:
                    verified[study_name] = all(check.ok for check in verify_lock(study_dir))
                except WorkflowError as exc:
                    verified[study_name] = False
                    skipped.append(f"{study_name}: lock unreadable ({exc})")
            if not verified[study_name]:
                skipped.append(f"{doc.name}: {study_name}#{claim_id} — lock does not verify")
                continue
            lock = load_lock(study_dir)
            schema = detect_lock_schema(lock)
            if schema < 2:
                # A schema-1 lock's `claims` map IS its numbers ledger: it has no
                # claim sentences to promote, only pinned values.
                skipped.append(f"{doc.name}: {study_name}#{claim_id} — lock schema 1")
                continue
            entry = claims_map(lock, schema).get(claim_id)
            if not isinstance(entry, dict):
                skipped.append(f"{doc.name}: {study_name}#{claim_id} — not in the lock")
                continue
            roots = [str(item) for item in (entry.get("evidence") or [])]
            duplicate = gk.duplicate_of(snapshot, roots) or _planned_duplicate(planned, roots)
            if duplicate:
                skipped.append(
                    f"{doc.name}: {study_name}#{claim_id} — same evidence roots as {duplicate}"
                )
                continue
            obj = gk.build_object(
                object_id=_next_id(snapshot, planned),
                object_type="claim",
                origin_repo="local",
                study=study_name,
                commit=head,
                lock_git_head=lock.get("git_head"),
                source_path=f"studies/{study_name}/claims.lock",
                source_hash=sha256_file(study_dir / "claims.lock"),
                claim_id=f"{study_name}#{claim_id}",
                text=str(entry.get("claim") or ""),
                claim_class=entry.get("class"),
                strength=entry.get("strength"),
                scope={},
                tags=tags_for(doc, front),
                evidence_roots=roots,
            )
            problems = gk.object_problems(obj)
            if problems:
                skipped.append(f"{doc.name}: {study_name}#{claim_id} — {'; '.join(problems)}")
                continue
            planned.append((obj, doc))

    for obj, doc in planned:
        print(
            f"{obj['id']} <- {obj['claim_id']} ({obj['class']}, {obj['strength']}) "
            f"cited by {doc.relative_to(repo)}"
        )
        print(f"    roots: {', '.join(obj['evidence_roots'])}")
        print(f"    tags:  {', '.join(obj['tags'])}")
    for line in skipped:
        print(f"skip {line}")
    if not planned:
        print("nothing to seed")
        return 1
    if not args.apply:
        print(f"\ndry run: {len(planned)} object(s) would be written; re-run with --apply")
        return 0

    written: list[str] = []
    for obj, _doc in planned:
        sha = gk.write_store_object(repo, obj)
        gk.append_store_event(
            repo,
            "promote",
            target=str(obj["id"]),
            study=str(obj["study"]),
            object_sha=sha,
            evidence_ids=list(obj["evidence_roots"]),
            rationale="seeded from an existing knowledge/ citation",
            testimony_fields={"actor": args.actor, "tool": "seed_knowledge_objects.py"},
        )
        written.append(f"{gk.OBJECTS_REL}/{sha}.json")
    print(f"\nwrote {len(written)} object(s). Nothing was committed; file them with:")
    print("  git add -- " + " ".join([*written, gk.EVENTS_REL]))
    print("  git commit -m 'knowledge: seed objects from existing citations'")
    print("Scope fields are EMPTY by design — curate them by hand before relying on them.")
    return 0


def _planned_duplicate(
    planned: list[tuple[dict[str, Any], Path]], roots: list[str]
) -> str | None:
    key = gk.evidence_key(roots)
    for obj, _doc in planned:
        if gk.evidence_key(obj["evidence_roots"]) == key:
            return str(obj["id"])
    return None


def _next_id(snapshot: gk.Snapshot, planned: list[tuple[dict[str, Any], Path]]) -> str:
    highest = max(
        [int(str(object_id)[1:]) for object_id in snapshot.objects]
        + [int(str(obj["id"])[1:]) for obj, _doc in planned],
        default=0,
    )
    return f"K{highest + 1}"


if __name__ == "__main__":  # pragma: no cover - exercised as a CLI
    raise SystemExit(main())
