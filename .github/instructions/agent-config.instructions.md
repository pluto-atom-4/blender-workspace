---
applyTo: ".claude/**,.github/copilot-instructions.md,.github/instructions/**,CLAUDE.md,AGENTS.md"
description: "Governance rules for AI tool configuration files"
---

# Agent configuration files

- Re-run `python3 scripts/context-audit.py` after editing any config file and commit the updated `docs/dev-note/context-baseline.json`. Token budgets and resident/on-demand context tallies drift silently otherwise.
- Preserve CI grep invariants: both `.github/copilot-instructions.md` and `.claude/hooks/block-destructive-bash.sh` must contain the substrings `rm -rf` and `git push --force` (workflow validation scans for these).
- Line 1 of `CLAUDE.md` must be exactly `@AGENTS.md` — this is the import directive for the config harness.
- `.claude/settings.json` permissions: do not add `permissions.defaultMode` (repo scope cannot grant it and it would shadow the user's global setting). Tier structure: `deny` (never, high severity), `ask` (confirm each time), `allow` (silent). Deny patterns must include the destructive operations: `rm -rf`, `git reset --hard`, `git push --force`, `sudo`.
- `.claude/agents/*.md` carry role guardrails in frontmatter (e.g., coder forbids editing governance files). The actual enforcement layer is `.claude/settings.json` permissions tiers; frontmatter is advisory only.
