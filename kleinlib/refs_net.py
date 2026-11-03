"""``klein refs verify`` — resolve every DOI and arXiv id in ``references.yaml`` (Klein 2.3).

The METHOD gate's references are checked by a person or a scholar agent reading
the source.  This verb adds the mechanical half: each ``doi`` is looked up at
Crossref (OpenAlex as the fallback) and each ``arxiv`` id at export.arxiv.org,
and the resolved title is compared with the title the card cites.

* It is **opt-in network**: refused under ``KLEIN_OFFLINE=1``, never imported by
  ``klein verify`` (which stays network-free — ``references.py`` is the loader
  verify uses), and it never changes what verify checks.
* ``--record`` writes the outcome back into ``references.yaml`` as a line edit
  that keeps every comment: ``resolved_by``, ``resolved_title``, ``resolved_at``
  on a match, and ``verified: true`` (with ``verified_by: klein-refs`` when the
  entry had no ``verified_by``) only for an entry that was not already verified.
  A human verification is never overwritten; a mismatch never sets anything.
* The exit status is non-zero when any locator fails to resolve or resolves to a
  different title — a DOI that points at another article is the reviewer's
  classic finding, caught before a claim leans on it.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .errors import WorkflowError
from .references import load_references, references_path

__all__ = ["Resolution", "resolve_reference", "title_match", "verify_references"]

Fetch = Callable[[str], bytes]

USER_AGENT = "klein-auto-research refs-verify (+https://github.com/Xiang-Shan/klein-auto-research)"
_ATOM = "{http://www.w3.org/2005/Atom}"


@dataclass(frozen=True)
class Resolution:
    key: str
    locator: str  # "doi:…" / "arxiv:…" / "" (no resolvable locator)
    source: str  # crossref | openalex | arxiv | ""
    resolved_title: str
    resolved_year: int | None
    ok: bool
    message: str


def _fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
    with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310 — fixed https hosts
        return response.read()


def _normalize(title: str) -> list[str]:
    text = re.sub(r"<[^>]+>", " ", title)  # Crossref titles may carry JATS markup
    text = re.sub(r"\$[^$]*\$", " ", text)  # inline TeX in arXiv titles
    return re.findall(r"[a-z0-9]+", text.lower())


def title_match(cited: str, resolved: str) -> bool:
    """True when two titles name the same work (case, punctuation and markup ignored).

    Exact token equality, or one title's tokens being a prefix-free superset of
    the other's (subtitles are often dropped), or a token Jaccard of at least 0.85.
    """
    a, b = _normalize(cited), _normalize(resolved)
    if not a or not b:
        return False
    if a == b:
        return True
    sa, sb = set(a), set(b)
    shorter, longer = (sa, sb) if len(sa) <= len(sb) else (sb, sa)
    if len(shorter) >= 4 and shorter <= longer:
        return True
    return len(sa & sb) / len(sa | sb) >= 0.85


def _clean_doi(raw: str) -> str:
    doi = raw.strip()
    doi = re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", doi, flags=re.IGNORECASE)
    return doi


def _clean_arxiv(raw: str) -> str:
    value = raw.strip()
    value = re.sub(r"^(https?://arxiv\.org/(abs|pdf)/|arxiv:)", "", value, flags=re.IGNORECASE)
    return re.sub(r"\.pdf$", "", value)


def _crossref(doi: str, fetch: Fetch) -> tuple[str, int | None]:
    payload = json.loads(fetch("https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="/")))
    message = payload.get("message", {})
    titles = message.get("title") or []
    year = None
    for field in ("issued", "published-print", "published-online", "created"):
        parts = (message.get(field) or {}).get("date-parts") or []
        if parts and parts[0] and parts[0][0]:
            year = int(parts[0][0])
            break
    return (titles[0] if titles else ""), year


def _openalex(doi: str, fetch: Fetch) -> tuple[str, int | None]:
    url = "https://api.openalex.org/works/doi:" + urllib.parse.quote(doi, safe="/")
    payload = json.loads(fetch(url))
    year = payload.get("publication_year")
    return str(payload.get("display_name") or payload.get("title") or ""), (
        int(year) if isinstance(year, int) else None
    )


def _arxiv(arxiv_id: str, fetch: Fetch) -> tuple[str, int | None]:
    url = "https://export.arxiv.org/api/query?id_list=" + urllib.parse.quote(arxiv_id)
    root = ET.fromstring(fetch(url))  # noqa: S314 — arXiv's own Atom feed
    entry = root.find(f"{_ATOM}entry")
    if entry is None:
        return "", None
    entry_id = (entry.findtext(f"{_ATOM}id") or "").strip()
    if "api/errors" in entry_id:
        return "", None
    title = " ".join((entry.findtext(f"{_ATOM}title") or "").split())
    published = (entry.findtext(f"{_ATOM}published") or "")[:4]
    return title, (int(published) if published.isdigit() else None)


def resolve_reference(key: str, entry: Mapping[str, Any], *, fetch: Fetch = _fetch) -> Resolution:
    """Resolve one entry's DOI (preferred) or arXiv id and compare titles."""
    cited = str(entry.get("title") or "")
    attempts: list[tuple[str, str, Callable[[], tuple[str, int | None]]]] = []
    if entry.get("doi"):
        doi = _clean_doi(str(entry["doi"]))
        attempts.append((f"doi:{doi}", "crossref", lambda: _crossref(doi, fetch)))
        attempts.append((f"doi:{doi}", "openalex", lambda: _openalex(doi, fetch)))
    if entry.get("arxiv"):
        arxiv_id = _clean_arxiv(str(entry["arxiv"]))
        attempts.append((f"arxiv:{arxiv_id}", "arxiv", lambda: _arxiv(arxiv_id, fetch)))
    if not attempts:
        return Resolution(key, "", "", "", None, True, "[WARN] no doi or arxiv locator — url-only, checked by a reader")
    errors: list[str] = []
    for locator, source, run in attempts:
        try:
            title, year = run()
        except (urllib.error.URLError, OSError, ValueError, ET.ParseError) as exc:
            errors.append(f"{source}: {exc}")
            continue
        if not title:
            errors.append(f"{source}: no record for {locator}")
            continue
        if not title_match(cited, title):
            return Resolution(
                key, locator, source, title, year, False,
                f"{locator} resolves to a different title: {title!r}",
            )
        note = ""
        cited_year = entry.get("year")
        if isinstance(cited_year, int) and year is not None and abs(cited_year - year) > 1:
            note = f" [WARN] year {cited_year} cited, {year} at {source}"
        return Resolution(key, locator, source, title, year, True, f"{locator} → {source}: title matches{note}")
    return Resolution(key, attempts[0][0], "", "", None, False, "; ".join(errors) or "unresolved")


# ------------------------------------------------------------------ recording


def _entry_span(lines: Sequence[str], key: str) -> tuple[int, int, str] | None:
    """(first body line, end line, body indent) of *key*'s block in references.yaml."""
    pattern = re.compile(rf"^(\s*){re.escape(key)}\s*:\s*(#.*)?$")
    for index, line in enumerate(lines):
        match = pattern.match(line)
        if not match:
            continue
        head_indent = len(match.group(1))
        end = index + 1
        body_indent = ""
        while end < len(lines):
            current = lines[end]
            stripped = current.strip()
            if stripped and not stripped.startswith("#"):
                indent = len(current) - len(current.lstrip())
                if indent <= head_indent:
                    break
                if not body_indent:
                    body_indent = current[:indent]
            end += 1
        while end > index + 1 and not lines[end - 1].strip():
            end -= 1
        return index + 1, end, body_indent or " " * (head_indent + 2)
    return None


def _drop_field(lines: list[str], start: int, end: int, indent: str, field: str) -> int:
    """Remove ``field:`` (and its continuation lines) from lines[start:end]; return new end."""
    i = start
    while i < end:
        if lines[i].startswith(f"{indent}{field}:"):
            j = i + 1
            while j < end and (not lines[j].strip() or len(lines[j]) - len(lines[j].lstrip()) > len(indent)):
                j += 1
            del lines[i:j]
            end -= j - i
            continue
        i += 1
    return end


def _record(path: Path, results: Sequence[Resolution], entries: Mapping[str, Any], today: str) -> list[str]:
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines()
    recorded: list[str] = []
    for result in results:
        if not result.ok or not result.source:
            continue
        span = _entry_span(lines, result.key)
        if span is None:
            continue
        start, end, indent = span
        fields = {
            "resolved_by": f"klein-refs ({result.source})",
            "resolved_title": result.resolved_title,
            "resolved_at": today,
        }
        entry = entries.get(result.key) or {}
        promote = entry.get("verified") is not True
        drop = list(fields) + (["verified"] if promote else [])
        if promote and not entry.get("verified_by"):
            drop.append("verified_by")
        for field in drop:
            end = _drop_field(lines, start, end, indent, field)
        new: list[str] = []
        if promote:
            new.append(f"{indent}verified: true")
            if not entry.get("verified_by"):
                new.append(f'{indent}verified_by: "klein-refs"')
                if not entry.get("verified_at"):
                    end = _drop_field(lines, start, end, indent, "verified_at")
                    new.append(f'{indent}verified_at: "{today}"')
        new += [f"{indent}{name}: {json.dumps(value, ensure_ascii=False)}" for name, value in fields.items()]
        lines[end:end] = new
        recorded.append(result.key)
    text = "\n".join(lines) + ("\n" if original.endswith("\n") else "")
    # The edit must leave every other field exactly as it was.
    before = load_references(path.parent)
    path.write_text(text, encoding="utf-8")
    try:
        after = load_references(path.parent)
        for key, entry in before.items():
            changed = {k for k in set(entry) | set(after.get(key, {})) if entry.get(k) != after[key].get(k)}
            allowed = {"resolved_by", "resolved_title", "resolved_at", "verified", "verified_by", "verified_at"}
            if not changed <= allowed:
                raise WorkflowError(f"refs verify: recording {key} would change {sorted(changed - allowed)}")
    except (WorkflowError, yaml.YAMLError, KeyError) as exc:
        path.write_text(original, encoding="utf-8")
        raise WorkflowError(f"references.yaml left unchanged: {exc}") from exc
    return recorded


def verify_references(
    study_dir: Path,
    *,
    keys: Sequence[str] = (),
    record: bool = False,
    fetch: Fetch | None = None,
    today: str | None = None,
) -> tuple[list[Resolution], list[str]]:
    """Resolve the study's references; with *record*, write matches back.  Returns (results, recorded keys)."""
    if os.environ.get("KLEIN_OFFLINE") == "1" and fetch is None:
        raise WorkflowError("klein refs verify needs the network; KLEIN_OFFLINE=1 refuses it")
    path = references_path(study_dir)
    if not path.is_file():
        raise WorkflowError(f"no {path.name} in {study_dir}")
    entries = load_references(study_dir)
    unknown = [key for key in keys if key not in entries]
    if unknown:
        raise WorkflowError(f"no such reference key(s): {', '.join(unknown)}")
    chosen = [key for key in entries if not keys or key in keys]
    results = [
        resolve_reference(key, entries[key] if isinstance(entries[key], Mapping) else {}, fetch=fetch or _fetch)
        for key in chosen
    ]
    recorded: list[str] = []
    if record:
        recorded = _record(path, results, entries, today or _dt.date.today().isoformat())
    return results, recorded
