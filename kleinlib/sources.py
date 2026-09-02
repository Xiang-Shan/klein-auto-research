"""Data source tags: the one grammar every Klein study names its evidence with.

Normative text: ``.claude/skills/klein/references/data-sources.md`` (the tag
table, the pinning rule, offline behaviour, ``klein doctor``). A study's
``data.source`` names WHERE its evidence comes from with a small, closed
vocabulary — ``csv:`` / ``parquet:`` / ``synthetic:`` / ``bundled:`` / ``hub:``
/ ``sklearn:`` / ``openml:`` / ``url:`` — so the same tag resolves the same way
on any machine that clones this repository, pinned by a hash whenever the
bytes could change, and refused outright when the machine is offline and the
tag needs the network.

Three entry points:

* :func:`parse_source` — the grammar. ``<scheme>:<value>``, scheme one of
  :class:`SourceKind`. This is the ONE parser; ``kleinlib.contract`` validates
  ``data.source``'s *shape* with its own small regex today and is meant to
  call this function once both land (see the E11 package note) — never
  duplicate the scheme list elsewhere.
* :func:`resolve` — the real thing: touches the filesystem (and, for
  ``openml:``/``url:``, the network unless already cached), prints the
  ``data source: ...`` provenance line every resolution owes the run log, and
  returns a :class:`ResolvedSource`. Fetching is real I/O, so callers pass
  ``offline=True`` (``KLEIN_OFFLINE=1``) to refuse a network scheme before any
  request is made.
* :func:`describe` — the safe, offline introspection ``klein doctor`` uses:
  never prints, never fetches, only checks what is already true on disk
  (a bundled copy present, a cache file already downloaded and pin-verified,
  a hub loader module importable) and reports readiness in a plain dict.

War story continuity: the two schemes that predate this module — ``hub:`` and
``bundled:`` — must keep printing the EXACT byte-identical
``data source: hub|bundled — <path>`` line the old ``kleinlib.data
.load_data_hub`` printed, because studies 00/05/06's run logs already contain
it as evidence.
"""

from __future__ import annotations

import enum
import importlib.util
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import WorkflowError
from .primitives import sha256_bytes, sha256_file

__all__ = [
    "ALLOWED_SKLEARN_LOADERS",
    "ParsedSource",
    "ResolvedSource",
    "SourceKind",
    "describe",
    "parse_source",
    "resolve",
]


class SourceKind(enum.StrEnum):
    """The eight schemes a `data.source` tag may name.

    A `str` enum on purpose: it compares equal to its scheme string
    (``SourceKind.CSV == "csv"``) and serializes as one in `--json` output
    without a custom encoder.
    """

    CSV = "csv"
    PARQUET = "parquet"
    SYNTHETIC = "synthetic"
    BUNDLED = "bundled"
    HUB = "hub"
    SKLEARN = "sklearn"
    OPENML = "openml"
    URL = "url"


#: Offline-safe scikit-learn toy-dataset loaders (scikit-learn's own "Toy
#: datasets" set: https://scikit-learn.org/stable/datasets/toy_dataset.html).
#: Every other `load_*`/`fetch_*` name either needs a positional argument
#: (`load_files`, `load_svmlight_file(s)`, `load_sample_image`) or the
#: network (`fetch_*`) — both refused.
ALLOWED_SKLEARN_LOADERS: frozenset[str] = frozenset(
    {
        "load_iris",
        "load_diabetes",
        "load_digits",
        "load_linnerud",
        "load_wine",
        "load_breast_cancer",
    }
)

_TAG_RE = re.compile(r"^([a-z][a-z0-9_]*):(.+)$", re.DOTALL)


@dataclass(frozen=True)
class ParsedSource:
    """A `data.source` tag split into its scheme and payload."""

    kind: SourceKind
    value: str
    raw: str


@dataclass(frozen=True)
class ResolvedSource:
    """What `resolve()` found.

    ``path`` is the on-disk file a caller should read (CSV/parquet path, a
    `synthetic:` script, a `bundled:`/`hub:` data file, an `openml:`/`url:`
    cache file) — ``None`` for the two schemes that hand back an already-
    loaded object instead of a bare file (`hub:` via a loader module,
    `sklearn:`), which populate ``loaded``/leave the caller to call the named
    loader themselves. ``digest`` is the sha256 of the resolved bytes when one
    was computed (always for a file; ``None`` for a bare loader reference).
    """

    path: Path | None
    kind: SourceKind
    provenance_line: str
    digest: str | None
    loaded: Any = None


def parse_source(tag: str) -> ParsedSource:
    """Parse `<scheme>:<value>` into a :class:`ParsedSource`.

    ``url:`` is the one scheme whose value itself contains a colon
    (`https://host/path`); the payload is everything after the FIRST colon,
    so `url:https://x.test/y` parses to `kind=URL, value="https://x.test/y"`.
    Raises :class:`WorkflowError` naming the tag and, for an unrecognized
    scheme, the allowed list — never silently coerces.
    """
    if not isinstance(tag, str) or not tag:
        raise WorkflowError(f"data source tag must be a non-empty string, got {tag!r}")
    match = _TAG_RE.match(tag)
    allowed = ", ".join(k.value for k in SourceKind)
    if not match:
        raise WorkflowError(
            f"data source tag {tag!r} is not '<scheme>:<value>' — allowed schemes: {allowed}"
        )
    scheme, value = match.group(1), match.group(2)
    try:
        kind = SourceKind(scheme)
    except ValueError:
        raise WorkflowError(
            f"data source tag {tag!r} uses unknown scheme {scheme!r} — allowed: {allowed}"
        ) from None
    if not value:
        raise WorkflowError(f"data source tag {tag!r} has an empty value after {scheme}:")
    return ParsedSource(kind=kind, value=value, raw=tag)


def resolve(
    tag: str,
    *,
    study_dir: Path | None,
    offline: bool,
    expected_sha256: str | None = None,
) -> ResolvedSource:
    """Resolve `tag` to real bytes on disk (or an already-loaded object).

    ``study_dir`` anchors the study-relative half of `csv:`/`parquet:`, the
    study-local `synthetic:` script, and the `data/raw/...` cache for
    `openml:`/`url:`; it may be ``None`` for the schemes that do not need one
    (`bundled:`, `hub:`, `sklearn:`) — a scheme that DOES need it raises a
    clear error rather than guessing a directory.

    ``offline`` (``KLEIN_OFFLINE=1`` at the call site) refuses `openml:`/
    `url:` BEFORE any request when no cached copy already satisfies the tag;
    every other scheme ignores it (nothing else ever touches the network).

    ``expected_sha256`` is the study's declared ``data.sha256`` pin. For
    `openml:`/`url:` it is effectively mandatory: an unpinned resolution
    still fetches (there is no other way to learn the digest) but then
    refuses, printing the digest to pin, exactly as
    ``references/data-sources.md`` describes; a declared pin that does not
    match the resolved bytes refuses too. Every other scheme ignores it (the
    DATA gate fingerprints their prepared output instead — no pin needed).

    Prints the `data source: ...` provenance line on success, once, and
    returns it as `.provenance_line` too, so a caller (or a test) never has
    to re-derive or re-capture it. Raises :class:`WorkflowError` on failure —
    :func:`kleinlib.data.load_data_hub` re-raises its `hub:` failures as
    `FileNotFoundError` to keep its own long-standing public contract.
    """
    parsed = parse_source(tag)
    if parsed.kind in (SourceKind.CSV, SourceKind.PARQUET):
        resolved = _resolve_csv_or_parquet(parsed, study_dir)
    elif parsed.kind is SourceKind.SYNTHETIC:
        resolved = _resolve_synthetic(parsed, study_dir)
    elif parsed.kind is SourceKind.BUNDLED:
        resolved = _resolve_bundled(parsed.value)
    elif parsed.kind is SourceKind.HUB:
        resolved = _resolve_hub(parsed.value)
    elif parsed.kind is SourceKind.SKLEARN:
        resolved = _resolve_sklearn(parsed.value)
    elif parsed.kind is SourceKind.OPENML:
        resolved = _resolve_openml(
            parsed.value, study_dir=study_dir, offline=offline, expected_sha256=expected_sha256
        )
    elif parsed.kind is SourceKind.URL:
        resolved = _resolve_url(
            parsed.value, study_dir=study_dir, offline=offline, expected_sha256=expected_sha256
        )
    else:  # pragma: no cover - exhaustive over SourceKind
        raise AssertionError(f"unhandled source kind {parsed.kind!r}")
    print(resolved.provenance_line)
    return resolved


# --------------------------------------------------------------------------
# Shared filesystem helpers
# --------------------------------------------------------------------------


def _engine_root() -> Path:
    """Repo root, anchored on this module's own location — NEVER on cwd.

    Same anchor `kleinlib.data` always used for the bundled datasets
    directory: study scripts and CI routinely run with cwd outside the repo,
    and a bare `pip install` of the `kleinlib` wheel has no `datasets/` or
    repo-relative files at all (only `hub:`/`sklearn:`/`openml:`/`url:` work
    there; `bundled:` and repo-relative `csv:`/`parquet:` fail loudly).
    """
    return Path(__file__).resolve().parent.parent


def _bundled_dataset_dir(name: str) -> Path:
    return _engine_root() / "datasets" / name


def _single_data_file(directory: Path) -> Path | None:
    """The one `*.csv`/`*.csv.gz` file in `directory`, or `None` if absent.

    A directory that EXISTS but holds zero or multiple matching files is a
    misconfiguration, not an "absent" signal: raises rather than silently
    falling through to the next resolution branch (`hub:`'s plain-directory
    step, then bundled) and masking it.
    """
    if not directory.is_dir():
        return None
    files = sorted(directory.glob("*.csv")) + sorted(directory.glob("*.csv.gz"))
    if len(files) != 1:
        raise WorkflowError(
            f"dataset directory {directory} must contain exactly one "
            f"*.csv/*.csv.gz file, found {len(files)}: {[f.name for f in files]}"
        )
    return files[0]


def _openml_cache_file(study_dir: Path, id_str: str) -> Path:
    return Path(study_dir) / "data" / "raw" / "openml" / id_str / f"{id_str}.csv"


def _url_cache_file(study_dir: Path, url_str: str) -> Path:
    url_key = sha256_bytes(url_str.encode())[:12]
    basename = Path(urllib.parse.urlparse(url_str).path).name or "download"
    return Path(study_dir) / "data" / "raw" / "url" / url_key / basename


def _require_pin(label: str, digest: str, expected_sha256: str | None) -> None:
    if expected_sha256 is None:
        raise WorkflowError(
            f"{label} has no data.sha256 pin declared — refusing to treat the "
            f"resolved bytes as usable evidence. Pin it: data.sha256: {digest}"
        )
    if expected_sha256 != digest:
        raise WorkflowError(
            f"{label} pin mismatch: study.yaml declares data.sha256={expected_sha256} "
            f"but the resolved bytes hash to {digest} — the remote data changed, or "
            "the declared pin is wrong; do not trust this data until this is resolved"
        )


# --------------------------------------------------------------------------
# csv: / parquet:
# --------------------------------------------------------------------------


def _resolve_csv_or_parquet(parsed: ParsedSource, study_dir: Path | None) -> ResolvedSource:
    if study_dir is None:
        raise WorkflowError(
            f"{parsed.raw!r} is study- then repo-relative and needs a study_dir"
        )
    candidates = [Path(study_dir) / parsed.value, _engine_root() / parsed.value]
    for candidate in candidates:
        if candidate.is_file():
            return ResolvedSource(
                path=candidate,
                kind=parsed.kind,
                provenance_line=f"data source: {parsed.kind.value} — {candidate}",
                digest=sha256_file(candidate),
            )
    tried = " or ".join(str(c) for c in candidates)
    raise WorkflowError(f"{parsed.raw!r} does not resolve: tried {tried}")


# --------------------------------------------------------------------------
# synthetic:
# --------------------------------------------------------------------------


def _resolve_synthetic(parsed: ParsedSource, study_dir: Path | None) -> ResolvedSource:
    if study_dir is None:
        raise WorkflowError(f"{parsed.raw!r} needs a study_dir (a study-local script)")
    script = Path(study_dir) / parsed.value
    if not script.is_file():
        raise WorkflowError(f"{parsed.raw!r} does not resolve: no such study-local script {script}")
    return ResolvedSource(
        path=script,
        kind=SourceKind.SYNTHETIC,
        provenance_line=f"data source: synthetic — {script}",
        digest=sha256_file(script),
    )


# --------------------------------------------------------------------------
# bundled: / hub: (and the shadow guard shared by both)
# --------------------------------------------------------------------------


def _refuse_hub_shadow(name: str) -> None:
    """Loud error when `bundled:<name>` is requested but `$DATA_HUB` also has one.

    Scoped to the one collision `describe`/`resolve` can check without any
    side effect: a plain `$DATA_HUB/<name>/*.csv` directory. Whether a hub
    LOADER MODULE would also serve `name` cannot be checked without calling
    it (a side effect this function refuses to have) — undetectable shadowing
    through a loader module is a known, documented limitation.
    """
    hub_root = os.environ.get("DATA_HUB")
    if not hub_root:
        return
    shadow_dir = Path(hub_root) / name
    shadow_file = _single_data_file(shadow_dir)
    if shadow_file is not None:
        raise WorkflowError(
            f"bundled:{name} was requested but $DATA_HUB={hub_root} also has a "
            f"same-named dataset at {shadow_dir} that hub:{name} would resolve "
            f"instead — almost certainly a mistake. Use hub:{name} for the hub "
            f"copy, or unset $DATA_HUB to use the bundled copy unambiguously."
        )


def _resolve_bundled(name: str) -> ResolvedSource:
    bundled_dir = _bundled_dataset_dir(name)
    data_file = _single_data_file(bundled_dir)
    if data_file is None:
        raise WorkflowError(f"bundled dataset directory does not exist: {bundled_dir}")
    _refuse_hub_shadow(name)
    return ResolvedSource(
        path=data_file,
        kind=SourceKind.BUNDLED,
        provenance_line=f"data source: bundled — {data_file}",
        digest=sha256_file(data_file),
    )


def _resolve_hub(name: str) -> ResolvedSource:
    """`hub:<name>` — loader module -> plain directory -> bundled copy -> error.

    The loader-module branch's provenance line and digest-less
    `ResolvedSource` are BYTE-IDENTICAL to the pre-E11
    `kleinlib.data.load_data_hub`, because studies 00/05/06's run logs
    already contain that exact line as evidence. The plain-directory branch
    is new (E11 review 2): a hub that ships no `loaders.python.hub` module at
    all is no longer a dead end — a `<name>/*.csv` (or `.csv.gz`) directory
    directly under `$DATA_HUB` now resolves too.
    """
    hub_root = os.environ.get("DATA_HUB")
    if hub_root:
        hub_path = Path(hub_root)
        if str(hub_path) not in sys.path:
            sys.path.insert(0, str(hub_path))
        try:
            from loaders.python.hub import load_dataset  # type: ignore[import-not-found]
        except ImportError:
            load_dataset = None
        if load_dataset is not None:
            loaded = load_dataset(name)
            return ResolvedSource(
                path=None,
                kind=SourceKind.HUB,
                provenance_line=f"data source: hub — {hub_path / 'datasets' / name}",
                digest=None,
                loaded=loaded,
            )
        plain_file = _single_data_file(hub_path / name)
        if plain_file is not None:
            return ResolvedSource(
                path=plain_file,
                kind=SourceKind.HUB,
                provenance_line=f"data source: hub — {plain_file}",
                digest=sha256_file(plain_file),
            )
    bundled_dir = _bundled_dataset_dir(name)
    bundled_file = _single_data_file(bundled_dir)
    if bundled_file is not None:
        return ResolvedSource(
            path=bundled_file,
            kind=SourceKind.HUB,
            provenance_line=f"data source: bundled — {bundled_file}",
            digest=sha256_file(bundled_file),
        )
    raise WorkflowError(
        f"cannot resolve dataset {name!r}: $DATA_HUB is not set and no bundled "
        f"copy exists at {bundled_dir}. Options: (1) export DATA_HUB=<your data-hub "
        f"root>; (2) run from a clone of the klein-auto-research repo, which "
        f"bundles its study datasets under datasets/; (3) point the study at a "
        f"local file instead (data source csv:<path> via kleinlib.data.load_prepared)."
    )


# --------------------------------------------------------------------------
# sklearn:
# --------------------------------------------------------------------------


def _resolve_sklearn(loader_name: str) -> ResolvedSource:
    if loader_name not in ALLOWED_SKLEARN_LOADERS:
        reason = "needs network — refused" if loader_name.startswith("fetch_") else "not on the offline allowlist"
        raise WorkflowError(
            f"sklearn:{loader_name} {reason}; offline-safe loaders: "
            + ", ".join(sorted(ALLOWED_SKLEARN_LOADERS))
        )
    return ResolvedSource(
        path=None,
        kind=SourceKind.SKLEARN,
        provenance_line=f"data source: sklearn — sklearn.datasets.{loader_name}",
        digest=None,
    )


# --------------------------------------------------------------------------
# openml: / url: — the two network schemes
# --------------------------------------------------------------------------


def _resolve_openml(
    id_str: str,
    *,
    study_dir: Path | None,
    offline: bool,
    expected_sha256: str | None,
) -> ResolvedSource:
    if study_dir is None:
        raise WorkflowError(f"openml:{id_str} needs a study_dir (the cache lives under data/raw/)")
    if not id_str.isdigit():
        raise WorkflowError(f"openml:{id_str} — the id must be numeric")
    cache_file = _openml_cache_file(Path(study_dir), id_str)
    if cache_file.is_file():
        digest = sha256_file(cache_file)
    else:
        if offline:
            raise WorkflowError(
                f"openml:{id_str} is not cached at {cache_file} and KLEIN_OFFLINE=1 "
                "refuses the network fetch needed to obtain it"
            )
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        _openml_download(id_str, cache_file)
        digest = sha256_file(cache_file)
    _require_pin(f"openml:{id_str}", digest, expected_sha256)
    return ResolvedSource(
        path=cache_file,
        kind=SourceKind.OPENML,
        provenance_line=f"data source: openml — {cache_file} (id={id_str})",
        digest=digest,
    )


def _resolve_url(
    url_str: str,
    *,
    study_dir: Path | None,
    offline: bool,
    expected_sha256: str | None,
) -> ResolvedSource:
    if study_dir is None:
        raise WorkflowError(f"url:{url_str} needs a study_dir (the cache lives under data/raw/)")
    if not url_str.startswith("https://"):
        raise WorkflowError(f"url:{url_str} must be https — refused")
    cache_file = _url_cache_file(Path(study_dir), url_str)
    if cache_file.is_file():
        digest = sha256_file(cache_file)
    else:
        if offline:
            raise WorkflowError(
                f"url:{url_str} is not cached at {cache_file} and KLEIN_OFFLINE=1 "
                "refuses the network fetch needed to obtain it"
            )
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        _download_url_streamed(url_str, cache_file)
        digest = sha256_file(cache_file)
    _require_pin(f"url:{url_str}", digest, expected_sha256)
    return ResolvedSource(
        path=cache_file,
        kind=SourceKind.URL,
        provenance_line=f"data source: url — {cache_file} ({url_str})",
        digest=digest,
    )


def _fetch_bytes_https(url: str) -> bytes:
    """The one place any bytes come off the network in this module."""
    if not url.startswith("https://"):
        raise WorkflowError(f"refusing a non-https URL: {url!r}")
    request = urllib.request.Request(url, headers={"User-Agent": "klein-auto-research/sources.py"})
    with urllib.request.urlopen(request, timeout=60) as response:  # noqa: S310 (https enforced above)
        return response.read()


def _download_url_streamed(url: str, dest: Path) -> None:
    """Stream `url` to `dest` via a temp file + atomic rename.

    Streamed per `data-sources.md` ("streamed, digest verified before use");
    the digest check itself happens in the caller, on the file this leaves
    behind, so a partial download can never look like the pinned bytes (an
    interrupted write leaves only the `.tmp` sibling, never `dest`).
    """
    request = urllib.request.Request(url, headers={"User-Agent": "klein-auto-research/sources.py"})
    temp = dest.with_name(f".{dest.name}.{os.getpid()}.tmp")
    try:
        with urllib.request.urlopen(request, timeout=60) as response, temp.open("wb") as handle:  # noqa: S310
            shutil.copyfileobj(response, handle, length=1024 * 1024)
        os.replace(temp, dest)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def _openml_download(id_str: str, dest: Path) -> None:
    """Fetch OpenML dataset `id_str`, writing it as CSV to `dest`.

    Prefers the `openml` package when it is importable (an optional extra —
    not declared by this project's own `pyproject.toml`; add it to your
    environment to use this path). Otherwise falls back to OpenML's public
    JSON description API plus a streamed ARFF download, parsed with
    `scipy.io.arff` (already a hard dependency via scikit-learn) — "the
    simplest path that pins bytes" the E11 package note asks for. Every
    network call funnels through `_fetch_bytes_https`/`_download_url_streamed`
    so a test can mock this one function wholesale; no test touches the
    network.
    """
    if importlib.util.find_spec("openml") is not None:
        import openml

        dataset = openml.datasets.get_dataset(int(id_str), download_data=True)
        frame, *_rest = dataset.get_data(dataset_format="dataframe")
        frame.to_csv(dest, index=False)
        return

    import pandas as pd
    from scipy.io import arff as scipy_arff

    description = json.loads(_fetch_bytes_https(f"https://www.openml.org/api/v1/json/data/{id_str}"))
    arff_url = description["data_set_description"]["url"]
    arff_bytes = _fetch_bytes_https(arff_url)
    with tempfile.NamedTemporaryFile(suffix=".arff") as handle:
        handle.write(arff_bytes)
        handle.flush()
        records, _meta = scipy_arff.loadarff(handle.name)
    frame = pd.DataFrame(records)
    for column in frame.columns:
        if frame[column].dtype == object:
            frame[column] = frame[column].apply(
                lambda v: v.decode("utf-8") if isinstance(v, bytes) else v
            )
    frame.to_csv(dest, index=False)


# --------------------------------------------------------------------------
# describe() — the offline, never-fetches introspection `klein doctor` uses
# --------------------------------------------------------------------------


def describe(
    tag: str,
    *,
    study_dir: Path | None = None,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    """A best-effort, network-free readiness report for `klein doctor`.

    Never raises for an ordinary "not ready yet" condition — a bad tag or a
    missing local file becomes `resolvable=False` with `detail` explaining
    why, so `klein doctor` can print one line per source and keep going
    rather than crash on the first unready study. Never prints, never
    fetches, never writes: every check here is a filesystem stat or a
    membership test.
    """
    try:
        parsed = parse_source(tag)
    except WorkflowError as exc:
        return {
            "tag": tag,
            "scheme": None,
            "value": None,
            "network_required": None,
            "pin_required": None,
            "pin_present": None,
            "resolvable": False,
            "detail": str(exc),
        }
    network_required = parsed.kind in (SourceKind.OPENML, SourceKind.URL)
    pin_present = (expected_sha256 is not None) if network_required else None
    resolvable, detail = _describe_readiness(
        parsed, study_dir=study_dir, expected_sha256=expected_sha256
    )
    return {
        "tag": tag,
        "scheme": parsed.kind.value,
        "value": parsed.value,
        "network_required": network_required,
        "pin_required": network_required,
        "pin_present": pin_present,
        "resolvable": resolvable,
        "detail": detail,
    }


def _describe_readiness(
    parsed: ParsedSource,
    *,
    study_dir: Path | None,
    expected_sha256: str | None,
) -> tuple[bool, str]:
    kind = parsed.kind
    if kind in (SourceKind.CSV, SourceKind.PARQUET):
        if study_dir is None:
            return False, "no --study given to check the study-/repo-relative candidates"
        candidates = [Path(study_dir) / parsed.value, _engine_root() / parsed.value]
        for candidate in candidates:
            if candidate.is_file():
                return True, f"found at {candidate}"
        return False, "not found at " + " or ".join(str(c) for c in candidates)

    if kind is SourceKind.SYNTHETIC:
        if study_dir is None:
            return False, "no --study given to check the study-local script"
        script = Path(study_dir) / parsed.value
        if script.is_file():
            return True, f"script found at {script}"
        return False, f"script not found at {script}"

    if kind is SourceKind.BUNDLED:
        bundled_dir = _bundled_dataset_dir(parsed.value)
        try:
            data_file = _single_data_file(bundled_dir)
        except WorkflowError as exc:
            return False, str(exc)
        if data_file is None:
            return False, f"no bundled directory at {bundled_dir}"
        return True, f"found at {data_file}"

    if kind is SourceKind.HUB:
        hub_root = os.environ.get("DATA_HUB")
        if hub_root:
            hub_path = Path(hub_root)
            loader_present = (hub_path / "loaders" / "python" / "hub.py").is_file()
            if loader_present:
                return True, f"$DATA_HUB={hub_path} has a loaders/python/hub.py loader module"
            try:
                plain_file = _single_data_file(hub_path / parsed.value)
            except WorkflowError as exc:
                return False, str(exc)
            if plain_file is not None:
                return True, f"$DATA_HUB plain directory found at {plain_file}"
        bundled_dir = _bundled_dataset_dir(parsed.value)
        try:
            bundled_file = _single_data_file(bundled_dir)
        except WorkflowError as exc:
            return False, str(exc)
        if bundled_file is not None:
            return True, f"falls back to the bundled copy at {bundled_file}"
        hub_note = f"$DATA_HUB={hub_root} has neither a loader nor a plain directory; " if hub_root else "$DATA_HUB is not set; "
        return False, hub_note + f"no bundled copy at {bundled_dir}"

    if kind is SourceKind.SKLEARN:
        if parsed.value not in ALLOWED_SKLEARN_LOADERS:
            return False, f"{parsed.value!r} is not on the offline allowlist"
        has_sklearn = importlib.util.find_spec("sklearn") is not None
        if has_sklearn:
            return True, f"sklearn.datasets.{parsed.value}"
        return False, "scikit-learn is not installed"

    if kind in (SourceKind.OPENML, SourceKind.URL):
        if study_dir is None:
            return False, "no --study given to check the data/raw/ cache"
        cache_file = (
            _openml_cache_file(Path(study_dir), parsed.value)
            if kind is SourceKind.OPENML
            else _url_cache_file(Path(study_dir), parsed.value)
        )
        if not cache_file.is_file():
            return False, f"not cached at {cache_file}; needs a network fetch (refused under KLEIN_OFFLINE=1)"
        digest = sha256_file(cache_file)
        if expected_sha256 is None:
            return False, f"cached at {cache_file} but data.sha256 is not declared — pin it: {digest}"
        if digest != expected_sha256:
            return False, f"cached bytes at {cache_file} hash to {digest}, which does not match the declared pin"
        return True, f"cached and pin-verified at {cache_file}"

    raise AssertionError(f"unhandled source kind {kind!r}")  # pragma: no cover
