"""``hf:`` sources and ``data.inputs`` (Klein 2.3) — pinned, cached, offline-safe."""

from __future__ import annotations

from pathlib import Path

import pytest

from kleinlib.contract import _data_inputs_problems, _data_source_problems
from kleinlib.errors import WorkflowError
from kleinlib.primitives import sha256_file
from kleinlib.sources import (
    SourceKind,
    _url_cache_file,
    describe,
    hf_url,
    parse_source,
    resolve,
    resolve_inputs,
)

REV = "0123456789abcdef0123456789abcdef01234567"
TAG = f"hf:openai/gsm8k@{REV}/main/test.jsonl"


def _seed_cache(study: Path, url: str, payload: bytes) -> str:
    cache = _url_cache_file(study, url)
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_bytes(payload)
    return sha256_file(cache)


def test_hf_tag_parses_and_maps_to_an_immutable_resolve_url() -> None:
    assert parse_source(TAG).kind is SourceKind.HF
    assert hf_url(TAG.removeprefix("hf:")) == (
        f"https://huggingface.co/datasets/openai/gsm8k/resolve/{REV}/main/test.jsonl"
    )
    with pytest.raises(WorkflowError, match="40-hex"):
        hf_url("openai/gsm8k@main/test.jsonl")


def test_hf_resolves_offline_from_a_pinned_cache(tmp_path: Path, capsys) -> None:
    digest = _seed_cache(tmp_path, hf_url(TAG.removeprefix("hf:")), b'{"q": 1}\n')
    resolved = resolve(TAG, study_dir=tmp_path, offline=True, expected_sha256=digest)
    assert resolved.kind is SourceKind.HF and resolved.digest == digest
    assert "data source: hf" in capsys.readouterr().out
    with pytest.raises(WorkflowError, match="does not match|mismatch|pin"):
        resolve(TAG, study_dir=tmp_path, offline=True, expected_sha256="0" * 64)
    assert describe(TAG, study_dir=tmp_path, expected_sha256=digest)["resolvable"] is True


def test_hf_offline_without_cache_is_refused_before_any_request(tmp_path: Path) -> None:
    with pytest.raises(WorkflowError, match="KLEIN_OFFLINE"):
        resolve(TAG, study_dir=tmp_path, offline=True, expected_sha256="0" * 64)
    report = describe(TAG, study_dir=tmp_path, expected_sha256="0" * 64)
    assert report["network_required"] is True and report["resolvable"] is False


def test_contract_requires_a_pin_for_hf() -> None:
    assert any("mandatory" in p for p in _data_source_problems({"source": TAG}))
    assert _data_source_problems({"source": TAG, "sha256": "a" * 64}) == []


def test_data_inputs_shape_rules() -> None:
    assert _data_inputs_problems({}) == []
    assert _data_inputs_problems({"inputs": []})
    good = {"inputs": [{"source": "url:https://example.org/a.dta", "sha256": "b" * 64}]}
    assert _data_inputs_problems(good) == []
    unpinned = {"inputs": [{"source": "url:https://example.org/a.dta"}]}
    assert any("mandatory" in p for p in _data_inputs_problems(unpinned))
    extra = {"inputs": [{"source": "csv:a.csv", "bogus": 1}]}
    assert any("unknown keys" in p for p in _data_inputs_problems(extra))


def test_resolve_inputs_reads_every_pinned_file(tmp_path: Path) -> None:
    a = "https://example.org/nsw.dta"
    b = "https://example.org/psid.dta"
    da = _seed_cache(tmp_path, a, b"A")
    db = _seed_cache(tmp_path, b, b"B")
    contract = {
        "data": {
            "source": f"url:{a}",
            "sha256": da,
            "inputs": [{"source": f"url:{b}", "sha256": db}],
        }
    }
    resolved = resolve_inputs(contract, study_dir=tmp_path, offline=True)
    assert [r.path.read_bytes() for r in resolved] == [b"B"]
