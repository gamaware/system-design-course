# CLAUDE.md — Project Instructions for Claude Code

This file is automatically loaded into context when Claude Code starts a conversation
in this repository. It defines the conventions, rules, and structure that must be followed.

## Repository Overview

Hands-on labs for Scalable Systems Design (ITE3901) at ITESO. Contains 16 modules
mapped to the course syllabus, each in a numbered directory with lab instructions,
scripts, and configurations.

## Repository Structure

```text
NN-topic-name/          # Module directories (01 through 16, kebab-case)
  README.md             # Lab instructions or placeholder
  setup.sh              # Lab setup script (when applicable)
  scripts/              # Additional scripts
  configs/              # Configuration files
docs/
  adr/                  # Architecture Decision Records (dateless)
.github/
  workflows/            # CI/CD pipelines
  actions/              # Composite actions
  ISSUE_TEMPLATE/       # Issue templates
  PULL_REQUEST_TEMPLATE.md
```

### Module Naming

Directories follow `NN-topic-name` format where NN is two-digit syllabus order (01-16).
Topic names use lowercase kebab-case reflecting both the syllabus topic and primary
technology (e.g., `03-load-balancing-haproxy`, `06-security-https-oauth2-keycloak`).

## Git Workflow

### Commits

- **Conventional commits required** — enforced by `conventional-pre-commit` hook.
- Format: `type: description` (e.g., `fix:`, `feat:`, `docs:`, `chore:`, `ci:`).
- Never commit directly to `main` — enforced by `no-commit-to-branch` hook.
- Always work on a feature branch and create a PR.
- Do NOT add `Co-Authored-By` watermarks to commits.

### Pull Requests

- All changes go through PRs — no direct pushes to `main`.
- Squash merge only (merge commits and rebase disabled).
- CodeRabbit auto-reviews all PRs — address its comments before merging.
- All required status checks must pass before merge.
- At least 1 approving review required (CODEOWNERS enforced).
- All review conversations must be resolved before merge.
- Use `--admin` flag to bypass branch protection when necessary.

### Branch Protection (main)

- Required status checks: Markdown Linting, YAML Validation, Shell Script Validation,
  Validate Repository Structure, Security Scan.
- Additional CI checks (not required but run on PRs): Check Links, README Quality Check.
- Strict status checks — branch must be up to date with main.
- Stale reviews dismissed on new pushes.
- Required linear history (squash only).

## Pre-commit Hooks

All hooks must pass before committing. Install with `pre-commit install`.

### Hooks in use

- **General**: trailing-whitespace, end-of-file-fixer, check-yaml, check-json,
  check-added-large-files (1MB), check-merge-conflict, detect-private-key,
  check-executables-have-shebangs, check-shebang-scripts-are-executable,
  check-symlinks, check-case-conflict, no-commit-to-branch (main).
- **Secrets**: detect-secrets (with `.secrets.baseline`), gitleaks.
- **Shell**: shellcheck (severity: warning), shellharden.
- **Markdown**: markdownlint with `--fix`.
- **GitHub Actions**: actionlint.
- **Commits**: conventional-pre-commit (commit-msg stage).

## Linting Policy

### Absolute rule: NO suppressions on our own code

- All default linting rules are enforced. Fix violations, never suppress them.
- Do not create `.markdownlintignore`, custom rule overrides, or inline disable comments.
- Markdownlint config: MD013 line length at 120 characters, tables exempt.
  That is the ONLY customization in `.markdownlint.yaml`.

### Allowed exclusions (third-party files only)

- `check-yaml` excludes Kubernetes Helm templates and AWS Copilot CloudFormation files
  (Go template syntax and `!Ref` intrinsics are structurally incompatible with YAML parsers).
- `yamllint` excludes `ecsdemo-*/` directories (third-party AWS demo applications).
- These are the ONLY acceptable exclusions. Do not add more without explicit approval.

## Shell Scripts

- Must pass both `shellcheck` and `shellharden`.
- Use `shellharden --replace` to auto-fix quoting issues.
- Quote all variables, use `"$var"` not `$var`.
- Use arrays properly for word splitting scenarios.
- Scripts must have shebangs and executable permissions (`git add --chmod=+x`).

## Markdown

- Line length limit: 120 characters (MD013).
- Tables are exempt from line length.
- Every directory must have a `README.md`.
- Table separator lines must have spaces around pipes: `| --- | --- |` not `|---|---|`.
- Use ATX headings (`#`), not bold text as headings.
- Fenced code blocks must specify a language.

## CI/CD Pipelines

### quality-checks.yml

Markdown linting, link checking, ShellCheck, YAML linting, repository structure
validation, README quality checks.

### security.yml

Semgrep static analysis and Trivy vulnerability scanning.

### update-pre-commit-hooks.yml

Weekly auto-update of pre-commit hook versions via PR.

### Dependabot

Monitors GitHub Actions dependencies weekly.

## Security

- Never commit secrets, credentials, private keys, or `.env` files.
- `.gitignore` excludes: `.env`, `.env.local`, `*.pem`, `*.key`, `credentials.json`.
- `detect-secrets` baseline must be updated for false positives:
  `detect-secrets scan --update .secrets.baseline`.
- Lab instructions use placeholder values (`YOUR_CLIENT_SECRET`, `<your-instance-ip>`).

## ADRs

Architecture Decision Records live in `docs/adr/`. They are dateless since the course
structure persists across semesters. Reference `docs/adr/README.md` for the full index.

## Repo Configuration

- **Visibility**: Public
- **Topics**: system-design, aws, docker, kubernetes, scalability, cloud-computing, labs,
  haproxy, dns, load-balancing, oauth2, keycloak
- **Merge strategy**: Squash only, PR title used as commit title
- **Auto merge**: Enabled (useful for Dependabot PRs)
- **Delete branch on merge**: Enabled
- **Wiki**: Disabled (content lives in repo)
- **Projects**: Disabled (not in use)
