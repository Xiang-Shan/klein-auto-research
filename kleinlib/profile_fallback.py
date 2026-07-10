"""Pure-pandas/stdlib dataset profiler — the DATA gate's always-available fallback.

`profile_dataframe` returns a markdown "data card": shape, per-column
dtype/missingness/cardinality/samples, a set of war-story-aware flags,
target balance (when a target column is given), and a "Modeling
implications" checklist translating the flags into concrete next actions.

Klein's DATA gate (Gate 1) prefers the global `dataset-profiler` skill when
present; this module is the fallback with zero dependencies beyond
pandas/stdlib, so the gate never blocks on a missing optional skill.

War story: never trust `dtype == "object"` to mean "this is text" — a
Yes/No column, a numeric-as-string column, and a real free-text column are
all `object` (or pandas `string`) dtype. Every flag below checks the actual
values, never the dtype label.
"""

from __future__ import annotations

import pandas as pd

#: Ratio of n_unique/n_rows at or above which a column is flagged ID-like.
#: Float columns are exempt (see `_is_floaty`): a continuous measurement is
#: expected to be near-unique per row and is not an identifier leak — only
#: int/object/string/category columns are checked against this ratio.
ID_LIKE_RATIO = 0.98

#: n_unique above which a non-numeric column is flagged high-cardinality.
HIGH_CARDINALITY_THRESHOLD = 50

#: Fraction of non-null values that must parse as numeric to flag a string
#: column as "suspicious numeric-as-string".
NUMERIC_STRING_THRESHOLD = 0.95

#: Missingness fraction above which a column earns a modeling-implications note.
HIGH_MISSING_THRESHOLD = 0.20

#: A target's minority-class share below/above which it's called "imbalanced".
IMBALANCE_MINORITY_PCT = 15.0

_YES_NO = frozenset({"Yes", "No"})


def _is_numeric_like(s: pd.Series) -> bool:
    return pd.api.types.is_numeric_dtype(s) or pd.api.types.is_bool_dtype(s)


def _is_floaty(s: pd.Series) -> bool:
    """True for float dtype — continuous measurements, never identifiers."""
    return pd.api.types.is_float_dtype(s)


def _is_yes_no(s: pd.Series) -> bool:
    vals = set(s.dropna().unique())
    return bool(vals) and vals <= _YES_NO


def _is_suspicious_numeric_as_string(s: pd.Series) -> bool:
    if _is_numeric_like(s):
        return False
    non_null = s.dropna()
    if non_null.empty:
        return False
    coerced = pd.to_numeric(non_null, errors="coerce")
    return bool(coerced.notna().mean() >= NUMERIC_STRING_THRESHOLD)


def _truncate(text: str, width: int = 24) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def _sample_values(s: pd.Series, n: int = 3) -> str:
    vals = s.dropna().unique()[:n]
    shown = ", ".join(_truncate(str(v)) for v in vals)
    return shown or "(all missing)"


def profile_dataframe(df: pd.DataFrame, *, target: str | None = None) -> str:
    """Return a markdown data-card profiling `df`.

    Pass `target` (a column name present in `df`) to add a target-balance
    section and target-aware modeling-implications notes (e.g. class
    imbalance).
    """
    n_rows, n_cols = df.shape
    lines: list[str] = ["# Data Profile", "", f"**Shape:** {n_rows} rows x {n_cols} columns", ""]

    lines.append("## Columns")
    lines.append("")
    lines.append("| Column | dtype | missing % | n_unique | sample values |")
    lines.append("|---|---|---|---|---|")

    id_like: list[tuple[str, int, int]] = []
    constant: list[str] = []
    yes_no: list[str] = []
    high_card: list[tuple[str, int]] = []
    numeric_as_string: list[str] = []
    high_missing: list[tuple[str, float]] = []

    for col in df.columns:
        s = df[col]
        n_missing = int(s.isna().sum())
        missing_pct = (n_missing / n_rows * 100) if n_rows else 0.0
        n_unique = int(s.nunique(dropna=True))
        lines.append(f"| {col} | {s.dtype} | {missing_pct:.1f}% | {n_unique} | {_sample_values(s)} |")

        if not _is_floaty(s) and n_rows > 1 and n_unique / n_rows >= ID_LIKE_RATIO:
            id_like.append((col, n_unique, n_rows))
        if n_unique <= 1:
            constant.append(col)
        if _is_yes_no(s):
            yes_no.append(col)
        if not _is_numeric_like(s) and n_unique > HIGH_CARDINALITY_THRESHOLD:
            high_card.append((col, n_unique))
        if _is_suspicious_numeric_as_string(s):
            numeric_as_string.append(col)
        if n_rows and (n_missing / n_rows) > HIGH_MISSING_THRESHOLD:
            high_missing.append((col, n_missing / n_rows * 100))

    lines.append("")
    lines.append("## Flags")
    lines.append("")
    any_flag = False
    if id_like:
        any_flag = True
        items = ", ".join(f"`{c}` ({u}/{r} unique)" for c, u, r in id_like)
        lines.append(f"- **ID-like** (unique ≈ rows): {items}")
    if constant:
        any_flag = True
        lines.append(f"- **Constant** (<=1 distinct value): {', '.join(f'`{c}`' for c in constant)}")
    if yes_no:
        any_flag = True
        lines.append(f"- **Yes/No-pattern string**: {', '.join(f'`{c}`' for c in yes_no)}")
    if high_card:
        any_flag = True
        items = ", ".join(f"`{c}` ({u} unique)" for c, u in high_card)
        lines.append(f"- **High-cardinality** (>{HIGH_CARDINALITY_THRESHOLD} unique, non-numeric): {items}")
    if numeric_as_string:
        any_flag = True
        lines.append(f"- **Suspicious numeric-as-string**: {', '.join(f'`{c}`' for c in numeric_as_string)}")
    if high_missing:
        any_flag = True
        items = ", ".join(f"`{c}` ({pct:.0f}%)" for c, pct in high_missing)
        lines.append(f"- **High missingness** (>{HIGH_MISSING_THRESHOLD * 100:.0f}%): {items}")
    if not any_flag:
        lines.append("- (none)")

    target_imbalanced = False
    target_minority_pct: float | None = None
    if target is not None and target in df.columns:
        lines.append("")
        lines.append(f"## Target balance (`{target}`)")
        lines.append("")
        t = df[target]
        t_non_null = t.dropna()
        n_unique_t = t_non_null.nunique()
        if 0 < n_unique_t <= 10:
            counts = t_non_null.value_counts()
            pcts = t_non_null.value_counts(normalize=True) * 100
            for val in counts.index:
                lines.append(f"- `{val}`: {counts[val]} rows ({pcts[val]:.2f}%)")
            if n_unique_t == 2:
                target_minority_pct = float(pcts.min())
                target_imbalanced = (
                    target_minority_pct < IMBALANCE_MINORITY_PCT
                    or target_minority_pct > (100.0 - IMBALANCE_MINORITY_PCT)
                )
        elif n_unique_t > 10:
            desc = t_non_null.describe()
            for stat in ("count", "mean", "std", "min", "25%", "50%", "75%", "max"):
                if stat in desc:
                    lines.append(f"- {stat}: {desc[stat]:.4g}")
        n_missing_t = int(t.isna().sum())
        if n_missing_t:
            lines.append(f"- missing: {n_missing_t} rows ({n_missing_t / n_rows * 100:.1f}%)")

    lines.append("")
    lines.append("## Modeling implications")
    lines.append("")
    checklist: list[str] = []
    if id_like:
        checklist.append(
            f"Drop ID-like columns before modeling ({', '.join(c for c, _, _ in id_like)}) "
            "— near-unique values carry no generalizable signal and can leak row identity."
        )
    if constant:
        checklist.append(
            f"Drop or investigate constant columns ({', '.join(constant)}) — "
            "zero variance, uninformative for every model family."
        )
    if yes_no:
        checklist.append(
            f"Convert Yes/No-pattern columns ({', '.join(yes_no)}) with "
            "`kleinlib.data.yes_no_to_int` — never trust `dtype == 'object'` "
            "to route these correctly."
        )
    if high_card:
        checklist.append(
            f"High-cardinality categorical columns ({', '.join(c for c, _ in high_card)}) "
            "— prefer target/frequency/hashing encoding over one-hot "
            "(see `kleinlib.encoders`), or check for a hidden ID-like column."
        )
    if numeric_as_string:
        checklist.append(
            f"Suspicious numeric-as-string columns ({', '.join(numeric_as_string)}) "
            "— coerce with `pd.to_numeric` and confirm no non-numeric rows are "
            "silently dropped before treating them as numeric features."
        )
    if high_missing:
        checklist.append(
            f"High-missingness columns ({', '.join(c for c, _ in high_missing)}) "
            "— decide impute vs. drop deliberately; don't let a default imputer "
            "hide a >20%-missing column."
        )
    if target_imbalanced and target_minority_pct is not None:
        checklist.append(
            f"Target `{target}` is imbalanced (minority class {target_minority_pct:.1f}%) "
            "— prefer `class_weight=None` + isotonic calibration + threshold "
            "tuning over naive `class_weight='balanced'` reweighting, which tends "
            "to wreck calibration on weak-signal data."
        )
    if not checklist:
        checklist.append("No structural red flags detected by this fallback profiler.")
    for item in checklist:
        lines.append(f"- [ ] {item}")

    return "\n".join(lines) + "\n"


def _main(argv: list[str] | None = None) -> int:
    """CLI: uv run python -m kleinlib.profile_fallback <csv-or-parquet> [--target COL]"""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="csv or parquet file to profile")
    parser.add_argument("--target", default=None, help="target column for balance stats")
    args = parser.parse_args(argv)

    path = str(args.path)
    df = pd.read_parquet(path) if path.endswith(".parquet") else pd.read_csv(path)
    print(profile_dataframe(df, target=args.target))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
