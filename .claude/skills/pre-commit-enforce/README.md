# Pre-Commit Enforcement Skill

Block commits to protected branches. Enforce feature branch workflow.

## Install (remote)

```bash
curl -sSL https://raw.githubusercontent.com/pluto-atom-4/pre-commit-enforce-skill/main/install.sh | bash
```

> Use `raw.githubusercontent.com`, not a `github.com/.../blob/...` URL — the latter returns an HTML page, not the script.

## Quick Start (30 seconds)

```bash
# 1. Copy skill to project
cp -r .claude/skills/pre-commit-enforce .claude/skills/

# 2. Run setup
bash .claude/skills/pre-commit-enforce/setup.sh

# 3. Test
git commit --allow-empty -m "test"  # ❌ Blocked
git checkout -b feat/test
git commit --allow-empty -m "test"  # ✅ Works
```

## Default Behavior

- **Protects**: `main` branch
- **Allows**: All other branches (`feat/*`, `fix/*`, `docs/*`, etc.)
- **Message**: "Direct commits to main are not allowed."

## Customize

Edit `.claude/settings.json`:

```json
{
  "skillConfigs": {
    "pre-commit-enforce": {
      "protectedBranches": ["main", "staging"],
      "message": "Feature branch required"
    }
  }
}
```

Config is read live on every commit — no reinstall needed after editing it.

## Update to Latest Version

Re-run the remote installer. It re-fetches the skill (latest GitHub Release, or `main` if no release exists), overwrites `.claude/skills/pre-commit-enforce/`, and re-registers the hook automatically:

```bash
curl -sSL https://raw.githubusercontent.com/pluto-atom-4/pre-commit-enforce-skill/main/install.sh | bash
```

> `setup.sh` alone does **not** update the skill — it only re-copies whatever hook code is already on disk into `.git/hooks/pre-commit`. Use `install.sh` to actually pull new code.

## Docs

See [SKILL.md](SKILL.md) for full documentation.

## Workflow

```
git checkout -b feat/issue-123-description    # Create feature branch
git commit -m "description"                     # Commit on branch
git push -u origin feat/issue-123-description   # Push branch
# Create PR on GitHub → Merge
```

## Support

- Check `.git/hooks/pre-commit` is executable: `ls -la .git/hooks/`
- Verify config: `cat .claude/settings.json | python3 -m json.tool`
- Hook missing/broken: `bash .claude/skills/pre-commit-enforce/setup.sh` (re-registers the hook from the currently installed skill code — does not fetch updates, see [Update to Latest Version](#update-to-latest-version))

---

**Install time**: < 1 minute  
**No dependencies**: Uses bash + git  
**Cross-platform**: Works on Linux, macOS, WSL
