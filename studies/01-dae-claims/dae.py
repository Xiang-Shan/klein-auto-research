"""dae.py — the study lib for 01-dae-claims: a swap-noise Denoising AutoEncoder.

This is the study's CENTREPIECE (the pedagogy the method_card.md teaches). It is a
study `lib/` module, NOT the mutable experiment surface — `train.py` stays thin and
imports `SwapNoiseDAE` from here; editing this file is a deliberate library change,
never a per-experiment diff.

What it is (see method_card.md for the full arc):
  * A denoising autoencoder is nonlinear PCA. We corrupt each row with **swap noise**
    (Jahrer's Porto-Seguro trick: resample a cell's value from a random OTHER row —
    the tabular-native corruption, since you cannot rotate/flip a table), then train an
    encoder+linear-decoder to reconstruct the CLEAN row. Forced to undo the corruption,
    the encoder must learn the joint structure of the columns.
  * The learned feature is the **deep-stack representation**: the concatenation of all
    three hidden-layer activations (3 x 256 = 768 dims), handed to a downstream model.

Input encoding (fit on TRAIN-fold features only by default — the FAIRNESS RULE):
  * numerics  -> RankGauss  (sklearn ``QuantileTransformer(output_distribution="normal")``)
  * categoricals -> ``OneHotEncoder(min_frequency=20, handle_unknown="ignore")``, dense
  * ``is_*`` binaries -> **passthrough**, and **excluded from swap noise** (corrupting a
    0/1 safety-feature flag is not meaningful denoising signal here).

Swap-noise granularity (the documented choice): corruption is applied at the
**ORIGINAL-column level** on the dataframe, then the corrupted frame is re-encoded. So a
categorical swap always yields a valid single one-hot, a numeric swap always gets
RankGauss'd consistently, and one-hot groups are never left in an inconsistent
half-corrupted state. (Because QuantileTransformer and OneHotEncoder are both per-column
deterministic maps, this is provably identical to "copy the donor row's encoded slice";
we do it on the dataframe because that is the honest, testable statement of the method.)

MPS-safety (the collapse war story): all torch batching goes through
``kleinlib.torch_loop.iterate_minibatches`` (index-shuffle, never a DataLoader/
TensorDataset on MPS); the device comes from ``kleinlib.torch_device.pick_device``; and
every representation/reconstruction crosses back to **CPU numpy** before returning.
Early stopping is on a held-out RECONSTRUCTION loss, so we drive our own epoch loop (the
pattern ``kleinlib.torch_loop``'s docstring points to) rather than its training-loss
``fit``.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, QuantileTransformer

import kleinlib  # engine: kleinlib.torch_loop (MPS-safe batching), kleinlib.torch_device

# --- fixed architecture / optimisation defaults (the plan's spec) -----------
DEFAULT_SWAP_RATE = 0.15          # Jahrer's Porto-Seguro rate; E5 sweeps {0.10,0.15,0.25}
HIDDEN_DIMS = (256, 256, 256)     # encoder 3x256 ReLU -> deep-stack 768
LEARNING_RATE = 1e-3
WEIGHT_DECAY = 1e-5
BATCH_SIZE = 256
MAX_EPOCHS = 100
EARLY_STOP_PATIENCE = 10
EARLY_STOP_FRACTION = 0.1         # held-out fraction (of the fit set) for recon early-stop
SEED = 42


def apply_swap_noise(
    X: pd.DataFrame,
    eligible_cols: list[str],
    *,
    rate: float,
    rng: np.random.Generator,
) -> tuple[pd.DataFrame, np.ndarray]:
    """Swap-noise corruption at the ORIGINAL-column level.

    For each eligible column independently, each row is flagged for corruption with
    probability ``rate``; a flagged cell is overwritten by the value of the SAME column
    in a uniformly-random donor row (self-donation is possible — standard swap noise).
    Columns NOT in ``eligible_cols`` (i.e. the ``is_*`` binaries) are never touched.

    Returns ``(X_corrupted, mask)`` where ``mask`` is an ``(n_rows, len(eligible_cols))``
    boolean array of which cells were flagged (in ``eligible_cols`` order). The mask
    counts INTENT: a flagged cell whose random donor happened to share its value is still
    ``True`` — the fraction of ``True`` is ~``rate`` regardless of column cardinality.
    """
    Xc = X.copy()
    n = len(X)
    mask = np.zeros((n, len(eligible_cols)), dtype=bool)
    for j, col in enumerate(eligible_cols):
        flagged = rng.random(n) < rate
        mask[:, j] = flagged
        idx = np.flatnonzero(flagged)
        if idx.size:
            donors = rng.integers(0, n, size=idx.size)
            col_vals = X[col].to_numpy()
            Xc.iloc[idx, Xc.columns.get_loc(col)] = col_vals[donors]
    return Xc, mask


class _DAENet(nn.Module):
    """Encoder (3 stacked ReLU layers) + a single linear decoder head.

    ``forward`` reconstructs ALL ``input_dim`` encoded dimensions from the last hidden
    layer (the autoencoder objective). ``representation`` returns the deep-stack feature
    — the concatenation of the three hidden activations (sum(hidden) dims) — which is
    what the downstream model consumes.
    """

    def __init__(self, input_dim: int, hidden: tuple[int, ...] = HIDDEN_DIMS) -> None:
        super().__init__()
        self.act = nn.ReLU()
        dims = (input_dim, *hidden)
        self.encoders = nn.ModuleList(
            nn.Linear(dims[i], dims[i + 1]) for i in range(len(hidden))
        )
        # Decoder reconstructs the full input from the LAST hidden layer (Jahrer-canonical
        # deep encoder + shallow linear decoder). The deep-stack feature is harvested from
        # the internal activations, not the decoder input.
        self.head = nn.Linear(hidden[-1], input_dim)

    def _hidden_activations(self, x: torch.Tensor) -> list[torch.Tensor]:
        acts: list[torch.Tensor] = []
        h = x
        for enc in self.encoders:
            h = self.act(enc(h))
            acts.append(h)
        return acts

    def representation(self, x: torch.Tensor) -> torch.Tensor:
        return torch.cat(self._hidden_activations(x), dim=1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.head(self._hidden_activations(x)[-1])


class SwapNoiseDAE:
    """Swap-noise denoising autoencoder with an sklearn-style API.

    Usage (headline, inductive — fit on the TRAIN fold only):

        dae = SwapNoiseDAE(swap_rate=0.15)          # fit_mode="inductive" is the default
        rep_tr = dae.fit_transform(X_tr)            # (n_tr, 768) CPU numpy
        rep_va = dae.transform(X_va)                # (n_va, 768) CPU numpy — val never seen at fit

    Kaggle-style transductive aside (fit on train+val FEATURES, no labels) — NOT the
    headline (see the FAIRNESS RULE in program.md):

        dae = SwapNoiseDAE(swap_rate=0.15, fit_mode="transductive")
        dae.fit(X_tr, X_transductive=X_va)          # encoder sees both feature sets
        rep_tr, rep_va = dae.transform(X_tr), dae.transform(X_va)

    ``reconstruct(X)`` returns the decoder output in encoded space (n, input_dim) for the
    imputer (E7) and anomaly (E8) experiments.
    """

    def __init__(
        self,
        *,
        swap_rate: float = DEFAULT_SWAP_RATE,
        hidden: tuple[int, ...] = HIDDEN_DIMS,
        lr: float = LEARNING_RATE,
        weight_decay: float = WEIGHT_DECAY,
        batch_size: int = BATCH_SIZE,
        max_epochs: int = MAX_EPOCHS,
        patience: int = EARLY_STOP_PATIENCE,
        min_frequency: int = 20,
        seed: int = SEED,
        fit_mode: str = "inductive",
        device: torch.device | None = None,
        verbose: bool = False,
    ) -> None:
        if fit_mode not in ("inductive", "transductive"):
            raise ValueError(f"fit_mode must be 'inductive' or 'transductive', got {fit_mode!r}")
        self.swap_rate = swap_rate
        self.hidden = hidden
        self.lr = lr
        self.weight_decay = weight_decay
        self.batch_size = batch_size
        self.max_epochs = max_epochs
        self.patience = patience
        self.min_frequency = min_frequency
        self.seed = seed
        self.fit_mode = fit_mode
        self.device_ = device if device is not None else kleinlib.torch_device.pick_device()
        self.verbose = verbose
        # set at fit time
        self.feature_cols_: list[str] | None = None
        self.numeric_cols_: list[str] = []
        self.is_star_cols_: list[str] = []
        self.categorical_cols_: list[str] = []
        self.eligible_cols_: list[str] = []
        self.transformer_: ColumnTransformer | None = None
        self.net_: _DAENet | None = None
        self.input_dim_: int | None = None
        self.n_fit_rows_: int | None = None
        self.history_: dict[str, list[float]] = {}

    # -- column routing & encoding ------------------------------------------
    def _route_columns(self, X: pd.DataFrame) -> None:
        cols = list(X.columns)
        self.is_star_cols_ = [c for c in cols if c.startswith("is_")]
        rest = [c for c in cols if c not in self.is_star_cols_]
        numeric, categorical = kleinlib.data.feature_column_groups(X[rest])
        self.numeric_cols_ = numeric
        self.categorical_cols_ = categorical
        # is_* binaries are deliberately NOT eligible for swap noise.
        self.eligible_cols_ = self.numeric_cols_ + self.categorical_cols_
        self.feature_cols_ = cols

    def _build_transformer(self, n_rows: int) -> ColumnTransformer:
        n_quantiles = int(min(1000, max(10, n_rows)))
        num_pipe = Pipeline(
            [
                ("impute", SimpleImputer(strategy="median")),
                (
                    "rankgauss",
                    QuantileTransformer(
                        output_distribution="normal",
                        n_quantiles=n_quantiles,
                        random_state=self.seed,
                    ),
                ),
            ]
        )
        cat_pipe = Pipeline(
            [
                ("impute", SimpleImputer(strategy="most_frequent")),
                (
                    "ohe",
                    OneHotEncoder(
                        min_frequency=self.min_frequency,
                        handle_unknown="ignore",
                        sparse_output=False,
                    ),
                ),
            ]
        )
        return ColumnTransformer(
            transformers=[
                ("num", num_pipe, self.numeric_cols_),
                ("bin", "passthrough", self.is_star_cols_),
                ("cat", cat_pipe, self.categorical_cols_),
            ],
            remainder="drop",
        )

    def _encode(self, X: pd.DataFrame) -> np.ndarray:
        assert self.transformer_ is not None and self.feature_cols_ is not None
        Z = self.transformer_.transform(X[self.feature_cols_])
        return np.asarray(Z, dtype=np.float32)

    # -- fit ----------------------------------------------------------------
    def _seed_everything(self) -> None:
        torch.manual_seed(self.seed)
        np.random.seed(self.seed)
        if self.device_.type == "mps":
            torch.mps.manual_seed(self.seed)

    def fit(self, X: pd.DataFrame, X_transductive: pd.DataFrame | None = None) -> "SwapNoiseDAE":
        """Fit the encoder. Inductive (default) uses `X` only; transductive also uses
        `X_transductive` FEATURES (no labels) to fit the transformer + DAE."""
        self._seed_everything()
        self._route_columns(X)

        if self.fit_mode == "transductive" and X_transductive is not None:
            X_fit = pd.concat([X[self.feature_cols_], X_transductive[self.feature_cols_]],
                              ignore_index=True)
        else:
            X_fit = X[self.feature_cols_].reset_index(drop=True)

        self.transformer_ = self._build_transformer(len(X_fit)).fit(X_fit)
        self.input_dim_ = int(self._encode(X_fit).shape[1])
        # canary for the FAIRNESS RULE: number of rows the encoder was fit on. In
        # inductive mode this equals len(X); in transductive it is len(X)+len(X_transductive).
        self.n_fit_rows_ = int(len(X_fit))

        # held-out reconstruction split for early stopping (unsupervised → plain shuffle)
        rng = np.random.default_rng(self.seed)
        n = len(X_fit)
        perm = rng.permutation(n)
        n_es = max(1, int(round(EARLY_STOP_FRACTION * n)))
        es_idx, tr_idx = perm[:n_es], perm[n_es:]
        X_tr = X_fit.iloc[tr_idx].reset_index(drop=True)
        X_es = X_fit.iloc[es_idx].reset_index(drop=True)

        Z_tr_clean = torch.as_tensor(self._encode(X_tr), device=self.device_)
        # fixed corrupted early-stop set → a STABLE early-stopping signal across epochs
        X_es_corrupt, _ = apply_swap_noise(
            X_es, self.eligible_cols_, rate=self.swap_rate,
            rng=np.random.default_rng(self.seed + 1),
        )
        Z_es_corrupt = torch.as_tensor(self._encode(X_es_corrupt), device=self.device_)
        Z_es_clean = torch.as_tensor(self._encode(X_es), device=self.device_)

        self.net_ = _DAENet(self.input_dim_, self.hidden).to(self.device_)
        optim = torch.optim.AdamW(self.net_.parameters(), lr=self.lr, weight_decay=self.weight_decay)
        loss_fn = nn.MSELoss()
        noise_rng = np.random.default_rng(self.seed + 2)

        best_es = float("inf")
        best_state: dict[str, torch.Tensor] | None = None
        bad = 0
        train_losses: list[float] = []
        es_losses: list[float] = []
        n_tr = len(X_tr)

        for epoch in range(self.max_epochs):
            # fresh swap noise each epoch (proper denoising training), re-encoded
            X_corrupt, _ = apply_swap_noise(
                X_tr, self.eligible_cols_, rate=self.swap_rate, rng=noise_rng
            )
            Z_corrupt = torch.as_tensor(self._encode(X_corrupt), device=self.device_)

            self.net_.train()
            batch_losses: list[float] = []
            for b in kleinlib.torch_loop.iterate_minibatches(
                n_tr, self.batch_size, shuffle=True, generator=noise_rng
            ):
                bt = torch.as_tensor(b, device=self.device_)
                optim.zero_grad()
                recon = self.net_(Z_corrupt[bt])
                loss = loss_fn(recon, Z_tr_clean[bt])
                loss.backward()
                optim.step()
                batch_losses.append(float(loss.detach().cpu()))
            train_losses.append(float(np.mean(batch_losses)))

            # held-out reconstruction loss (no grad) — the early-stop signal
            self.net_.eval()
            with torch.no_grad():
                es_loss = float(loss_fn(self.net_(Z_es_corrupt), Z_es_clean).detach().cpu())
            es_losses.append(es_loss)

            if es_loss < best_es - 1e-6:
                best_es = es_loss
                best_state = {k: v.detach().clone() for k, v in self.net_.state_dict().items()}
                bad = 0
            else:
                bad += 1
                if bad >= self.patience:
                    break
            if self.verbose:
                print(f"epoch {epoch:3d}  train_mse={train_losses[-1]:.5f}  es_mse={es_loss:.5f}")

        if best_state is not None:
            self.net_.load_state_dict(best_state)
        self.history_ = {"train_loss": train_losses, "es_loss": es_losses,
                         "best_es": best_es, "epochs_run": len(train_losses)}
        return self

    # -- transform / reconstruct (always CPU numpy) -------------------------
    def _batched_apply(self, fn: Callable[[torch.Tensor], torch.Tensor], Z: np.ndarray) -> np.ndarray:
        assert self.net_ is not None
        self.net_.eval()
        Zt = torch.as_tensor(Z, dtype=torch.float32, device=self.device_)
        outs: list[np.ndarray] = []
        with torch.no_grad():
            for b in kleinlib.torch_loop.iterate_minibatches(
                len(Z), self.batch_size, shuffle=False, generator=None
            ):
                bt = torch.as_tensor(b, device=self.device_)
                outs.append(fn(Zt[bt]).detach().cpu().numpy())
        return np.concatenate(outs, axis=0)

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        """Deep-stack representation (n, sum(hidden)=768) as CPU numpy."""
        if self.net_ is None:
            raise RuntimeError("SwapNoiseDAE.transform called before fit")
        return self._batched_apply(self.net_.representation, self._encode(X))

    def fit_transform(self, X: pd.DataFrame, X_transductive: pd.DataFrame | None = None) -> np.ndarray:
        return self.fit(X, X_transductive).transform(X)

    def reconstruct(self, X: pd.DataFrame) -> np.ndarray:
        """Decoder reconstruction in encoded space (n, input_dim) as CPU numpy.

        Used by E7 (impute missing cells from the reconstruction) and E8 (rank rows by
        reconstruction error as an anomaly score)."""
        if self.net_ is None:
            raise RuntimeError("SwapNoiseDAE.reconstruct called before fit")
        return self._batched_apply(self.net_.forward, self._encode(X))
