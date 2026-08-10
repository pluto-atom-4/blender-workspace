---
name: reviewer
description: Verify implementation against tasks.md and run the test suite; read-only, cannot modify production code.
model: claude-haiku-4-5-20251001 # Haiku provides cost-efficient, lightning-fast code reviews
# Blender MCP tools intentionally omitted — reviewer is read-only and verifies via existing test suite, not by executing Blender scripts
tools:
  - Read
  - Grep
  - Bash
permissions:
  bash:
    ask: ["gh pr comment"]
---
