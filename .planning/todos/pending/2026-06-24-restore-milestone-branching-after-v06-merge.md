---
created: 2026-06-24T00:00:00.000Z
title: Restore git.branching_strategy=milestone after v0.6 merges
area: tooling
resolves_phase: 46
files: [.planning/config.json]
---

## Problem

During Phase 44 (v0.6, "Engine owns the pool") the GSD commit helper
(`gsd-tools query commit`) kept auto-switching git branches: with
`config.git.branching_strategy = "milestone"` it computes
`gsd/{milestone}-{slug}` from STATE `milestone:` + the ROADMAP heading and
`git checkout`s it before committing, stranding task commits on the wrong branch.

To keep Phase 44 commits clean on the manually-managed `gsd/v0.6-milestone`
branch, the strategy was set to **`none`** (commit to current branch). This is
**temporary** — the project's normal mode is branch-per-milestone.

## Solution

Once the v0.6 work (`gsd/v0.6-milestone`) merges back to the usual line, restore
the default:

    gsd-tools query config-set git.branching_strategy milestone

Verify STATE `milestone:` + the active ROADMAP `## ... vX.Y ...` heading resolve
to the branch name you actually want before the next GSD commit (otherwise it
will create/switch to the derived `gsd/{version}-{slug}` branch again).

See memory [[project_gsd_commit_branch_autoswitch]].
