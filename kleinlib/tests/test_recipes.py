"""``klein new --recipe`` (Klein 2.3): domain scaffolds that run, and refuse to be rubber-stamped."""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from kleinlib.cli import main
from kleinlib.contract import load_contract, validate_contract
from kleinlib.errors import WorkflowError
from kleinlib.recipes import RECIPES
from kleinlib.state import record_gate

ROOT = Path(__file__).resolve().parents[2]
HAS_TORCH = importlib.util.find_spec("torch") is not None
TORCH_RECIPES = {"cv-classify", "dl-scaling"}


def _scaffold(tmp_path: Path, recipe: str, *extra: str) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    slug = "20-" + recipe
    assert main(["new", slug, "--root", str(repo / "studies"), "--recipe", recipe, *extra]) == 0
    return repo / "studies" / slug


def _fill_judgment(study: Path) -> None:
    for name in ("study.yaml", "program.md", "research_plan.md"):
        path = study / name
        text = path.read_text(encoding="utf-8")
        text = re.sub(r"\{\{[^{}]+\}\}", "filled by the test", text)
        path.write_text(text, encoding="utf-8")


@pytest.mark.parametrize("recipe", sorted(RECIPES))
def test_recipe_scaffolds_a_valid_contract_once_judgment_is_filled(tmp_path: Path, recipe: str) -> None:
    study = _scaffold(tmp_path, recipe)
    spec = RECIPES[recipe]
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    assert contract["kind"] == spec.kind
    assert contract["profile"] == spec.profile
    assert contract["data"]["modality"] == spec.modality
    assert contract["entrypoint"]["printed"] == "block"
    assert contract["policy"]["card_sections"] == "enforce"
    assert (spec.seeds is None) == ("seeds" not in contract["entrypoint"])
    for target in spec.files:
        assert (study / target).is_file(), target
    card = (study / "data_card.md").read_text(encoding="utf-8")
    assert "{{" in card  # the findings are the auditor's, never the recipe's
    with pytest.raises(WorkflowError, match="placeholder"):
        record_gate(study, "consult", acknowledged_by="tester")
    _fill_judgment(study)
    problems = validate_contract(load_contract(study), study)
    assert problems == [], problems


def _smoke(study: Path, script: str) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "KLEIN_SMOKE": "1", "PYTHONPATH": str(ROOT)}
    return subprocess.run(
        [sys.executable, "-u", script], cwd=study, env=env, capture_output=True, text=True, timeout=600
    )


@pytest.mark.parametrize("recipe", sorted(RECIPES))
def test_recipe_example_code_smokes_offline(tmp_path: Path, recipe: str) -> None:
    if recipe in TORCH_RECIPES and not HAS_TORCH:
        pytest.skip("needs the deep extra (torch)")
    study = _scaffold(tmp_path, recipe)
    _fill_judgment(study)
    prepared = _smoke(study, "prepare.py")
    assert prepared.returncode == 0, prepared.stdout + prepared.stderr
    entry = RECIPES[recipe].entrypoint
    run = _smoke(study, entry)
    assert run.returncode == 0, run.stdout + run.stderr
    assert "\n---\n" in "\n" + run.stdout
    assert "primary_metric:" in run.stdout


def test_explicit_flags_beat_the_recipe(tmp_path: Path) -> None:
    study = _scaffold(tmp_path, "tabular-predict", "--profile", "insurance", "--max-run-seconds", "77")
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    assert contract["profile"] == "insurance"
    assert contract["max_run_seconds"] == 77


def test_runner_python_rewrites_every_launch_command(tmp_path: Path) -> None:
    study = _scaffold(tmp_path, "math-verify", "--runner", "python")
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    assert contract["entrypoint"]["command"] == ["python", "-u", "search.py"]
    assert contract["tracks"]["primary"]["verifier"]["command"] == ["python", "-u", "verify.py"]


def test_dl_scaling_declares_the_exponent_track(tmp_path: Path) -> None:
    study = _scaffold(tmp_path, "dl-scaling")
    contract = yaml.safe_load((study / "study.yaml").read_text(encoding="utf-8"))
    assert set(contract["tracks"]) == {"primary", "exponent"}
    assert contract["tracks"]["exponent"]["mode"] == "registered"
