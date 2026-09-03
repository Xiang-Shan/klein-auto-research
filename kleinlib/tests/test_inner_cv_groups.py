"""`evaluate_with_inner_cv(groups=)` — no entity straddles the inner split.

The DATA gate audits the OUTER split for group overlap
(`kleinlib.leakage._group_check`); nothing audited the INNER one, so a tuning
loop on grouped data could quietly score itself on the same entities it was
fitted on.  `groups=` routes the folds through `StratifiedGroupKFold`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression

from kleinlib.eval import evaluate_with_inner_cv


def _grouped_frame(n_groups: int = 24, per_group: int = 4, seed: int = 0):
    """Each group's rows are near-duplicates: a straddling group is memorizable."""
    rng = np.random.default_rng(seed)
    groups = np.repeat(np.arange(n_groups), per_group)
    labels = np.repeat(rng.integers(0, 2, size=n_groups), per_group)
    centre = rng.normal(0.0, 3.0, size=n_groups)
    x = np.repeat(centre, per_group) + rng.normal(0.0, 0.01, size=groups.size)
    frame = pd.DataFrame({"x": x, "noise": rng.normal(size=groups.size)})
    return frame, pd.Series(labels), groups


def _factory():
    return LogisticRegression(max_iter=500)


def test_grouped_folds_keep_every_entity_on_one_side(monkeypatch) -> None:
    X, y, groups = _grouped_frame()
    seen: list[tuple[set, set]] = []

    import kleinlib.eval as klein_eval

    real = klein_eval.StratifiedGroupKFold

    class Recording(real):  # type: ignore[misc, valid-type]
        def split(self, X, y=None, groups=None):  # noqa: N803
            for tr, va in super().split(X, y, groups):
                seen.append((set(groups[tr]), set(groups[va])))
                yield tr, va

    monkeypatch.setattr(klein_eval, "StratifiedGroupKFold", Recording)
    mean, folds = evaluate_with_inner_cv(
        _factory, X, y, n_splits=3, metric="val_auc", groups=groups
    )

    assert len(folds) == 3
    assert 0.0 <= mean <= 1.0
    assert seen, "the grouped path must go through StratifiedGroupKFold"
    for train_groups, val_groups in seen:
        assert not (train_groups & val_groups)


def test_without_groups_the_stratified_path_is_unchanged() -> None:
    X, y, _ = _grouped_frame()
    mean, folds = evaluate_with_inner_cv(_factory, X, y, n_splits=3, metric="val_auc")
    assert len(folds) == 3
    assert 0.0 <= mean <= 1.0


def test_ignoring_groups_inflates_the_inner_score() -> None:
    """The reason the argument exists, measured rather than asserted."""
    X, y, groups = _grouped_frame(n_groups=30, per_group=4)
    leaky, _ = evaluate_with_inner_cv(_factory, X, y, n_splits=3, metric="val_auc")
    honest, _ = evaluate_with_inner_cv(
        _factory, X, y, n_splits=3, metric="val_auc", groups=groups
    )
    assert leaky > honest


def test_a_mis_sized_group_vector_is_refused() -> None:
    X, y, groups = _grouped_frame()
    with pytest.raises(ValueError, match="one label per row"):
        evaluate_with_inner_cv(_factory, X, y, groups=groups[:-1])
