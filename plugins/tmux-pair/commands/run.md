---
description: Auto-entry to tmux-pair. Inspects the repo + task and invokes solo with the right flags. Solo is the only mode.
argument-hint: <project-path> <base> <feature> [task...] [<any solo flag>]
---

# run

Default tmux-pair entry-point. `/run` performs a short repo + task recon, then invokes solo. Multi-pane spawn modes were removed: shared CARGO_TARGET_DIR contention, git-index-lock races, cross-writer PROJECT.md races, and dual-review coordination consistently outweighed the parallelism gain. The lean replacement is solo + subagent fan-out + adversarial codex-CLI second-opinion at each gate (see `commands/solo.md`).

## Invocation

`/run <project-path> <base> <feature> [task...] [<any solo flag>]`

- `<project-path>`: path to the git repository
- `<base>`: ref to branch from (default `origin/main`)
- `<feature>`: short feature name
- `[task...]`: free-form task description forwarded to solo.

All `/solo` flags are forwarded unchanged.

## Examples

- `/run ~/code/myapp origin/main retry-budget add a per-tenant retry budget to the webhook dispatcher`
- `/run ~/code/myapp main typo-fix fix typo in README --no-gated`
- `/run ~/code/myapp main migrate-rules-to-skills --no-worktree`

## Decision logic

1. **Task clarification**: if `<task>` is missing or ambiguous (single keyword, no verb), ask the user once via `AskUserQuestion`. Continue with the clarified intent.
2. **Repo recon**: inspect `<project-path>` for size, language stack, `.claude/agents/`, `.claude/rules/`. Used to pre-pick a sensible `--with-standards` / `--greenfield` flag if appropriate.
3. **Invoke solo** with the resolved flags.

For tasks that look like 15+ bullet sweeps: batch into 3-5 bullets per solo run and chain them, rather than packing everything into one monolithic solo. Plan-drift correlates strongly with bullet count per run.

## Optional flags

All `/solo` flags are forwarded. There is no `--spawn`-style mode anymore.

## Action

Parse arguments. If feature or task is ambiguous, ask the user once. Then run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/tmux_pair.py solo \
  --project <project-path> --base <base> --feature <feature> --task "<task>" \
  [...forwarded solo flags]
```

## Output

JSON from `/solo`, prefixed by a one-line recon note (e.g. `recon: 12 affected files, .claude/rules/ present`).

## Cleanup (manual)

Same as `/solo`. See `commands/solo.md`.
