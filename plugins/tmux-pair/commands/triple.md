---
description: Spawn an orchestrator + writer + reviewer triple in a fresh git worktree, with PROJECT.md care in the gated workflow
argument-hint: <project-path> <base> <feature> [task...] [--with-standards] [--greenfield] [--no-worktree] [--dual-review] [--claude-model SLUG] [--claude-effort LEVEL] [--reviewer-2-agent NAME]
---

# triple

Spawn a writer + reviewer pair plus a dedicated orchestrator in a fresh `git worktree`. The orchestrator runs in a pane on top across the full width, the two engineers sit side by side beneath. The orchestrator does recon, writes the engineer briefings, watches the pair loop, and reports up to the human pane on major events only.

The human gets to dispatch the spawn and step away. They are not the recon agent and not the relay between writer and reviewer.

Every `send` message gets a stable sender prefix such as `[FROM: or.<feature>]`
or `[FROM: wr.<feature>]` unless the message already starts with `[FROM:`.
The helper stores sender names in tmux pane options so agent TUI spinner titles
do not leak into pings.

The orchestrator also checks whether the repository has a project-local
`PROJECT.md`. Feature and refactor bullets must keep it current when package
map, feature surface, design decisions, or implementation history change.
Reviewers sign off on the update or on a justified skip, and
`~/git/example-project/PROJECT.md` is the reference example.

Plans must include explicit parallel markers per bullet: `B3 || B4 [parallel]`
when work can run together, or `B3 -> B4 [sequenziell: <reason>]` when ordering
is required. The orchestrator checks whether independent bullets are needlessly
serial and may propose additional worktrees or pair spawns for independent work.

## Invocation

`/triple <project-path> <base> <feature> [task...]`

- `<project-path>`: path to the git repository
- `<base>`: ref to branch from (default `origin/main`)
- `<feature>`: short feature name
- `[task...]`: free-form task description sent ONLY to the orchestrator. Engineers stay idle until the orchestrator briefs them after recon.

## Examples

- `/triple ~/code/myapp origin/main session-tokens`
- `/triple ~/code/myapp main rate-limit-redesign rebuild the rate limiter so it survives the redis failover scenario from incident 2026-01`
- `/triple ~/code/myapp main smallfeature --claude-model claude-opus-4-6` (200k context, cheaper for short tasks)
- `/triple ~/code/myapp main full-review --with-standards`
- `/triple ~/code/myapp main first-session --greenfield` (adds standards and greenfield pre-flight)
- `/triple ~/code/myapp main resume-existing --no-worktree --project ~/code/myapp-wt-existing` (reuse an existing worktree directly)
- `/triple ~/code/myapp main risky-refactor --dual-review` (orchestrator + writer + two cross-checking reviewers)

## Optional flags

- `--with-standards` — append the durable standards bundle (STANDARDS, recall discipline, bullet-start ritual, pair protocol) to engineer briefings in the Orchestrator handoff. Default is slim.
- `--greenfield` — enable `--with-standards` plus the greenfield pre-flight block.
- `--no-worktree` — skip `git worktree add`. Use when resuming on an existing worktree (point `--project` at the worktree path) or running directly on the project branch. With `--no-worktree`, the plugin skips writing AGENTS.md to the project repo; codex picks up standards via the briefing only.
- `--claude-model <slug>`: claude model to switch into post-boot for orchestrator + writer (default `claude-opus-4-7`, 1M context). Switch to `claude-opus-4-6` for 200k context; the compact-watcher threshold rescales automatically (700k → 140k). Codex pane boot follows the user's configured CLI default; engineer subagent defaults are documented in the workflow briefing.
- `--claude-effort <level>` — claude reasoning effort, set as `--effort <level>` in the claude boot-command for any claude pane (Writer + Orchestrator) (default `max`). Choices: `low|medium|high|xhigh|max`. Pass an empty string to skip the flag (claude default or `CLAUDE_CODE_EFFORT_LEVEL` env-var applies). The CLI flag is race-free vs. the `/effort` slash-command after a `/model` switch.
- `--dual-review` — opt-in second reviewer. Layout becomes: orchestrator on top full width, writer bottom-left, reviewer-1 + reviewer-2 stacked on the bottom-right side. Both reviewers review independently, swap findings, then send final reports to the orchestrator who consolidates before forwarding to the writer. Off by default.
- `--reviewer-2-agent <agent>` — override the second reviewer agent (default codex). Only relevant with `--dual-review`.

## When to use triple instead of pair

Use **triple** when:
- the task spans multiple unfamiliar files and needs upfront recon
- you expect the pair loop to take more than ~15 minutes and you don't want to relay
- the failure mode "engineers brief themselves and miss the real problem" is plausible
- you want the human pane free for other work while the triple runs

Use **pair** for short, well-scoped tasks where the human is willing to relay between writer and reviewer.

## Action

Parse arguments. If unambiguous, run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/tmux_pair.py triple \
  --project <project-path> \
  --base <base> \
  --feature <feature> \
  --task "<task>" \
  [--with-standards] [--greenfield] [--no-worktree] [--claude-model <slug>] [--claude-effort <level>] \
  [--dual-review] [--reviewer-2-agent <agent>]
```

If feature or task is ambiguous, ask the user.

## Output

JSON with `worktree`, `branch`, `window`, `orchestrator_pane`, `orchestrator_name`, `writer_pane`, `writer_name`, `reviewer_pane`, `reviewer_name`, `human_pane`. With `--dual-review`: additional `reviewer_2_pane`, `reviewer_2_agent`, and `reviewer_2_name`. Relay back to the user.

## Cleanup (manual)

Same as `/pair`. The orchestrator does NOT clean up; that decision stays with the human.
