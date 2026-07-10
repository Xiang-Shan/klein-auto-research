# scripts/

Repo-level tooling that isn't part of the `klein` skill itself (that lives under
`.claude/skills/klein/scripts/` — `preflight.py`, `new_study.py`, `summarize_results.py`,
`make_figures.py`).

## `verify_e2e.sh`

Local, one-command proof that the whole Klein pipeline still works on this machine —
scaffold a study, run a real 3-experiment edit/run/commit-or-revert/log loop, preflight,
summarize, render figures — without ever touching the real checkout. See the script's
own header for the exact mechanics (temporary git worktree + branch, torn down on exit).

```bash
bash scripts/verify_e2e.sh
```

Exits non-zero if any check fails; prints a PASS/FAIL table either way. This is the local
counterpart to `.github/workflows/ci.yml` — CI runs a narrower, credential-free slice
(unit tests + the studies/00 sample fixture + the studies/02 E1 gate) on every push;
this script is the broader, slower local smoke test you'd run before trusting a change
to the loop scripts or `kleinlib` itself.
