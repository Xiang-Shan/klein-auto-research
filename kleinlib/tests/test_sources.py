"""Tests for kleinlib.sources: parse_source / resolve / describe.

No test touches the network — `_openml_download` and `_download_url_streamed`
are the two (and only two) seams that ever reach `urllib.request`, and every
network-shaped test here monkeypatches one of them (or, for the offline and
cache-hit paths, proves neither is even called by making them raise if
invoked).
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from kleinlib import sources
from kleinlib.errors import WorkflowError
from kleinlib.primitives import sha256_bytes, sha256_file
from kleinlib.sources import (
    ParsedSource,
    ResolvedSource,
    SourceKind,
    describe,
    parse_source,
    resolve,
)

# --------------------------------------------------------------------------
# parse_source
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tag", "kind", "value"),
    [
        ("csv:data/prepared/x.csv", SourceKind.CSV, "data/prepared/x.csv"),
        ("parquet:data/prepared/x.parquet", SourceKind.PARQUET, "data/prepared/x.parquet"),
        ("synthetic:make_data.py", SourceKind.SYNTHETIC, "make_data.py"),
        ("bundled:insurance-claims", SourceKind.BUNDLED, "insurance-claims"),
        ("hub:freMTPL2", SourceKind.HUB, "freMTPL2"),
        ("sklearn:load_iris", SourceKind.SKLEARN, "load_iris"),
        ("openml:41214", SourceKind.OPENML, "41214"),
        ("url:https://example.test/a.csv", SourceKind.URL, "https://example.test/a.csv"),
    ],
)
def test_parse_source_every_scheme(tag: str, kind: SourceKind, value: str) -> None:
    parsed = parse_source(tag)
    assert parsed == ParsedSource(kind=kind, value=value, raw=tag)


def test_parse_source_url_value_keeps_its_own_colon() -> None:
    parsed = parse_source("url:https://example.test:8443/a.csv")
    assert parsed.value == "https://example.test:8443/a.csv"


@pytest.mark.parametrize("tag", ["", "no-colon-here", "csv:", ":emptyscheme", "  "])
def test_parse_source_rejects_malformed_tags(tag: str) -> None:
    with pytest.raises(WorkflowError):
        parse_source(tag)


def test_parse_source_rejects_unknown_scheme() -> None:
    with pytest.raises(WorkflowError, match="unknown scheme 'data_hub'"):
        parse_source("data_hub:freMTPL2")


def test_parse_source_rejects_non_string() -> None:
    with pytest.raises(WorkflowError):
        parse_source(None)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# csv: / parquet:
# --------------------------------------------------------------------------


def test_resolve_csv_study_relative(tmp_path: Path, capsys) -> None:
    study = tmp_path / "study"
    (study / "data" / "prepared").mkdir(parents=True)
    csv_path = study / "data" / "prepared" / "x.csv"
    csv_path.write_text("a,b\n1,2\n", encoding="utf-8")

    resolved = resolve("csv:data/prepared/x.csv", study_dir=study, offline=True)

    assert resolved.path == csv_path
    assert resolved.kind is SourceKind.CSV
    assert resolved.digest == sha256_file(csv_path)
    assert resolved.provenance_line == f"data source: csv — {csv_path}"
    assert capsys.readouterr().out.strip() == resolved.provenance_line


def test_resolve_csv_falls_back_to_repo_relative(tmp_path: Path, monkeypatch) -> None:
    fake_repo = tmp_path / "fake_repo"
    fake_repo.mkdir()
    repo_file = fake_repo / "shared.csv"
    repo_file.write_text("a\n1\n", encoding="utf-8")
    monkeypatch.setattr(sources, "_engine_root", lambda: fake_repo)

    study = tmp_path / "study"
    study.mkdir()

    resolved = resolve("csv:shared.csv", study_dir=study, offline=True)
    assert resolved.path == repo_file


def test_resolve_csv_missing_names_both_candidates(tmp_path: Path, monkeypatch) -> None:
    fake_repo = tmp_path / "fake_repo"
    fake_repo.mkdir()
    monkeypatch.setattr(sources, "_engine_root", lambda: fake_repo)
    study = tmp_path / "study"
    study.mkdir()

    with pytest.raises(WorkflowError) as excinfo:
        resolve("csv:nope.csv", study_dir=study, offline=True)
    message = str(excinfo.value)
    assert str(study / "nope.csv") in message
    assert str(fake_repo / "nope.csv") in message


def test_resolve_parquet_study_relative(tmp_path: Path) -> None:
    pytest.importorskip("pyarrow")  # the parquet extra is optional
    study = tmp_path / "study"
    study.mkdir()
    frame_path = study / "x.parquet"
    pd.DataFrame({"a": [1, 2]}).to_parquet(frame_path)

    resolved = resolve("parquet:x.parquet", study_dir=study, offline=True)
    assert resolved.kind is SourceKind.PARQUET
    assert resolved.path == frame_path


@pytest.mark.parametrize("tag", ["csv:x.csv", "parquet:x.parquet", "synthetic:make.py"])
def test_resolve_requires_study_dir_for_local_schemes(tag: str) -> None:
    with pytest.raises(WorkflowError, match="study_dir"):
        resolve(tag, study_dir=None, offline=True)


# --------------------------------------------------------------------------
# synthetic:
# --------------------------------------------------------------------------


def test_resolve_synthetic_returns_script_path_and_digest(tmp_path: Path) -> None:
    study = tmp_path / "study"
    study.mkdir()
    script = study / "make_data.py"
    script.write_text("# generates data\n", encoding="utf-8")

    resolved = resolve("synthetic:make_data.py", study_dir=study, offline=True)
    assert resolved.path == script
    assert resolved.kind is SourceKind.SYNTHETIC
    assert resolved.digest == sha256_file(script)
    assert resolved.provenance_line == f"data source: synthetic — {script}"


def test_resolve_synthetic_missing_script_raises(tmp_path: Path) -> None:
    study = tmp_path / "study"
    study.mkdir()
    with pytest.raises(WorkflowError, match="make_data.py"):
        resolve("synthetic:make_data.py", study_dir=study, offline=True)


# --------------------------------------------------------------------------
# bundled:
# --------------------------------------------------------------------------


def test_resolve_bundled_reads_repo_dataset(capsys) -> None:
    resolved = resolve("bundled:hurricane_top30_pl1998", study_dir=None, offline=True)
    assert resolved.kind is SourceKind.BUNDLED
    assert resolved.path is not None
    assert resolved.path.name == "hurricane_top30_pl1998.csv"
    assert resolved.digest == sha256_file(resolved.path)
    assert capsys.readouterr().out.strip() == f"data source: bundled — {resolved.path}"


def test_resolve_bundled_missing_raises() -> None:
    with pytest.raises(WorkflowError, match="does not exist"):
        resolve("bundled:no-such-dataset-anywhere", study_dir=None, offline=True)


def test_resolve_bundled_shadowed_by_data_hub_raises_loudly(tmp_path: Path, monkeypatch) -> None:
    hub = tmp_path / "hub"
    shadow_dir = hub / "hurricane_top30_pl1998"
    shadow_dir.mkdir(parents=True)
    (shadow_dir / "data.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    monkeypatch.setenv("DATA_HUB", str(hub))

    with pytest.raises(WorkflowError, match="almost certainly a mistake"):
        resolve("bundled:hurricane_top30_pl1998", study_dir=None, offline=True)


def test_resolve_bundled_unaffected_by_unrelated_data_hub(tmp_path: Path, monkeypatch) -> None:
    hub = tmp_path / "hub"
    hub.mkdir()
    monkeypatch.setenv("DATA_HUB", str(hub))
    resolved = resolve("bundled:hurricane_top30_pl1998", study_dir=None, offline=True)
    assert resolved.path is not None


# --------------------------------------------------------------------------
# hub:
# --------------------------------------------------------------------------


def _write_hub_loader(hub: Path, body: str) -> None:
    loader_pkg = hub / "loaders" / "python"
    loader_pkg.mkdir(parents=True)
    (hub / "loaders" / "__init__.py").write_text("")
    (loader_pkg / "__init__.py").write_text("")
    (loader_pkg / "hub.py").write_text(body)


def test_resolve_hub_loader_module_branch_matches_legacy_line(tmp_path: Path, monkeypatch, capsys) -> None:
    hub = tmp_path / "hub"
    _write_hub_loader(
        hub,
        "import pandas as pd\n\n\ndef load_dataset(name):\n    return pd.DataFrame({'from_hub': [name]})\n",
    )
    monkeypatch.setenv("DATA_HUB", str(hub))

    resolved = resolve("hub:some-name", study_dir=None, offline=True)
    assert resolved.path is None
    assert list(resolved.loaded.columns) == ["from_hub"]
    expected_line = f"data source: hub — {hub / 'datasets' / 'some-name'}"
    assert resolved.provenance_line == expected_line
    assert capsys.readouterr().out.strip() == expected_line


def test_resolve_hub_plain_directory_fallback(tmp_path: Path, monkeypatch) -> None:
    hub = tmp_path / "hub"
    plain = hub / "myset"
    plain.mkdir(parents=True)
    data_file = plain / "myset.csv"
    data_file.write_text("a,b\n1,2\n", encoding="utf-8")
    monkeypatch.setenv("DATA_HUB", str(hub))

    resolved = resolve("hub:myset", study_dir=None, offline=True)
    assert resolved.path == data_file
    assert resolved.loaded is None
    assert resolved.digest == sha256_file(data_file)
    assert resolved.provenance_line == f"data source: hub — {data_file}"


def test_resolve_hub_falls_back_to_bundled_when_data_hub_has_neither(tmp_path: Path, monkeypatch) -> None:
    hub = tmp_path / "hub"
    hub.mkdir()  # exists, but no loader module and no matching plain directory
    monkeypatch.setenv("DATA_HUB", str(hub))

    resolved = resolve("hub:hurricane_top30_pl1998", study_dir=None, offline=True)
    assert resolved.path is not None
    assert resolved.path.name == "hurricane_top30_pl1998.csv"
    assert resolved.provenance_line == f"data source: bundled — {resolved.path}"


def test_resolve_hub_raises_actionable_error_when_nowhere_found(monkeypatch) -> None:
    monkeypatch.delenv("DATA_HUB", raising=False)
    with pytest.raises(WorkflowError) as excinfo:
        resolve("hub:no-such-dataset-anywhere", study_dir=None, offline=True)
    message = str(excinfo.value)
    assert "DATA_HUB" in message
    assert "datasets/" in message
    assert "csv:" in message


# --------------------------------------------------------------------------
# sklearn:
# --------------------------------------------------------------------------


def test_resolve_sklearn_allowed_loader() -> None:
    resolved = resolve("sklearn:load_iris", study_dir=None, offline=True)
    assert resolved.kind is SourceKind.SKLEARN
    assert resolved.path is None
    assert resolved.provenance_line == "data source: sklearn — sklearn.datasets.load_iris"


def test_resolve_sklearn_refuses_fetch_loader() -> None:
    with pytest.raises(WorkflowError, match="needs network"):
        resolve("sklearn:fetch_openml", study_dir=None, offline=True)


def test_resolve_sklearn_refuses_unknown_loader() -> None:
    with pytest.raises(WorkflowError, match="not on the offline allowlist"):
        resolve("sklearn:load_files", study_dir=None, offline=True)


# --------------------------------------------------------------------------
# openml:
# --------------------------------------------------------------------------


def test_resolve_openml_offline_refuses_before_any_request(tmp_path: Path, monkeypatch) -> None:
    study = tmp_path / "study"
    study.mkdir()

    def _boom(*_args, **_kwargs):
        raise AssertionError("must not fetch when offline")

    monkeypatch.setattr(sources, "_openml_download", _boom)
    with pytest.raises(WorkflowError, match="KLEIN_OFFLINE"):
        resolve("openml:41214", study_dir=study, offline=True)


def test_resolve_openml_unpinned_fetch_refuses_and_prints_digest_to_pin(tmp_path: Path, monkeypatch) -> None:
    study = tmp_path / "study"
    study.mkdir()
    payload = b"a,b\n1,2\n"

    def _fake_download(_id_str: str, dest: Path) -> None:
        dest.write_bytes(payload)

    monkeypatch.setattr(sources, "_openml_download", _fake_download)
    expected_digest = sha256_bytes(payload)

    with pytest.raises(WorkflowError, match=f"data.sha256: {expected_digest}"):
        resolve("openml:41214", study_dir=study, offline=False)

    # The bytes were cached even though the pin was refused: re-resolving
    # with the correct pin must not need to fetch again.
    monkeypatch.setattr(
        sources, "_openml_download", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("no refetch"))
    )
    resolved = resolve("openml:41214", study_dir=study, offline=False, expected_sha256=expected_digest)
    assert resolved.digest == expected_digest


def test_resolve_openml_pin_mismatch_raises(tmp_path: Path, monkeypatch) -> None:
    study = tmp_path / "study"
    study.mkdir()
    monkeypatch.setattr(sources, "_openml_download", lambda _id, dest: dest.write_bytes(b"x\n"))
    with pytest.raises(WorkflowError, match="pin mismatch"):
        resolve("openml:41214", study_dir=study, offline=False, expected_sha256="0" * 64)


def test_resolve_openml_pin_match_succeeds_and_caches(tmp_path: Path, monkeypatch, capsys) -> None:
    study = tmp_path / "study"
    study.mkdir()
    payload = b"a,b\n1,2\n"
    monkeypatch.setattr(sources, "_openml_download", lambda _id, dest: dest.write_bytes(payload))
    digest = sha256_bytes(payload)

    resolved = resolve("openml:41214", study_dir=study, offline=False, expected_sha256=digest)
    assert resolved.digest == digest
    assert resolved.path == study / "data" / "raw" / "openml" / "41214" / "41214.csv"
    assert resolved.path.read_bytes() == payload
    assert "data source: openml —" in capsys.readouterr().out


def test_resolve_openml_uses_cache_without_refetching(tmp_path: Path, monkeypatch) -> None:
    study = tmp_path / "study"
    cache_file = study / "data" / "raw" / "openml" / "41214" / "41214.csv"
    cache_file.parent.mkdir(parents=True)
    payload = b"cached,bytes\n1,2\n"
    cache_file.write_bytes(payload)
    monkeypatch.setattr(
        sources, "_openml_download", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("no fetch"))
    )
    digest = sha256_bytes(payload)
    resolved = resolve("openml:41214", study_dir=study, offline=True, expected_sha256=digest)
    assert resolved.digest == digest


def test_resolve_openml_requires_study_dir() -> None:
    with pytest.raises(WorkflowError, match="study_dir"):
        resolve("openml:41214", study_dir=None, offline=True)


def test_resolve_openml_rejects_non_numeric_id(tmp_path: Path) -> None:
    study = tmp_path / "study"
    study.mkdir()
    with pytest.raises(WorkflowError, match="numeric"):
        resolve("openml:not-a-number", study_dir=study, offline=True)


# --------------------------------------------------------------------------
# url:
# --------------------------------------------------------------------------


def test_resolve_url_rejects_non_https(tmp_path: Path) -> None:
    study = tmp_path / "study"
    study.mkdir()
    with pytest.raises(WorkflowError, match="https"):
        resolve("url:http://example.test/a.csv", study_dir=study, offline=True)


def test_resolve_url_offline_refuses_before_any_request(tmp_path: Path, monkeypatch) -> None:
    study = tmp_path / "study"
    study.mkdir()
    monkeypatch.setattr(
        sources, "_download_url_streamed", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("no fetch"))
    )
    with pytest.raises(WorkflowError, match="KLEIN_OFFLINE"):
        resolve("url:https://example.test/a.csv", study_dir=study, offline=True)


def test_resolve_url_unpinned_prints_digest_to_pin(tmp_path: Path, monkeypatch) -> None:
    study = tmp_path / "study"
    study.mkdir()
    payload = b"col\nval\n"
    monkeypatch.setattr(sources, "_download_url_streamed", lambda _url, dest: dest.write_bytes(payload))
    digest = sha256_bytes(payload)
    with pytest.raises(WorkflowError, match=f"data.sha256: {digest}"):
        resolve("url:https://example.test/a.csv", study_dir=study, offline=False)


def test_resolve_url_pin_match_succeeds_and_caches(tmp_path: Path, monkeypatch) -> None:
    study = tmp_path / "study"
    study.mkdir()
    payload = b"col\nval\n"
    monkeypatch.setattr(sources, "_download_url_streamed", lambda _url, dest: dest.write_bytes(payload))
    digest = sha256_bytes(payload)

    resolved = resolve(
        "url:https://example.test/dir/a.csv", study_dir=study, offline=False, expected_sha256=digest
    )
    assert resolved.digest == digest
    assert resolved.path.name == "a.csv"
    assert resolved.path.read_bytes() == payload


def test_resolve_url_uses_cache_without_refetching(tmp_path: Path, monkeypatch) -> None:
    study = tmp_path / "study"
    study.mkdir()
    tag = "url:https://example.test/dir/a.csv"
    payload = b"col\nval\n"
    # Prime the cache exactly where resolve() will look for it.
    monkeypatch.setattr(sources, "_download_url_streamed", lambda _url, dest: dest.write_bytes(payload))
    digest = sha256_bytes(payload)
    resolve(tag, study_dir=study, offline=False, expected_sha256=digest)

    monkeypatch.setattr(
        sources, "_download_url_streamed", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("no refetch"))
    )
    resolved = resolve(tag, study_dir=study, offline=True, expected_sha256=digest)
    assert resolved.digest == digest


# --------------------------------------------------------------------------
# describe() — offline, never fetches
# --------------------------------------------------------------------------


def test_describe_unparseable_tag_reports_without_raising() -> None:
    report = describe("data_hub:freMTPL2")
    assert report["resolvable"] is False
    assert report["scheme"] is None
    assert "unknown scheme" in report["detail"]


def test_describe_csv_present_and_absent(tmp_path: Path) -> None:
    study = tmp_path / "study"
    study.mkdir()
    (study / "x.csv").write_text("a\n1\n", encoding="utf-8")

    present = describe("csv:x.csv", study_dir=study)
    assert present["resolvable"] is True
    assert present["network_required"] is False
    assert present["pin_required"] is False

    absent = describe("csv:missing.csv", study_dir=study)
    assert absent["resolvable"] is False


def test_describe_bundled_matches_resolve() -> None:
    report = describe("bundled:hurricane_top30_pl1998")
    assert report["resolvable"] is True
    assert report["scheme"] == "bundled"


def test_describe_bundled_reads_the_member_form_resolve_accepts() -> None:
    """`bundled:<name>/<file>` is the form a MULTI-file dataset needs — hubble1929
    ships two tables and no single one — and `describe` used to read the whole
    value as a directory name, telling `klein doctor` the source did not resolve
    on a machine where `resolve()` finds it immediately."""
    report = describe("bundled:hubble1929/hubble1929_table1.csv")
    assert report["resolvable"] is True, report["detail"]
    assert report["detail"].endswith("hubble1929_table1.csv")
    resolved = resolve("bundled:hubble1929/hubble1929_table1.csv", study_dir=None, offline=True)
    assert report["detail"] == f"found at {resolved.path}"

    missing = describe("bundled:hubble1929/nope.csv")
    assert missing["resolvable"] is False and "no file 'nope.csv'" in missing["detail"]
    escaping = describe("bundled:hubble1929/../insurance-claims")
    assert escaping["resolvable"] is False and "escapes" in escaping["detail"]
    absent = describe("bundled:no-such-dataset/x.csv")
    assert absent["resolvable"] is False and "no bundled directory" in absent["detail"]


def test_describe_sklearn_allowlist() -> None:
    ok = describe("sklearn:load_iris")
    assert ok["resolvable"] is True
    bad = describe("sklearn:load_files")
    assert bad["resolvable"] is False


def test_describe_openml_reports_pin_status_from_cache_without_network(tmp_path: Path, monkeypatch) -> None:
    def _boom(*_a, **_k):
        raise AssertionError("describe must never fetch")

    monkeypatch.setattr(sources, "_openml_download", _boom)
    monkeypatch.setattr(sources, "_download_url_streamed", _boom)

    study = tmp_path / "study"
    study.mkdir()

    not_cached = describe("openml:41214", study_dir=study)
    assert not_cached["resolvable"] is False
    assert not_cached["pin_required"] is True
    assert not_cached["pin_present"] is False

    cache_file = study / "data" / "raw" / "openml" / "41214" / "41214.csv"
    cache_file.parent.mkdir(parents=True)
    payload = b"a,b\n1,2\n"
    cache_file.write_bytes(payload)
    digest = sha256_bytes(payload)

    unpinned = describe("openml:41214", study_dir=study)
    assert unpinned["resolvable"] is False
    assert unpinned["pin_present"] is False

    wrong_pin = describe("openml:41214", study_dir=study, expected_sha256="0" * 64)
    assert wrong_pin["resolvable"] is False
    assert wrong_pin["pin_present"] is True

    right_pin = describe("openml:41214", study_dir=study, expected_sha256=digest)
    assert right_pin["resolvable"] is True


def test_describe_never_touches_the_network(tmp_path: Path, monkeypatch) -> None:
    """A strong version of "never fetches": urlopen itself explodes if called."""
    import urllib.request

    def _boom(*_a, **_k):
        raise AssertionError("describe() must never open a network connection")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    study = tmp_path / "study"
    study.mkdir()

    tags = [
        "csv:x.csv",
        "parquet:x.parquet",
        "synthetic:make.py",
        "bundled:hurricane_top30_pl1998",
        "hub:hurricane_top30_pl1998",
        "sklearn:load_iris",
        "openml:41214",
        "url:https://example.test/a.csv",
        "not-a-real-tag",
    ]
    for tag in tags:
        describe(tag, study_dir=study)  # must not raise via urlopen


# --------------------------------------------------------------------------
# ResolvedSource shape (documents the deliberate `loaded` extension)
# --------------------------------------------------------------------------


def test_resolved_source_loaded_field_defaults_to_none() -> None:
    resolved = ResolvedSource(path=Path("x"), kind=SourceKind.CSV, provenance_line="p", digest="d")
    assert resolved.loaded is None


# bundled:<name>/<file> — multi-file bundled datasets


def test_resolve_bundled_member_file(capsys) -> None:
    resolved = resolve("bundled:hubble1929/hubble1929_table1.csv", study_dir=None, offline=True)
    assert resolved.kind is SourceKind.BUNDLED
    assert resolved.path.name == "hubble1929_table1.csv"
    assert capsys.readouterr().out.strip() == f"data source: bundled — {resolved.path}"
    gz = resolve("bundled:tinyshakespeare/tinyshakespeare.txt.gz", study_dir=None, offline=True)
    assert gz.path.suffix == ".gz" and len(gz.digest) == 64


def test_resolve_bundled_member_escape_and_missing_refused() -> None:
    with pytest.raises(WorkflowError, match="escapes"):
        resolve("bundled:hubble1929/../insurance-claims/insurance_claims.csv.gz", study_dir=None, offline=True)
    with pytest.raises(WorkflowError, match="no file"):
        resolve("bundled:hubble1929/nope.csv", study_dir=None, offline=True)


def test_resolve_bundled_multi_file_dir_needs_a_member() -> None:
    with pytest.raises(WorkflowError, match="exactly one"):
        resolve("bundled:hubble1929", study_dir=None, offline=True)
