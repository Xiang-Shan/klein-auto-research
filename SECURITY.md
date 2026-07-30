# Security policy

## Supported development line

Security fixes target the current repository development line (`0.3.0` in
package metadata — see `CHANGELOG.md`). The shipped v0.1 studies are immutable research evidence, not
a separately supported executable distribution.

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

Model pickle/joblib payloads can execute code while loading. v0.2 manifests may
record local artifact availability and SHA-256, but unsafe or large pickle
payloads should not be committed or accepted from an untrusted source. A hash
confirms identity, not safety.

Scientific validity problems, unexpected model quality, and ordinary dependency
bugs are valuable reports but are not automatically security vulnerabilities.
