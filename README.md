# derveloper-skills

Personal [Claude Code](https://claude.com/claude-code) plugin marketplace. Workflow tooling for single-agent coding sessions in tmux: one solo agent in a fresh `git` worktree, gated self-review, subagent fan-out for bounded parallel work, and `codex exec` as the independent second-opinion path.

## Install

```text
/plugin marketplace add derveloper/derveloper-skills
/plugin install tmux-pair@derveloper-skills
```

## Plugins

### tmux-pair (v0.22.8)

Run one coding agent on a task. The agent lives in its own tmux pane, works in a fresh `git worktree`, follows the 7-phase Solo workflow, and uses scoped subagents plus `codex exec` for adversarial gates. Legacy `tmux_pair.py spawn` still exists for manual recovery and old experiments, but it is not the documented happy path.

#### Slash commands

| Command | What it spawns | Layout | When to use |
|---------|----------------|--------|-------------|
| `/run <project> <base> <feature> [task]` | auto-entry: short recon, agent pick, dispatch to `/solo` | single pane | default entry-point |
| `/solo <project> <base> <feature> [task]` | one agent, gated 7-phase self-driven workflow | single pane | direct Solo start with explicit flags |

`/solo` runs Recon -> Clarify -> Reviewer-Readiness -> Plan-Check -> Implementation -> Final-Verify -> Persist -> Commit -> Auto-Squash-Merge, with `tmux-pair:reviewer-readiness-check`, `tmux-pair:rules-bootstrap`, `tmux-pair:gate-2-plan-check`, `tmux-pair:gate-3-verifier`, and `tmux-pair:gate-3-code-reviewer` as scoped subagents. Phase 7 squashes the feature branch onto the base branch, removes the worktree, deletes the per-worktree Cargo target, deletes the feature branch, then pings `DONE-MERGED`.

#### Features

- **Worktree isolation** per Solo run. Branch `feature/<name>` from any base ref. Agents never touch the human's working dir unless `--no-worktree` is explicit.
- **Three agent backends**: `codex` default, `claude` for Claude-shaped profiles, `pi` opt-in for cheap bulk work.
- **Durable standards** survive `/compact`: claude boots with `--append-system-prompt-file`, codex reads worktree-local `AGENTS.md`, pi reads both.
- **Gate subagents** with explicit model + tool scoping (Sonnet for plan-check/code-review/readiness/bootstrap, Haiku for verifier and recon).
- **Repo-specific subagent auto-detection**: any `.claude/agents/<repo>-*.md` in the target repo is listed in the briefing so the agents prefer domain experts over `general-purpose`.
- **TESTS-PROOF trust chain (V7)**: bullet commits carry `TESTS-PROOF` markers; `gate-3-verifier` trusts certified suites and skips re-runs when `HEAD == COMMIT_SHA`. No workspace-wide "to be safe" doubles.
- **Parallel-by-default plans**: every bullet carries either `B3 || B4 [parallel]` or `B3 -> B4 [sequenziell: <reason>]`. GATE 2 blocks missing markers.
- **PROJECT.md care**: feature and refactor bullets that change package map, feature surface, design decisions, or implementation history update `PROJECT.md`. Verifier checks the diff.
- **Smart workflow V1-V10**: inline-fix-spec, solo self-decisions with `PROJECT.md` audit trail, adaptive GATE-strictness per `task_kind`, WARNING/NOTE auto-resolve, unattended-by-default with `--interactive` opt-in, helper-only readiness/recon caches, TESTS-PROOF marker, per-worktree `CARGO_TARGET_DIR`, inline-gates for trivial bug-fix plans.
- **Compact-watcher**: model-aware token threshold (1M -> 700k, 200k -> 140k), `/compact <focus>` over the pane, automatic re-brief.
- **Bundled companion skills**: `/tmux-pair:gepa` (Genetic-Pareto prompt optimization, arXiv:2507.19457) and `/tmux-pair:dg` (Dinesh-vs-Gilfoyle adversarial code review).
- **Shipped guidance templates** for 7 stacks: Rust, TypeScript, Python, Go, JavaScript, Java, generic skeleton. Used by `tmux-pair:rules-bootstrap` to create `.claude/skills/<repo>-<topic>/SKILL.md` by default; `.claude/rules/<topic>.md` is reserved for cross-cutting always-on guidance.

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
