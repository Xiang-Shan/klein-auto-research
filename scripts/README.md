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

Two artifact classes are never committed by policy: prepared datasets (`.gitignore`:
`data/`) and unsafe model payloads (`*.joblib` and friends, whose manifests record
`committed: false, availability: local`). In a fresh clone their bytes are simply not
there, so `klein verify` reports each absence as `[WARN] local artifact absent (not
committed by policy) — hash recorded <sha>` and passes; a PRESENT artifact is still
byte-checked against that hash. A job that regenerates the local artifacts first
should use `klein verify --require-local`, which turns absence back into a failure.

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

## `seed_knowledge_objects.py`

The one-off that seeds the repo-level knowledge store from the typed claim
citations already in `knowledge/**/*.md`
(`.claude/skills/klein/references/knowledge-protocol.md`). It opens every markdown
file read-only — **no markdown is ever written** — skips any cited study whose
`claims.lock` does not verify right now, copies each claim's class, strength and
evidence roots verbatim, deduplicates by evidence roots, and leaves the scope
fields empty because inventing a scope from a citation is exactly the failure the
store exists to prevent.

```bash
uv run --locked python scripts/seed_knowledge_objects.py            # dry run
uv run --locked python scripts/seed_knowledge_objects.py --apply    # writes
```

Dry-run by default; `--apply` writes objects and transactions but does NOT commit
— it prints the exact `git add -- …` for the operator to run.

## `check_generated_tutorial_network.py`

Builds a fresh temporary v2 tutorial with the real assembler, opens its `file://`
URL in headless Chrome, and inspects Chrome's `URL_REQUEST_START_JOB` netlog events.
The check fails on any HTTP(S) request and can write a small JSON evidence record.
It intentionally does not inspect or rewrite the immutable v0.1 reports.

```bash
uv run --no-sync python scripts/check_generated_tutorial_network.py \
  --evidence tutorial-network-evidence.json
```

## `check_shipped_reports.py`

Focused acceptance on the twelve reports we already shipped, measured in a real
browser: zero page-initiated HTTP(S) requests (the sibling script's netlog
machinery, imported so the two jobs cannot drift), no sideways scroll at
1440/768/390/320 px, every `nav.topnav` anchor landing below the sticky nav's
bottom edge at phone widths, every inlined figure decoded, and one report printed
to PDF and re-read with `pdftotext`. It never rebuilds a study and never writes
under `studies/`.

The reports ship a `default-src 'none'` CSP, so the measurement cannot be
injected into a report. Instead a wrapper page in a temp dir `<iframe>`s the
report, measures `iframe.contentDocument`, and base64s the JSON into its own
`<pre id="result">`, which `--dump-dom` hands back — one bounded subprocess, no
debugging port. Schema-2 studies (03, 05–09) and any schema-3 report built before
the builder's current layout generation (the page head's
`<meta name="generator" content="klein build_tutorial layout-N">`) are measured
but reported `LEGACY`: they are shipped history, and only a current-generation
schema-3 report's FAIL sets the exit code.

```bash
uv run --locked python scripts/check_shipped_reports.py \
  --evidence shipped-reports-evidence.json [--studies 15-iris-90years-relaunch]
```

Exits 1 when a schema-3 report fails a check, 2 on a usage error, 0 otherwise.
`.github/workflows/scheduled.yml`'s `shipped-reports` job runs it weekly on
ubuntu-latest with `poppler-utils` installed and uploads the evidence record.
On macOS, `Google Chrome --headless=new` hangs on any page containing an iframe
(Chrome 152; the same wrapper finishes in 0.2 s under `chrome-headless-shell`),
so pass `--chrome /path/to/chrome-headless-shell` there.
