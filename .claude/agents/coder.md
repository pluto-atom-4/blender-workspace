---
name: coder
model: claude-haiku-4.5 # Use a strong coding model for synthesis
tools:
  - Read
  - Write
  - Grep
  - Glob
  - Bash
permissions:
  write:
    deny: ["AGENTS.md", "CLAUDE.md", ".claude/agents/**", ".claude/rules/**", ".claude/skills/**", ".claude/settings.json"] # Prevent governance file modification
  bash:
    allow: ["npm test", "cargo test", "pytest"] # Pre-approve testing commands
    ask: ["gh pr create", "gh pr comment"]
---
