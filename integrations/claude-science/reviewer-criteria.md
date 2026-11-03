# Reviewer criteria for Klein studies

Claude Science's Reviewer re-reads responses, the approved plan, saved artifacts and the
execution record, and flags claims that do not match what ran. Add the block below under
**Settings → Specialists → Reviewer → Instructions**: it is appended to every review and
can neither remove nor weaken the built-in checks.

This makes the Reviewer a useful **pre-referee pass**. It is not Klein's Gate 3: the
Reviewer runs on the session's own model inside the same tool, so it never satisfies the
independence a referee needs (`README.md` §4). Never record `klein gate record referee`
from a Reviewer finding.

```text
When the session works in a Klein study (a directory with study.yaml and
study_state.json under studies/), also check:

1. Receipts are never hand-edited. Flag any write by Claude (an editor, `cat >`, a Python
   write) to runs/**/manifest.json, study_state.json, events.jsonl, results.tsv,
   claims.lock or verify_receipt.json. These files change only through `klein` verbs.
2. One experiment = one `klein run-one`. Flag an entrypoint (train.py, analyze.py,
   search.py, simulate.py or the file entrypoint.command names) executed directly without
   KLEIN_SMOKE=1, and any metric quoted from such a run.
3. Numbers have homes. Every metric value in a response, findings.md or report must equal
   a value in a run manifest, results.tsv, aux_metrics.tsv, an `art:` table or
   claims.lock. Flag a number that is rounded differently, recomputed in the kernel, or
   absent from those files.
4. Predictions are adjudicated by the notary. Flag "P# was confirmed/refuted" unless
   study_state.json (via `klein predict list`) holds that verdict, and a refuted
   prediction without a dated `Decision:` line in program.md.
5. Gates belong to the person. Flag a `klein gate record consult|data|method|phase|referee`
   that ran without the person's explicit acknowledgement in the conversation.
6. Sealed data is used once. Flag a `--final-test` run not preceded by
   `klein run-one --final-test --dry-run`, or a second sealed run on the same track.
7. Strength words follow claims.lock. Flag "confirmed", "proved", "significant",
   "state of the art" or a causal verb on a claim whose class/strength in claims.lock is
   exploratory, and any word on the study profile's banned list
   (.claude/skills/klein/references/profiles/<profile>.md §7).
8. Detached runs are attested. Flag a claim resting only on runs with
   `execution.mode: detached` that is written as observed fact without a replication
   record or the word "attested".
9. Costs are copied. Flag a token, call or dollar figure that is not copied from
   manifest.usage.
10. Self-review is not referee. Flag any statement that the study "passed review" or is
    "refereed" unless referee_report.md exists, was written in a different session or
    tool (program.md Roster), and the referee gate is recorded in study_state.json.
```
