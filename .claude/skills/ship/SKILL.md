---
name: ship
description: >-
  End-to-end PR lifecycle: update docs, commit, create PR, monitor CI,
  address CodeRabbit and Copilot reviews, and merge. Use this skill
  whenever the user says "ship it", "send a PR", "commit and merge",
  "push this", or wants to finalize and land their changes. Pass a PR
  number to resume monitoring an existing PR.
disable-model-invocation: true
user-invocable: true
argument-hint: "[optional PR number to resume monitoring]"
---

# Ship — Commit, Monitor, Fix, Merge

End-to-end workflow: update documentation, commit, create PR, monitor CI
and code reviews, address feedback, and merge when everything passes.

If `$ARGUMENTS` contains a PR number, skip to the monitoring phase for
that PR.

## Phase 1 — Update Documentation

Before committing, review all staged and unstaged changes to understand
what was modified, then update:

1. **CLAUDE.md** — If any CI/CD pipelines, hooks, skills, conventions,
   or project structure changed, update the relevant sections.
2. **README.md** — If modules, structure, or tooling changed, update the
   relevant sections (module table, structure tree, descriptions).
3. **docs/adr/** — If a significant architectural decision was made
   (new pattern, new tool, structural change), create or update an ADR.
4. **MEMORY.md** — Update project memory at
   `$HOME/.claude/projects/-Users-gamaware-Documents-Repos-personal-system-design-course/memory/MEMORY.md`
   if there are new gotchas, patterns, or preferences learned.

Only update files where changes are actually needed. Do not update docs
for trivial changes.

## Phase 2 — Commit and Push

1. Stage all changes (including doc updates from Phase 1).
2. Write a conventional commit message summarizing all changes.
3. Push to the current feature branch.
4. Create a PR if one does not exist yet. Use the commit message as
   the PR title. Include a summary and test plan in the body.

## Phase 3 — Monitor CI

Poll CI status using `gh pr checks <number>` every 30 seconds until
all checks complete (pass, fail, or skip). Report the final status.

If any check fails:

1. Read the failure logs with `gh run view <id> --log-failed`.
2. Diagnose and fix the issue.
3. Commit and push the fix.
4. Return to monitoring.

## Phase 4 — Monitor Code Reviews

Check for review comments from CodeRabbit and Copilot:

```bash
gh api repos/{owner}/{repo}/pulls/{number}/comments
gh api repos/{owner}/{repo}/issues/{number}/comments
```

If CodeRabbit is rate-limited, wait for the timeout period then trigger
with `gh pr comment <number> --body "@coderabbitai review"`.

For each review comment:

1. Read the comment carefully.
2. Check if the comment is stale (already fixed in a later commit) by
   reading the current file state. Dismiss stale comments.
3. If the comment is valid, fix the issue, commit, and push.
4. After fixing, re-monitor CI (return to Phase 3).

After all fixes are pushed and the incremental review passes, resolve
stale CodeRabbit threads in bulk:

```bash
gh pr comment <number> --body "@coderabbitai resolve"
```

For Copilot threads, resolve them via the GraphQL API:

```bash
gh api graphql -f query='{
  repository(owner: "gamaware", name: "system-design-course") {
    pullRequest(number: <NUMBER>) {
      reviewThreads(first: 100) { nodes { id isResolved } }
    }
  }
}'
```

Then for each unresolved thread ID:

```bash
gh api graphql -f query='mutation {
  resolveReviewThread(input: {threadId: "<ID>"}) {
    thread { isResolved }
  }
}'
```

## Phase 5 — Merge

Once ALL of the following are true:

- All CI checks pass
- CodeRabbit review has no unaddressed comments
- Copilot review has no unaddressed comments

Then merge:

```bash
gh pr merge <number> --squash --admin --delete-branch
```

Pull main locally after merge:

```bash
git checkout main && git pull
```

Report the merge commit and confirm the branch was deleted.

## Rules

- Never suppress lint violations — fix them.
- No AI attribution in commits.
- Conventional commit messages required.
- CodeRabbit may hit hourly rate limits — wait and retry.
- Copilot comments may be stale after fix commits — verify current file state.
- CodeRabbit auto-reviews incrementally on every push (up to 5 commits,
  then pauses). Use `@coderabbitai review` to resume after pause.
- CodeRabbit does NOT auto-resolve its threads — use `@coderabbitai resolve`
  after fixes are confirmed.
- Use `--admin` to bypass branch protection for merge.
