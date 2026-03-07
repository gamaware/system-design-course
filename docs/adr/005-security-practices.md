# ADR-005: Security Practices for Lab Content

## Status

Accepted

## Context

Lab exercises involve cloud credentials, TLS certificates, OAuth client secrets, and
infrastructure configuration. Students may accidentally commit sensitive material. The
repository must prevent credential leaks while keeping labs functional.

## Decision

### Secret detection

- **detect-secrets**: Pre-commit hook with a maintained baseline (`.secrets.baseline`).
  False positives are added to the baseline; real secrets are never committed.
- **gitleaks**: Secondary pre-commit scanner for patterns not covered by detect-secrets.
- **detect-private-key**: Pre-commit hook that blocks commits containing private keys.

### Lab credential handling

- All lab instructions use placeholder values (e.g., `YOUR_CLIENT_SECRET`,
  `<your-instance-ip>`).
- Setup scripts generate credentials locally and never echo them to log files.
- `.gitignore` excludes common credential files (`.env`, `*.pem`, `*.key`,
  `credentials.json`).

### Large file prevention

- `check-added-large-files` blocks files over 1MB to prevent accidental commits of
  binaries, database dumps, or disk images.

### Branch protection

- `no-commit-to-branch` hook prevents direct commits to `main`.
- All changes require a pull request with automated checks passing.

## Consequences

- Students learn secure development practices as part of the lab workflow.
- The `.secrets.baseline` must be updated when new false positives appear
  (`detect-secrets scan --update .secrets.baseline`).
- Cloud credentials used during labs must be rotated or deleted after each session.
- Lab instructions explicitly remind students to clean up AWS resources.
