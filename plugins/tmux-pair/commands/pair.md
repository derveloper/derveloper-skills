---
description: Spawn a writer + reviewer agent pair in a fresh git worktree, side by side in tmux
argument-hint: <project-path> <base> <feature> [task...] [--with-standards] [--greenfield] [--no-worktree] [--dual-review] [--claude-model SLUG] [--claude-effort LEVEL] [--reviewer-2-agent NAME]
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
- `/pair ~/code/myapp main hotfix-x --no-worktree` (work directly on the project's current branch)
- `/pair ~/code/myapp main small-job --claude-model claude-opus-4-6` (200k context, cheaper for short tasks)
- `/pair ~/code/myapp main risky-refactor --dual-review` (two reviewers cross-checking, codex + claude)

## Optional flags

- `--with-standards` — append the durable standards bundle (STANDARDS, recall discipline, bullet-start ritual, pair protocol) to engineer briefings. Default is slim.
- `--greenfield` — enable `--with-standards` plus the greenfield pre-flight block.
- `--no-worktree` — skip `git worktree add`. Engineers commit directly on the project's current branch in the project directory. Use sparingly: any uncommitted work in the project becomes pair-visible. With `--no-worktree`, the plugin skips writing AGENTS.md (codex receives standards via the briefing only).
- `--claude-model <slug>` — claude model to switch into post-boot via `/model <slug>` (default `claude-opus-4-7`, 1M context). Switch to `claude-opus-4-6` for 200k context; the compact-watcher threshold rescales automatically. Codex always uses `gpt-5.5 xhigh` per user setup.
- `--claude-effort <level>` — claude reasoning effort, set as `--effort <level>` in the claude boot-command (default `max`). Choices: `low|medium|high|xhigh|max`. Pass an empty string to skip the flag (claude default or `CLAUDE_CODE_EFFORT_LEVEL` env-var applies). The CLI flag is race-free vs. the `/effort` slash-command after a `/model` switch.
- `--dual-review` — opt-in second reviewer. Spawns reviewer-1 (claude by default) and reviewer-2 (codex by default) stacked vertically on the right side. Both review independently, swap findings, then send a final report each to the human (= orchestrator in pair-mode) for consolidation. Off by default.
- `--reviewer-2-agent <agent>` — override the second reviewer agent (default codex). Only relevant with `--dual-review`.

## Action

Parse arguments. If they are unambiguous, run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/tmux_pair.py pair \
  --project <project-path> \
  --base <base> \
  --feature <feature> \
  --task "<task>" \
  [--with-standards] [--greenfield] [--no-worktree] [--claude-model <slug>] \
  [--claude-effort <level>] \
  [--dual-review] [--reviewer-2-agent <agent>]
```

If the feature description is missing or ambiguous, ask the user before spawning. Spawning idle agents costs more than asking one short question.

## Output

JSON with `worktree`, `branch`, `window`, `writer_pane`, `reviewer_pane`, `human_pane`. With `--dual-review`: additional `reviewer_2_pane` + `reviewer_2_agent`. Relay these back to the user so they can address either agent directly via the `send` subcommand.

## Cleanup (manual)

```bash
cd <project-path>
git worktree remove ../<project-name>-wt-<feature>
git branch -d feature/<feature>   # after merge
```
