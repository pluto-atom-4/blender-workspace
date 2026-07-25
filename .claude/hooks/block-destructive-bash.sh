#!/usr/bin/env bash
# PreToolUse hook for the Bash matcher: blocks a short list of destructive
# command patterns before they run. Exit 2 blocks the tool call (stderr is
# surfaced as the reason); exit 0 lets it through unchanged.
set -euo pipefail

command=$(jq -r '.tool_input.command // empty')

if [[ -z "$command" ]]; then
  exit 0
fi

if echo "$command" | grep -qE 'rm[[:space:]]+-rf|git[[:space:]]+reset[[:space:]]+--hard|git[[:space:]]+push[[:space:]].*(-f\b|--force\b)'; then
  echo "Blocked by PreToolUse hook: command matches a destructive pattern (rm -rf / git reset --hard / git push --force). Run it manually outside the hook if this is intentional." >&2
  exit 2
fi

exit 0
