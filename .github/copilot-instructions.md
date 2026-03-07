# Copilot Code Review Instructions

This is a university course repository for Scalable Systems Design (ITE3901).
It contains hands-on labs with shell scripts, markdown documentation, YAML configs,
and Python code.

## Review priorities

1. **Reproducibility** — Lab instructions must work from a clean environment.
   Flag hardcoded paths, missing prerequisites, or steps that assume prior state.

2. **Technical accuracy** — Verify AWS CLI commands, HAProxy configs, DNS records,
   OAuth flows, and Docker commands are correct and follow current best practices.

3. **Security** — Flag any committed credentials, hardcoded secrets, private keys,
   or AWS account IDs. Lab instructions should use placeholders.

4. **Shell script quality** — Scripts must be shellcheck and shellharden compliant.
   Variables must be quoted. No unintended word splitting or globbing.

5. **Dateless content** — No semester-specific dates, Canvas course links, or
   time-bound references. Content must be reusable across semesters.

6. **Markdown quality** — Line length max 120 characters (tables exempt).
   Fenced code blocks must specify a language. No bold text as headings.

7. **Cross-references** — Directory paths in instructions must match actual
   directory names (kebab-case with NN- prefix, e.g., `03-load-balancing-haproxy`).

## What NOT to flag

- Third-party files in `ecsdemo-*/` directories (AWS demo apps, not our code).
- Placeholder READMEs in modules 07-16 (content under development).
- The `verify=False` in Python code for self-signed certificates (intentional for labs).
