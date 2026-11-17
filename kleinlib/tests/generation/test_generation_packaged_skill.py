"""The generation layer finds its protocols and assets in an installed wheel.

A checkout keeps the skill at ``<repo>/.claude/skills/klein``; a wheel ships it as
``kleinlib/_skill``.  Neither ``protocol_hashes`` nor the benchmark schema lookup may
assume the checkout layout — both resolve through :mod:`kleinlib.resources`.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from kleinlib import resources
from kleinlib.generation import benchmark as gb
from kleinlib.generation import manifest as gm
from kleinlib.primitives import sha256_file

REPO_ROOT = Path(__file__).resolve().parents[3]
CHECKOUT_SKILL = REPO_ROOT / gm.SKILL_ROOT


@pytest.fixture
def packaged_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A fake installed package: ``<site>/kleinlib/_skill`` and nothing else.

    ``resources._PACKAGE`` points at it, so the checkout copy of the skill is not
    reachable through the package or engine-root candidates; the 'repository'
    passed to the code under test is an empty directory with no skill of its own.
    """
    package = tmp_path / "site" / "kleinlib"
    skill = package / "_skill"
    skill.mkdir(parents=True)
    shutil.copyfile(CHECKOUT_SKILL / "SKILL.md", skill / "SKILL.md")
    for key in gm.protocol_keys(gm.SUPPORTED_CAPABILITIES):
        target = skill / key
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(CHECKOUT_SKILL / key, target)
    schema = skill / "assets" / "generation" / gb.SCHEMA_NAME
    schema.parent.mkdir(parents=True)
    shutil.copyfile(CHECKOUT_SKILL / "assets" / "generation" / gb.SCHEMA_NAME, schema)
    monkeypatch.setattr(resources, "_PACKAGE", package)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    return skill


def test_protocol_hashes_resolve_from_the_packaged_layout(packaged_only: Path, tmp_path: Path) -> None:
    foreign_repo = tmp_path / "foreign-repo"
    foreign_repo.mkdir()
    assert resources.skill_root(foreign_repo) == packaged_only

    for repo in (foreign_repo, None):
        hashes = gm.protocol_hashes(repo, list(gm.SUPPORTED_CAPABILITIES))
        # keys stay the skill-relative paths
        assert set(hashes) == set(gm.protocol_keys(gm.SUPPORTED_CAPABILITIES))
        assert all(key.startswith("references/generation/") for key in hashes)
        assert None not in hashes.values()
        for key, digest in hashes.items():
            assert digest == sha256_file(packaged_only / key), key


def test_the_repository_copy_wins_over_the_packaged_one(packaged_only: Path, tmp_path: Path) -> None:
    repo = tmp_path / "vendored"
    (repo / ".git").mkdir(parents=True)
    vendored = repo / ".claude" / "skills" / "klein"
    (vendored / gm.SPINE_PROTOCOL).parent.mkdir(parents=True)
    (vendored / "SKILL.md").write_text("# vendored\n", encoding="utf-8")
    (vendored / gm.SPINE_PROTOCOL).write_text("pinned by the study\n", encoding="utf-8")

    hashes = gm.protocol_hashes(repo)
    assert hashes == {gm.SPINE_PROTOCOL: sha256_file(vendored / gm.SPINE_PROTOCOL)}


def test_the_benchmark_schema_resolves_from_the_packaged_layout(packaged_only: Path, tmp_path: Path) -> None:
    foreign_repo = tmp_path / "foreign-repo"
    foreign_repo.mkdir()
    expected = packaged_only / "assets" / "generation" / gb.SCHEMA_NAME
    assert gb.packaged_schema(foreign_repo) == expected
    assert gb.packaged_schema(None) == expected
    assert resources.asset_path(gb.SCHEMA_NAME) == expected  # a bare name is searched for recursively


def test_no_skill_anywhere_is_a_null_hash_not_a_crash(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(resources, "_PACKAGE", tmp_path / "nowhere" / "kleinlib")
    monkeypatch.setattr(resources, "_candidates", lambda study_dir: [tmp_path / "no-skill"])
    assert set(gm.protocol_hashes(tmp_path).values()) == {None}
    assert gb.packaged_schema(tmp_path) is None
