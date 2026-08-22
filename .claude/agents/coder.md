---
name: coder
description: Implement features and tests from tasks.md; writes src/ and tests/, forbidden from governance files.
model: claude-haiku-4-5-20251001 # Haiku for cost-efficient, fast coding
tools:
  - Read
  - Write
  - Grep
  - Glob
  - Bash
  - mcp__blender-local-agent__run_blender_python
  - mcp__blender-local-agent__check_blender_live_status
permissions:
  write:
    deny: ["AGENTS.md", "CLAUDE.md", ".claude/agents/**", ".claude/rules/**", ".claude/skills/**", ".claude/settings.json"] # Prevent governance file modification
  bash:
    allow: ["npm test", "cargo test", "pytest"] # Pre-approve testing commands
    deny: ["gh pr create"] # Reviewer creates PR after Gate-2 verification
    ask: ["gh pr comment"]
---
