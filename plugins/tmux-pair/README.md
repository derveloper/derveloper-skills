# tmux-pair

Spawn coding-agent pairs or triples in tmux panes, each pinned to its own fresh `git worktree`.

## What it does

Two modes, both create a sibling worktree and a tmux window with one pane per agent:

| Mode | Panes | Layout | Use when |
|------|-------|--------|----------|
| **pair** | Writer + Reviewer | side by side | tasks small enough that the human directly relays between the two |
| **triple** | Writer + Reviewer + Orchestrator | Orchestrator on top, Writer/Reviewer below | tasks large enough that you want a dedicated agent doing recon, briefing the engineers, and filtering noise upward |

In both modes the agents talk peer-to-peer by running:

```
python3 <plugin>/scripts/tmux_pair.py send <pane-id> "<message>"
```

The helper handles the multi-line submit quirks of common agent TUIs (paste-buffer + extra Enters) so messages reliably land.

## Requirements

- `tmux` (running session — the script spawns into the current session)
- `git` 2.5+ (worktrees)
- `python3` 3.9+
- One or more agent CLIs on `PATH` (defaults assume `claude` and `codex`, configurable)

## Quick start

Inside an existing tmux session:

```
/pair <project-path> <base-ref> <feature-name> <task description>
```

or for a triple:

```
/triple <project-path> <base-ref> <feature-name> <task description>
```

Both create a worktree at `<project-parent>/<project-basename>-wt-<feature>`, branch `feature/<feature>` from `<base-ref>`, and brief the agents.

## Configuration

Spawn-time flags (both modes unless noted):

```
--writer-agent codex            # default: codex
--reviewer-agent claude         # default: claude (reviewer-1 in dual-review)
--orchestrator-agent claude     # triple only, default: claude
--dual-review                   # opt-in second reviewer (off by default)
--reviewer-2-agent codex        # second reviewer when --dual-review (default: codex)
--no-worktree                   # skip git worktree, run on the project's current branch
--claude-model claude-opus-4-7  # default model for any claude pane
--claude-effort max             # default --effort level for any claude pane
```

Add or replace agent commands in `~/.config/tmux-pair/agents.json`:

```json
{
  "claude": "claude --dangerously-skip-permissions",
  "codex": "codex --dangerously-bypass-approvals-and-sandbox",
  "myagent": "my-agent-cli --some-flag"
}
```

The defaults baked into the script are deliberately minimal: a single command per agent, nothing project-specific.

## Model selection and Compact-Watcher

The default claude model is `claude-opus-4-7` (1M context). Override per spawn:

```
/pair  ~/code/myapp main session-tokens --claude-model claude-opus-4-6
/triple ~/code/myapp main session-tokens --claude-model claude-opus-4-6
```

The compact-watcher threshold scales with the context window automatically: 1M → 700k threshold (70%), 200k → 140k threshold. Override with `monitor --threshold-k <N>` if needed. Codex always uses `gpt-5.5 xhigh` per user setup; not parameterised.

The default reasoning effort for any claude pane is `--effort max`, set directly in the boot-command (race-free vs. the `/effort` slash). Override per spawn with `--claude-effort <low|medium|high|xhigh|max>`; pass an empty string to skip the flag entirely so `claude` uses its own default or the `CLAUDE_CODE_EFFORT_LEVEL` env-var.

## Dual-Review (opt-in)

Both `/pair` and `/triple` accept `--dual-review` to spawn TWO reviewers (default: claude as reviewer-1, codex as reviewer-2) instead of one. The default is OFF; existing single-reviewer flow is unchanged.

| Mode | Layout with `--dual-review` |
|------|------------------------------|
| **pair** | Writer left (main pane), Reviewer-1 top right, Reviewer-2 bottom right (right side vertically split) |
| **triple** | Orchestrator on top full width, Writer bottom left, Reviewer-1 + Reviewer-2 stacked on the bottom right |

Per cycle: writer pings `REVIEW-READY` to BOTH reviewers in parallel, both review independently (no crosstalk), then swap findings via `REVIEWER-FINDINGS:` + `PEER-REVIEW:`, finally each sends a `REVIEW-FINAL (Reviewer):` to the orchestrator (= human in pair, = orchestrator agent in triple) for consolidation. The orchestrator merges both reports (keep all unique BLOCKERs, dedupe overlaps, surface contradictions with context) and sends ONE `REVIEW-CONSOLIDATED:` to the writer. Reviewers never speak directly to the writer.

Override the second reviewer with `--reviewer-2-agent <agent>`. When to opt in: risky refactors, security-sensitive code, blast-radius changes, anywhere you want diversity of opinions on the diff.

## Durable standards

Standards survive `/compact` and context resets because they sit in the system prompt:

- **claude panes** boot with `--append-system-prompt-file <path>` (the plugin writes a per-spawn standards file under `/tmp/tmux-pair-durable-<window>-<role>.md`).
- **codex panes** read `AGENTS.md` from the worktree root. The plugin writes that file when a real worktree is created. With `--no-worktree` the plugin skips the AGENTS.md write to avoid polluting the project repo; codex receives standards via the briefing only in that mode.
- `agents.json` overrides are respected: if the user has remapped `claude` to a wrapper, the plugin does not inject `--append-system-prompt-file` blindly.

## Scoped subagents (Haiku/Sonnet routing)

The orchestrator's gate-checks and recon are routed to plugin-namespaced subagents with explicit model + tool restrictions instead of generic `general-purpose`:

| Role | Subagent | Model | Tools | Why |
|------|----------|-------|-------|-----|
| GATE 1.5 Readiness-Check | `tmux-pair:reviewer-readiness-check` | Sonnet 4.6 | Read + Grep + Glob + Bash | Reviews `.claude/rules/*.md` against an 8-item checklist (style, tests, architecture, anti-patterns, naming, security, build, domain). Returns READY or NEEDS-RULES. NO Edit/Write so it cannot bake rules itself. |
| GATE 1.5 Rules-Bootstrap | `tmux-pair:rules-bootstrap` | Sonnet 4.6 | Read + Grep + Glob + Bash + Edit + Write | Bakes `.claude/rules/<topic>.md` from plugin language templates + repo recon + orchestrator-collected user answers. Edit+Write because writing rules files IS the job. Does not call AskUserQuestion itself; orchestrator owns the user dialog. |
| GATE 2 Plan-Check | `tmux-pair:gate-2-plan-check` | Sonnet 4.6 | Read + Grep + Glob + Bash | Plan validation needs reasoning. NO Edit/Write so the agent cannot accidentally commit code. |
| GATE 3 Verifier | `tmux-pair:gate-3-verifier` | Haiku 4.5 | Read + Grep + Glob + Bash | Goal-backward coverage check + build/test runs are deterministic; Haiku is sufficient and ~5x cheaper than Sonnet. |
| GATE 3 Code-Reviewer | `tmux-pair:gate-3-code-reviewer` | Sonnet 4.6 | Read + Grep + Glob + Bash | Style nuance, security edge cases, anti-AI-slop detection need Sonnet's nuance. |
| RECON | built-in `Explore` | Haiku 4.5 | read-only | File-snippet lookups + pointer extraction; Anthropic's stock Explore agent fits. |

Net effect: ~60-70 percent token savings vs all-Opus subagents, no quality loss on gate-tasks. The agent files live in `agents/` and ship with the plugin; per-spawn customisation goes in those files, not in the orchestrator briefing.

### Reviewer-Readiness + rules-bootstrap (GATE 1.5)

A reviewer without rules says "looks fine" — that is the failure mode GATE 1.5 prevents. The orchestrator runs the readiness-check before planning. On `NEEDS-RULES`, it loops: per gap one `AskUserQuestion`, then the bootstrap subagent generates `.claude/rules/<topic>.md` from one of seven shipped language templates (Rust, TypeScript, Python, Go, JavaScript, Java, generic skeleton) plus repo recon plus user answers. Templates ship in `templates/rules/` and are sanitized — no company-specific naming, ADRs, or domain references. Project-specific content comes from the user's own answers, baked into the user's own repo.

Optional opt-in `/gepa` pass after fresh rules; the plugin does not call `/gepa` automatically because the GEPA skill is optional user setup. If the user opts in, they trigger `/gepa` themselves out-of-band after the run.

## Token management (long-running pairs/triples)

Three helper subcommands let an orchestrator (or the human directly) refresh an agent in place:

```
python3 <plugin>/scripts/tmux_pair.py status <pane-id>
python3 <plugin>/scripts/tmux_pair.py compact <pane-id> --briefing-file <path> [--focus "<one-liner>"] [--timeout 300]
python3 <plugin>/scripts/tmux_pair.py monitor --orch-pane <id> --panes <id1> <id2> [...] [--threshold-k <N>] [--cooldown-sec <N>]
```

`status` returns JSON with the detected agent, current token count (parsed from claude's footer; codex usually shows up as `null` so callers fall back to a time/event heuristic), and the raw matched footer line.

`compact` sends `/compact [focus]` to the pane (the official claude `/compact [instructions]` form, see [code.claude.com/docs/en/commands](https://code.claude.com/docs/en/commands)), polls `capture-pane` for completion (claude prints `Conversation compacted`; for codex we accept a token-count drop ≥50% as a fallback signal), then sends the re-brief from `--briefing-file` via the regular send path. The optional `--focus` hint shapes the summary so the agent retains plan + REVIEW-state + peer-protocol. The re-brief MUST be self-contained: after `/compact` the agent has lost the conversational state and only remembers the summary. Include role, task, current progress recap, the next concrete step, the peer protocol, and the standards.

**Compact has two paths.** The orchestrator-driven path uses `tmux_pair.py compact <pane>` (sends `/compact` plus Re-Brief, useful when the watcher pings or the engineer is mid-tool-call and unaware). The engineer-driven self-compact path uses `tmux_pair.py send <eigener_pane> "/compact <focus>"` — same mechanic, engineer-initiated. Self-compact discipline: between cycles only, never mid-edit; prepare a self-re-brief file (plan-bullet, REVIEW-state, next step, peer pane ids) BEFORE sending; signal `SELF-COMPACT-PLANNED: <bullet> <focus>` to the orchestrator so the watcher does not also fire. Codex panes have no known `/compact` form; self-compact is claude-only.

`monitor` runs as a background watcher. The triple orchestrator briefing kicks one off automatically as DUTY 0; pair-mode does not auto-start it (the human is in the loop).

Trigger windows for manual `compact`:

- between REVIEW cycles when the engineer is idle, never mid-edit or mid-tool-call
- the watcher's threshold ping (model-aware: 140k for 200k-context models, 700k for 1M-context)
- before a known long phase (e.g. starting Wave N) so the agent enters it fresh

To compact both engineers in a triple in parallel, run two `compact` calls with `&` from the orchestrator's shell.

## Skills

The plugin ships three skills:

- **`tmux-pair-orchestration`** — documents the pair protocol (`REVIEW-READY` → `REVIEW` → loop), when to choose pair vs. triple, briefing templates for each role, and failure modes. Triggers when the user asks for things like "spin up a writer/reviewer pair", "run two agents on this", "set up an orchestrator + pair", or names the workflow directly.
- **`/tmux-pair:gepa`** — Genetic-Pareto prompt/text-artifact optimization (paper arXiv:2507.19457). Used opt-in after rules-bootstrap to optimize freshly generated `.claude/rules/*.md` against user-supplied test diffs. Plugin-namespaced so it does not collide with a user-local `/gepa` install. Skill files: `skills/gepa/`.
- **`/tmux-pair:dg`** — Dinesh-vs-Gilfoyle adversarial code review. Two AI personas (attacker + defender) debate a diff or file until convergence. Useful as an optional pre-GATE-3 step on security/concurrency/auth/crypto/migration bullets. Skill files: `skills/dg/`.

External companion (NOT bundled, install separately): the official `code-simplifier` plugin from `claude-plugins-official` for refactor-passes after a feature lands.

## License

Apache 2.0.
