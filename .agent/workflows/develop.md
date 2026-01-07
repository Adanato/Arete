---
description: End-to-end development workflow for implementing GitHub issues
---

# Issue Development Workflow

This workflow guides end-to-end development from a GitHub issue to a merged PR.

## Prerequisites
- User must provide an issue number or URL
- Repository must have `gh` CLI configured
- Project must have a `justfile` with `check` and `check-types` recipes

---

## Phase 1: Issue Analysis

1. **Fetch the Issue**
   ```bash
   gh issue view <ISSUE_NUMBER> --json title,body,labels,assignees
   ```

2. **Understand the Scope**
   - Read the issue title and description carefully
   - Identify acceptance criteria (if any)
   - Note any labels (bug, feature, enhancement)
   - Check for linked PRs or related issues

3. **Research the Codebase**
   - Use `grep_search` and `view_file_outline` to understand affected areas
   - Identify files that will need modification
   - Check for existing tests covering the area

---

## Phase 2: Planning

1. **Create a Feature Branch**
   ```bash
   git checkout main && git pull origin main
   git checkout -b <BRANCH_NAME>
   ```
   - Branch naming: `feat/<short-description>`, `fix/<short-description>`, or `chore/<short-description>`

2. **Write Implementation Plan**
   - Create `implementation_plan.md` artifact with:
     - Goal description
     - Proposed file changes (grouped by component)
     - Verification plan (tests to add/modify)
     - Any user decisions required

3. **Request User Approval**
   - Use `notify_user` with `BlockedOnUser: true` and `PathsToReview` pointing to the plan
   - **STOP** and wait for user feedback
   - If user requests changes, update the plan and re-request approval

---

## Phase 3: Development Loop

Repeat the following cycle until QA passes with zero issues:

### Step 3.1: Develop
- Implement the changes according to the plan
- Write or update tests as you go
- Keep changes minimal and focused

### Step 3.2: Test
```bash
# Run unit tests
uv run just coverage

# Run TypeScript tests (if applicable)
cd obsidian-plugin && npm test
```
- Fix any test failures before proceeding

### Step 3.3: QA Check
```bash
# Full QA suite
uv run just check && uv run just check-types
```
- If QA fails:
  - Analyze the error output
  - Fix the issues
  - Return to **Step 3.2**

### Step 3.4: Exit Condition
- QA passes with **0 errors**
- All tests pass
- Proceed to Phase 4

---

## Phase 4: Commit Preparation

1. **Review All Changes**
   ```bash
   git status
   git diff --stat
   ```

2. **Organize Commits**
   - Group related changes into logical commits
   - Use conventional commit messages:
     - `feat:` for new features
     - `fix:` for bug fixes
     - `test:` for test additions/changes
     - `chore:` for maintenance
     - `docs:` for documentation
   - Example:
     ```bash
     git add <files> && git commit -m "feat: Add image occlusion support"
     git add <test-files> && git commit -m "test: Add tests for image occlusion"
     ```

3. **Push the Branch**
   ```bash
   git push origin <BRANCH_NAME>
   ```

---

## Phase 5: Pull Request

1. **Create the PR**
   ```bash
   gh pr create --title "<PR_TITLE>" --body "<PR_BODY>" --base main
   ```
   - Title should match the issue (e.g., "feat: Add image occlusion support")
   - Body should include:
     - Summary of changes
     - `Closes #<ISSUE_NUMBER>` to auto-close the issue
     - Verification notes

2. **Notify User**
   - Use the `notify` CLI tool:
     ```bash
     notify "[o2a] PR #<NUMBER> created for Issue #<ISSUE_NUMBER>"
     ```

---

## Error Handling

- **Test Failures**: Debug and fix before proceeding. Do not skip tests.
- **QA Failures**: Fix all linting/type errors. Do not use `# noqa` or `@ts-ignore` unless absolutely necessary.
- **User Rejection**: Update the plan based on feedback and re-request approval.
- **Git Conflicts**: Rebase on main and resolve conflicts before pushing.

---

## Quick Reference

| Phase | Key Action | Exit Condition |
|-------|------------|----------------|
| 1. Analysis | `gh issue view` | Issue understood |
| 2. Planning | Create `implementation_plan.md` | User approves |
| 3. Dev Loop | Code → Test → QA | 0 errors |
| 4. Commit | Organize & push | Branch pushed |
| 5. PR | `gh pr create` | PR created |
