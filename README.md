# derveloper-skills

Personal [Claude Code](https://claude.com/claude-code) plugin marketplace. Workflow tooling for multi-agent coding sessions in tmux: solo agents with gated self-review, or coordinated spawn-teams of orchestrator + writers + reviewers (size 3..5), sharing fresh `git` worktrees.

## Install

```text
/plugin marketplace add derveloper/derveloper-skills
/plugin install tmux-pair@derveloper-skills
```

## Plugins

### tmux-pair (v0.16.0)

Spawn one to five coding agents on a single task. Each agent lives in its own tmux pane, all panes share a fresh `git worktree`, and the agents talk peer-to-peer through a small Python helper that handles the multi-line submit quirks of common agent TUIs.

#### Slash commands

| Command | What it spawns | Layout | When to use |
|---------|----------------|--------|-------------|
| `/run <project> <base> <feature> [task]` | auto-recommends solo vs spawn after a short recon | depends on recommendation | default entry-point; let the skill pick the right mode |
| `/solo <project> <base> <feature> [task]` | one agent, gated 6-phase self-driven workflow | single pane | self-contained refactor/cleanup; adversarial gate-subagents are enough |
| `/spawn <project> <base> <feature> [task]` | coordinated team: orchestrator + writers + reviewers (size 3..5 via `--size`, dual-review at size 4 default, `--parallel-writers` for disjoint-bullet teams) | orchestrator on top, engineers below | bigger task, recon-heavy, want a dedicated orchestrator to filter + brief + verify |

`/solo` runs Recon -> Plan + GATE-2 -> Impl -> GATE-3 self-review -> PROJECT.md + skill persist -> Commit, with `tmux-pair:gate-2-plan-check`, `tmux-pair:gate-3-verifier`, and `tmux-pair:gate-3-code-reviewer` as scoped subagents. `/spawn` enforces the 5-gate workflow (Clarify, Reviewer-Readiness with rules-bootstrap loop, Plan-Check, Implementation Loop, Final-Verify).

#### Features

- **Worktree isolation** per spawn. Branch `feature/<name>` from any base ref. Agents never touch the human's working dir.
- **Three agent backends**: `claude` (default reviewer + orchestrator), `codex` (default writer), `pi` (the user's custom CLI; cortecs/qwen3-coder-next default, or via `pi-claude-bridge` for Anthropic-Subscription).
- **Durable standards** survive `/compact`: claude boots with `--append-system-prompt-file`, codex reads worktree-local `AGENTS.md`, pi reads both.
- **Gate subagents** with explicit model + tool scoping (Sonnet for plan-check/code-review/readiness/bootstrap, Haiku for verifier and recon).
- **Repo-specific subagent auto-detection**: any `.claude/agents/<repo>-*.md` in the target repo is listed in the briefing so the agents prefer domain experts over `general-purpose`.
- **TESTS-PROOF trust chain (V7)**: writer-DONE pings + bullet commits carry `TESTS-PROOF` markers; `gate-3-verifier` trusts engineer-certified suites and skips re-runs when `HEAD == COMMIT_SHA`. No workspace-wide "to be safe" doubles.
- **Parallel-by-default plans**: every bullet carries either `B3 || B4 [parallel]` or `B3 -> B4 [sequenziell: <reason>]`. GATE 2 blocks missing markers.
- **PROJECT.md care**: feature and refactor bullets that change package map, feature surface, design decisions, or implementation history update `PROJECT.md`. Verifier checks the diff.
- **Smart workflow V1-V10**: inline-fix-spec, orchestrator-direct-decisions with `PROJECT.md` audit trail, adaptive GATE-strictness per `task_kind`, WARNING/NOTE auto-resolve, unattended-by-default with `--interactive` opt-in, readiness-cache (24h TTL), TESTS-PROOF marker, shared `CARGO_TARGET_DIR`, recon-cache with delta-mode (1h TTL), inline-gates for trivial bug-fix plans.
- **Dynamic team sizing** (`/spawn --size 3..5`, `--parallel-writers`): preset for 1W/1R/1O (size 3), 1W/2R/1O dual-review (size 4 default), 2W/1R/1O parallel-writers (size 4 + flag), or 2W/2R/1O (size 5). Reviewers cross-check + consolidate; writers split disjoint plan-bullets.
- **Compact-watcher**: model-aware token threshold (1M -> 700k, 200k -> 140k), `/compact <focus>` over the pane, automatic re-brief.
- **Bundled companion skills**: `/tmux-pair:gepa` (Genetic-Pareto prompt optimization, arXiv:2507.19457) and `/tmux-pair:dg` (Dinesh-vs-Gilfoyle adversarial code review).
- **Shipped rules templates** for 7 stacks: Rust, TypeScript, Python, Go, JavaScript, Java, generic skeleton. Used by `tmux-pair:rules-bootstrap` when a fresh repo has no `.claude/rules/`.

#### Documentation

- [Plugin README](plugins/tmux-pair/README.md) for the full feature set, flag reference, and configuration.
- [PROJECT.md](plugins/tmux-pair/PROJECT.md) for architecture, design decisions, and version history.
- Skills: `tmux-pair-orchestration` (workflow + briefing templates), `tmux-pair:gepa`, `tmux-pair:dg`.

## Contributing

Three version fields must stay aligned per plugin:

- `plugins/<name>/plugin.json`: the plugin's own manifest
- `.claude-plugin/marketplace.json` `plugins[].version`: what `/plugin update` and claude-code cache-keying read
- the orchestration skill's `version:` frontmatter: what end-users see in the skill listing

A pre-commit hook (`hooks/pre-commit` -> `scripts/check-plugin-versions.py`) enforces the first two. Activate after cloning:

```bash
git config core.hooksPath hooks
```

The hook blocks commits on version mismatch, missing manifest, name/dir disagreement, or orphan entries. `--no-verify` only with a reason in the commit body.

## License

[Apache 2.0](LICENSE).
