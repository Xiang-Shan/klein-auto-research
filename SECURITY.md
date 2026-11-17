# Security policy

## Supported development line

Security fixes target the current release line, 3.x (`3.1.0` in package
metadata — see `CHANGELOG.md`); "supported" means exactly that it receives
security fixes. 2.3.x remains the engine that judges schema-2 studies (tag
`v2.3.1`) and is maintained only for that purpose. The shipped studies are
immutable research evidence, not a separately supported executable distribution.

## Reporting a vulnerability

Please use GitHub's private vulnerability reporting flow for this repository:

<https://github.com/Xiang-Shan/klein-auto-research/security/advisories/new>

Include a minimal reproduction, affected version or commit, impact, and any
suggested mitigation. Do not include secrets, private datasets, or personal data
in the report. Please do not open a public issue until a fix or coordinated
disclosure is ready.

## Security boundaries

Klein executes study-owned Python and Git commands on the local machine. Treat a
study checkout as code, not as a passive document. Review untrusted `train.py`,
hooks, and configuration before running them, and use an isolated environment for
untrusted studies.

Model pickle/joblib payloads can execute code while loading. Run manifests may
record local artifact availability and SHA-256, but unsafe or large pickle
payloads should not be committed or accepted from an untrusted source. A hash
confirms identity, not safety.

Scientific validity problems, unexpected model quality, and ordinary dependency
bugs are valuable reports but are not automatically security vulnerabilities.
