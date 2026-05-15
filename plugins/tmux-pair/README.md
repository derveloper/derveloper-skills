# tmux-pair

Spawn coding-agent solos or coordinated spawn-teams (orchestrator + writers + reviewers, size 3..5) in tmux panes, each pinned to its own fresh `git worktree`.

## What it does

Two modes, both create a sibling worktree and a tmux window with one pane per agent:

| Mode | Panes | Layout | Use when |
|------|-------|--------|----------|
| **solo** | one agent (gated 6-phase, subagent-driven self-review) | single pane | self-contained refactor/cleanup where adversarial gate-subagents are enough; human is hands-off after spawn |
| **spawn** | orchestrator + 1-2 writers + 1-2 reviewers, sized via `--size 3..5` (default 3 = 1W/1R/1O; 4 = 1W/2R/1O dual-review; 4 + `--parallel-writers` = 2W/1R/1O; 5 = 2W/2R/1O) | orchestrator on top, engineers below; dual-review and parallel-writer panes stack vertically under their primary | bigger task, recon-heavy, want a dedicated agent to brief engineers, filter noise, and consolidate reviews |

A third top-level entry-point, `/run`, performs a short repo + task recon and recommends solo or spawn (with a recommended `--size`) based on task complexity. Explicit mode-flags from the user override the recommendation.

In spawn mode, the agents talk peer-to-peer by running:

```
python3 <plugin>/scripts/tmux_pair.py send <pane-id> "<message>"
```

The helper handles the multi-line submit quirks of common agent TUIs (paste-buffer + extra Enters) so messages reliably land. It also prefixes normal send messages with `[FROM: <pane-name>] ` unless the message already starts with `[FROM:`. Spawned panes store the stable sender name in `@tmux-pair-sender`, so prefixes stay useful even when Claude or Codex overwrites the visible pane title with a spinner.

## Requirements

- `tmux` (running session: the script spawns into the current session)
- `git` 2.5+ (worktrees)
- `python3` 3.9+
- One or more agent CLIs on `PATH` (defaults assume `claude` and `codex`, configurable)

## Quick start

Inside an existing tmux session:

```
/run    <project-path> <base-ref> <feature-name> <task description>
/solo   <project-path> <base-ref> <feature-name> <task description>
/spawn  <project-path> <base-ref> <feature-name> <task description>
```

`/run` is the default: it inspects the repo and task and recommends solo or spawn. `/solo` and `/spawn` invoke the modes directly. All three create a worktree at `<project-parent>/<project-basename>-wt-<feature>` and branch `feature/<feature>` from `<base-ref>`.

Solo runs a single agent through a 6-phase gated workflow (recon, plan+GATE-2, impl, GATE-3 self-review, PROJECT.md + skill persist, commit). Subagents drive the parallel recon, the adversarial plan-check (`tmux-pair:gate-2-plan-check`), and the final review (`tmux-pair:gate-3-verifier` + `tmux-pair:gate-3-code-reviewer`). Switch off the gates with `--no-gated`.

Spawn runs the 5-gate workflow (Clarify, Reviewer-Readiness with rules-bootstrap loop, Plan-Check, Implementation Loop, Final-Verify). Team size is set with `--size` (default 3) and the optional `--parallel-writers` flag for disjoint-bullet writer splits.

## Configuration

Spawn-time flags:

```
# solo only
--agent claude                  # default: claude (choices: claude|codex|pi)
--no-gated                      # bypass the 6-phase gated workflow briefing

# spawn only
--size 3                        # team size: 3..5 (default 3 = 1W/1R/1O)
--parallel-writers              # 2 writers on disjoint bullets (requires --size 4 or 5)
--writer-agent codex            # default: codex
--writer-2-agent codex          # second writer when parallel-writers active
--reviewer-agent claude         # default: claude (reviewer-1 in dual-review)
--reviewer-2-agent codex        # second reviewer when dual-review active (size 4 default or size 5)
--orchestrator-agent claude     # default: claude

# both modes
--with-standards                # include durable standards bundle in briefings
--greenfield                    # include standards plus greenfield pre-flight
--no-worktree                   # skip git worktree, run on the project's current branch
--interactive                   # opt-in Decision-Pause-Points for V2 decisions
--claude-model claude-opus-4-7  # default model for any claude pane
--claude-effort max             # default --effort level for any claude pane
--pi-provider cortecs           # pi default provider (claude-bridge for Subscription)
--pi-model qwen3-coder-next     # pi default model (claude-opus-4-7 via bridge)
--pi-thinking high              # pi default reasoning level
--no-cache                      # disable V6 readiness-cache + V9 recon-cache (spawn only)
--no-shared-target              # disable V8 CARGO_TARGET_DIR sharing
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
Briefings are task-focused and compact by default.
In spawn, this lean default is useful for resume flows. For full orchestrator boot-time procedure coverage on first runs, use `--greenfield`.

## Model selection and Compact-Watcher

The default claude model is `claude-opus-4-7` (1M context). Override per spawn:

```
/solo  ~/code/myapp main rule-migration --no-gated
/solo  ~/code/myapp main repo-rename --claude-model claude-opus-4-6
/spawn ~/code/myapp main session-tokens --claude-model claude-opus-4-6
/spawn ~/code/myapp main session-tokens --size 4
/spawn ~/code/myapp main feature-split --size 5
/spawn ~/code/myapp main greenfield-session --greenfield
```

The compact-watcher threshold scales with the context window automatically: 1M to 700k threshold (70%), 200k to 140k threshold. Override with `monitor --threshold-k <N>` if needed. Codex pane boot follows the user's configured CLI default; Codex engineer subagents use the Spark-first policy below.

The default reasoning effort for any claude pane is `--effort max`, set directly in the boot-command (race-free vs. the `/effort` slash). Override per spawn with `--claude-effort <low|medium|high|xhigh|max>`; pass an empty string to skip the flag entirely so `claude` uses its own default or the `CLAUDE_CODE_EFFORT_LEVEL` env-var.

## Dynamic team sizing

`/spawn --size N` picks one of four presets. The flag maps directly to the writer + reviewer count; dual-review and parallel-writer behaviour follow from the resulting pane count.

| `--size` | `--parallel-writers` | Writers | Reviewers | Orchestrator | Layout |
|----------|----------------------|---------|-----------|--------------|--------|
| 3 (default) | n/a | 1 | 1 | 1 | orchestrator top, writer bottom-left, reviewer bottom-right |
| 4 | off (default) | 1 | 2 | 1 | dual-review preset: reviewer-2 stacked under reviewer-1 |
| 4 | on | 2 | 1 | 1 | parallel-writers preset: writer-2 stacked under writer-1 |
| 5 | n/a | 2 | 2 | 1 | both presets active: writer-2 + reviewer-2 stacked under their primaries |

Per dual-review cycle: writer pings `REVIEW-READY` to BOTH reviewers in parallel, both review independently (no crosstalk), then swap findings via `REVIEWER-FINDINGS:` + `PEER-REVIEW:`, finally each sends a `REVIEW-FINAL (Reviewer):` to the orchestrator for consolidation. The orchestrator merges both reports (keep all unique BLOCKERs, dedupe overlaps, surface contradictions with context) and sends ONE `REVIEW-CONSOLIDATED:` to the writer. Reviewers never speak directly to the writer.

Per parallel-writers cycle: orchestrator partitions plan-bullets into disjoint sub-sets (`B3 -> wr1`, `B4 -> wr2`), briefs both writers separately, each writer pings REVIEW-READY independently to the reviewer. No direct sync between writers; collisions on shared files go back to the orchestrator via `CLARIFY-NEEDED` for re-partitioning.

`--parallel-writers` requires `--size 4` or `--size 5`. Passing it with `--size 3` errors out at argparse time.

## Durable standards

Standards survive `/compact` and context resets because they sit in the system prompt. Engineer briefings are slim by default.

- **claude panes** boot with `--append-system-prompt-file <path>` (the plugin writes a per-spawn standards file under `/tmp/tmux-pair-durable-<window>-<role>.md`).
- **codex panes** read `AGENTS.md` from the worktree root. The plugin writes that file when a real worktree is created.
- For task-specific runs, briefings are minimal by default and omit durable standards block repetition.
- Add `--with-standards` to include the standards bundle in briefings, or `--greenfield` for standards plus pre-flight.
- For `--no-worktree` with codex, the plugin automatically sets standards-on when needed so codex still receives the rule set via briefing.
- `agents.json` overrides are respected: if the user has remapped `claude` to a wrapper, the plugin does not inject `--append-system-prompt-file` blindly.

## Scoped subagents (Haiku/Sonnet routing)

The orchestrator's gate-checks and recon are routed to plugin-namespaced subagents with explicit model + tool restrictions instead of generic `general-purpose`:

| Role | Subagent | Model | Tools | Why |
|------|----------|-------|-------|-----|
| GATE 1.5 Readiness-Check | `tmux-pair:reviewer-readiness-check` | Sonnet 4.6 | Read + Grep + Glob + Bash | Reviews `.claude/rules/*.md` against an 8-item checklist (style, tests, architecture, anti-patterns, naming, security, build, domain). Returns READY or NEEDS-RULES. NO Edit/Write so it cannot bake rules itself. |
| GATE 1.5 Rules-Bootstrap | `tmux-pair:rules-bootstrap` | Sonnet 4.6 | Read + Grep + Glob + Bash + Edit + Write | Bakes `.claude/rules/<topic>.md` from plugin language templates + repo recon + orchestrator-collected user answers. Edit+Write because writing rules files IS the job. Does not call AskUserQuestion itself; orchestrator owns the user dialog. |
| GATE 2 Plan-Check | `tmux-pair:gate-2-plan-check` | Sonnet 4.6 | Read + Grep + Glob + Bash | Plan validation needs reasoning. Checks every bullet for explicit `B3 || B4 [parallel]` or `B3 -> B4 [sequenziell: reason]` markers. NO Edit/Write so the agent cannot accidentally commit code. |
| GATE 3 Verifier | `tmux-pair:gate-3-verifier` | Haiku 4.5 | Read + Grep + Glob + Bash | Goal-backward coverage check + build/test runs are deterministic; Haiku is sufficient and ~5x cheaper than Sonnet. |
| GATE 3 Code-Reviewer | `tmux-pair:gate-3-code-reviewer` | Sonnet 4.6 | Read + Grep + Glob + Bash | Style nuance, security edge cases, anti-AI-slop detection need Sonnet's nuance. |
| RECON | built-in `Explore` | Haiku 4.5 | read-only | File-snippet lookups + pointer extraction; Anthropic's stock Explore agent fits. |

Net effect: ~60-70 percent token savings vs all-Opus subagents, no quality loss on gate-tasks. The agent files live in `agents/` and ship with the plugin; per-spawn customisation goes in those files, not in the orchestrator briefing.

## Smart workflow (V1-V10)

- V1 Reviewer-Trivial-Fix-Inline: reviewers can send isolated <20 LOC cosmetic,
  typo, or missing-doc patches as `INLINE-FIX`; writers apply and ACK with
  `applied B<N> inline-fix (X lines)`.
- V2 Orchestrator-Direct-Decision-Threshold: small repo-pattern decisions run
  autonomously by default and every self-decision is logged in `COMPLETE` AND
  persisted as a row in the consumer repo's `PROJECT.md` Implementation
  History. A spawn run is not complete without that `PROJECT.md` entry.
- V3 Adaptive GATE-Strictness: `task_kind` is `bug-fix`, `feature`, or
  `refactor`; GATE 2 and GATE 3 verifier adapt deterministic checklist items
  per class.
- V4 Engineer-Auto-Resolve WARNINGs: BLOCKER enters the fix-loop, WARNING goes
  to follow-up memory plus PROJECT.md when relevant, NOTE is log-only.
- V5 Unattended-Default: `/solo`, `/spawn`, `/run` run unattended by default;
  `--interactive` turns V2 self-decisions into `AskUserQuestion` pause points.
- V6 Readiness-Cache (24h TTL): `reviewer-readiness-check` results cached at
  `~/.cache/tmux-pair/readiness/<repo>-<rules-hash>-<commit>.json`. Cache-Hit +
  PASS skips the subagent spawn. `NEEDS-RULES` is never cached. Bust via
  `--no-cache`.
- V7 Test-Trust-Chain (TESTS-PROOF marker): writer DONE-Pings and bullet
  commit messages carry a `TESTS-PROOF:` block (test/lint/fmt commands + PASS
  counts + `COMMIT_SHA`). `gate-3-verifier` parses via
  `tmux_pair.py parse-tests-proof` and trusts when `HEAD == COMMIT_SHA`. Stale
  markers WARNING + narrow re-run; missing on 0.14+ runs BLOCKER. No
  workspace-wide re-runs when the engineers already certified the suite.
- V8 Cargo-Target-Sharing: shared `CARGO_TARGET_DIR=~/.cache/tmux-pair/cargo-target/<repo>/`
  prefix on every boot command for Cargo repos. Cross-worktree cache; cargo's
  lock-file handles concurrency. Non-Rust repos skip automatically. Bust via
  `--no-shared-target`.
- V9 Recon-Cache with Delta-Mode (1h TTL): orchestrator recon JSON cached at
  `/tmp/tmux-pair-recon-<repo>-<commit>.json`; follow-up spawns read the cache
  + delta-recon for files with `mtime > cache-time`. Bust via `--no-cache`.
- V10 Inline-Gates for trivial plans: when `task_kind=bug-fix` AND
  `bullets <= 3` AND `predicted files-touched <= 5`, the orchestrator runs
  GATE 2 inline in its own pane; `gate-3-verifier` may also inline when
  TESTS-PROOF is valid. `gate-3-code-reviewer` always stays as subagent.
  Helper: `tmux_pair.py inline-gate-decide --plan-file <path> --task-kind <kind>`.

### Engineer subagents and parallel plans

Writer, reviewer, and orchestrator briefings tell engineers to keep their main panes lean by using subagents for bounded side work:

- parallel recon files, where each subagent reads an independent module and returns short `file:line` pointers
- parallel test suites, where unit, integration, lint, or browser-smoke checks can run without shared mutable state
- parallel fix branches, where independent plan bullets with disjoint files can use extra worktrees or additional spawn invocations

For Codex subagent spawns using codex apps or the Helmholtz/Maxwell pattern, the documented default is `gpt-5.3-codex-spark` with `reasoning_effort=high` while the user limit allows it. On rate-limit hit, fall back to the current default model, `gpt-5.5` with `high`. Claude stays on the Task tool and uses the model from the subagent definition.

Plans must make parallelism visible. Use markers like `B3 || B4 [parallel]` for independent work and `B3 -> B4 [sequenziell: shared file scripts/tmux_pair.py]` when ordering is required. GATE 2 warns when independent bullets are needlessly serial and blocks missing per-bullet markers.

### PROJECT.md care

The gated workflow treats project-local `PROJECT.md` care as mandatory for
feature and refactor bullets that change the package map, feature surface,
design decisions, or implementation history. The writer owns the update and
the reviewer signs off on either the concrete `PROJECT.md` diff or a justified
skip for refactor, test, or docs-only bullets with no feature-surface change.

The GATE 3 verifier checks whether `PROJECT.md` was touched when the plan
includes a feature, workflow, command, flag, package-map, architecture, or
history-worthy change. If a repository has no `PROJECT.md`, the orchestrator
checks that during recon and asks whether to bootstrap a human-maintained
skeleton. `~/git/example-project/PROJECT.md` is the reference example for format and
detail depth.

### Reviewer-Readiness + rules-bootstrap (GATE 1.5)

A reviewer without rules says "looks fine": that is the failure mode GATE 1.5 prevents. The orchestrator runs the readiness-check before planning. On `NEEDS-RULES`, it loops: per gap one `AskUserQuestion`, then the bootstrap subagent generates `.claude/rules/<topic>.md` from one of seven shipped language templates (Rust, TypeScript, Python, Go, JavaScript, Java, generic skeleton) plus repo recon plus user answers. Templates ship in `templates/rules/` and are sanitized: no company-specific naming, ADRs, or domain references. Project-specific content comes from the user's own answers, baked into the user's own repo.

Optional opt-in `/gepa` pass after fresh rules; the plugin does not call `/gepa` automatically because the GEPA skill is optional user setup. If the user opts in, they trigger `/gepa` themselves out-of-band after the run.

## Token management (long-running spawns)

Three helper subcommands let an orchestrator (or the human directly) refresh an agent in place:

```
python3 <plugin>/scripts/tmux_pair.py status <pane-id>
python3 <plugin>/scripts/tmux_pair.py compact <pane-id> --briefing-file <path> [--focus "<one-liner>"] [--timeout 300]
python3 <plugin>/scripts/tmux_pair.py monitor --orch-pane <id> --panes <id1> <id2> [...] [--threshold-k <N>] [--cooldown-sec <N>]
```

`status` returns JSON with the detected agent, current token count (parsed from claude's footer; codex usually shows up as `null` so callers fall back to a time/event heuristic), and the raw matched footer line.

`compact` sends `/compact [focus]` to the pane (the official claude `/compact [instructions]` form, see [code.claude.com/docs/en/commands](https://code.claude.com/docs/en/commands)), polls `capture-pane` for completion (claude prints `Conversation compacted`; for codex we accept a token-count drop of 50% or more as a fallback signal), then sends the re-brief from `--briefing-file` via the regular send path. The optional `--focus` hint shapes the summary so the agent retains plan + REVIEW-state + peer-protocol. The re-brief MUST be self-contained: after `/compact` the agent has lost the conversational state and only remembers the summary. Include role, task, current progress recap, the next concrete step, the peer protocol, and the standards.

**Compact has two paths.** The orchestrator-driven path uses `tmux_pair.py compact <pane>` (sends `/compact` plus Re-Brief, useful when the watcher pings or the engineer is mid-tool-call and unaware). The engineer-driven self-compact path uses `tmux_pair.py send <eigener_pane> "/compact <focus>"`: same mechanic, engineer-initiated. Self-compact discipline: between cycles only, never mid-edit; prepare a self-re-brief file (plan-bullet, REVIEW-state, next step, peer pane ids) BEFORE sending; signal `SELF-COMPACT-PLANNED: <bullet> <focus>` to the orchestrator so the watcher does not also fire. Codex panes have no known `/compact` form; self-compact is claude-only.

`monitor` runs as a background watcher. The spawn orchestrator briefing kicks one off automatically as DUTY 0; solo mode does not auto-start it (the agent self-compacts between phases).

Trigger windows for manual `compact`:

- between REVIEW cycles when the engineer is idle, never mid-edit or mid-tool-call
- the watcher's threshold ping (model-aware: 140k for 200k-context models, 700k for 1M-context)
- before a known long phase (e.g. starting Wave N) so the agent enters it fresh

To compact both engineers in a spawn in parallel, run two `compact` calls with `&` from the orchestrator's shell.

## Skills

The plugin ships three skills:

- **`tmux-pair-orchestration`**: documents the pair protocol (`REVIEW-READY` to `REVIEW` loop), when to choose solo vs spawn, briefing templates for each role, the 6-phase solo workflow, the 5-gate spawn workflow with V1-V10 smartness, and failure modes. Triggers when the user asks for things like "spawn a solo with self-review", "spin up a writer/reviewer team", "run multiple agents on this", "set up an orchestrator + team", or names the workflow directly.
- **`/tmux-pair:gepa`**: Genetic-Pareto prompt/text-artifact optimization (paper arXiv:2507.19457). Used opt-in after rules-bootstrap to optimize freshly generated `.claude/rules/*.md` against user-supplied test diffs. Plugin-namespaced so it does not collide with a user-local `/gepa` install. Skill files: `skills/gepa/`.
- **`/tmux-pair:dg`**: Dinesh-vs-Gilfoyle adversarial code review. Two AI personas (attacker + defender) debate a diff or file until convergence. Useful as an optional pre-GATE-3 step on security/concurrency/auth/crypto/migration bullets. Skill files: `skills/dg/`.

External companion (NOT bundled, install separately): the official `code-simplifier` plugin from `claude-plugins-official` for refactor-passes after a feature lands.

## License

Apache 2.0.
