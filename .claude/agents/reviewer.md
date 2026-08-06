---
name: reviewer
description: Verify implementation against tasks.md and run the test suite; read-only, cannot modify production code.
model: claude-haiku-4.5 # Haiku provides cost-efficient, lightning-fast code reviews
tools:
  - Read
  - Grep
  - Bash
permissions:
  bash:
    ask: ["gh pr comment"]
---
