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
  presentation/         # Module slide deck (index.html + slides.js)
shared/
  presentation/           # Shared presentation theme, JS, and assets
    theme.css             # Design tokens, reveal.js overrides, component styles
    presenter.js          # Particle canvas, animations, theme/lang toggle, Reveal init
    assets/               # AWS icons (SVG) and DB engine logos (PNG)
docs/
  adr/                  # Architecture Decision Records (dateless)
  lab-template.md       # Standard 13-section lab README template
  presentation-template/  # Starter template for new module presentations
.claude/
  settings.json         # Project-level Claude Code settings (hooks, permissions)
  hooks/                # Automation hooks (post-edit formatters, file protection)
  skills/               # Reusable skills (e.g., /new-lab to scaffold modules)
.github/
  workflows/            # CI/CD pipelines
  actions/              # Composite actions
  ISSUE_TEMPLATE/       # Issue templates
  PULL_REQUEST_TEMPLATE.md
  copilot-instructions.md  # Copilot code review custom instructions
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
- Do NOT add `Co-Authored-By` watermarks or any Claude/AI attribution to commits, code, or content. Ever.

### Pull Requests

- All changes go through PRs — no direct pushes to `main`.
- Squash merge only (merge commits and rebase disabled).
- CodeRabbit and GitHub Copilot auto-review all PRs — address their comments before merging.
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
- **Docker**: hadolint (Dockerfiles), docker-compose-check (docker-compose.yml).
- **Prose**: Vale with write-good (passive voice, weasel words) and proselint (grammar, usage).
- **GitHub Actions**: actionlint, zizmor (security analysis).
- **Commits**: conventional-pre-commit (commit-msg stage).

## Claude Code Hooks

Hooks in `.claude/settings.json` automate deterministic actions:

- **Post-edit** (`post-edit.sh`): Auto-runs `shellharden --replace` and `chmod +x` on `.sh`
  files, `markdownlint --fix` on `.md` files after every Edit/Write.
- **Protect third-party** (`protect-third-party.sh`): Blocks edits to `ecsdemo-*` directories
  (exit code 2 prevents the action).

## Claude Code Skills

Skills in `.claude/skills/` provide reusable workflows:

- **`/new-lab [NN-topic-name]`** — Scaffolds a new lab module with README template,
  setup/cleanup scripts, and updates root README. See `docs/lab-template.md` for the
  13-section structure.
- **`/ship-it [PR-number]`** — End-to-end PR lifecycle: updates docs (CLAUDE.md, README,
  ADRs, MEMORY.md), commits, creates PR, monitors CI, addresses CodeRabbit and Copilot
  review comments, merges with `--admin`, and cleans up stale local branches.
  Pass a PR number to resume monitoring. Uses global skill.

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
- Quote all variables. Prefer `"$var"` over `"${var}"` — only use braces when needed (e.g., `"${var}_suffix"`).
- Use arrays properly for word splitting scenarios.
- Scripts must have shebangs and executable permissions (`chmod +x <script>`).
- Editing tools may strip executable permissions — verify with `git diff --summary`
  and restore with `chmod +x <script>` if needed.

## Markdown

- Line length limit: 120 characters (MD013).
- Tables are exempt from line length.
- Every directory must have a `README.md`.
- Table separator lines must have spaces around pipes: `| --- | --- |` not `|---|---|`.
- Use ATX headings (`#`), not bold text as headings.
- Fenced code blocks must specify a language.

## CI/CD Pipelines

### quality-checks.yml

Markdown linting, link checking, ShellCheck, YAML linting, Dockerfile linting,
repository structure validation, README quality checks, zizmor (Actions security),
Vale (prose linting).

### security.yml

Semgrep static analysis and Trivy vulnerability scanning.

### update-pre-commit-hooks.yml

Weekly auto-update of pre-commit hook versions via PR.

### Dependabot

Monitors GitHub Actions dependencies weekly.

## Code Review

- **CodeRabbit** — Auto-reviews via `.coderabbit.yaml`. Detailed suggestions with path-specific instructions.
- **GitHub Copilot** — Auto-reviews via ruleset. Custom instructions in `.github/copilot-instructions.md`.
- Both reviewers run on every PR. Address comments from both before merging.
- Reviewers may comment on issues already fixed in subsequent commits.
  Verify current file state before acting — stale comments can be dismissed.

## GitHub Actions Security

- All `actions/checkout` steps must include `persist-credentials: false`.
- Action references use tag pins (e.g., `@v6`); configured via `zizmor.yml` with `ref-pin` policy.
- zizmor runs in CI and as a pre-commit hook to catch security issues in workflows.

## Security

- GitHub secret scanning and push protection enabled at the repository level.
- Never commit secrets, credentials, private keys, or `.env` files.
- `.gitignore` excludes: `.env`, `.env.local`, `*.pem`, `*.key`, `credentials.json`.
- `detect-secrets` baseline must be updated for false positives:
  `detect-secrets scan --update .secrets.baseline`.
- Lab instructions use placeholder values (`YOUR_CLIENT_SECRET`, `<your-instance-ip>`,
  `YOUR_AWS_ACCOUNT_ID`).

## Lab Content Rules

- **Dateless** — No semester names, specific dates, or Canvas course links. Content must
  be reusable across semesters.
- **English only** — All lab content, code comments, and HTML output in English.
- **Placeholders** — Never hardcode AWS account IDs, credentials, or instance IPs.
- **Cross-references** — Directory paths in instructions must match actual directory names.

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
