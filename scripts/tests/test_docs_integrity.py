"""Docs-integrity guard: the normative markdown stays consistent with itself.

Klein's protocols are the source of truth and are read by agents verbatim, so the
usual drift failures (a protocol renamed but still referenced, a worker agent listed
with the wrong model, four copies of the lifecycle string that no longer agree, a
war-story count that stopped matching the stories) must fail a test, not a reader.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_DIR = REPO_ROOT / ".claude" / "skills" / "klein"
REFERENCES = SKILL_DIR / "references"
ASSETS = SKILL_DIR / "assets"
AGENTS_DIR = REPO_ROOT / ".claude" / "agents"

LIFECYCLE = (
    "new ─▶ CONSULT ─▶ DATA ─▶ METHOD ═══▶ EXPERIMENT/SWEEP ─▶ SYNTHESIZE ─▶ REFEREE ─▶ TUTORIAL\n"
    "        Gate 0   Gate 1   Gate 2      └ the honest loop ┘    findings.md    Gate 3     report/"
)
LIFECYCLE_COPIES = (
    REPO_ROOT / "AGENTS.md",
    SKILL_DIR / "SKILL.md",
    REPO_ROOT / "README.md",
    REPO_ROOT / "docs" / "diagrams" / "src" / "lifecycle.py",
)

NORMATIVE_MD = [
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "CLAUDE.md",
    REPO_ROOT / "README.md",
    SKILL_DIR / "SKILL.md",
    *sorted(REFERENCES.rglob("*.md")),
    *sorted(AGENTS_DIR.glob("*.md")),
]

STATUS_VOCAB = {"seed", "ported", "promoted", "validated", "contested", "moved", "superseded"}
CITATION_RE = re.compile(r"\((supports|refutes) (\d{2}-[a-z0-9-]+)#C\d+\)")
KNOWN_STUDIES = {p.name for p in (REPO_ROOT / "studies").iterdir() if p.is_dir()}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    block = text[3:end]
    out: dict[str, str] = {}
    for line in block.splitlines():
        if ":" in line and not line.startswith(" "):
            key, _, value = line.partition(":")
            out[key.strip()] = value.strip().strip('"')
    return out


def test_lifecycle_string_is_byte_identical_in_four_places() -> None:
    for path in LIFECYCLE_COPIES:
        assert LIFECYCLE in _read(path), f"{path.relative_to(REPO_ROOT)} lost the canonical lifecycle string"


#: Asset suffixes a protocol may name. The templates the generation layer added are
#: `.yaml`, `.json` and `.py`, so a regex that stopped at `.md|.toml` silently
#: exempted exactly the newest half of `assets/` from the dangling-reference check.
ASSET_SUFFIXES = ("md", "toml", "yaml", "json", "py")

ASSET_REF_RE = re.compile(
    r"`(?:\.claude/skills/klein/)?"
    r"(references/[A-Za-z0-9_./<>-]+\.md"
    rf"|assets/[A-Za-z0-9_.-]+\.(?:{'|'.join(ASSET_SUFFIXES)}))`"
)


def test_every_referenced_protocol_and_asset_exists() -> None:
    missing: list[str] = []
    for path in NORMATIVE_MD:
        for match in ASSET_REF_RE.finditer(_read(path)):
            target = match.group(1)
            if "<" in target:  # `references/profiles/<profile>.md` placeholders
                continue
            if not (SKILL_DIR / target).exists():
                missing.append(f"{path.relative_to(REPO_ROOT)} → {target}")
    assert not missing, "dangling protocol/asset references:\n" + "\n".join(missing)


def test_no_orphan_asset() -> None:
    """Every packaged asset is named by at least one protocol or normative doc.

    The mirror of ``test_no_orphan_protocol``: a template nobody points at is a
    template nobody will find, and the fix is the pointer — never a narrower test.
    """
    corpus = "\n".join(_read(p) for p in NORMATIVE_MD)
    orphans = [
        asset.name
        for asset in sorted(ASSETS.iterdir())
        if asset.is_file()
        and asset.suffix.lstrip(".") in ASSET_SUFFIXES
        and f"assets/{asset.name}" not in corpus
    ]
    assert not orphans, f"assets nobody points at: {orphans}"


def test_no_orphan_protocol() -> None:
    corpus = "\n".join(_read(p) for p in NORMATIVE_MD if p.parent != REFERENCES or p.name == "README.md")
    corpus += "\n".join(_read(p) for p in NORMATIVE_MD)
    orphans = []
    for proto in sorted(REFERENCES.rglob("*.md")):
        rel = proto.relative_to(REFERENCES).as_posix()
        mentioned = f"references/{rel}" in corpus or rel in corpus
        if not mentioned:
            orphans.append(rel)
    assert not orphans, f"protocols nobody points at: {orphans}"


def test_claude_md_agent_table_matches_agent_files() -> None:
    table = re.findall(r"^\| (klein-[a-z-]+) \| (\w+) \| ([A-Z/ ]+) \|$", _read(REPO_ROOT / "CLAUDE.md"), re.M)
    assert table, "CLAUDE.md has no agent table"
    listed = {name: model for name, model, _stage in table}
    files = {p.stem: _frontmatter(_read(p)) for p in AGENTS_DIR.glob("klein-*.md")}
    assert set(listed) == set(files), f"table {sorted(listed)} vs files {sorted(files)}"
    for name, model in listed.items():
        assert files[name].get("model") == model, f"{name}: table says {model}, file says {files[name].get('model')}"


def test_skill_worker_column_names_real_agents() -> None:
    skill = _read(SKILL_DIR / "SKILL.md")
    workers: set[str] = set()
    for line in skill.splitlines():
        if line.startswith("| `") and line.count("|") >= 6:
            last = line.rstrip("|").rsplit("|", 1)[-1]
            workers.update(re.findall(r"klein-[a-z-]+", last))
    assert workers, "no worker column parsed from the SKILL.md stage table"
    files = {p.stem for p in AGENTS_DIR.glob("klein-*.md")}
    unknown = workers - files
    assert not unknown, f"SKILL.md names workers that do not exist: {sorted(unknown)}"
    referee_line = [line for line in skill.splitlines() if line.startswith("| `referee`")]
    assert referee_line and "klein-referee" in referee_line[0]


def test_knowledge_frontmatter_status_vocabulary_and_typed_citations() -> None:
    problems = []
    for doc in sorted((REPO_ROOT / "knowledge").rglob("*.md")):
        fm = _frontmatter(_read(doc))
        rel = doc.relative_to(REPO_ROOT)
        if not fm:
            problems.append(f"{rel}: no frontmatter")
            continue
        if fm.get("status") not in STATUS_VOCAB:
            problems.append(f"{rel}: status {fm.get('status')!r} not in {sorted(STATUS_VOCAB)}")
        for verb, study in CITATION_RE.findall(_read(doc)):
            if study not in KNOWN_STUDIES:
                problems.append(f"{rel}: ({verb} {study}#…) cites a study that is not in studies/")
    assert not problems, "\n".join(problems)


def test_research_discipline_cites_claims_that_exist() -> None:
    doc = _read(REPO_ROOT / "knowledge" / "research-discipline.md")
    cited = set(re.findall(r"\((?:supports|refutes) (\d{2}-[a-z0-9-]+)#(C\d+)\)", doc))
    assert cited, "research-discipline.md carries no typed citations"
    missing = []
    for study, claim in sorted(cited):
        findings = _read(REPO_ROOT / "studies" / study / "findings.md")
        if not re.search(rf"(\*\*\[{claim}\]\*\*|\[{claim}\]|\b{claim} ·)", findings):
            missing.append(f"{study}#{claim}")
    assert not missing, f"cited claims not found in their findings.md: {missing}"


def test_war_story_count_matches_headings() -> None:
    text = _read(REFERENCES / "war-stories.md")
    headings = re.findall(r"^## (\d+)\. ", text, re.M)
    assert headings == [str(i) for i in range(1, len(headings) + 1)], headings
    words = {"six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12}
    first = re.search(r"^(\w+) failures", text, re.M)
    assert first, "intro sentence must start with '<Number> failures'"
    assert words[first.group(1).lower()] == len(headings), f"intro says {first.group(1)}, found {len(headings)} stories"


@pytest.mark.parametrize("path", sorted(REFERENCES.glob("profiles/*.md")))
def test_each_profile_has_the_eight_sections(path: Path) -> None:
    if path.name == "README.md":
        pytest.skip("the index")
    text = _read(path)
    for n, key in enumerate(("Audience", "§⑤ heading", "Doctrine", "Figures", "Knowledge", "Budgets", "Vocabulary", "CONSULT hints"), start=1):
        assert re.search(rf"^## {n}\. {re.escape(key)}", text, re.M), f"{path.name}: section {n} ({key}) missing"
