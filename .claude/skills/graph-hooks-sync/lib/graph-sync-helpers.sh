#!/usr/bin/env bash
# graph-sync-helpers.sh
# Shared helpers sourced by the graph-hooks-sync git hooks (post-commit,
# post-merge, post-checkout). Keeps code-review-graph and graphify's local
# knowledge graphs in sync automatically.
#
# Generated/installed by .claude/skills/graph-hooks-sync/install.sh — the
# INSTALLED copy under .git/hooks/graph-sync-helpers.sh is untracked and
# regenerated on each install run; edit the SOURCE under
# .claude/skills/graph-hooks-sync/lib/graph-sync-helpers.sh instead, then
# re-run install.sh.
#
# By design there is no CPU/memory resource guard here (see SKILL.md,
# "Resource guards" / Q5): dedup via pgrep is the only safeguard against
# pile-up from rapid-fire commits/merges/checkouts.

GRAPH_SYNC_LOG_DIR="${HOME}/.cache/blender-workspace"
GRAPH_SYNC_LOG="${GRAPH_SYNC_LOG_DIR}/graph-hooks.log"

graph_sync_log() {
  local hook="$1"; shift
  mkdir -p "$GRAPH_SYNC_LOG_DIR" 2>/dev/null || return 0
  if [ -f "$GRAPH_SYNC_LOG" ]; then
    tail -n 2000 "$GRAPH_SYNC_LOG" > "${GRAPH_SYNC_LOG}.tmp" 2>/dev/null \
      && mv "${GRAPH_SYNC_LOG}.tmp" "$GRAPH_SYNC_LOG" 2>/dev/null
  fi
  printf '[%s] [%s] %s\n' "$(date -Iseconds)" "$hook" "$*" >> "$GRAPH_SYNC_LOG"
}

# Dedup guard: skip spawning a new job if one tagged with the same
# job_name is already running. Matches on a literal "graph-sync:<job_name>"
# marker embedded in the running job's own command line (see
# graph_sync_spawn_detached), found via `pgrep -f`.
graph_sync_dedup_guard() {
  local job_name="$1"
  pgrep -f "graph-sync:${job_name}" >/dev/null 2>&1 && return 1
  return 0
}

# Runs "$@" as a detached background job (tagged as job_name) so the
# calling git command (commit/merge/checkout) returns immediately. Capped
# at 5 minutes via `timeout`. The "graph-sync:<job_name>" marker is
# embedded directly in the backgrounded process's own command line (as a
# harmless shell variable assignment) so it stays visible to `pgrep -f`
# for the job's entire runtime.
#
# The trailing "; :" no-op is load-bearing, not decorative: without it,
# bash's "exec last simple command" optimization replaces this wrapper
# process's own argv with `timeout`'s argv the moment it runs the final
# statement, silently erasing the GRAPH_SYNC_JOB marker from `ps`/`pgrep
# -f` for the rest of the job's runtime (verified empirically — the
# marker vanished within well under a second). The trailing no-op means
# `timeout ...` is no longer the last command, so bash forks it as a real
# child instead of exec-replacing itself, keeping the marker-bearing argv
# visible to `pgrep -f` for the job's whole duration.
graph_sync_spawn_detached() {
  local job_name="$1"; shift
  local quoted_cmd
  printf -v quoted_cmd '%q ' "$@"
  setsid nohup bash -c \
    "GRAPH_SYNC_JOB=graph-sync:${job_name}; timeout 300 ${quoted_cmd}; :" \
    >> "$GRAPH_SYNC_LOG" 2>&1 < /dev/null &
  disown
}
