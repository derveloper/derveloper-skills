---
description: Spawn an orchestrator + writer + reviewer triple in a fresh git worktree (orchestrator on top, engineers below)
argument-hint: <project-path> <base> <feature> [task...]
---

# triple

Spawn a writer + reviewer pair plus a dedicated orchestrator in a fresh `git worktree`. The orchestrator runs in a pane on top across the full width, the two engineers sit side by side beneath. The orchestrator does recon, writes the engineer briefings, watches the pair loop, and reports up to the master pane on major events only.

The master gets to dispatch the spawn and step away. They are not the recon agent and not the relay between writer and reviewer.

## Invocation

`/triple <project-path> <base> <feature> [task...]`

- `<project-path>`: path to the git repository
- `<base>`: ref to branch from (default `origin/main`)
- `<feature>`: short feature name
- `[task...]`: free-form task description sent ONLY to the orchestrator. Engineers stay idle until the orchestrator briefs them after recon.

## Examples

- `/triple ~/code/myapp origin/main session-tokens`
- `/triple ~/code/myapp main rate-limit-redesign rebuild the rate limiter so it survives the redis failover scenario from incident 2026-01`

## When to use triple instead of pair

Use **triple** when:
- the task spans multiple unfamiliar files and needs upfront recon
- you expect the pair loop to take more than ~15 minutes and you don't want to relay
- the failure mode "engineers brief themselves and miss the real problem" is plausible
- you want the master pane free for other work while the triple runs

Use **pair** for short, well-scoped tasks where the master is willing to relay between writer and reviewer.

## Action

Parse arguments. If unambiguous, run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/tmux_pair.py triple \
  --project <project-path> \
  --base <base> \
  --feature <feature> \
  --task "<task>"
```

If feature or task is ambiguous, ask the user.

## Output

JSON with `worktree`, `branch`, `window`, `orchestrator_pane`, `writer_pane`, `reviewer_pane`, `master_pane`. Relay back to the user.

## Cleanup (manual)

Same as `/pair`. The orchestrator does NOT clean up; that decision stays with the master.
