# Profile: cv

For studies whose evidence is images (or image-like arrays: microscopy, medical scans,
satellite tiles, spectrograms) and whose question is about a vision model or a vision
dataset — classification, segmentation, a pretraining or augmentation choice.

## 1. Audience
A computer-vision researcher or a domain scientist with images (a pathologist, an
astronomer, an ecologist) who knows that image benchmarks leak through near-duplicates
and patients, and will ask "split by what unit, at what resolution, with which
pretrained weights?" before "what accuracy?".

## 2. §⑤ heading
**⑤ What this means for the imaging pipeline.** Prompt: state the change (architecture,
augmentation, resolution, pretraining), the split unit and near-duplicate rate it was
measured under, the seed spread it cleared, the per-class effect where it is uneven,
and the compute it took.

## 3. Doctrine
Split by the unit that would leak (patient, slide, scene, capture session), never by
file, and audit near-duplicates across partitions before any model trains
(`python -m kleinlib.leakage --index … --near-dup image`). Multiclass work is scored by
`evaluate_multiclass` with macro-F1 or balanced accuracy as the primary when classes
are imbalanced (accuracy is reported, never the only number) and the confusion table
pinned. Deep runs are seed arrays (`entrypoint.seeds`) and the floor is measured on
aggregates; augmentation happens after the split, inside the training loop, never in
`prepare.py`. Pretrained weights are evidence inputs: name the checkpoint, its source
and its pretraining data, because a backbone pretrained on the test images is
contamination. MedMNIST-style benchmarks (Yang et al. 2023, Scientific Data) ship
official splits — keep them (`data.split.kind: predefined`) and say whether they are
patient-grouped.

## 4. Figures
A sample grid per class (a handful of images, never the sealed partition); the
confusion matrix (row-normalized) of the frontier and sealed runs; per-class recall
bars; seed-array spread at the anchor and at the best candidate; training/validation
curves; the decision trajectory per track. Tutorial §⑥ heading: **Vision-model coding advice**.

## 5. Knowledge
`knowledge/domains/cv/` (created when the first vision exhibit closes) and
`knowledge/research-discipline.md`; method card `knowledge/method_cards/cnn-image-classification.md`.

## 6. Budgets
| Run-cost class | Starting `max_run_seconds` | Floor recipe |
|---|---|---|
| small images (≤ 64 px), CPU, minutes | 900 per seed array | 3-seed aggregate, k ≥ 3 blocks |
| one GPU, hours | set explicitly; budget in steps/epochs | 3-seed aggregate at a reduced budget, disclosed |
| cluster or cloud GPU | detached runs (`run-one --detach`) | as above |
Report images/second and the device; `wall_seconds` is informational, steps are the budget.

## 7. Vocabulary
Banned: "SOTA", "state of the art", "human-level", "superhuman" — none is measured by a
study on one dataset. Must be qualified: "accurate" (which metric, which class
balance), "generalizes" (to which held-out site, scanner or time), "robust" (to which
shift). Honest verbs: classified, segmented, at matched epochs, cleared the floor by
k×, per-class recall rose for, did not transfer to.

## 8. CONSULT hints
`predict` for a model on a held-out partition (frontier); `estimate` for a scaling
exponent or a calibration level with its interval; `test` for "does augmentation /
resolution A differ from B at fixed budget". Modality `image`, an index split
(`data.split.index`) with the leakage unit as `group`, or `predefined` for a dataset's
official partitions. The mutable surface is usually `model.py` + `train.py`.
