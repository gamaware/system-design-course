---
name: new-lab
description: >-
  Scaffold a new lab module with the standard 13-section README,
  setup/cleanup scripts, and directory structure. Use this skill
  whenever the user wants to create a new lab, add a module, scaffold
  a lesson, or says something like "create lab 08" or "add a new
  module for caching".
disable-model-invocation: true
user-invocable: true
argument-hint: "[NN-topic-name]"
---

# Scaffold a New Lab Module

Create a new lab module directory following the course conventions.

Argument: `$ARGUMENTS` is the module directory name in `NN-topic-name` format
(e.g., `08-distributed-file-systems`).

## Steps

1. Read `docs/lab-template.md` to understand the 13-section structure.
2. Create the module directory: `$ARGUMENTS/`
3. Generate `$ARGUMENTS/README.md` with:
   - Title derived from the topic name (convert kebab-case to title case)
   - All 13 sections from the lab template as scaffolded placeholders
   - Appropriate technology badges
   - Author and license sections
4. Create `$ARGUMENTS/setup.sh` with a basic shebang and `set -euo pipefail`
5. Create `$ARGUMENTS/cleanup.sh` with a basic shebang and `set -euo pipefail`
6. Make both scripts executable with `chmod +x`
7. Update the root `README.md` to change the module entry from
   `_(coming soon)_` to a full description (use existing modules as examples)

## Conventions

- Directory names: `NN-topic-name` (two-digit number, kebab-case)
- Files stay flat at the lab root until 5+ files of the same type warrant a subdirectory
- All content in English, dateless, no hardcoded credentials
- Use placeholder values for AWS resources (`YOUR_INSTANCE_IP`, etc.)
- Follow the hint pattern from docs/lab-template.md for questions
