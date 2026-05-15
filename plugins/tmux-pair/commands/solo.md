---
description: Spawn a single agent in a fresh git worktree, gated by a 6-phase self-driven workflow (recon, plan-check, impl, self-review, PROJECT.md/skill-persist, commit) with subagent-driven adversarial gates
argument-hint: <project-path> <base> <feature> [task...] [--no-gated] [--no-worktree] [--interactive] [--with-standards] [--greenfield] [--agent claude|codex|pi] [--claude-model SLUG] [--claude-effort LEVEL] [--pi-model SLUG] [--pi-thinking LEVEL] [--pi-provider NAME] [--no-shared-target]
---

# solo

Spawn a single agent in a fresh `git worktree`, gated by a 6-phase self-driven
workflow. The solo agent uses subagents for parallel recon (Phase 1), an
adversarial plan-check (Phase 2), parallel implementation where independent
(Phase 3), self-review (Phase 4), persists decisions to PROJECT.md + skills
(Phase 5), then commits and pings the human (Phase 6). Default gated; switch
off with `--no-gated` for plain spawn + task.

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

## When solo vs pair vs triple

| Scenario | Recommended |
|----------|-------------|
| Self-contained refactor with adversarial self-review enough | **solo (gated)** |
| Doc cleanup, rule-to-skill migration, repo-wide rename | **solo (gated)** or **solo --no-gated** |
| Plugin update with workflow consistency check | **solo (gated)** |
| Risky feature, want second pair of eyes throughout | **pair** |
| Multi-file feature with upfront recon need | **triple** |
| Security-sensitive, dual review wanted | **pair --dual-review** or **triple --dual-review** |

Solo trades a second pane (reviewer) for subagent-driven self-review. Cheaper
in panes, but less continuous oversight. Good for cleanups and trivial-but-large
work where the agent can adversarially check itself with `gate-2-plan-check`
and `gate-3-*` subagents.

## Optional flags

- `--no-gated`: bypass the 6-phase workflow briefing. Minimal spawn + task. Use for trivial tasks where subagent-driven recon/plan/review is overkill.
- `--no-worktree`: skip `git worktree add`, run on the project's current branch directly. Codex `AGENTS.md` write to project is skipped to avoid pollution.
- `--interactive`: decision-pause-points in solo briefing (rare; default autonom). Flag-parity with pair/triple.
- `--with-standards`: append the durable standards bundle (STANDARDS, RECALL_DISCIPLINE, BULLET_START_RITUAL, PAIR_PROTOCOL) to the briefing.
- `--greenfield`: enables `--with-standards` plus the greenfield pre-flight block. For first-session repos without `.claude/rules/` seed.
- `--agent <name>`: agent for the solo pane (default `claude`). Other choices per `~/.config/tmux-pair/agents.json`: `codex`, `pi`.
- `--claude-model <slug>`: claude model slug (default `claude-opus-4-7`). Only applied when `--agent claude`.
- `--claude-effort <level>`: claude effort level (default `max`).
- `--pi-provider <name>` / `--pi-model <slug>` / `--pi-thinking <level>`: pi-specific overrides. Only applied when `--agent pi`.
- `--pi-writer-provider` / `--pi-writer-model` / `--pi-writer-thinking`: pi role-specific overrides (solo internally uses the `writer` role for cargo/AGENTS.md handling).
- `--no-shared-target`: do not set `CARGO_TARGET_DIR`. Default: shared cache `~/.cache/tmux-pair/cargo-target/<repo>/`.

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
  [--no-shared-target]
```

If the feature description is missing or ambiguous, ask the user before spawning.

## Output

JSON with `worktree`, `branch`, `window`, `solo_pane`, `solo_agent`, `solo_name`, `solo_ready`, `human_pane`. Relay back to the user so they can address the solo via the `send` subcommand.

## Cleanup (manual)

```bash
cd <project-path>
git worktree remove ../<project-name>-wt-<feature>
git branch -d feature/<feature>   # after merge
```
