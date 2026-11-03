# Incident 2026-11-03 — branch history repaired after a lead operator error

**What happened (lead agent's error, not the experimenter's).** While run E0005 (att ·
1-NN matching, P4) was executing, the lead cherry-picked a framework fix (`kleinlib:
a seed array pins one evaluator table per seed`, 692977f) onto this branch — the
checkout the experimenter was using. E0005 then filed its evidence commits on top of
it (0fcec05 evidence, d25a53e finalize). Believing the run was still open, the lead ran
`git reset --keep 6f6ec26` to take the cherry-pick back off the candidate, which removed
E0005's two evidence commits from the branch. The experimenter committed its E0005
reflection (be8e02a) and started the next cell — AIPW, P3 — whose candidate (657fbaf)
was therefore numbered E0005 a second time on a base that lacked E0005's evidence.

**What was done.** The lead killed the misnumbered AIPW run before it filed any
evidence (its manifest was `pending`; it produced no number), preserved everything it
left behind in this directory, and reset the local, never-pushed experiments branch to
d25a53e — the state in which E0005 was completely filed — then re-applied the
reflection commit (now f8e207f). After the repair `klein verify` passes (event chain
valid, ledger matches manifests, no pending transaction) and E0005 is the matching cell
the notary recorded. The AIPW cell is re-run as the next experiment id.

**What was dropped from the branch, and why that is not lost evidence.** Only the
orphaned candidate 657fbaf (an AIPW cell that never completed and produced no metric)
and its uncommitted pending files — all kept here: `killed_aipw_manifest.json`
(transaction `pending`), `killed_aipw_run.log` (partial log), `killed_aipw_events.diff`
(the events it had appended), `orphan_candidate_657fbaf.txt` (the candidate's diff),
`reflog.txt` (the reflog showing every step). Commit 692977f stays in history between
E0005's candidate and its evidence; it changes only the default file names of two
evaluators this study does not call.

**Lesson, applied from here on.** Never commit, cherry-pick or reset in a checkout where
a `klein run-one` may be in flight; framework fixes go to the main-branch worktree and
reach an experiments branch only between runs.
