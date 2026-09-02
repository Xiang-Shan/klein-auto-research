---
title: "knowledge/domains — field knowledge, one directory per profile"
type: reference
domain: science
status: seed
concepts: [domains, profiles, promotion, typed-citations]
related: [../README.md, ../research-discipline.md]
---

# knowledge/domains/

Field-specific knowledge, one directory per profile (`.claude/skills/klein/references/profiles/`).
The framework's own lessons — the ones that transfer across fields — live one level
up in `research-discipline.md`; what lives here is what a study in a field learned
about that field.

| Directory | Profile | Seeded by |
|---|---|---|
| `insurance/` | `insurance` | the 2026-04 ancestor campaign; studies 00, 05, 12 |
| `physics/` | `generic` | study 10 (Hubble 1929) |
| `math/` | `math` | study 11 (exact-verifier construction) |
| `ml-research/` | `ml-research` | study 13 (fixed-budget character language model) |

Every statement promoted here carries a typed claim citation —
`(supports <study>#Cn)` / `(refutes <study>#Cn)` — and every file has the frontmatter
of `knowledge/README.md`. A new field starts with a `README.md` naming its doctrine
anchor and its first citation; an empty directory is not a domain.
