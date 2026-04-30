---
description: Spawn a writer + reviewer agent pair in a fresh git worktree, side by side in tmux
---

# pair

Spawn a writer + reviewer pair in a fresh `git worktree`, each in its own tmux pane, with a small JSON receipt printed back so you can address them later.

## Invocation

`/pair <project-path> <base> <feature> [task...]`

- `<project-path>`: path to the git repository to base the worktree on
- `<base>`: ref to branch from, e.g. `origin/main` (default), `main`, a tag, a SHA
- `<feature>`: short feature name (used in branch + window name)
- `[task...]`: optional free-form task description sent verbatim to both agents

## Examples

- `/pair ~/code/myapp origin/main retry-budget`
- `/pair ~/code/myapp main webhook-backoff implement exponential backoff for outbound webhooks`

## Action

Parse arguments. If they are unambiguous, run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/tmux_pair.py pair \
  --project <project-path> \
  --base <base> \
  --feature <feature> \
  --task "<task>"
```

If the feature description is missing or ambiguous, ask the user before spawning. Spawning idle agents costs more than asking one short question.

## Output

JSON with `worktree`, `branch`, `window`, `writer_pane`, `reviewer_pane`, `master_pane`. Relay these back to the user so they can address either agent directly via the `send` subcommand.

## Cleanup (manual)

```bash
cd <project-path>
git worktree remove ../<project-name>-wt-<feature>
git branch -d feature/<feature>   # after merge
```
