# scripts/

Repo-level tooling that isn't part of the `klein` skill itself (that lives under
`.claude/skills/klein/scripts/` — `preflight.py`, `new_study.py`, `summarize_results.py`, `build_tutorial.py`,
`make_figures.py`).

## `verify_e2e.sh`

Local, one-command proof that the legacy compatibility pipeline still works on
this machine: build an explicit v1 fixture, run a real three-experiment loop,
preflight, summarize, and render figures without touching the real checkout. It
owns a random temporary worktree/branch, uses the committed lockfile, streams each
run through the timeout-safe subprocess helper, and tears down only resources this
invocation created.

This is intentionally separate from the schema-v2 acceptance fixture. The v2
keep/discard/crash transaction, candidate-commit resolution, recovery, and sealed
final-test checks live in `kleinlib/tests/test_workflow_v2.py` and run in CI.

```bash
bash scripts/verify_e2e.sh
```

Exits non-zero if any check fails; prints a PASS/FAIL table either way. This is the local
counterpart to `.github/workflows/ci.yml`, which also runs the Python compatibility
matrix, deep/GBDT integration coverage, reproduction anchors, cross-platform CLI
smokes, and clean-wheel installation.

## `check_generated_tutorial_network.py`

Builds a fresh temporary v2 tutorial with the real assembler, opens its `file://`
URL in headless Chrome, and inspects Chrome's `URL_REQUEST_START_JOB` netlog events.
The check fails on any HTTP(S) request and can write a small JSON evidence record.
It intentionally does not inspect or rewrite the immutable v0.1 reports.

```bash
uv run --no-sync python scripts/check_generated_tutorial_network.py \
  --evidence tutorial-network-evidence.json
```
