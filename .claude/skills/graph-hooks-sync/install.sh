#!/usr/bin/env bash
# install.sh — installs the graph-hooks-sync git hooks into this repo's
# LOCAL .git/hooks/ directory. Safe to re-run (idempotent; overwrites the
# previously-installed copies unconditionally, since they're generated,
# not hand-edited).
#
# Source layout is split into hooks/ (the 3 git-hook templates, named
# literally after the hook they become) and lib/ (shared helpers) — see
# SKILL.md "File layout" for why this diverges from pre-commit-enforce's
# flat src/ convention. All 4 files are installed FLAT into .git/hooks/
# (matching real git hook names + a plain helper file alongside them), so
# each hook's own `source "$(dirname "${BASH_SOURCE[0]}")/graph-sync-helpers.sh"`
# keeps working unchanged after install.
#
# Requires: this repo's global `core.hooksPath`
# (/home/pluto-atom-4/.config/git/hooks on this machine) to already chain
# to local .git/hooks/<name> for post-commit/post-merge/post-checkout —
# confirmed true for this repo (see issue #121's investigation notes). If
# that global chain is ever removed/changed, these hooks will silently
# stop firing; verify with `git config --get core.hooksPath` and inspect
# that directory's post-commit/post-merge/post-checkout scripts.
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(git -C "$SKILL_DIR" rev-parse --show-toplevel)"
HOOKS_DIR="${REPO_ROOT}/.git/hooks"

mkdir -p "$HOOKS_DIR"

cp "${SKILL_DIR}/lib/graph-sync-helpers.sh" "${HOOKS_DIR}/graph-sync-helpers.sh"
chmod +x "${HOOKS_DIR}/graph-sync-helpers.sh"
echo "Installed ${HOOKS_DIR}/graph-sync-helpers.sh"

for name in post-commit post-merge post-checkout; do
  src="${SKILL_DIR}/hooks/${name}"
  dest="${HOOKS_DIR}/${name}"
  cp "$src" "$dest"
  chmod +x "$dest"
  echo "Installed ${dest}"
done

echo "graph-hooks-sync installed. Verify with:"
echo "  git config --get core.hooksPath   # should print the global hooks dir"
echo "  ls -la ${HOOKS_DIR}/{post-commit,post-merge,post-checkout,graph-sync-helpers.sh}"
