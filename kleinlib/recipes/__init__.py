"""Domain recipes for ``klein new --recipe <id>`` (Klein 2.3).

A recipe is the plain ``klein new`` scaffold plus a domain overlay:

* the three axes, task type, metric, split and track mode a study in that field
  usually needs (each still overridable by an explicit ``klein new`` flag);
* the Klein 2.3 contract blocks a new study should have from day one —
  ``entrypoint.printed: block``, a seed array where seeds matter, an index
  split for non-tabular items, and a ``policy:`` block that makes the card
  headings, the realized split and the measured floor mechanical;
* WORKING example code (``prepare.py``, the entrypoint, a verifier where the
  kind needs one) on a small offline default source, so
  ``KLEIN_SMOKE=1 python prepare.py && KLEIN_SMOKE=1 python <entrypoint>`` runs
  the minute the study exists — swap ``data.source`` for your own data;
* a ``data_card.md`` skeleton with exactly the headings the policy enforces.

What a recipe never does is the judgment: the goal, the research questions, the
predictions and their rules, the audience and every data-card finding stay
``{{placeholders}}``, and every gate refuses a placeholder — a recipe saves
typing, never a decision.

Templates live INSIDE the package (``kleinlib/recipes/<dir>/*.tmpl``) because
the engine never reads the skill directory: a wheel installed in a foreign repo
(or in Claude Science) carries its recipes with it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

__all__ = ["RECIPES", "Recipe", "apply_recipe", "recipe_defaults"]


@dataclass(frozen=True)
class Recipe:
    id: str
    summary: str
    kind: str
    modality: str
    profile: str
    task_type: str
    metric_name: str
    metric_goal: str
    track_mode: str
    data_source: str
    data_path: str
    template_dir: str
    entrypoint: str
    mutable: tuple[str, ...]
    split_yaml: str
    files: dict[str, str] = field(default_factory=dict)
    seeds: tuple[int, ...] | None = None
    extra_metric_yaml: str = ""
    verifier_yaml: str = ""
    guardrails_yaml: str = ""
    family: str = ""
    target: str = ""
    max_run_seconds: int = 600
    calls_yaml: str = ""
    extra_tracks_yaml: str = ""
    exactness_yaml: str = ""


_POLICY_YAML = """\
# Klein 2.3 strictness, written by the recipe. Each knob only ADDS a requirement:
# card headings are checked at the DATA gate, a split that cannot be realized
# refuses the gate, and a frontier track may not run past Phase 1 unmeasured.
policy:
  card_sections: enforce
  realized_split: required
  noise_floor: required

"""

RECIPES: dict[str, Recipe] = {
    "tabular-predict": Recipe(
        id="tabular-predict",
        summary="predict · tabular · generic — binary classification on a table, frontier track",
        kind="predict",
        modality="tabular",
        profile="generic",
        task_type="classification",
        metric_name="val_auc",
        metric_goal="higher",
        track_mode="frontier",
        data_source="sklearn:load_breast_cancer",
        data_path="data/prepared/prepared.csv",
        template_dir="tabular_predict",
        entrypoint="train.py",
        mutable=("train.py",),
        split_yaml=(
            "  split:\n"
            "    kind: stratified\n"
            "    seed: {{SPLIT_SEED}}\n"
            "    development_size: 0.20\n"
            "    test_size: 0.20\n"
        ),
        files={"prepare.py": "prepare.py.tmpl", "train.py": "train.py.tmpl"},
        family="linear",
        target="target",
        max_run_seconds=300,
    ),
    "cv-classify": Recipe(
        id="cv-classify",
        summary="predict · image · cv — multiclass image classification, seed-array frontier",
        kind="predict",
        modality="image",
        profile="cv",
        task_type="classification",
        metric_name="val_macro_f1",
        metric_goal="higher",
        track_mode="frontier",
        data_source="sklearn:load_digits",
        data_path="data/prepared",
        template_dir="cv_classify",
        entrypoint="train.py",
        mutable=("model.py", "train.py"),
        split_yaml=(
            "  split:\n"
            "    kind: stratified        # or predefined, with split_column, for official partitions\n"
            "    seed: {{SPLIT_SEED}}\n"
            "    development_size: 0.20\n"
            "    test_size: 0.20\n"
            "    index: index.csv        # inside prepared_path: id, label[, group][, split]\n"
            "    id_column: id\n"
            "    label_column: label\n"
        ),
        files={
            "prepare.py": "prepare.py.tmpl",
            "model.py": "model.py.tmpl",
            "train.py": "train.py.tmpl",
        },
        seeds=(0, 1, 2),
        family="cnn",
        target="label",
        max_run_seconds=1800,
    ),
    "dl-scaling": Recipe(
        id="dl-scaling",
        summary="estimate · image · ml-research — data-scaling cells (registered) and a power-law fit",
        kind="estimate",
        modality="image",
        profile="ml-research",
        task_type="scalar",
        metric_name="val_mlogloss",
        metric_goal="lower",
        track_mode="registered",
        data_source="sklearn:load_digits",
        data_path="data/prepared",
        template_dir="dl_scaling",
        entrypoint="analyze.py",
        mutable=("analyze.py",),
        split_yaml=(
            "  split:\n"
            "    kind: random\n"
            "    seed: {{SPLIT_SEED}}\n"
            "    development_size: 0.20\n"
            "    test_size: 0.20\n"
            "    index: index.csv\n"
            "    id_column: id\n"
            "    label_column: label\n"
        ),
        files={"prepare.py": "prepare.py.tmpl", "analyze.py": "analyze.py.tmpl"},
        extra_tracks_yaml=(
            "  exponent:\n"
            "    mode: registered          # the power-law fit over every pinned cell\n"
            "    metric:\n"
            "      name: \"scaling_exponent\"\n"
            "      goal: \"higher\"\n"
            "      minimum_delta: 0.0\n"
            "      exactness: stochastic\n"
            "    guardrails: {}\n"
        ),
        seeds=(0, 1, 2),
        family="cnn",
        target="label",
        max_run_seconds=1800,
    ),
    "llm-eval": Recipe(
        id="llm-eval",
        summary="test · text · llm — a prompt/decoding comparison on benchmark items through the call ledger",
        kind="test",
        modality="text",
        profile="llm",
        task_type="scalar",
        metric_name="exact_match",
        metric_goal="higher",
        track_mode="registered",
        data_source="synthetic:prepare.py",
        data_path="data/prepared",
        template_dir="llm_eval",
        entrypoint="analyze.py",
        mutable=("analyze.py",),
        split_yaml=(
            "  split:\n"
            "    kind: predefined        # public items for development, a FRESH block sealed\n"
            "    index: index.csv        # id, answer, block, split\n"
            "    id_column: id\n"
            "    split_column: split\n"
        ),
        files={
            "prepare.py": "prepare.py.tmpl",
            "analyze.py": "analyze.py.tmpl",
            "score.py": "score.py.tmpl",
        },
        family="prompting",
        target="answer",
        max_run_seconds=3600,
        calls_yaml=(
            "# The model-call ledger (kleinlib.calls): every request/response is pinned under\n"
            "# calls/ and committed with the run, so the study re-verifies offline.\n"
            "calls:\n"
            "  dir: calls\n"
            "  base_url: \"https://dashscope.aliyuncs.com/compatible-mode/v1\"   # any OpenAI-compatible endpoint\n"
            "  model: \"{{MODEL_ID}}\"\n"
            "  budget_calls: 5000               # a hard stop in calls; add price + budget_usd to cap dollars\n"
            "  # price: {input_per_mtok: 0.0, output_per_mtok: 0.0}   # from the provider's page, dated\n"
            "  # budget_usd: 5.0\n"
            "\n"
        ),
    ),
    "ds-causal": Recipe(
        id="ds-causal",
        summary="estimate · tabular · data-science — an effect (ATT) with a bootstrap interval",
        kind="estimate",
        modality="tabular",
        profile="data-science",
        task_type="scalar",
        metric_name="att",
        metric_goal="higher",
        track_mode="registered",
        data_source="synthetic:make_data.py",
        data_path="data/prepared/prepared.csv",
        template_dir="ds_causal",
        entrypoint="analyze.py",
        mutable=("analyze.py",),
        split_yaml=(
            "  split:\n"
            "    kind: random            # nuisance models fit on train, the effect estimated on the held-out part\n"
            "    seed: {{SPLIT_SEED}}\n"
            "    development_size: 0.30\n"
            "    test_size: 0.30\n"
        ),
        files={
            "make_data.py": "make_data.py.tmpl",
            "prepare.py": "prepare.py.tmpl",
            "analyze.py": "analyze.py.tmpl",
        },
        family="propensity-score",
        target="y",
        max_run_seconds=300,
    ),
    "math-verify": Recipe(
        id="math-verify",
        summary="optimize · none · math — a verifier-judged search (Golomb rulers by default)",
        kind="optimize",
        modality="none",
        profile="math",
        task_type="scalar",
        metric_name="ruler_length",
        metric_goal="lower",
        track_mode="frontier",
        data_source="synthetic:prepare.py",
        data_path="data/prepared/instance.json",
        template_dir="math_verify",
        entrypoint="search.py",
        mutable=("search.py",),
        split_yaml=(
            "  split:\n"
            "    kind: none              # no rows: the instance and its seed blocks are frozen at DATA\n"
            "    seed: {{SPLIT_SEED}}\n"
        ),
        files={
            "prepare.py": "prepare.py.tmpl",
            "search.py": "search.py.tmpl",
            "verify.py": "verify.py.tmpl",
        },
        family="randomized search",
        target="ruler_length",
        max_run_seconds=300,
        exactness_yaml=(
            "      exactness: exact\n"
            "      exactness_note: \"The objective is the length of the verified ruler, an integer recomputed "
            "by verify.py with exact integer arithmetic; its resolution is 1.\"\n"
        ),
    ),
}


def recipe_defaults(recipe_id: str) -> dict[str, Any]:
    """The ``scaffold_study`` keyword defaults a recipe implies."""
    recipe = _get(recipe_id)
    scalar = recipe.task_type == "scalar"
    return {
        "kind": recipe.kind,
        "modality": recipe.modality,
        "profile": recipe.profile,
        "task_type": recipe.task_type,
        "metric_name": recipe.metric_name,
        "metric_goal": recipe.metric_goal,
        "data_source": recipe.data_source,
        "data_path": recipe.data_path,
        "family": recipe.family,
        "target": recipe.target,
        "max_run_seconds": recipe.max_run_seconds,
        "split_kind": "none" if scalar and "kind: none" in recipe.split_yaml else None,
    }


def _get(recipe_id: str) -> Recipe:
    try:
        return RECIPES[recipe_id]
    except KeyError:
        raise ValueError(f"unknown recipe {recipe_id!r}; choose one of {sorted(RECIPES)}") from None


def _template(recipe: Recipe, name: str) -> str:
    return (resources.files(__package__) / recipe.template_dir / name).read_text(encoding="utf-8")


def _render(text: str, values: dict[str, str]) -> str:
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


def _replace_block(text: str, start_pattern: str, end_pattern: str, replacement: str) -> str:
    match = re.search(start_pattern + r".*?(?=" + end_pattern + r")", text, flags=re.DOTALL | re.MULTILINE)
    if match is None:
        raise ValueError(f"recipe overlay could not find {start_pattern!r} in study.yaml")
    return text[: match.start()] + replacement + text[match.end() :]


def _card_skeleton(contract: dict[str, Any], recipe: Recipe) -> str:
    from ..state import required_card_sections

    lines = [
        "---",
        f"modality: {recipe.modality}",
        "---",
        "",
        "# Data card — {{STUDY_TITLE}}",
        "",
        f"Recipe `{recipe.id}`. Every heading below is required by `policy.card_sections:",
        "enforce`; replace each `{{…}}` with the finding, its evidence and its rank",
        "(`references/data-gate-protocol.md`). The DATA gate refuses a placeholder.",
        "",
    ]
    for heading in required_card_sections(contract):
        lines += [f"## {heading}", "", "{{" + heading.upper().replace(" ", "_").replace("/", "") + "}}", ""]
    lines += ["> **Decision:** {{GO_OR_NO_GO}}", ""]
    return "\n".join(lines)


def apply_recipe(study_dir: Path, recipe_id: str, *, split_seed: int = 42) -> list[str]:
    """Overlay ``recipe_id`` on a freshly scaffolded schema-3 study; returns files written."""
    import yaml

    recipe = _get(recipe_id)
    study_dir = Path(study_dir)
    contract_path = study_dir / "study.yaml"
    text = contract_path.read_text(encoding="utf-8")

    command = ", ".join(f'"{part}"' for part in ("uv", "run", "--locked", "python", "-u", recipe.entrypoint))
    mutable = ", ".join(f'"{name}"' for name in recipe.mutable)
    entry = (
        "entrypoint:\n"
        f"  command: [{command}]\n"
        f"  mutable: [{mutable}]\n"
        "  printed: block                # metrics are read from the final `---` block only\n"
    )
    if recipe.seeds is not None:
        entry += (
            f"  seeds: [{', '.join(str(s) for s in recipe.seeds)}]"
            "             # one candidate = one seed array; the notary decides on the mean\n"
        )
    text = _replace_block(text, r"^entrypoint:\n", r"\n# A track owns", entry)
    text = _replace_block(
        text,
        r"^  split:\n",
        r"\n# Per-run, per-phase",
        _render(recipe.split_yaml, {"SPLIT_SEED": str(int(split_seed))}),
    )
    text = text.replace(
        "# Per-run, per-phase time, and experiment-count limits are intentionally separate.",
        _POLICY_YAML
        + recipe.calls_yaml
        + "# Per-run, per-phase time, and experiment-count limits are intentionally separate.",
        1,
    )
    if recipe.exactness_yaml:
        text = text.replace(
            "      exactness: stochastic       # exact for an integer/closed-form objective\n",
            recipe.exactness_yaml,
        )
        text = re.sub(r"(\n      minimum_delta: )0(\n)", r"\g<1>1\2", text)
    if recipe.extra_tracks_yaml:
        text = text.replace("\ndata:\n", "\n" + recipe.extra_tracks_yaml + "data:\n", 1)
        n_tracks = len(yaml.safe_load(text).get("tracks") or {})
        text = re.sub(
            r"(  - id: confirmation\n(?:    [^\n]*\n)*?    max_experiments: )(\d+)",
            lambda m: m.group(1) + str(max(int(m.group(2)), n_tracks)),
            text,
            count=1,
        )
    contract_path.write_text(text, encoding="utf-8")
    contract = yaml.safe_load(text)

    written: list[str] = []
    values = {"STUDY_ID": str(contract.get("study_id")), "METRIC_NAME": recipe.metric_name}
    for target, template in recipe.files.items():
        (study_dir / target).write_text(_render(_template(recipe, template), values), encoding="utf-8")
        written.append(target)
    (study_dir / "data_card.md").write_text(_card_skeleton(contract, recipe), encoding="utf-8")
    written.append("data_card.md")
    return written
