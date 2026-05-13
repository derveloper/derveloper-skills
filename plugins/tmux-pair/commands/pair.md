---
description: Spawn a writer + reviewer agent pair in a fresh git worktree, side by side in tmux, with PROJECT.md care in the gated workflow
argument-hint: <project-path> <base> <feature> [task...] [--interactive] [--with-standards] [--greenfield] [--no-worktree] [--dual-review] [--writer-agent claude|codex|pi] [--reviewer-agent claude|codex|pi] [--claude-model SLUG] [--claude-effort LEVEL] [--pi-model SLUG] [--pi-thinking LEVEL] [--reviewer-2-agent NAME]
---

# pair

Spawn a writer + reviewer pair in a fresh `git worktree`, each in its own tmux pane, with a small JSON receipt printed back so you can address them later.

Every `send` message gets a stable sender prefix such as `[FROM: wr.<feature>]`
unless the message already starts with `[FROM:`. The helper stores sender names
in tmux pane options so agent TUI spinner titles do not leak into pings.

The gated workflow includes mandatory project-local `PROJECT.md` care: feature
and refactor bullets update package map, feature surface, design decisions, or
implementation history when those surfaces change. Reviewers sign off on the
update or on a justified skip. `~/git/example-project/PROJECT.md` is the reference
example.

Plans must include explicit parallel markers per bullet: `B3 || B4 [parallel]`
when work can run together, or `B3 -> B4 [sequenziell: <reason>]` when ordering
is required. Engineers may use subagents for parallel recon files, parallel test
suites, or independent fix branches when that keeps their main pane lean.

## Invocation

`/pair <project-path> <base> <feature> [task...] [--interactive]`

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
- `/pair ~/code/myapp main workflow-tune --interactive`
- `/pair ~/code/myapp main pi-experiment --writer-agent pi` (pi als Writer, Standard claude-opus-4-7 via pi-claude-bridge)
- `/pair ~/code/myapp main eu-only --writer-agent pi --pi-provider cortecs --pi-model qwen3-coder-next` (pi mit EU/ZDR-Stack via Cortecs)

## Optional flags

- `--with-standards`: append the durable standards bundle (STANDARDS, recall discipline, bullet-start ritual, pair protocol) to engineer briefings. Default is slim.
- `--greenfield`: enable `--with-standards` plus the greenfield pre-flight block.
- `--no-worktree`: skip `git worktree add`. Engineers commit directly on the project's current branch in the project directory. Use sparingly: any uncommitted work in the project becomes pair-visible. With `--no-worktree`, the plugin skips writing AGENTS.md (codex receives standards via the briefing only).
- `--interactive` (default off): aktiviert Decision-Pause-Points im Master-Briefing. Ohne Flag laufen alle V2-Self-Decisions autonom mit Log im COMPLETE-Ping. Mit Flag hält der Master vor jeder Self-Decision an und fragt den User via AskUserQuestion.
- `--claude-model <slug>`: claude model to switch into post-boot via `/model <slug>` (default `claude-opus-4-7`, 1M context). Switch to `claude-opus-4-6` for 200k context; the compact-watcher threshold rescales automatically. Codex pane boot follows the user's configured CLI default; engineer subagent defaults are documented in the workflow briefing.
- `--claude-effort <level>`: claude reasoning effort, set as `--effort <level>` in the claude boot-command (default `max`). Choices: `low|medium|high|xhigh|max`. Pass an empty string to skip the flag (claude default or `CLAUDE_CODE_EFFORT_LEVEL` env-var applies). The CLI flag is race-free vs. the `/effort` slash-command after a `/model` switch.
- `--writer-agent <name>` / `--reviewer-agent <name>`: Agent-Wahl pro Rolle. Erlaubt: `claude` (Default Reviewer), `codex` (Default Writer), `pi` (Custom CLI mit pi-claude-bridge als Default-Backend, alle drei Rollen unterstützt).
- `--pi-model <slug>`: pi-Model-Slug für jedes pi-Pane (default `claude-opus-4-7` via Default-Provider `claude-bridge`). Wird als `--model <slug>` im pi-Boot gesetzt. Alternative Slugs aus dem User-Catalog: `claude-sonnet-4-6`, `claude-haiku-4-5`, `gpt-5.3-codex`, `gpt-5.5`, `glm-5.1`, `deepseek-v3.2`.
- `--pi-provider <name>`: pi-Provider (default `claude-bridge`). Alternativen: `openai-codex` für Codex-Stack, `cortecs` für EU/OSS-Stack, `anthropic` für direkte API (sofern Key konfiguriert).
- `--pi-thinking <level>`: pi-Reasoning-Level (default `high`). Choices: `off|minimal|low|medium|high|xhigh`. Wird als `--thinking <level>` im pi-Boot gesetzt. Äquivalent zu `--claude-effort`, aber andere Skala.
- `--pi-<role>-model <slug>` / `--pi-<role>-thinking <level>`: pro-Rolle Override für pi-Panes. Rollen: `writer`, `reviewer`, `reviewer-2` (mit `--dual-review`). Wenn gesetzt, gewinnt die Rolle-Variante gegenüber `--pi-model` / `--pi-thinking`. Beispiel: `--writer-agent pi --pi-writer-model deepseek-v4-pro --reviewer-2-agent pi --pi-reviewer-2-model kimi-k2.6` startet Writer mit deepseek und Reviewer-2 mit kimi.
- `--dual-review`: opt-in second reviewer. Spawns reviewer-1 (claude by default) and reviewer-2 (codex by default) stacked vertically on the right side. Both review independently, swap findings, then send a final report each to the human (= orchestrator in pair-mode) for consolidation. Off by default.
- `--reviewer-2-agent <agent>`: override the second reviewer agent (default codex). Only relevant with `--dual-review`.

## Action

Parse arguments. If they are unambiguous, run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/tmux_pair.py pair \
  --project <project-path> \
  --base <base> \
  --feature <feature> \
  --task "<task>" \
  [--interactive] [--with-standards] [--greenfield] [--no-worktree] \
  [--writer-agent <claude|codex|pi>] [--reviewer-agent <claude|codex|pi>] \
  [--claude-model <slug>] [--claude-effort <level>] \
  [--pi-model <slug>] [--pi-thinking <level>] \
  [--dual-review] [--reviewer-2-agent <agent>]
```

If the feature description is missing or ambiguous, ask the user before spawning. Spawning idle agents costs more than asking one short question.

## Output

JSON with `worktree`, `branch`, `window`, `writer_pane`, `writer_name`, `reviewer_pane`, `reviewer_name`, `human_pane`. With `--dual-review`: additional `reviewer_2_pane`, `reviewer_2_agent`, and `reviewer_2_name`. Relay these back to the user so they can address either agent directly via the `send` subcommand.

## Cleanup (manual)

```bash
cd <project-path>
git worktree remove ../<project-name>-wt-<feature>
git branch -d feature/<feature>   # after merge
```
