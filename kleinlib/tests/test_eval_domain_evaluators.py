"""Klein 2.3 evaluators: multiclass, per-item (pass@k), ranking, survival, segmentation.

Every number is checked against an independent implementation (sklearn, scipy,
brute force); every evaluator prints the canonical block the notary parses.
"""

from __future__ import annotations

import itertools
import math
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    f1_score,
    log_loss,
    ndcg_score,
    top_k_accuracy_score,
)

from kleinlib import schema
from kleinlib.decision import parse_metric_log
from kleinlib.eval import (
    KNOWN_IDEALS,
    evaluate,
    evaluate_items,
    evaluate_multiclass,
    evaluate_ranking,
    evaluate_segmentation,
    evaluate_survival,
    get_metric_spec,
)
from kleinlib.eval_items import bootstrap_mean_ci, pass_at_k, read_item_table
from kleinlib.eval_multiclass import multiclass_metrics
from kleinlib.eval_structured import concordance_index, ranking_metrics, segmentation_metrics
from kleinlib.metrology import (
    item_bootstrap,
    mcnemar_exact,
    paired_item_bootstrap,
    resample_spread,
    seed_item_variance,
)


def _proba(n: int = 300, k: int = 4, seed: int = 0) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    y = rng.integers(0, k, n)
    logits = rng.normal(size=(n, k))
    logits[np.arange(n), y] += 1.5
    p = np.exp(logits)
    return y, p / p.sum(axis=1, keepdims=True)


# --------------------------------------------------------------- multiclass


def test_multiclass_metrics_match_sklearn() -> None:
    y, p = _proba()
    metrics, confusion, labels = multiclass_metrics(y, p)
    pred = p.argmax(axis=1)
    assert metrics["val_accuracy"] == pytest.approx(accuracy_score(y, pred))
    assert metrics["val_balanced_accuracy"] == pytest.approx(balanced_accuracy_score(y, pred))
    assert metrics["val_macro_f1"] == pytest.approx(f1_score(y, pred, average="macro"))
    assert metrics["val_mlogloss"] == pytest.approx(log_loss(y, p), rel=1e-9)
    assert metrics["val_top5_accuracy"] == 1.0  # K=4 <= 5
    _, p6 = _proba(k=8)
    y6 = np.random.default_rng(1).integers(0, 8, 300)
    m6, _, _ = multiclass_metrics(y6, p6)
    assert m6["val_top5_accuracy"] == pytest.approx(top_k_accuracy_score(y6, p6, k=5))
    assert confusion.sum() == y.size and labels == [0, 1, 2, 3]
    assert 0.0 <= metrics["val_ece"] <= 1.0


def test_multiclass_collapse_and_shape_guards() -> None:
    y = np.array([0, 1, 2, 0, 1, 2])
    p = np.tile([0.8, 0.1, 0.1], (6, 1))
    with pytest.raises(RuntimeError, match="Collapsed"):
        multiclass_metrics(y, p)
    with pytest.raises(ValueError, match="sum to 1"):
        multiclass_metrics(y, np.full((6, 3), 0.5))
    with pytest.raises(ValueError, match="pass proba"):
        multiclass_metrics(y)
    hard, _, _ = multiclass_metrics(["a", "b", "a"], y_pred=["a", "b", "b"], labels=["a", "b"])
    assert hard["val_accuracy"] == pytest.approx(2 / 3)
    assert "val_mlogloss" not in hard


def test_evaluate_multiclass_prints_a_parseable_block_and_pins_the_confusion(
    tmp_path: Path, capsys
) -> None:
    y, p = _proba()
    value = evaluate_multiclass(y, p, exp_id="E0001", metric_name="val_macro_f1", study_dir=tmp_path, train_n=900)
    out = capsys.readouterr().out
    log = tmp_path / "run.log"
    log.write_text(out, encoding="utf-8")
    primary, name, goal, metrics = parse_metric_log(log, scope="block")
    assert (primary, name, goal) == (pytest.approx(value), "val_macro_f1", "higher")
    for key in schema.EVALUATOR_PRINTED_KEYS["evaluate_multiclass"]:
        assert key in metrics, key
    assert "artifact: tables/confusion_E0001.tsv" in out
    assert (tmp_path / "tables" / "confusion_E0001.tsv").read_text().startswith("true\\pred")
    with pytest.raises(ValueError, match="binary metrics"):
        evaluate_multiclass(y, p, exp_id="E0001", metric_name="val_auc")


def test_binary_evaluate_refuses_multiclass_metric_names() -> None:
    with pytest.raises(ValueError, match="BINARY"):
        evaluate(None, None, None, exp_id=1, t0=0, fit_seconds=0, train_n=1, val_n=1,
                 metric_name="val_macro_f1", metric_goal="higher")


def test_new_metrics_are_registered_with_directions_and_ideals() -> None:
    for name, goal in (("val_mlogloss", "lower"), ("val_ece", "lower"), ("pass_at_k", "higher"),
                       ("val_c_index", "higher"), ("val_miou", "higher"), ("exact_match", "higher")):
        assert get_metric_spec(name).goal == goal
        assert name in KNOWN_IDEALS
    with pytest.raises(ValueError, match="canonical goal"):
        get_metric_spec("val_ece", goal="higher")


# ----------------------------------------------------------------- items


def test_pass_at_k_matches_the_combinatorial_definition() -> None:
    for n, c, k in itertools.product(range(1, 9), range(0, 9), range(1, 9)):
        if c > n or k > n:
            continue
        expected = 1.0 - math.comb(n - c, k) / math.comb(n, k)
        assert pass_at_k(n, c, k) == pytest.approx(expected, abs=1e-12)
    with pytest.raises(ValueError):
        pass_at_k(3, 4, 1)


def test_bootstrap_ci_is_seeded_and_cluster_aware() -> None:
    scores = np.array([1, 0, 1, 1, 0, 1, 1, 0, 1, 1], dtype=float)
    first = bootstrap_mean_ci(scores)
    assert first == bootstrap_mean_ci(scores)  # a replay reproduces the interval
    low, high = first
    assert low <= scores.mean() <= high
    clustered = bootstrap_mean_ci(scores, groups=np.repeat(["a", "b"], 5))
    assert clustered != first


def test_evaluate_items_pins_the_per_item_table(tmp_path: Path, capsys) -> None:
    items = pd.DataFrame({"item_id": [f"q{i}" for i in range(50)], "score": [i % 3 != 0 for i in range(50)]})
    items["score"] = items["score"].astype(int)
    value = evaluate_items(items, exp_id="E0002", metric_name="exact_match", study_dir=tmp_path)
    out = capsys.readouterr().out
    assert value == pytest.approx(items["score"].mean())
    log = tmp_path / "run.log"
    log.write_text(out, encoding="utf-8")
    _, name, _, metrics = parse_metric_log(log, scope="block")
    assert name == "exact_match"
    for key in schema.EVALUATOR_PRINTED_KEYS["evaluate_items"]:
        assert key in metrics, key
    table = read_item_table(tmp_path / "tables" / "items_E0002.tsv")
    assert list(table.columns) == ["item_id", "score"] and len(table) == 50
    assert "artifact: tables/items_E0002.tsv" in out


def test_evaluate_items_pass_at_k_and_guards(tmp_path: Path, capsys) -> None:
    items = pd.DataFrame({"item_id": ["a", "b", "c"], "n": [5, 5, 5], "c": [0, 1, 5]})
    value = evaluate_items(items, exp_id="E0003", metric_name="pass_at_k", k=2)
    assert value == pytest.approx((0.0 + pass_at_k(5, 1, 2) + 1.0) / 3)
    assert "pass_k:" in capsys.readouterr().out
    with pytest.raises(ValueError, match="0 or 1"):
        evaluate_items(pd.DataFrame({"item_id": ["a"], "score": [0.5]}), exp_id=1, metric_name="exact_match")
    with pytest.raises(ValueError, match="duplicate"):
        evaluate_items(pd.DataFrame({"item_id": ["a", "a"], "score": [1, 0]}), exp_id=1)
    custom = evaluate_items(
        pd.DataFrame({"item_id": ["a", "b"], "score": [3.0, 4.0]}),
        exp_id=1, metric_name="judge_score", metric_goal="higher",
    )
    assert custom == 3.5


# ---------------------------------------------------------------- ranking


def test_ranking_metrics_match_sklearn_ndcg() -> None:
    rng = np.random.default_rng(3)
    qids, rel, scores = [], [], []
    for q in range(20):
        r = rng.integers(0, 3, 8)
        r[0] = max(r[0], 1)
        s = rng.normal(size=8)
        qids += [q] * 8
        rel += r.tolist()
        scores += s.tolist()
    metrics = ranking_metrics(qids, rel, scores, k=5)
    expected = np.mean([
        ndcg_score([rel[i * 8:(i + 1) * 8]], [scores[i * 8:(i + 1) * 8]], k=5) for i in range(20)
    ])
    assert metrics["val_ndcg_at_k"] == pytest.approx(expected)
    perfect = ranking_metrics([0, 0, 0], [0, 1, 0], [0.1, 0.9, 0.2], k=1)
    assert perfect["val_mrr"] == 1.0 and perfect["val_recall_at_k"] == 1.0


def test_evaluate_ranking_block(capsys) -> None:
    value = evaluate_ranking([0, 0, 1, 1], [1, 0, 0, 1], [0.9, 0.1, 0.8, 0.2], exp_id=1, k=1, metric_name="val_mrr")
    assert value == pytest.approx((1.0 + 0.5) / 2)
    assert "n_queries: 2" in capsys.readouterr().out


# --------------------------------------------------------------- survival


def test_concordance_index_brute_force() -> None:
    rng = np.random.default_rng(5)
    t = rng.exponential(size=60).round(2)
    e = rng.random(60) < 0.7
    r = -t + rng.normal(scale=0.5, size=60)
    conc = pairs = 0.0
    for i in range(60):
        for j in range(60):
            if e[i] and t[i] < t[j]:
                pairs += 1
                conc += 1.0 if r[i] > r[j] else (0.5 if r[i] == r[j] else 0.0)
    c, n_pairs = concordance_index(t, e, r)
    assert c == pytest.approx(conc / pairs) and n_pairs == pairs
    value = evaluate_survival(t, e, r, exp_id=1)
    assert value == pytest.approx(c)


# ----------------------------------------------------------- segmentation


def test_segmentation_iou_and_dice_by_hand() -> None:
    truth = np.array([[0, 0, 1, 1], [0, 0, 1, 1]])
    pred = np.array([[0, 1, 1, 1], [0, 0, 1, 2]])
    m = segmentation_metrics(truth, pred, n_classes=3)
    # class 0: tp 3, fp 0, fn 1 -> 3/4 ; class 1: tp 3, fp 1, fn 1 -> 3/5 ; class 2: tp 0, fp 1 -> 0
    assert m["val_miou"] == pytest.approx((3 / 4 + 3 / 5 + 0) / 3)
    assert m["val_dice"] == pytest.approx((6 / 7 + 6 / 8 + 0) / 3)
    ignored = segmentation_metrics(truth, pred, n_classes=3, ignore_index=1)
    assert ignored["pixel_accuracy"] == pytest.approx(3 / 4)
    assert evaluate_segmentation(truth[None], pred[None], n_classes=3, exp_id=1) == pytest.approx(m["val_miou"])


# -------------------------------------------------------------- metrology


def test_item_metrology() -> None:
    from scipy.stats import binomtest

    a = np.array([1, 1, 1, 0, 1, 1, 0, 1, 1, 1, 1, 0])
    b = np.array([1, 0, 0, 0, 1, 0, 0, 1, 0, 1, 1, 0])
    result = mcnemar_exact(a, b)
    assert (result["n10"], result["n01"]) == (4, 0)
    assert result["p_value"] == pytest.approx(binomtest(4, 4, 0.5).pvalue)
    floor = item_bootstrap(a.astype(float), n_boot=200)
    assert floor.recipe == "item-bootstrap" and floor.estimand == "marginal-resplit"
    estimate, shared = paired_item_bootstrap(
        {f"q{i}": float(v) for i, v in enumerate(a)},
        {f"q{i}": float(v) for i, v in enumerate(b)} | {"extra": 1.0},
        n_boot=100,
    )
    assert shared == 12 and estimate.estimand == "paired-comparison"
    assert resample_spread([0.61, 0.63, 0.6]).block_key == "fit_noise"
    decomposition = seed_item_variance(np.vstack([a, b, a]))
    assert decomposition["items"] == 12 and decomposition["var_seed_means"] >= 0
