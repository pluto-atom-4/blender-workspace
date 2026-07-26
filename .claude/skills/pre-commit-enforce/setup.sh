#!/bin/bash
# Setup script: Install and register pre-commit enforcement hook

set -e

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
GIT_HOOKS_DIR="$REPO_ROOT/.git/hooks"

echo "📦 Setting up pre-commit enforcement..."
echo ""

# Verify git repo
if [ ! -d "$REPO_ROOT/.git" ]; then
  echo "❌ Not a git repository: $REPO_ROOT"
  exit 1
fi

# Create .git/hooks if missing
mkdir -p "$GIT_HOOKS_DIR"

# Copy hook template
HOOK_FILE="$GIT_HOOKS_DIR/pre-commit"
cp "$SKILL_DIR/src/hook-template.sh" "$HOOK_FILE"
chmod +x "$HOOK_FILE"

echo "✅ Hook installed at: $HOOK_FILE"

# Verify skill directory is accessible
if [ ! -d "$REPO_ROOT/.claude/skills/pre-commit-enforce" ]; then
  echo "⚠️  Skill not found at .claude/skills/pre-commit-enforce"
  echo "   Please ensure skill is installed in project"
  exit 1
fi

echo "✅ Skill directory verified"

# Check config file
if [ -f "$REPO_ROOT/.claude/settings.json" ]; then
  echo "✅ Config file found: .claude/settings.json"
else
  echo "ℹ️  No config file — using defaults (protect: main)"
  echo "   Add .claude/settings.json to customize"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Protected branches: $(source $SKILL_DIR/src/helpers.sh && get_protected_branches)"
echo ""
echo "Test: Try to commit on a protected branch (should be blocked)"
