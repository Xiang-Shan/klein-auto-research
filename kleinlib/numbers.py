"""The numbers law as a scan over a whole document.

``references/claims-protocol.md`` states the law once: *every numeral in
``findings.md``, ``claims.lock`` and ``report/index.html`` is a copy of a value
that exists in a pinned artifact*.  :mod:`kleinlib.claims` already mechanizes
the half that lives inside the lock — check 5's ``_check_claim_sentences``, which
asks whether each numeral in a CLAIM SENTENCE is carried by one of that claim's
``numbers`` aliases.  This module mechanizes the other half: the whole
``findings.md`` document, and (always advisory) the tutorial's rendered text.

Nothing here re-states the law's vocabulary.  :data:`kleinlib.claims.NUMERAL_RE`,
:data:`~kleinlib.claims.SENTENCE_EXEMPT_RE` and
:data:`~kleinlib.claims.NUMBERS_OK_RE` are imported and reused verbatim; the one
thing a document needs that a claim sentence does not is
:data:`DOCUMENT_EXEMPT_RE` — structural numbering, percentages, seeds, dates and
bibliographic identifiers, the classes the protocol names but a one-sentence
claim never carries.

Two design decisions worth stating, because both were measured against the
shipped studies rather than guessed (see ``kleinlib/tests/test_numbers_scan.py``):

* **Exempt SPANS, not substitutions.**  A numeral that merely OVERLAPS an
  exempt span is dropped whole.  Substituting the span away instead can split a
  neighbouring numeral into a fragment that is a different number — study 07's
  ``±0.008 of 0.023445`` becomes ``±0.00`` + ``.023445`` under the law's own
  "N of M" exemption.  A fragment is a false positive with a plausible-looking
  value, which is the worst kind.
* **``claims.lock`` is read in full.**  The lock is the study's append-only,
  hash-checked, git-history-verified receipt; a number written into it is on the
  record by construction, and check 5 separately asks whether each PINNED value
  traces to its artifact.  This scan asks the weaker, different question — did
  this numeral come from anywhere at all.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

from .claims import (
    DEFAULT_PRECISION,
    NUMBERS_OK_RE,
    NUMERAL_RE,
    SENTENCE_EXEMPT_RE,
    numeral_matches,
    text_numerals,
)

__all__ = [
    "DOCUMENT_EXEMPT_PATTERNS",
    "DOCUMENT_EXEMPT_RE",
    "INDEX_SUFFIXES",
    "Literal",
    "LiteralIndex",
    "extract_literals",
    "html_text",
    "literal_precision",
    "unsourced_literals",
]

# --------------------------------------------------------------------------
# extraction
# --------------------------------------------------------------------------

#: A YAML frontmatter block, replaced by blank lines so line numbers survive.
FRONTMATTER_RE = re.compile(r"\A---\n.*?\n---\n", re.DOTALL)

#: The opening (or closing) line of a fenced code block.
FENCE_RE = re.compile(r"^\s{0,3}(?P<fence>```+|~~~+)")

#: Inline code — the protocol's "numerals inside code blocks" exemption, at
#: span granularity.
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")

#: A markdown table's separator row (``|---|:--:|``): punctuation, never data.
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?[\s:|-]+\|[\s:|-]*$")

#: An ATX heading — "section, figure and table numbering" in its most common form.
HEADING_RE = re.compile(r"^\s{0,3}#{1,6}\s")

#: U+2212 MINUS SIGN, which prose uses and :data:`NUMERAL_RE` does not know.
#: Normalised to ASCII ``-`` before extraction — a 1:1 substitution, so exempt
#: spans stay aligned with the original line.  Without it ``−0.0595`` extracts
#: as ``+0.0595``, and a real value is reported unsourced because its sign flipped.
UNICODE_MINUS = "−"

_DASH = r"[‐-―-]"

#: The document-level half of the law's exemption list — the classes
#: ``claims-protocol.md`` names ("years and dates; identifiers; section, figure
#: and table numbering; small counts that name their source") that a one-sentence
#: claim never carries, so :data:`SENTENCE_EXEMPT_RE` has no branch for them.
#:
#: Kept as SEPARATE patterns, each scanned independently, rather than one
#: alternation: ``re`` scans an alternation left to right, so one branch that
#: matches early can starve a longer, more specific one that starts inside it —
#: "a seed below 2" swallows the ``2`` of ``2**32`` and leaves ``32`` homeless.
#: :data:`DOCUMENT_EXEMPT_RE` is built from this same tuple, so the documented
#: single object and the behaviour can never drift apart.
DOCUMENT_EXEMPT_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(source, re.VERBOSE | re.IGNORECASE)
    for source in (
        # structural numbering: "Section 4", "Fig. 2", "Table 1", "phase 3"
        r"""\b(?:section|sec|fig(?:ure)?|table|tbl|step|phase|chapter|appendix|part
            |lesson|item|panel|row|col(?:umn)?|note|rung|gate|track)s?
            \s*\.?\s*\d+(?:\.\d+)*\b""",
        r"§+\s*[IVXLC]*\d*(?:\.\d+)*",
        # percentages ("68% of the papers")
        r"\d+(?:\.\d+)?\s*%",
        # seeds and seed ranges ("seed 20260912", "(20260829..20260848)")
        r"\bseeds?\b[^.\n]{0,24}?\d+",
        r"\b\d+\s*\.\.\s*\d+\b",
        # dates, the replication timestamp token, and a disambiguated citation
        # year ("Serfling (2002a)", which SENTENCE_EXEMPT_RE's \b20\d{2}\b misses
        # because the suffix letter eats the word boundary)
        r"\b\d{4}-\d{2}-\d{2}(?:T\d{2}:\d{2}:\d{2}Z?)?\b",
        r"\b\d{8}T\d{6}Z\b",
        r"\b(?:1[89]|20)\d{2}[a-z]\b",
        # versions and powers ("v2", "schema 3", "Python 3.13", "2**32")
        r"\bv\d+(?:\.\d+)*\b",
        r"\bschema[\ _-]?v?\d+\b",
        r"\b(?:python|numpy|scikit-learn|sklearn|pandas|scipy|torch)\s*\d+(?:\.\d+)*\b",
        r"\b\d+\s*\*\*\s*\d+\b",
        # shapes and ratios ("150x4", "4:1:-5")
        r"(?<![\d.])\d+\s*[x×]\s*\d+(?![\d.])",
        r"(?<![\d.])\d+(?::[-+]?\d+)+(?![\d.])",
        # bibliographic identifiers: DOI, arXiv, ISBN, pages, volume(issue), #id
        r"\b10\.\d{4,9}/\S+",
        r"\barxiv:\s*\d{4}\.\d{4,5}(?:v\d+)?\b",
        r"\bisbn[\s:]*[\d" + _DASH + r"x]+\b",
        r"\b(?:pp?|p)\.\s*\d+(?:\s*" + _DASH + r"\s*\d+)?\b",
        r"\b\d+\s*\(\s*\d+\s*\)\s*:\s*\d+(?:\s*" + _DASH + r"\s*\d+)?",
        r"\#\d+\b",
        r"\b(?:eprint|pmid|pmcid|rfc|issue|pr)\s*[:#]?\s*\d+\b",
    )
)

#: The same list as one object, for documentation and for a caller that only
#: wants to ask "is anything on this line exempt?".
DOCUMENT_EXEMPT_RE = re.compile(
    "|".join(f"(?:{pattern.pattern})" for pattern in DOCUMENT_EXEMPT_PATTERNS),
    re.VERBOSE | re.IGNORECASE,
)


@dataclass(frozen=True)
class Literal:
    """One numeral the law asks about, with enough context to fix it by hand."""

    value: float
    line: int
    token: str
    context: str

    @property
    def precision(self) -> int:
        """Decimals as WRITTEN — the precision the index has to match at."""
        return literal_precision(self.token)

    def describe(self) -> str:
        return f"line {self.line}: {self.token} ({self.context})"


def literal_precision(token: str) -> int:
    """How many decimals a numeral was written with.

    ``0.330`` is matched at three decimals, ``2.22`` at two, ``42`` exactly.
    Scientific notation has no meaningful written precision, so it falls back to
    the lock's :data:`~kleinlib.claims.DEFAULT_PRECISION`.
    """
    lowered = token.lower()
    if "e" in lowered:
        return DEFAULT_PRECISION
    return len(lowered.split(".", 1)[1]) if "." in lowered else 0


def _exempt_spans(line: str) -> list[tuple[int, int]]:
    """Character ranges of ``line`` the law exempts.

    Every rule is scanned over the ORIGINAL line, so no rule can consume text a
    later one needed.  In particular the document rules never run over a line the
    sentence rules have already blanked: a DOI carries a year inside it, and
    stripping the year first would split the DOI into unsourced digits.
    """
    spans: list[tuple[int, int]] = []
    for pattern in (INLINE_CODE_RE, *DOCUMENT_EXEMPT_PATTERNS, SENTENCE_EXEMPT_RE):
        spans.extend(match.span() for match in pattern.finditer(line))
    return spans


def _scannable_lines(markdown: str) -> Iterator[tuple[int, str]]:
    """(1-based line number, line) for every line the law actually scans.

    Skipped whole: frontmatter, fenced code, table separator rows, headings, and
    any line carrying the law's ``klein:numbers-ok`` marker.
    """
    body = FRONTMATTER_RE.sub(lambda m: "\n" * m.group().count("\n"), markdown)
    fence: str | None = None
    for number, raw in enumerate(body.splitlines(), start=1):
        opener = FENCE_RE.match(raw)
        if fence is not None:
            if (
                opener
                and opener.group("fence")[0] == fence[0]
                and len(opener.group("fence")) >= len(fence)
            ):
                fence = None
            continue
        if opener:
            fence = opener.group("fence")
            continue
        if "|" in raw and TABLE_SEPARATOR_RE.match(raw):
            continue
        if NUMBERS_OK_RE.search(raw):
            continue
        if HEADING_RE.match(raw):
            continue
        yield number, raw.replace(UNICODE_MINUS, "-")


def extract_literals(markdown: str) -> list[Literal]:
    """Every numeral in ``markdown`` the numbers law asks for a home for."""
    literals: list[Literal] = []
    for number, line in _scannable_lines(markdown):
        spans = _exempt_spans(line)
        context = line.strip()
        for match in NUMERAL_RE.finditer(line):
            start, end = match.span()
            if any(start < stop and begin < end for begin, stop in spans):
                continue
            try:
                value = float(match.group())
            except ValueError:  # pragma: no cover - NUMERAL_RE only matches floats
                continue
            literals.append(Literal(value, number, match.group(), context))
    return literals


# --------------------------------------------------------------------------
# the index of everything the study actually measured
# --------------------------------------------------------------------------

#: Text artifacts the index reads.  A binary payload (a model blob, a PNG) is
#: not scanned — the claims law reports the same absence as a warning, never a
#: silent pass.
#: ``.lock`` is here because ``claims.lock`` is JSON under a receipt's name.
INDEX_SUFFIXES = frozenset(
    {".tsv", ".csv", ".json", ".jsonl", ".yaml", ".yml", ".md", ".log", ".txt", ".lock"}
)


@dataclass(frozen=True)
class LiteralIndex:
    """Every numeral the study MEASURED, and where each source came from."""

    values: tuple[float, ...]
    sources: tuple[str, ...]

    def covers(self, literal: Literal) -> bool:
        """True when some measured value equals this numeral at its own precision."""
        return numeral_matches(literal.value, self.values, literal.precision)

    @classmethod
    def for_study(
        cls,
        study_dir: Path,
        state: Mapping[str, Any] | None = None,
        *,
        exclude: Iterable[Path] = (),
    ) -> LiteralIndex:
        """Build the index the protocol names, in its order.

        ``results.tsv``, ``aux_metrics.tsv``, every run manifest, ``study.yaml``,
        ``study_state.json``, ``claims.lock`` and every artifact it pins, and
        every sidecar and script registered with ``klein sweep register``.

        ``exclude`` keeps the document under scan out of its own index — a
        findings file pinned as an artifact of itself would make the scan
        vacuous, and study 09's lock pins exactly that.
        """
        excluded = {path.resolve() for path in exclude}
        values: list[float] = []
        sources: list[str] = []

        def read(path: Path, label: str) -> None:
            try:
                resolved = path.resolve()
            except OSError:  # pragma: no cover - defensive
                return
            if resolved in excluded or not path.is_file():
                return
            if path.suffix.lower() not in INDEX_SUFFIXES:
                return
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:  # pragma: no cover - defensive
                return
            excluded.add(resolved)  # never double-count a file two routes name
            values.extend(text_numerals(text))
            sources.append(label)

        for name in ("results.tsv", "aux_metrics.tsv", "study.yaml", "study_state.json"):
            read(study_dir / name, name)
        for manifest in sorted((study_dir / "runs").glob("E*/manifest.json")):
            read(manifest, f"runs/{manifest.parent.name}/manifest.json")

        lock_path = study_dir / "claims.lock"
        read(lock_path, "claims.lock")
        for alias, meta in _pinned_artifacts(lock_path).items():
            read(_resolve(study_dir, meta), f"art:{alias}")

        registry = (state or {}).get("sweeps")
        if isinstance(registry, Mapping):
            for name in sorted(registry):
                record = registry[name]
                if not isinstance(record, Mapping):
                    continue
                for role in ("sidecar", "script"):
                    relative = record.get(role)
                    if isinstance(relative, str):
                        read(study_dir / relative, f"sweep:{name} ({role})")

        return cls(tuple(values), tuple(sources))


def _pinned_artifacts(lock_path: Path) -> dict[str, Mapping[str, Any]]:
    """``claims.lock``'s artifact block, or nothing when there is no lock."""
    if not lock_path.is_file():
        return {}
    try:
        payload = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    artifacts = payload.get("artifacts") if isinstance(payload, Mapping) else None
    if not isinstance(artifacts, Mapping):
        return {}
    return {
        str(alias): meta for alias, meta in artifacts.items() if isinstance(meta, Mapping)
    }


def _resolve(study_dir: Path, meta: Mapping[str, Any]) -> Path:
    """A pinned artifact's path — repo-relative as the lock writes it, or study-relative."""
    raw = meta.get("path")
    if not isinstance(raw, str):
        return study_dir / "\0"  # a path that never exists; read() ignores it
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    # Locks pin repo-relative paths ("studies/09-…/results.tsv"); walk up from
    # the study until one of them resolves, then fall back to study-relative.
    for base in (study_dir, *study_dir.resolve().parents):
        if (base / candidate).is_file():
            return base / candidate
    return study_dir / candidate


def unsourced_literals(markdown: str, index: LiteralIndex) -> list[Literal]:
    """Every numeral in ``markdown`` with no measured home."""
    return [literal for literal in extract_literals(markdown) if not index.covers(literal)]


# --------------------------------------------------------------------------
# the tutorial pass — text nodes only, and always advisory
# --------------------------------------------------------------------------


class _TextNodes(HTMLParser):
    """Rendered text of an HTML page: no tags, no attributes, no code, no math.

    ``report/index.html`` inlines its figures as base64 and typesets its math as
    SVG at build time (``references/tutorial-spec.md``), so scanning anything but
    text nodes would scan megabytes of encoded bytes and every path coordinate.
    ``<code>``/``<pre>``/``<script>``/``<style>``/``<svg>`` are the law's code and
    formula exemptions, applied where a document keeps them.
    """

    SKIP = frozenset({"script", "style", "code", "pre", "svg", "math", "textarea"})

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._depth = 0

    def handle_starttag(self, tag: str, attrs: object) -> None:
        if tag in self.SKIP:
            self._depth += 1
        self.parts.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.SKIP and self._depth:
            self._depth -= 1
        # A separator at EVERY tag boundary, or two adjacent table cells
        # (`<td>E0001</td><td>0.029442</td>`) concatenate into the numeral
        # `00010.029442`, which is a number the study never wrote.
        self.parts.append(" ")

    def handle_startendtag(self, tag: str, attrs: object) -> None:
        self.parts.append(" ")

    def handle_data(self, data: str) -> None:
        if not self._depth:
            self.parts.append(data)


def html_text(html: str) -> str:
    """The page's text nodes, newline-joined so line numbers stay meaningful."""
    parser = _TextNodes()
    try:
        parser.feed(html)
        parser.close()
    except Exception:  # pragma: no cover - html.parser is forgiving by design
        return ""
    return "".join(parser.parts)


def format_literals(literals: Sequence[Literal], *, limit: int = 5) -> str:
    """The first few offenders, as one message line."""
    shown = "; ".join(literal.describe() for literal in literals[:limit])
    if len(literals) > limit:
        shown += f"; … {len(literals) - limit} more"
    return shown
