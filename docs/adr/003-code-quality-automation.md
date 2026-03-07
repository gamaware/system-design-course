# ADR-003: Code Quality and Automation Pipeline

## Status

Accepted

## Context

The repository contains shell scripts, markdown documentation, YAML configurations, and
GitHub Actions workflows. Maintaining quality across these file types requires automated
checks both locally (pre-commit) and in CI (GitHub Actions).

## Decision

### Pre-commit hooks

The repository uses `pre-commit` with the following hooks:

- **General**: trailing-whitespace, end-of-file-fixer, check-yaml, check-json,
  check-added-large-files (1MB limit), check-merge-conflict, detect-private-key,
  check-executables-have-shebangs, check-shebang-scripts-are-executable, check-symlinks,
  check-case-conflict, no-commit-to-branch (main).
- **Secrets**: detect-secrets (with baseline), gitleaks.
- **Shell**: shellcheck (severity: warning), shellharden.
- **Markdown**: markdownlint with `--fix`.
- **GitHub Actions**: actionlint.
- **Commits**: conventional-pre-commit (commit-msg stage).

### CI workflows

- **quality-checks.yml**: Markdown linting, link checking, ShellCheck, YAML linting,
  repository structure validation, and README quality checks.
- **update-pre-commit-hooks.yml**: Weekly auto-update of pre-commit hook versions via PR.

### Linting policy

- All default rules are enforced. No suppressions on our own code.
- Only third-party files with structurally incompatible syntax (Go templates in Kubernetes
  manifests, CloudFormation intrinsic functions) may be excluded from `check-yaml`.
- Markdownlint config: MD013 line length at 120 characters, tables exempt.

### Code review

- CodeRabbit auto-review on all pull requests via `.coderabbit.yaml`.
- Dependabot monitors GitHub Actions dependencies weekly.

## Consequences

- All contributors must install pre-commit locally (`pre-commit install`).
- Direct commits to `main` are blocked by the `no-commit-to-branch` hook; all changes go
  through pull requests.
- Lint violations must be fixed, not suppressed. This keeps the codebase clean and teaches
  students good practices.
- Hook versions are kept current automatically via the weekly update workflow.
