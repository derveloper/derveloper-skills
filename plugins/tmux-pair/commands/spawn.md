---
description: Spawn a coordinated agent team (orchestrator + writers + reviewers, size 3..5) in a fresh git worktree, with PROJECT.md care in the gated workflow
argument-hint: <project-path> <base> <feature> [task...] [--size 3|4|5] [--parallel-writers] [--interactive] [--with-standards] [--greenfield] [--no-worktree] [--writer-agent NAME] [--writer-2-agent NAME] [--reviewer-agent NAME] [--reviewer-2-agent NAME] [--orchestrator-agent NAME] [--claude-model SLUG] [--claude-effort LEVEL] [--pi-model SLUG] [--pi-thinking LEVEL]
---

# spawn

Spawn a coordinated team of agents in a fresh `git worktree`. Team size is set via `--size` (3..5, default 3). The orchestrator runs in a pane on top across the full width; writers + reviewers sit beneath. The orchestrator does recon, writes the engineer briefings, watches the implementation loop, and reports up to the human pane on major events only (`COMPLETE` after GATE-3-PASS, `ABORT` if irreparable).

The human dispatches the spawn and can step away. They are not the recon agent and not the relay between writer and reviewer.

## Team sizes

| `--size` | `--parallel-writers` | Writers | Reviewers | Orchestrator | Use when |
|----------|----------------------|---------|-----------|--------------|----------|
| 3 (default) | n/a | 1 | 1 | 1 | standard task, one writer + one reviewer is enough |
| 4 | off (default) | 1 | 2 | 1 | risky / security-sensitive: two reviewers cross-check, orchestrator consolidates |
| 4 | on | 2 | 1 | 1 | parallel-friendly bullets, two writers on disjoint plan-bullets |
| 5 | n/a | 2 | 2 | 1 | big feature with both dual-review and parallel-writers active |

`--parallel-writers` requires `--size 4` or `--size 5`. Passing it with `--size 3` errors out.

Every `send` message gets a stable sender prefix such as `[FROM: or.<feature>]`, `[FROM: wr.<feature>]` (or `wr1`/`wr2` when parallel-writers), or `[FROM: rv.<feature>]` (or `rv1`/`rv2` when dual-review), unless the message already starts with `[FROM:`. The helper stores sender names in tmux pane options so agent TUI spinner titles do not leak into pings.

The orchestrator also checks whether the repository has a project-local `PROJECT.md`. Feature and refactor bullets must keep it current when package map, feature surface, design decisions, or implementation history change. Reviewers sign off on the update or on a justified skip, and `~/git/example-project/PROJECT.md` is the reference example.

Plans must include explicit parallel markers per bullet: `B3 || B4 [parallel]` when work can run together, or `B3 -> B4 [sequenziell: <reason>]` when ordering is required. The orchestrator checks whether independent bullets are needlessly serial and may propose additional worktrees or spawn invocations for independent work.

## Invocation

`/spawn <project-path> <base> <feature> [task...] [--size 3|4|5] [--parallel-writers] [--interactive]`

- `<project-path>`: path to the git repository
- `<base>`: ref to branch from (default `origin/main`)
- `<feature>`: short feature name
- `[task...]`: free-form task description sent ONLY to the orchestrator. Engineers stay idle until the orchestrator briefs them after recon.

## Examples

- `/spawn ~/code/myapp origin/main session-tokens` (default size 3 = 1W/1R/1O)
- `/spawn ~/code/myapp main risky-refactor --size 4` (dual-review: 1W/2R/1O)
- `/spawn ~/code/myapp main parallel-feature --size 4 --parallel-writers` (2W/1R/1O on disjoint bullets)
- `/spawn ~/code/myapp main big-overhaul --size 5` (2W/2R/1O, both presets active)
- `/spawn ~/code/myapp main rate-limit-redesign rebuild the rate limiter so it survives the redis failover scenario from incident 2026-01`
- `/spawn ~/code/myapp main smallfeature --claude-model claude-opus-4-6` (200k context, cheaper for short tasks)
- `/spawn ~/code/myapp main full-review --with-standards`
- `/spawn ~/code/myapp main first-session --greenfield` (adds standards and greenfield pre-flight)
- `/spawn ~/code/myapp main resume-existing --no-worktree --project ~/code/myapp-wt-existing` (reuse an existing worktree directly)
- `/spawn ~/code/myapp main workflow-tune --interactive`
- `/spawn ~/code/myapp main pi-driven --writer-agent pi --reviewer-agent pi --orchestrator-agent pi` (alle drei Rollen via pi, cortecs/qwen3-coder-next als Default-Model)
- `/spawn ~/code/myapp main pi-bridge --writer-agent pi --pi-provider claude-bridge --pi-model claude-opus-4-7` (pi-Writer via pi-claude-bridge auf Anthropic-Subscription, claude als Reviewer/Orchestrator)

## Optional flags

- `--size <3|4|5>` (default 3): team size. 3 = 1W/1R/1O. 4 = 1W/2R/1O (dual-review preset). 4 + `--parallel-writers` = 2W/1R/1O. 5 = 2W/2R/1O.
- `--parallel-writers`: use two writers on disjoint plan-bullets instead of a second reviewer. Requires `--size 4` or `--size 5`; implicit for size 5.
- `--with-standards`: append the durable standards bundle (STANDARDS, recall discipline, bullet-start ritual, pair protocol) to engineer briefings in the Orchestrator handoff. Default is slim.
- `--greenfield`: enable `--with-standards` plus the greenfield pre-flight block.
- `--no-worktree`: skip `git worktree add`. Use when resuming on an existing worktree (point `--project` at the worktree path) or running directly on the project branch. With `--no-worktree`, the plugin skips writing AGENTS.md to the project repo; codex picks up standards via the briefing only.
- `--no-cache` (default off): disables the V6 readiness-cache (`~/.cache/tmux-pair/readiness/`) and V9 recon-cache (`/tmp/tmux-pair-recon-*`) for this spawn. Cache files on disk are left untouched. Use when rules or recon assumptions changed in ways the (rules-hash, commit-sha) cache key doesn't capture.
- `--no-shared-target` (default off): disables V8 `CARGO_TARGET_DIR` sharing across worktrees. Each agent builds into the worktree-local `target/`. Default behavior is to share `~/.cache/tmux-pair/cargo-target/<repo-slug>/` for Cargo projects; non-Rust repos always skip the env regardless of the flag.
- `--interactive` (default off): aktiviert Decision-Pause-Points im Orch-Briefing. Ohne Flag laufen alle V2-Self-Decisions autonom mit Log im COMPLETE-Ping. Mit Flag hält Orch vor jeder Self-Decision an und fragt den User via AskUserQuestion.
- `--claude-model <slug>`: claude model to switch into post-boot for any claude pane (default `claude-opus-4-7`, 1M context). Switch to `claude-opus-4-6` for 200k context; the compact-watcher threshold rescales automatically (700k to 140k). Codex pane boot follows the user's configured CLI default; engineer subagent defaults are documented in the workflow briefing.
- `--claude-effort <level>`: claude reasoning effort, set as `--effort <level>` in the claude boot-command (default `max`). Choices: `low|medium|high|xhigh|max`. Pass an empty string to skip the flag (claude default or `CLAUDE_CODE_EFFORT_LEVEL` env-var applies).
- `--writer-agent <name>` / `--writer-2-agent <name>` / `--reviewer-agent <name>` / `--reviewer-2-agent <name>` / `--orchestrator-agent <name>`: Agent-Wahl pro Rolle. Erlaubt: `claude` (Default Reviewer + Orchestrator), `codex` (Default Writer + Reviewer-2), `pi` (Custom CLI mit Cortecs als Default-Backend für günstige Bulk-Work).
- `--pi-model <slug>`: pi-Model-Slug für jedes pi-Pane (default `qwen3-coder-next` via Default-Provider `cortecs`). Wird als `--model <slug>` im pi-Boot gesetzt. Alternative Slugs: `glm-4.6` (mid), `glm-4.7` (planner), `glm-5.1` (top), `kimi-k2.6` (code), `deepseek-v4-pro` (reasoning), oder via `--pi-provider claude-bridge` mit `claude-opus-4-7` / `claude-sonnet-4-6` / `claude-haiku-4-5`. Beachte: pi kann das Model NICHT mid-session wechseln (kein `/model` Slash-Command), nur Restart der Pane.
- `--pi-provider <name>`: pi-Provider (default `cortecs`). Alternativen: `claude-bridge`, `openai-codex`, `anthropic`.
- `--pi-thinking <level>`: pi-Reasoning-Level (default `high`). Choices: `off|minimal|low|medium|high|xhigh`.
- `--pi-<role>-model <slug>` / `--pi-<role>-thinking <level>` / `--pi-<role>-provider <name>`: pro-Rolle Override für pi-Panes. Rollen: `writer`, `writer-2`, `reviewer`, `reviewer-2`, `orchestrator`. Beispiel: `--writer-agent pi --reviewer-agent pi --pi-reviewer-provider claude-bridge --pi-reviewer-model claude-opus-4-7` mischt Cortecs-Writer (cheap) mit Anthropic-Reviewer (top-gate).

## When to use spawn instead of solo

Use **spawn** when:
- the task spans multiple unfamiliar files and needs upfront recon
- you expect the implementation loop to take more than ~15 minutes and you don't want to relay
- the failure mode "engineer briefs itself and misses the real problem" is plausible
- you want the human pane free for other work while the team runs
- two reviewers consolidating reduce false-APPROVE risk (size 4 default)
- the plan has parallel-friendly bullets that two writers can split (size 4 + `--parallel-writers`, or size 5)

Use **solo** for self-contained refactors where adversarial gate-subagents are enough oversight.

Not sure which? Use `/run` instead: it does a short recon and recommends solo or spawn (with a recommended `--size`).

## Action

Parse arguments. If unambiguous, run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/tmux_pair.py spawn \
  --project <project-path> \
  --base <base> \
  --feature <feature> \
  --task "<task>" \
  [--size <3|4|5>] [--parallel-writers] \
  [--interactive] [--with-standards] [--greenfield] [--no-worktree] \
  [--writer-agent <claude|codex|pi>] [--writer-2-agent <name>] \
  [--reviewer-agent <claude|codex|pi>] [--reviewer-2-agent <name>] \
  [--orchestrator-agent <claude|codex|pi>] \
  [--claude-model <slug>] [--claude-effort <level>] \
  [--pi-model <slug>] [--pi-thinking <level>]
```

If feature or task is ambiguous, ask the user.

## Output

JSON with `mode: "spawn"`, `size`, `writers`, `reviewers`, `parallel_writers`, `dual_review`, `worktree`, `branch`, `window`, `orchestrator_pane`, `orchestrator_name`, `writer_pane`, `writer_name`, `reviewer_pane`, `reviewer_name`, `human_pane`. With dual-review active (reviewers >= 2): additional `reviewer_2_pane`, `reviewer_2_agent`, `reviewer_2_name`. With parallel-writers active (writers >= 2): additional `writer_2_pane`, `writer_2_agent`, `writer_2_name`. Relay back to the user.

## Cleanup (manual)

```bash
cd <project-path>
git worktree remove ../<project-name>-wt-<feature>
git branch -d feature/<feature>   # after merge
```

The orchestrator does NOT clean up; that decision stays with the human.
