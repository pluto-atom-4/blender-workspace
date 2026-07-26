# Pre-Commit Enforcement Skill

Enforce feature branch workflow by blocking commits to protected branches (default: main).

## Overview

This skill installs a git pre-commit hook that:
- Blocks commits directly to protected branches
- Shows workflow instructions when violation detected
- Reads configuration from `.claude/settings.json`
- Works across any project in your workspace

## Installation

### Method 1: Copy to Project

```bash
cp -r .claude/skills/pre-commit-enforce .claude/skills/
bash .claude/skills/pre-commit-enforce/setup.sh
```

### Method 2: Git Submodule

```bash
git submodule add https://github.com/org/pre-commit-enforce .claude/skills/pre-commit-enforce
bash .claude/skills/pre-commit-enforce/setup.sh
```

### Method 3: Symlink (Multiple Projects)

```bash
# From project A
ln -s /path/to/skill .claude/skills/pre-commit-enforce
bash .claude/skills/pre-commit-enforce/setup.sh
```

## Configuration

Add to `.claude/settings.json`:

```json
{
  "skillConfigs": {
    "pre-commit-enforce": {
      "protectedBranches": ["main", "develop"],
      "showInstructions": true,
      "message": "Direct commits to protected branches not allowed."
    }
  }
}
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `protectedBranches` | array | `["main"]` | Branches that block commits |
| `showInstructions` | bool | `true` | Show workflow instructions on violation |
| `message` | string | "Direct commits to protected branches..." | Custom error message |

## How It Works

1. **On each commit attempt**: Git runs `.git/hooks/pre-commit`
2. **Hook reads config**: Loads protected branches from `.claude/settings.json`
3. **Checks current branch**: If current branch is protected, blocks commit
4. **Shows instructions**: Displays proper workflow steps
5. **Allows feature branches**: Commits on non-protected branches succeed

## Usage Examples

### Example 1: Default (Protect main)

No config needed. By default protects `main` branch.

```bash
# This fails
git commit -m "test"  # ❌ Direct commits to main are not allowed

# This works
git checkout -b feat/example
git commit -m "test"  # ✅ Succeeds
```

### Example 2: Protect Multiple Branches

`.claude/settings.json`:
```json
{
  "skillConfigs": {
    "pre-commit-enforce": {
      "protectedBranches": ["main", "staging", "production"]
    }
  }
}
```

### Example 3: Custom Message

```json
{
  "skillConfigs": {
    "pre-commit-enforce": {
      "protectedBranches": ["main"],
      "message": "⚠️  Feature branches required. Use git checkout -b feat/..."
    }
  }
}
```

### Example 4: Disable Instructions

```json
{
  "skillConfigs": {
    "pre-commit-enforce": {
      "protectedBranches": ["main"],
      "showInstructions": false
    }
  }
}
```

## Workflow

```
Feature Branch Workflow:
1. Create feature branch
   git checkout -b feat/issue-XXX-description

2. Commit changes
   git commit -m "message"

3. Push branch
   git push -u origin feat/issue-XXX-description

4. Create PR on GitHub

5. Merge via PR (never direct push)
```

## Troubleshooting

### "Hook not found"

Ensure skill is in `.claude/skills/pre-commit-enforce`:
```bash
ls -la .claude/skills/pre-commit-enforce/src/
```

### "No such file"

Reinstall hook:
```bash
bash .claude/skills/pre-commit-enforce/setup.sh
```

### "Permission denied"

Make hook executable:
```bash
chmod +x .git/hooks/pre-commit
```

### Config not being read

Check `.claude/settings.json` exists and is valid JSON:
```bash
cat .claude/settings.json | python3 -m json.tool
```

## Removal

To disable enforcement:

```bash
# Delete hook
rm .git/hooks/pre-commit

# Delete skill (optional)
rm -rf .claude/skills/pre-commit-enforce
```

## Files

- `src/hook-template.sh` — Git hook implementation
- `src/helpers.sh` — Config parsing and utilities
- `setup.sh` — Installation script
- `SKILL.md` — This file
- `README.md` — Quick start guide

## Related

- [CLAUDE.md](../../../CLAUDE.md) — Project workflow policy
- [Git Workflow](../../../CLAUDE.md#git-workflow-enforced) — Feature branch instructions

---

**Status**: Ready for production  
**Last Updated**: 2026-07-17
