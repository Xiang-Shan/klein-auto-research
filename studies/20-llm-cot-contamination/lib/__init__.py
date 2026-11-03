"""Stable machinery for study 20 — NOT the per-experiment mutable surface.

`study.yaml:entrypoint.mutable` names `analyze.py` and nothing else. The modules
here are the measuring instrument, written once before E0001 and changed only
rarely and deliberately (never as part of a cell's diff):

* `twins`    — the GSM-Symbolic-style templates, their audited selection, the
               twin generator and its validator;
* `prompts`  — the two prompt arms, the decoding parameters and the scorer;
* `measure`  — the index, the lanes, the bootstrap intervals and the
               deterministic table writer every cell uses.
"""
