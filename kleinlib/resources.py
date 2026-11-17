"""Where the skill lives — one resolver, so nothing assumes the working directory.

Klein's protocols, card templates, audience profiles, worker agents and the two
report scripts are the *skill* (``.claude/skills/klein`` in this repository).
They ship inside the wheel as package data, so every one of them is reachable
after ``pip install`` with no checkout:

1. **the host repository's own copy** — ``<repo>/.claude/skills/klein``, when a
   study's repository carries one (``klein skill install`` writes it).  A study
   pins the protocols it was run under by committing that copy.
2. **the installed package** — ``kleinlib/_skill``.
3. **this checkout** — ``<engine root>/.claude/skills/klein`` (an editable install).

``klein explain <topic>`` prints a protocol or a glossary term from wherever it
resolves; ``klein skill install`` copies the skill and the agents into a host
repository.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from .errors import WorkflowError

__all__ = [
    "SKILL_REL",
    "agents_root",
    "asset_path",
    "explain_topic",
    "glossary",
    "install_skill",
    "load_schema",
    "profile_path",
    "reference_path",
    "schema_index",
    "schema_names",
    "script_path",
    "skill_root",
    "topics",
]

#: The skill's location inside a repository that carries it.
SKILL_REL = Path(".claude") / "skills" / "klein"
AGENTS_REL = Path(".claude") / "agents"
_PACKAGE = Path(__file__).resolve().parent


def _repo_of(start: Path | None) -> Path | None:
    """The git repository containing ``start`` (or the working directory), if any."""
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def _candidates(study_dir: Path | None) -> list[Path]:
    roots: list[Path] = []
    repo = _repo_of(study_dir)
    if repo is not None:
        roots.append(repo / SKILL_REL)
    roots.append(_PACKAGE / "_skill")
    roots.append(_PACKAGE.parent / SKILL_REL)
    return roots


def skill_root(study_dir: Path | None = None) -> Path | None:
    """The first place the skill is found, or None when it is nowhere on this machine."""
    for root in _candidates(study_dir):
        if (root / "SKILL.md").is_file():
            return root
    return None


def _find(relative: str, study_dir: Path | None) -> Path | None:
    for root in _candidates(study_dir):
        path = root / relative
        if path.is_file():
            return path
    return None


def reference_path(name: str, study_dir: Path | None = None) -> Path | None:
    """``references/<name>`` (``consult-protocol.md``), wherever it resolves."""
    return _find(f"references/{name}", study_dir)


def asset_path(name: str, study_dir: Path | None = None) -> Path | None:
    """The shipped asset ``name`` (``benchmark-submission.schema.json``), wherever it resolves.

    ``name`` may carry a subfolder (``generation/slate-template.yaml``); a bare file
    name is searched for recursively, so the opt-in generation layer's assets
    (``assets/generation/``) are found by name like the core ones.
    """
    direct = _find(f"assets/{name}", study_dir)
    if direct is not None:
        return direct
    for root in _candidates(study_dir):
        base = root / "assets"
        if base.is_dir():
            for path in sorted(base.rglob(Path(name).name)):
                if path.is_file() and path.relative_to(base).as_posix().endswith(name):
                    return path
    return None


def profile_path(name: str, study_dir: Path | None = None) -> Path | None:
    """The shipped audience profile ``<name>.md``."""
    return _find(f"references/profiles/{name}.md", study_dir)


def script_path(name: str, study_dir: Path | None = None) -> Path | None:
    """One of the skill's scripts (``build_tutorial.py``, ``summarize_results.py``)."""
    return _find(f"scripts/{name}", study_dir)


def agents_root() -> Path | None:
    """The worker agents (``klein-*.md``) that ship with Klein."""
    for root in (_PACKAGE / "_agents", _PACKAGE.parent / AGENTS_REL):
        if root.is_dir() and any(root.glob("klein-*.md")):
            return root
    return None


# --------------------------------------------------------------------------
# schemas
# --------------------------------------------------------------------------

_SCHEMAS = _PACKAGE / "_schemas"
_SCHEMA_SUFFIX = ".schema.json"


def schema_names() -> list[str]:
    """Every shipped JSON Schema's name (``envelope``, ``next``, ...), sorted."""
    return sorted(path.name[: -len(_SCHEMA_SUFFIX)] for path in _SCHEMAS.glob(f"*{_SCHEMA_SUFFIX}"))


def schema_index() -> dict[str, str]:
    """``{verb path: data schema name}`` from ``_schemas/index.json`` (``*`` is the default)."""
    return json.loads((_SCHEMAS / "index.json").read_text(encoding="utf-8"))


def load_schema(name: str) -> dict[str, Any]:
    """One shipped JSON Schema (draft 2020-12) by name; an unknown name is a refusal."""
    names = schema_names()
    if name not in names:
        close = ", ".join(n for n in names if name and name in n)
        hint = f" — did you mean: {close}?" if close else ""
        raise WorkflowError(f"no schema {name!r}{hint} (run `klein schema` for the list: {', '.join(names)})")
    return json.loads((_SCHEMAS / f"{name}{_SCHEMA_SUFFIX}").read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# explain
# --------------------------------------------------------------------------

#: Short names for the protocols people ask for by stage.
ALIASES: dict[str, str] = {
    "scaffold": "defaults-and-scaffolding",
    "new": "defaults-and-scaffolding",
    "consult": "consult-protocol",
    "inquiry": "inquiry-model",
    "data": "data-gate-protocol",
    "method": "method-gate-protocol",
    "experiment": "registered-mode",
    "registered": "registered-mode",
    "sweep": "sweep-rules",
    "replicate": "replication-protocol",
    "calls": "model-calls-protocol",
    "compute": "compute-and-devices",
    "synthesize": "synthesis-protocol",
    "claims": "claims-protocol",
    "referee": "referee-protocol",
    "tutorial": "tutorial-spec",
    "phase": "phase-ritual",
    "explore": "exploration-protocol",
    "probe": "exploration-protocol",
    "generation": "generation-overview",
    "skill": "SKILL",
    "agents": "manual",
    "loop": "manual",
}


def topics(study_dir: Path | None = None) -> dict[str, Path]:
    """Every explainable document: ``{topic: path}`` (protocols, profiles, the skill itself)."""
    root = skill_root(study_dir)
    found: dict[str, Path] = {}
    if root is None:
        return found
    found["SKILL"] = root / "SKILL.md"
    # The operating manual (AGENTS.md): beside the skill in a wheel, at the
    # repository root in a checkout.
    for manual in (root / "AGENTS.md", root.parents[2] / "AGENTS.md"):
        if manual.is_file():
            found["manual"] = manual
            break
    for path in sorted((root / "references").rglob("*.md")):
        relative = path.relative_to(root / "references")
        if path.name == "README.md":
            key = "/".join((*relative.parts[:-1], "README")) if relative.parts[:-1] else "README"
        elif relative.parts[0] == "profiles":
            key = f"profile:{path.stem}"
        else:
            key = path.stem
        found.setdefault(key, path)
    for path in sorted((root / "assets").rglob("*")):
        if path.is_file() and path.name != ".gitkeep" and "__pycache__" not in path.parts:
            found.setdefault(f"template:{path.name}", path)
    figures = root / "scripts" / "make_figures.py"
    if figures.is_file():
        found.setdefault("template:make_figures.py", figures)
    return found


_TERM_RE = re.compile(r"^### +(.+?)\s*$", re.M)


def glossary(study_dir: Path | None = None) -> dict[str, str]:
    """``{term: definition}`` from ``references/glossary.md`` (one ``###`` heading per term)."""
    path = reference_path("glossary.md", study_dir)
    if path is None:
        return {}
    text = path.read_text(encoding="utf-8")
    matches = list(_TERM_RE.finditer(text))
    terms: dict[str, str] = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : end]
        body = re.split(r"^## ", body, maxsplit=1, flags=re.M)[0].strip()
        terms[match.group(1).strip()] = body
    return terms


def _normal(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def explain_topic(topic: str, study_dir: Path | None = None) -> dict[str, Any]:
    """A glossary term or a protocol, as ``{"topic", "kind", "path", "text"}``.

    ``topic`` is matched as: ``term:<name>`` (a glossary definition), a stage alias
    (``consult``), a protocol's file stem (``consult-protocol``), ``profile:<name>``,
    ``template:<file>`` — and otherwise a glossary term (``gate``, ``notary``).
    With an empty topic the result lists what can be explained.
    """
    available = topics(study_dir)
    terms = glossary(study_dir)
    if not topic.strip():
        return {
            "topic": "",
            "kind": "index",
            "path": None,
            "text": "Protocols: " + ", ".join(sorted(available)) + "\n\nTerms: " + ", ".join(terms) + "\n",
            "topics": sorted(available),
            "terms": list(terms),
        }
    def term_entry(wanted: str) -> dict[str, Any] | None:
        for term, body in terms.items():
            if _normal(term) == wanted or wanted in {_normal(part) for part in re.split(r"[/,]| or ", term)}:
                return {"topic": term, "kind": "term", "path": None, "text": f"{term}\n\n{body}\n"}
        return None

    # `term:gate` asks for the definition outright; otherwise a stage name or a
    # protocol name wins (`referee` -> the referee protocol), then a glossary term.
    if topic.strip().lower().startswith("term:"):
        entry = term_entry(_normal(topic.split(":", 1)[1]))
        if entry is None:
            raise WorkflowError(f"no glossary term {topic.split(':', 1)[1]!r} (run `klein explain` for the list)")
        return entry
    wanted = _normal(topic)
    key = ALIASES.get(topic.strip().lower(), topic.strip())
    by_normal = {_normal(name): name for name in available}
    name = key if key in available else by_normal.get(_normal(key))
    if name is None:
        entry = term_entry(wanted)
        if entry is not None:
            return entry
        close = sorted(n for n in available if wanted and wanted in _normal(n))
        hint = f" — did you mean: {', '.join(close)}?" if close else ""
        raise WorkflowError(
            f"nothing to explain for {topic!r}{hint} (run `klein explain` for the list)"
        )
    path = available[name]
    return {"topic": name, "kind": "protocol", "path": str(path), "text": path.read_text(encoding="utf-8")}


# --------------------------------------------------------------------------
# skill install
# --------------------------------------------------------------------------


def _plan_copy(source: Path, target: Path, *, force: bool) -> list[tuple[Path, Path]]:
    """Every ``(from, to)`` of a tree copy — refused as a whole before anything is written."""
    plan: list[tuple[Path, Path]] = []
    for path in sorted(source.rglob("*")):
        if path.is_dir() or "__pycache__" in path.parts or path.name == ".gitkeep":
            continue
        if "tests" in path.relative_to(source).parts:
            continue
        plan.append((path, target / path.relative_to(source)))
    differing = [
        destination
        for path, destination in plan
        if destination.exists() and destination.read_bytes() != path.read_bytes()
    ]
    if differing and not force:
        shown = ", ".join(str(path) for path in differing[:3])
        more = f" and {len(differing) - 3} more" if len(differing) > 3 else ""
        raise WorkflowError(
            f"{shown}{more} exist(s) and differ(s) — nothing was written. Pass --force to "
            "overwrite (a study pins the protocols it ran under; overwrite deliberately)"
        )
    return plan


def _write_copy(plan: list[tuple[Path, Path]]) -> list[str]:
    for path, destination in plan:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
    return [destination.as_posix() for _path, destination in plan]


def install_skill(target: Path, *, agents: bool = True, force: bool = False) -> dict[str, Any]:
    """Copy the skill (and the worker agents) into ``target`` — a host repository's root."""
    target = Path(target).resolve()
    if not target.is_dir():
        raise WorkflowError(f"{target} is not a directory")
    source = None
    for root in (_PACKAGE / "_skill", _PACKAGE.parent / SKILL_REL):
        if (root / "SKILL.md").is_file():
            source = root
            break
    if source is None:
        raise WorkflowError("this installation carries no skill to install (a damaged package?)")
    destination = target / SKILL_REL
    if source.resolve() == destination.resolve():
        raise WorkflowError(f"the skill is already at {destination}")
    skill_plan = _plan_copy(source, destination, force=force)
    agent_plan: list[tuple[Path, Path]] = []
    agent_source = agents_root()
    if agents and agent_source is not None and agent_source.resolve() != (target / AGENTS_REL).resolve():
        agent_plan = _plan_copy(agent_source, target / AGENTS_REL, force=force)
    written = _write_copy(skill_plan)
    agent_files = _write_copy(agent_plan)
    return {
        "target": str(target),
        "skill": str(destination),
        "files": len(written),
        "agents": [Path(name).name for name in agent_files],
    }
