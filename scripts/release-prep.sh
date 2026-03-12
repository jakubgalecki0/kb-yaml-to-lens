#!/bin/bash
# Release Preparation Script
#
# Opens GitHub issues for pre-release review tasks. Each issue is designed
# to be triaged and worked on independently (e.g., by Claude Code via auto-triage).
#
# Usage:
#   ./scripts/release-prep.sh [version]
#
# Examples:
#   ./scripts/release-prep.sh 0.3.0
#   ./scripts/release-prep.sh          # uses current version from pyproject.toml

set -euo pipefail

REPO="strawgate/kb-yaml-to-lens"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

# Get version from argument or pyproject.toml
if [ $# -ge 1 ]; then
    VERSION="$1"
else
    VERSION=$(grep '^version' "$ROOT_DIR/pyproject.toml" | head -1 | sed 's/.*= *"\(.*\)"/\1/')
fi

echo "Preparing release v${VERSION}"
echo "Creating pre-release review issues..."
echo

# Label for all release-prep issues
LABEL="release-prep"

# Ensure the label exists
gh label create "$LABEL" --repo "$REPO" --color "D4C5F9" --description "Pre-release preparation tasks" 2>/dev/null || true

# ============================================================================
# Issue 1: Documentation Review
# ============================================================================
echo "Creating issue: Documentation Review..."
gh issue create --repo "$REPO" \
    --label "$LABEL" \
    --title "Release v${VERSION}: Documentation review" \
    --body "$(cat <<'BODY'
## Task

Review all documentation for accuracy ahead of the v__VERSION__ release.

### Files to review

- [ ] `RELEASE.md` — release steps match current tooling (just vs make)
- [ ] `DEVELOPING.md` — setup instructions work on a fresh clone
- [ ] `CONTRIBUTING.md` — contribution guide is current
- [ ] `packages/kb-dashboard-cli/DEVELOPING.md`
- [ ] `packages/kb-dashboard-core/DEVELOPING.md`
- [ ] `packages/vscode-extension/DEVELOPING.md`
- [ ] `packages/kb-dashboard-docs/DEVELOPING.md`
- [ ] `packages/kb-dashboard-docs/content/CLI.md` — CLI usage instructions
- [ ] `packages/kb-dashboard-docs/content/vscode-extension.md`
- [ ] `packages/kb-dashboard-docs/content/panels/*.md` — panel documentation

### What to look for

- Commands that reference `make` instead of `just` (or vice versa)
- Outdated version numbers or package names
- Broken links or references to removed files
- Missing documentation for new features (e.g., collapsible sections)
- Setup instructions that skip required steps
- Examples that no longer work

### Definition of done

Open a PR fixing any issues found, or comment confirming all docs are accurate.
BODY
)" | sed "s/__VERSION__/${VERSION}/g"

# ============================================================================
# Issue 2: Release Dry Run
# ============================================================================
echo "Creating issue: Release Dry Run..."
gh issue create --repo "$REPO" \
    --label "$LABEL" \
    --title "Release v${VERSION}: Dry run of release steps" \
    --body "$(cat <<BODY
## Task

Perform a dry run of the release process to catch issues before tagging.

### Steps

1. **Version bump dry run**
   \`\`\`bash
   uv run scripts/bump-version.py patch --dry-run
   \`\`\`
   Verify all files that would be updated look correct.

2. **Full CI check**
   \`\`\`bash
   just all ci
   \`\`\`
   All tests, lints, and type checks must pass.

3. **Build all packages**
   \`\`\`bash
   just core build
   just tools build
   just lint build
   just cli build
   just vscode package
   \`\`\`
   Verify all packages build successfully.

4. **Docker build test**
   \`\`\`bash
   docker build -f packages/kb-dashboard-cli/Dockerfile -t kb-dashboard-compiler:test .
   \`\`\`

5. **Version consistency check**
   Verify all \`pyproject.toml\` and \`package.json\` files have the same version.

6. **Dependency pin check**
   Verify internal dependencies (e.g., kb-dashboard-core in kb-dashboard-cli) are pinned to the correct version.

### Definition of done

Comment with results of each step. If any step fails, open a PR to fix it.
BODY
)"

# ============================================================================
# Issue 3: Code Quality Scan
# ============================================================================
echo "Creating issue: Code Quality Scan..."
gh issue create --repo "$REPO" \
    --label "$LABEL" \
    --title "Release v${VERSION}: Code quality scan" \
    --body "$(cat <<'BODY'
## Task

Scan the codebase for code smells, dead code, and quality issues before release.

### Areas to check

- [ ] **Dead code**: Unused functions, classes, imports, or variables across all packages
- [ ] **Dead files**: Files that are not imported or referenced anywhere
- [ ] **TODO/FIXME/HACK comments**: Review and resolve or convert to issues
- [ ] **Commented-out code**: Remove or restore
- [ ] **Inconsistent error handling**: Missing error messages, swallowed exceptions
- [ ] **Type safety**: Any `type: ignore` comments that can be resolved, `Any` types that should be narrowed
- [ ] **Test coverage gaps**: Important code paths without tests (especially new features)
- [ ] **Dependency health**: Outdated or vulnerable dependencies

### Commands to run

```bash
# Find TODOs/FIXMEs
rg "TODO|FIXME|HACK|XXX" --type py --type ts -g '!node_modules' -g '!.venv'

# Find type: ignore comments
rg "type: ignore" --type py

# Check for unused imports (Python)
just core lint
just cli lint
just tools lint
just lint lint

# TypeScript lint
just vscode lint
```

### Definition of done

Open PRs for any fixes, or comment confirming the codebase is clean.
BODY
)"

# ============================================================================
# Issue 4: Test Suite Review
# ============================================================================
echo "Creating issue: Test Suite Review..."
gh issue create --repo "$REPO" \
    --label "$LABEL" \
    --title "Release v${VERSION}: Test suite review" \
    --body "$(cat <<'BODY'
## Task

Review the test suite for completeness and reliability before release.

### Checks

- [ ] **All tests pass**: `just all ci`
- [ ] **New features have tests**: Check recent PRs for test coverage
- [ ] **Flaky tests**: Identify any tests that fail intermittently
- [ ] **Test examples match docs**: Verify docstring/doctest examples still work
- [ ] **Example dashboards compile**: All YAML files in `packages/kb-dashboard-docs/content/examples/` should compile without errors
- [ ] **E2E tests**: Run `just cli test-e2e` and `just vscode test-e2e` if environments are available

### Commands

```bash
# Run all unit tests
just core test
just cli test
just tools test
just lint test

# Test example dashboards
just cli test-e2e

# Run doctest examples
just core test  # includes doctests
```

### Definition of done

Comment confirming all tests pass and coverage is adequate for new features.
BODY
)"

# ============================================================================
# Issue 5: CHANGELOG / Release Notes Draft
# ============================================================================
echo "Creating issue: Release Notes Draft..."
RELEASE_NOTES_BODY="## Task

Draft release notes for v${VERSION} based on changes since the last release.

### Steps

1. Review commits since last tag:
   \`\`\`bash
   git log \$(git describe --tags --abbrev=0)..HEAD --oneline
   \`\`\`

2. Categorize changes:
   - **New Features**: \`feat:\` commits
   - **Bug Fixes**: \`fix:\` commits
   - **Breaking Changes**: Any API or config format changes
   - **Documentation**: \`docs:\` commits
   - **Internal**: \`refactor:\`, \`chore:\`, \`ci:\` commits

3. Write user-facing release notes highlighting:
   - What's new and why it matters
   - Migration steps for any breaking changes
   - Notable bug fixes

4. Post the draft as a comment on this issue for review.

### Definition of done

Release notes draft reviewed and approved."
gh issue create --repo "$REPO" \
    --label "$LABEL" \
    --title "Release v${VERSION}: Draft release notes" \
    --body "$RELEASE_NOTES_BODY"

echo
echo "Done! Created 5 release-prep issues for v${VERSION}."
echo "View them at: https://github.com/${REPO}/labels/release-prep"
