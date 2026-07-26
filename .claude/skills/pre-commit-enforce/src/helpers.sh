#!/bin/bash
# Helper functions for pre-commit enforcement skill

# Parse JSON config from .claude/settings.json
# Usage: get_config_value "skillConfigs.pre-commit-enforce.protectedBranches"
get_config_value() {
  local key="$1"
  local config_file=".claude/settings.json"

  if [ ! -f "$config_file" ]; then
    return 1
  fi

  # Simple JSON parsing (works for simple structures)
  python3 -c "
import json
try:
  with open('$config_file') as f:
    config = json.load(f)
  keys = '$key'.split('.')
  val = config
  for k in keys:
    val = val.get(k, '') if isinstance(val, dict) else ''
  if isinstance(val, list):
    print(' '.join(val))
  else:
    print(val)
except:
  pass
" 2>/dev/null
}

# Get protected branches from config or use default
get_protected_branches() {
  local branches=$(get_config_value "skillConfigs.pre-commit-enforce.protectedBranches")

  if [ -z "$branches" ]; then
    # Default to main if not configured
    echo "main"
  else
    echo "$branches"
  fi
}

# Get custom message or use default
get_message() {
  local msg=$(get_config_value "skillConfigs.pre-commit-enforce.message")

  if [ -z "$msg" ]; then
    echo "Direct commits to protected branches are not allowed."
  else
    echo "$msg"
  fi
}

# Check if should show instructions
should_show_instructions() {
  local show=$(get_config_value "skillConfigs.pre-commit-enforce.showInstructions")

  # Default to true if not set
  if [ -z "$show" ]; then
    return 0
  fi

  if [ "$show" = "true" ] || [ "$show" = "True" ] || [ "$show" = "1" ]; then
    return 0
  else
    return 1
  fi
}

# Log message with color
log_error() {
  echo "❌ $1" >&2
}

log_success() {
  echo "✅ $1" >&2
}

log_info() {
  echo "ℹ️  $1" >&2
}

# Get repo root
get_repo_root() {
  git rev-parse --show-toplevel 2>/dev/null || pwd
}

# Expand ~ in paths
expand_path() {
  echo "$1" | sed "s|^~|$HOME|"
}
