# scripts/

Repo-level tooling that isn't part of the `klein` skill itself (that lives under
`.claude/skills/klein/scripts/` — `summarize_results.py`, `build_tutorial.py`,
`make_figures.py`; scaffolding and preflight checks are the packaged `klein new` /
`klein preflight` CLI verbs).

## `verify_shipped_studies.py`

The guard rail CI runs on every push: discovers every `studies/*/study.yaml` with a
`schema_version`, runs `klein verify` on each, prints a passed / warned / failed
table, and exits non-zero if any shipped ledger stops verifying. Run it before any
engine change is committed.

```bash
uv run --no-sync python scripts/verify_shipped_studies.py [--studies 07-iris-90years ...]
```

## `verify_e2e.py`

Local, one-command proof that the legacy compatibility pipeline still works on
this machine: build an explicit v1 fixture, run a real three-experiment loop,
preflight, summarize, and render figures without touching the real checkout. It
owns a random temporary worktree/branch, uses the committed lockfile, streams each
run through the timeout-safe subprocess helper, and tears down only resources this
invocation created.

This is intentionally separate from the schema-v2 acceptance fixture. The v2
keep/discard/crash transaction, candidate-commit resolution, recovery, and sealed
final-test checks live in `kleinlib/tests/test_workflow_v2.py` and run in CI.

Stdlib-only and cross-platform (Linux, macOS, Windows — no bash, no `awk`/`sed`,
every subprocess call goes through `subprocess.run` with an explicit argument
list and a timeout). `scripts/verify_e2e.sh` is kept as a two-line POSIX shim
that execs this file, so every previously documented `bash scripts/verify_e2e.sh`
invocation keeps working unchanged on Linux/macOS.

```bash
uv run --locked python scripts/verify_e2e.py
# or, on a POSIX shell, the (unchanged) shim:
bash scripts/verify_e2e.sh
```

Exits non-zero if any check fails; prints a PASS/FAIL table either way. This is the local
counterpart to `.github/workflows/ci.yml`, which also runs the Python compatibility
matrix, deep/GBDT integration coverage, reproduction anchors, cross-platform CLI
smokes, and clean-wheel installation. The `e2e` job runs this on all three
platforms; `scripts/tests/test_verify_e2e_py.py` unit-tests its pure helpers
(table rendering, branch-name refusal, the temp-dir containment guard) without
running the full proof, and `scripts/tests/test_verify_e2e.py` exercises the
safety discipline (branch-collision refusal, worktree/branch/tempdir teardown)
as a subprocess through the shim.

## `check_generated_tutorial_network.py`

Builds a fresh temporary v2 tutorial with the real assembler, opens its `file://`
URL in headless Chrome, and inspects Chrome's `URL_REQUEST_START_JOB` netlog events.
The check fails on any HTTP(S) request and can write a small JSON evidence record.
It intentionally does not inspect or rewrite the immutable v0.1 reports.

```bash
uv run --no-sync python scripts/check_generated_tutorial_network.py \
  --evidence tutorial-network-evidence.json
```
