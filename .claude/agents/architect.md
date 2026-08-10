---
name: architect
description: Draft implementation plans, module boundaries, and architectural decisions; read-only against code.
model: claude-sonnet-5 # Use Sonnet or Opus for deep planning & architecture
# Blender MCP tools intentionally omitted — architect is read-only and does not execute Blender scripts
tools:
  - Read
  - Grep
  - Glob
  - Bash
permissions:
  bash:
    allow: ["gh issue create", "gh issue list", "gh issue comment"]
    ask: ["*"] # Prompts human before executing destructive or arbitrary commands
---
