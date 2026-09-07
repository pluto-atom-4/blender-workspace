---
name: graph-hooks-sync
description: Installs local git hooks that keep code-review-graph and graphify's knowledge graphs in sync on commit/merge/checkout.
---

# graph-hooks-sync

Keeps the `code-review-graph` graph (`.code-review-graph/graph.db`) and the
`graphify` graph (`graphify-out/graph.json`) up to date automatically, by
installing hand-written git hooks into this repo's local `.git/hooks/`.
Both graph outputs are gitignored (self-ignored / global-ignored
respectively, see CLAUDE.md "Graph Intelligence Tools") — this is a
local-developer-experience convenience only, not something CI needs.

## File layout (note: diverges from `pre-commit-enforce`)

```
.claude/skills/graph-hooks-sync/
├── SKILL.md
├── install.sh
├── hooks/                  # the 3 git-hook templates, one file per hook name
│   ├── post-commit
│   ├── post-merge
│   └── post-checkout
└── lib/
    └── graph-sync-helpers.sh   # shared log/dedup/detach helpers
```

The sibling `pre-commit-enforce` skill uses a flat `src/helpers.sh` +
`src/hook-template.sh` layout. This skill deliberately does **not** mirror
that: a flat `src/*` here would read as "project source" (this repo's
`src/`-adjacent conventions mean actual project code), and 3 of the flat
filenames (`post-commit`, `post-merge`, `post-checkout`) are identical to
real git hook names, which made it easy to confuse the *tracked source*
copy under the skill with the *installed* copy under `.git/hooks/`.
Splitting into `hooks/` (named literally after the git hook each becomes)
and `lib/` (helpers, not a hook itself) removes that ambiguity at the cost
of one level of inconsistency with `pre-commit-enforce` — an intentional
naming-clarity trade-off, not an oversight.

## Why hand-written hooks, not `graphify hook install`

`graphify` ships its own git-hook installer (`graphify hook install`), but
**do not use it on this machine** (or any machine where `core.hooksPath`
is set globally, as it is here — `/home/pluto-atom-4/.config/git/hooks`,
from an unrelated prior project). `git rev-parse --git-path hooks`
resolves to that GLOBAL directory, not this repo's `.git/hooks/`, because
of `core.hooksPath`. Confirmed via `graphify hook status`, which already
reports `post-commit: not installed (hook exists but graphify not found)`
— i.e. it is inspecting the global chain-only hook file, not a repo-local
one. Running `graphify hook install` would write into that shared,
cross-repo directory, risking overwrite/corruption of the hook chain
relied on by every other repo on this machine. `code-review-graph` has no
native git-hook installer at all (`install`/`uninstall` only manage MCP
registration + AI-assistant-side hooks, unrelated to git). Both tools'
sync logic is therefore hand-written here, as local `.git/hooks/*` scripts
only, chained through the existing global `core.hooksPath` chain-only
design (confirmed: `post-commit`/`post-merge`/`post-checkout` in the
global hooks dir `exec` this repo's local hook of the same name if
present+executable, else no-op).

`graphify`'s own `merge-driver` (union-merge for `graph.json` across
branches) is not used either: `graph.json` is gitignored and never
committed, so there is nothing to merge-conflict on.

## Files

- `lib/graph-sync-helpers.sh` — shared log/dedup/detach helpers, sourced
  by all three hooks below. Installed alongside them (flat) in
  `.git/hooks/graph-sync-helpers.sh` so the hooks' own
  `source "$(dirname "${BASH_SOURCE[0]}")/graph-sync-helpers.sh"` works
  unchanged at runtime.
- `hooks/post-commit` — after every commit: incremental update
  (`code-review-graph update --skip-flows` + `graphify update .`),
  detached so `git commit` returns immediately.
- `hooks/post-merge` — after `git merge` / `git pull`: incremental update
  if ≤5 files changed since `ORIG_HEAD`, else a full rebuild
  (`code-review-graph build` + `graphify update . --force`).
- `hooks/post-checkout` — after a branch checkout (skips file-level
  checkouts): same ≤5-files-changed threshold; a fresh clone (all-zero
  previous HEAD) always forces a full rebuild.
- `install.sh` — copies `lib/graph-sync-helpers.sh` and the 3 files under
  `hooks/` into this repo's `.git/hooks/` (flat, matching real git hook
  names), `chmod +x`s them. Idempotent; safe to re-run after editing the
  `hooks/`/`lib/` source files.

There is intentionally **no `pre-push` hook** (Q2): both graph outputs are
local-only (gitignored, never pushed), so a rebuild at push time doesn't
benefit anyone pulling the pushed commits.

There is intentionally **no CPU/memory resource guard** (Q5): this repo is
small (~80 files; full rebuilds take ~2-3s) and this machine has ample
headroom. The only pile-up guard is `pgrep`-based dedup in
`graph-sync-helpers.sh` (skips spawning a new job if one with the same
name is already running). Revisit if the repo or graphs grow
significantly.

`code-review-graph embed` (semantic-search embeddings) is intentionally
**not** run from `post-commit` (Q4): this machine doesn't have the local
embeddings extra installed (`sentence_transformers` missing) and no cloud
embedding API key is configured. Run it manually if/when that changes.

## Install

```bash
.claude/skills/graph-hooks-sync/install.sh
```

Each developer runs this once after cloning (or after pulling changes to
this skill's `hooks/`/`lib/` files). It only writes to this repo's local,
untracked `.git/hooks/` — it does not touch the global hooks directory or
any other repo.

## Uninstall

```bash
rm -f .git/hooks/{post-commit,post-merge,post-checkout,graph-sync-helpers.sh}
```

(Leaves `.git/hooks/pre-commit`, owned by the separate
`pre-commit-enforce` skill, untouched.)

## Logs

`~/.cache/blender-workspace/graph-hooks.log` (outside the repo). Truncated
to the last 2000 lines at the start of each hook run — simple,
dependency-free retention; revisit if verbosity becomes a problem.
