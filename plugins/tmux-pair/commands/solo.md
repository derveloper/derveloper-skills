---
description: Spawn a single agent in a fresh git worktree, gated by a 7-phase self-driven workflow (recon, plan-check, impl, self-review, PROJECT.md/skill-persist, commit, auto-squash-merge) with subagent-driven adversarial gates
argument-hint: <project-path> <base> <feature> [task...] [--no-gated] [--no-worktree] [--interactive] [--with-standards] [--greenfield] [--agent claude|codex|pi] [--claude-model SLUG] [--claude-effort LEVEL] [--pi-model SLUG] [--pi-thinking LEVEL] [--pi-provider NAME] [--shared-target]
---

# solo

Spawn a single agent in a fresh `git worktree`, gated by a 7-phase self-driven
workflow. The solo agent uses subagents for parallel recon (Phase 1), an
adversarial plan-check (Phase 2) backed by a `codex exec` second-opinion,
implementation (Phase 3), self-review (Phase 4) backed by `codex exec` for
adversarial diff-review, persists decisions to PROJECT.md + skills (Phase 5),
commits per bullet (Phase 6), then auto-squash-merges to base + cleans up the
feature branch + worktree (Phase 7) before pinging DONE-MERGED. Default gated;
switch off with `--no-gated` for plain spawn + task (Phase 7 still applies).

Solo is the only mode. Multi-pane spawn (size 3/4/5, parallel-writers, dual-
reviewer panes) was removed: shared CARGO_TARGET_DIR contention, git-index-lock
races, cross-writer PROJECT.md races, and dual-review coordination consistently
outweighed the parallelism gain. Adversarial review-quality is preserved by
running two independent minds in parallel at each gate: claude-subagent plus
`codex exec` (different model family, fresh context, no pane setup).

The plugin script auto-detects repo-specific subagents under
`.claude/agents/<repo>-*.md` and lists them in the briefing so the solo
agent picks domain-experts over `general-purpose` for parallel work.

## Invocation

`/solo <project-path> <base> <feature> [task...]`

- `<project-path>`: path to the git repository
- `<base>`: ref to branch from (default `origin/main`)
- `<feature>`: short feature name (used in branch + window name)
- `[task...]`: free-form task description sent to the solo

## Examples

- `/solo ~/code/myapp origin/main retry-budget`
- `/solo ~/code/myapp main webhook-backoff implement exponential backoff for outbound webhooks`
- `/solo ~/code/myapp main hotfix-x --no-gated` (plain spawn + task, no gates)
- `/solo ~/code/myapp main migrate-rules-to-skills --no-worktree` (work on current branch)
- `/solo ~/code/myapp main small-doc --claude-model claude-opus-4-6` (200k context)
- `/solo ~/code/myapp main bulk-rename --agent pi` (pi as solo, default cortecs/qwen3-coder-next)

## Bullet-Sweep Sizing

| Bullet count | Recommendation |
|---|---|
| 1-3 | solo, monolithic |
| 4-10 | solo, monolithic, gated |
| 11-22 | chain 3-5-bullet solo runs back-to-back, each its own squash-merge + retro. Plan-drift correlates strongly with bullet count in one run. |

## Adversarial Gates (correctness preservation)

Solo keeps the same gates spawn-mode used, just with leaner mechanics:

- **GATE-2 Plan-Check**: `Agent(gate-2-plan-check)` AND `codex exec "adversarial plan-attack"` in parallel. Two independent minds, different model families. BLOCKER in either → fix loop. PASS in both → proceed.
- **GATE-3 Verify + Code-Review**: `Agent(gate-3-verifier)` (goal-backward against plan) AND `Agent(gate-3-code-reviewer)` (adversarial, claude) AND `codex exec "adversarial diff-review"` (adversarial, codex) in parallel. BLOCKER in any → fix loop. WARNING-only → proceed with documented follow-ups.
- **Per-Bullet REVIEW-READY**: solo writes + spawns `Agent(gate-3-code-reviewer)` per bullet for inline review when the bullet is non-trivial. Codex-CLI per bullet is opt-in (cost-aware).
- **Post-Merge Retro**: solo spawns 3 `Agent` personas (orchestrator-view, writer-view, reviewer-view) plus one `codex exec` retro, synthesizes the 4 outputs into a memory entry. Mandatory after every squash-merge.

## Optional flags

- `--no-gated`: bypass the 7-phase workflow briefing. Minimal spawn + task. Use for trivial tasks where subagent-driven recon/plan/review is overkill.
- `--no-worktree`: skip `git worktree add`, run on the project's current branch directly. Codex `AGENTS.md` write to project is skipped to avoid pollution.
- `--interactive`: decision-pause-points in solo briefing (rare; default autonom). Without this flag, V2 self-decisions proceed without asking the user.
- `--with-standards`: append the durable standards bundle (STANDARDS, RECALL_DISCIPLINE, BULLET_START_RITUAL, PAIR_PROTOCOL) to the briefing.
- `--greenfield`: enables `--with-standards` plus the greenfield pre-flight block. For first-session repos without `.claude/rules/` seed.
- `--agent <name>`: agent for the solo pane (default `claude`). Other choices per `~/.config/tmux-pair/agents.json`: `codex`, `pi`.
- `--claude-model <slug>`: claude model slug (default `claude-opus-4-7`). Only applied when `--agent claude`.
- `--claude-effort <level>`: claude effort level (default `xhigh`). Choices: `low|medium|high|xhigh|max`.
- `--codex-effort <level>`: codex reasoning effort, set as `-c model_reasoning_effort=<level>` (default `xhigh`, gpt-5.5 supports xhigh). Choices: `minimal|low|medium|high|xhigh`.
- `--pi-provider <name>` / `--pi-model <slug>` / `--pi-thinking <level>`: pi-specific overrides. Only applied when `--agent pi`.
- `--pi-writer-provider` / `--pi-writer-model` / `--pi-writer-thinking`: pi role-specific overrides (solo internally uses the `writer` role for cargo/AGENTS.md handling).
- `--shared-target`: use one shared `CARGO_TARGET_DIR` per repo across all worktrees (legacy 0.14.0..0.22.0 behavior, max cache warmth, single active agent). Default since 0.22.1: per-worktree `CARGO_TARGET_DIR` (`~/.cache/tmux-pair/cargo-target/<repo>__<wt-slug>/`) so parallel solos on the same project don't fight for the cargo file-lock.

## Action

Parse arguments. If unambiguous, run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/tmux_pair.py solo \
  --project <project-path> \
  --base <base> \
  --feature <feature> \
  --task "<task>" \
  [--no-gated] [--no-worktree] [--interactive] [--with-standards] [--greenfield] \
  [--agent <claude|codex|pi>] \
  [--claude-model <slug>] [--claude-effort <level>] \
  [--pi-model <slug>] [--pi-thinking <level>] [--pi-provider <name>] \
  [--shared-target]
```

If the feature description is missing or ambiguous, ask the user before spawning.

## Output

JSON with `worktree`, `branch`, `window`, `solo_pane`, `solo_agent`, `solo_name`, `solo_ready`, `human_pane`. Relay back to the user so they can address the solo via the `send` subcommand.

## Cleanup (auto, Phase 7)

Phase 7 of the gated workflow does the squash-merge + branch-delete + worktree-remove automatically. The human only kills the tmux window after the Post-Merge Retro:

```bash
tmux kill-window -t <window-name>
```

If solo encountered a merge-conflict in Phase 7, it sends a BLOCKER-ping instead of DONE-MERGED. Then the human resolves manually and confirms before solo retries.

See `skills/tmux-pair-orchestration/references/gated-workflow.md` for the full retro procedure.
