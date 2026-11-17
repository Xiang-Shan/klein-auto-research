# Archived studies

Klein 3.0 ships eight exhibits — one refereed study per domain and question type. The
nine studies below left the working tree in 3.0. **Nothing was rewritten or lost:** every
file is in the history at commit `217cd46` (release 2.3.1), where it verifies with the
engine that judged it.

```bash
git checkout 217cd46 -- studies/07-iris-90years      # bring one study back into your tree
git worktree add ../klein-2.3.1 217cd46              # or open the whole 2.3.1 repository
```

`archive.yaml` beside this file is the machine-readable index: it lists each archived
study's claim ids, so `(supports <study>#Cn)` citations in `knowledge/` still resolve.
Studies 01, 02 and 04 are older still (tag `v1.0.0`); `00-glm-claims-quickstart` is at
tag `v1.3.0`.

| Study | Format | What it asked | Why it left the tree |
|---|---|---|---|
| `03-noisy-rosenbrock-dfo` | schema 2 | At a fixed 200-evaluation budget on noisy Rosenbrock (sigma=0.5), do restarts beat plain Nelder-Mead, and does SPSA beat both? | Schema-2 simulator exhibit; unrefereed, no claims lock |
| `05-fremtpl2-gap-forensics` | schema 2 | On freMTPL2 claim frequency, WHERE does a gradient-boosted model's Poisson-deviance advantage over a spline-shaped GLM live, how much of it transfers back into GLM-representable… | Schema-2 insurance exhibit; unrefereed, no claims lock |
| `06-hurricane-gqls-returnlevels` | schema 2 | On the 30 most-damaging US hurricanes (Pielke-Landsea 1998, normalized 1995 USD), does a from-scratch gQLS reproduce Adjieteh (2024) Table 6.9 within the published reporting resolution;… | Schema-2 insurance exhibit; unrefereed, no claims lock |
| `07-iris-90years` | schema 2 | On Fisher's 100 hard-pair iris rows (versicolor vs virginica, target is_virginica), does any of four pre-registered post-1936 challengers - logistic regression, kNN, SVM-RBF, HGBT -… | Schema-2; first of four studies on the same iris question |
| `08-iris-rematch` | schema 2 | Large-budget rematch: under a selection-honest registered protocol, can any of 21 modern challenger families (incl. the 2025 TabPFN v2 foundation model) beat the 1936 LDA anchor on the… | Schema-2; second of four studies on the same iris question |
| `09-iris-first-lesson` | schema 2 | Measure, with per-candidate paired resolution thresholds and a registered family selection guard, whether any frozen modern challenger earns a licensed win over 1936 four-feature LDA on… | Schema-2; third of four studies on the same iris question |
| `13-charlm-fixed-budget` | schema 3 · predict / ml-research | Under a fixed 2000-step training budget on a character-level corpus, which single-change training-recipe edits to a small char transformer improve held-out validation loss by more than… | The ml-research profile is represented by 22-cnn-data-scaling |
| `15-iris-90years-relaunch` | schema 3 · predict / generic | Ninety years after Fisher's 1936 linear discriminant, does any modern post-1936 classifier — regularized logistic regression, k-nearest neighbours, an RBF support-vector machine, or a… | Schema-3 relaunch of 07; generic tabular predict is represented by 00 |
| `24-golomb-llm-vs-search` | schema 3 · test / math | At a matched budget of verifier calls, does an LLM proposing Golomb rulers as data match the known optimal lengths (OEIS A003022) as often as a classical randomized search, on… | The math profile is represented by 11, model calls by 20 |

Schema-2 studies (03, 05–09) are judged by schema-2 rules, which the 3.0 engine no
longer carries; verify them at the archive commit, exactly as version-1 studies are
verified at tag `v1.3.0`.
