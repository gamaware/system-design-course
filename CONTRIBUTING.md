# Contributing

Thank you for your interest in improving these course materials.

## Who Can Contribute

- Students who spot errors or outdated instructions in a lab
- Instructors or collaborators who want to improve or add content
- Anyone who finds a bug in a script or configuration file

## How to Report an Issue

Open a [GitHub Issue](../../issues) describing:

- Which module/lab is affected
- What is wrong or unclear
- What the correct behavior or content should be

## How to Submit a Fix

1. Fork the repository
2. Create a branch: `git checkout -b fix/short-description`
3. Make your changes
4. Open a Pull Request against `main` with a clear description of what you changed and why

## Lab Content Guidelines

- Each module lives in its own directory (`NN-topic-name/`)
- Every module must have a `README.md` with learning objectives, technologies, and step-by-step instructions
- Scripts must pass ShellCheck (`shellcheck script.sh`)
- Markdown must pass markdownlint (config in `.markdownlint.yaml`)
- Keep instructions reproducible — avoid steps that depend on local machine state

## Questions

Reach out via Canvas or email: <alejandrogarcia@iteso.mx>
