# tmux-pair

Run a single coding agent on a task via tmux + git worktrees. The agent lives in its own pane in a fresh `git worktree`, executes a 7-phase gated self-driven workflow with adversarial review at each gate, then auto-squash-merges its bullet commits onto the base branch and cleans up the feature branch, worktree, and per-worktree Cargo target.

## What it does

`/run` is the default entry-point: it does a short repo + task recon, defaults to `codex`, and only switches to `claude` for profiles that clearly need Claude-specific strengths. `/solo` spawns a single agent in a fresh worktree and runs the gated workflow.

| Slash command | Purpose |
|---|---|
| `/run` | auto-entry: recon + agent pick + dispatch to `/solo` |
| `/solo` | spawn solo agent directly with explicit flags |

There is one mode. Solo, gated, self-driven, with subagent fan-out for parallel work. Adversarial review-quality is preserved by running two independent minds at each gate: a claude subagent (`Agent(...)`) plus `codex exec` (out-of-process, different model family, fresh context).

## Requirements

- `tmux` (running session: the script spawns into the current session)
- `git` 2.5+ (worktrees)
- `python3` 3.9+
- `codex` on `PATH` for the default solo agent and the second-opinion gates
- `claude` on `PATH` for Claude-led solos and scoped Task-tool subagents
- `pi` on `PATH` only when `--agent pi` is used

## Quick start

Inside an existing tmux session:

```
/run    <project-path> <base-ref> <feature-name> <task description>
/solo   <project-path> <base-ref> <feature-name> <task description>
```

Both create a worktree at `<project-parent>/<project-basename>-wt-<feature>` and branch `feature/<feature>` from `<base-ref>`. Phase 7 squashes that feature branch back onto the base, removes the worktree, deletes the matching per-worktree Cargo target, deletes the branch, and pings `DONE-MERGED` so sequential chained runs always start from a clean base.

## /run agent-pick heuristic

When the user does NOT pass `--agent` explicitly, `/run` defaults to `codex` and only picks `claude` for task profiles that clearly need Claude-specific strengths:

| Task profile | Pick | Reason |
|---|---|---|
| Recon-heavy, multi-file, plan-integration, AskUserQuestion-heavy, design work, briefings, greenfield scaffolding, compliance/PII | `claude` | Plan integration + Task tool subagent spawn + structured AskUserQuestion. Explicit exception to the codex default. |
| Single-file edits, code translation (lang A to B), mechanic refactor, bulk-rename, codemod | `codex` | Terminal-driven, direct file-ops, fast turnaround per file. |
| Adversarial bug-hunt, debugging mystery panics, race-condition tracing, "find the real cause" | `codex` | Installed Codex CLI default model with `xhigh` reasoning, sharp on adversarial logic. |
| Cost-sensitive bulk work (mass renames, mechanic migrations) | `pi` (opt-in via `--agent pi`) | Cortecs/qwen3 fits bulk; expensive top-tier models would burn budget. |

Ambiguous task -> `codex` (default). The picked agent is surfaced in the `/run` recon note.

**The same heuristic applies inside the solo run to subagent spawns**: `Agent(...)` (claude Task tool) for recon-heavy / plan-driven / repo-domain sub-bullets, `Bash(codex exec --cd <sub-wt> "...")` for single-file / mechanic / codemod / adversarial bug-hunt sub-bullets. Subagent tie-breaker stays `claude`. Phase 1 (Recon) defaults to claude subagents; Phase 3 (Impl) picks per sub-bullet profile; Phase 2 and Phase 4 (Gates) already run both minds in parallel.

## Solo workflow (7 phases)

```
Phase 1 Recon -> Phase 2 Plan + GATE-2 -> Phase 3 Implementation + bullet commits -> Phase 4 GATE-3 Final-Verify -> Phase 5 PROJECT.md + Skill-Persist -> Phase 6 Commit hygiene -> Phase 7 Auto-Squash-Merge + Cleanup -> DONE-MERGED -> Post-Merge Retro
```

1. **Recon**: 4-6 parallel subagent spawns. Domain-experts when `.claude/agents/<repo>-*.md` exists; `Explore` otherwise. Each subagent under 300 words with `file:line` pointers.
2. **Plan + GATE-2 Plan-Check**: bullet plan with parallel/sequential markers, then two independent adversarial checks in parallel: `Agent(gate-2-plan-check)` plus `Bash(codex exec "adversarial plan-attack")`. BLOCKER in either means fix-loop. GATE 1 Clarify and GATE 1.5 Reviewer-Readiness fold into this phase: solo calls `AskUserQuestion` for missing intent, and the readiness-check subagent confirms `.claude/rules/*.md`, `.claude/skills/*/SKILL.md`, and root project docs cover the 8-item checklist (with a rules-bootstrap loop on `NEEDS-RULES`).
3. **Implementation + bullet commits**: agent codes directly. Per-bullet runs nextest + clippy + per-crate gates inline, then commits the logical step with a `TESTS-PROOF` block. PROJECT.md care applies for feature/refactor bullets.
4. **GATE-3 Final-Verify**: three independent adversarial checks in parallel: `Agent(gate-3-verifier)`, `Agent(gate-3-code-reviewer)`, `Bash(codex exec "diff-review")`. The verifier reads the bullet commits and their `TESTS-PROOF` receipts. BLOCKER in any means fix-loop. WARNING-only proceeds with documented follow-up.
5. **PROJECT.md + Skill-Persist**: phase block + decisions in PROJECT.md, domain insights as `.claude/skills/<repo>-<topic>/SKILL.md` by default, `.claude/rules/<key>.md` only for cross-cutting always-on guidance with explicit justification.
6. **Commit hygiene**: all intended bullet commits and guidance/docs commits exist, use Conventional Commits, carry enough detail for the squash body, and leave the worktree clean. No push.
7. **Auto-Squash-Merge + Cleanup**: solo squashes its bullet commits into one commit on the base branch, removes the worktree, deletes the per-worktree Cargo target, deletes the feature branch, then pings `DONE-MERGED`. Sequential chained runs always start from a clean base. On merge conflict: AskUserQuestion in own pane with 2-4 recovery options. No BLOCKER ping back to master.

All human input lands in the solo agent's own pane via `AskUserQuestion`. The Phase 7 `DONE-MERGED` ping is the only back-channel signal to the spawning master pane.

Switch off the gates with `--no-gated` for trivial tasks (Phase 7 still applies).

## Configuration

```
--agent codex                   # default: codex (choices: claude|codex|pi)
--no-gated                      # bypass the 7-phase gated workflow briefing
--no-worktree                   # skip git worktree add, run on the current branch
--with-standards                # append the durable standards bundle to the briefing
--greenfield                    # --with-standards plus greenfield pre-flight
--interactive                   # turn V2 self-decisions into AskUserQuestion pause points
--claude-model claude-opus-4-8  # default claude model (1M context); claude-opus-4-6 for 200k
--claude-effort xhigh           # default --effort for claude
--codex-effort xhigh            # default model_reasoning_effort for codex
--pi-provider cortecs           # pi default provider
--pi-model qwen3-coder-next     # pi default model
--pi-thinking high              # pi default reasoning level
--pi-writer-provider <name>     # pi role override (solo uses the writer role internally)
--pi-writer-model <slug>
--pi-writer-thinking <level>
--shared-target                 # opt-in: one shared CARGO_TARGET_DIR per repo (legacy 0.14..0.22.0). Default since 0.22.1: per-worktree target so parallel solos do not fight for the cargo file-lock. Since 0.22.4, Phase 7 removes per-worktree targets.
```

Add or replace agent commands in `~/.config/tmux-pair/agents.json`:

```json
{
  "claude": "claude --dangerously-skip-permissions",
  "codex": "codex --dangerously-bypass-approvals-and-sandbox",
  "myagent": "my-agent-cli --some-flag"
}
```

Agent boot commands are started as the tmux pane's shell-command. They are not
typed into an interactive zsh prompt, so full claude/codex/pi launch lines do
not land in `~/.zsh_history`.

Briefings are task-focused and compact by default. `--with-standards` includes the standards bundle; `--greenfield` adds the greenfield pre-flight block for first-session repos without `.claude/rules/` or `.claude/skills/`.

## Model selection and Compact-Watcher

Default claude model: `claude-opus-4-8` (1M context). Override per spawn:

```
/solo  ~/code/myapp main rule-migration --no-gated
/solo  ~/code/myapp main repo-rename --claude-model claude-opus-4-6
/solo  ~/code/myapp main greenfield-session --greenfield
```

The compact-watcher threshold scales with the context window automatically: 1M context to 700k threshold (70%), 200k to 140k. Override with `monitor --threshold-k <N>`.

Default reasoning effort: `xhigh` on both harnesses. Claude panes start with `--effort xhigh`; codex panes start with `-c model_reasoning_effort=xhigh` when the installed CLI supports it. Override per spawn with `--claude-effort`, `--codex-effort`; pass an empty string to skip the flag.

Solo does not auto-start the watcher: the agent self-compacts between phases when appropriate. Self-compact pattern: write a self-re-brief file at `/tmp/self-compact-<window>.md` (plan-bullet, current state, next step, relevant standards), send `/compact <focus>` to own pane, after settle read the file and continue.

## Subagent fan-out (sub-worktrees)

When the plan contains parallel-friendly bullets (`B3 || B4 [parallel]`), the solo agent fans out via the Task tool into per-bullet sub-worktrees:

1. `git worktree add ../<feature>-sub-<bullet-id> -b <feature>/sub-<bullet-id>` per parallel bullet.
2. One subagent per sub-worktree, working there with isolated files. `Agent(...)` (claude Task tool) for recon-heavy / plan-driven / repo-domain sub-bullets; `Bash(codex exec --cd <sub-wt> "<task>")` for single-file / mechanic / codemod / adversarial sub-bullets.
3. After subagent-DONE: `git -C <feature-wt> merge --ff-only <feature>/sub-<bullet-id>`. FF failure means the feature-WT moved on: solo calls `AskUserQuestion` in own pane (no force-merge-commit).
4. `git worktree remove ../<feature>-sub-<bullet-id>` + `git branch -D <feature>/sub-<bullet-id>` to clean up.
5. Phase 7 squashes the feature branch onto base, keeping main linear.

Sequential bullets (`B5 -> B6 [sequential: <reason>]`) stay in the main solo pane.

## Durable standards

Standards survive `/compact` and context resets because they sit in the system prompt, not in the briefing user-message. Engineer briefings are slim by default.

- **claude panes** boot with `--append-system-prompt-file <path>` (the plugin writes a per-spawn standards file under `/tmp/tmux-pair-durable-<window>-<role>.md`).
- **codex panes** read `AGENTS.md` from the worktree root. The plugin writes that file when a real worktree is created.
- For task-specific runs, briefings are minimal by default and omit durable standards block repetition.
- Add `--with-standards` to include the standards bundle in briefings, or `--greenfield` for standards plus pre-flight.
- For `--no-worktree` with codex, the plugin auto-enables standards-in-briefing so codex still receives the rule set.
- `agents.json` overrides are respected: a wrapper-remap of `claude` is not blindly augmented with `--append-system-prompt-file`.

## Scoped subagents (Haiku/Sonnet routing)

Gate checks and recon are routed to plugin-namespaced subagents with explicit model + tool restrictions instead of generic `general-purpose`:

| Role | Subagent | Model | Tools | Why |
|------|----------|-------|-------|-----|
| GATE 1.5 Readiness-Check | `tmux-pair:reviewer-readiness-check` | Sonnet 4.6 | Read + Grep + Glob + Bash | Reviews `.claude/rules/*.md`, `.claude/skills/*/SKILL.md`, and root project docs against an 8-item checklist (style, tests, architecture, anti-patterns, naming, security, build, domain). Returns READY or NEEDS-RULES. NO Edit/Write so it cannot bake guidance itself. |
| GATE 1.5 Rules-Bootstrap | `tmux-pair:rules-bootstrap` | Sonnet 4.6 | Read + Grep + Glob + Bash + Edit + Write | Bakes `.claude/skills/<repo>-<topic>/SKILL.md` by default from plugin language templates + repo recon + solo-collected user answers. Writes `.claude/rules/<topic>.md` only for justified cross-cutting guidance. |
| GATE 2 Plan-Check | `tmux-pair:gate-2-plan-check` | Sonnet 4.6 | Read + Grep + Glob + Bash | Plan validation needs reasoning. Checks every bullet for explicit `B3 || B4 [parallel]` or `B3 -> B4 [sequential: <reason>]` markers. NO Edit/Write so the agent cannot accidentally commit code. |
| GATE 3 Verifier | `tmux-pair:gate-3-verifier` | Haiku 4.5 | Read + Grep + Glob + Bash | Goal-backward coverage check + build/test runs are deterministic; Haiku is sufficient and ~5x cheaper than Sonnet. |
| GATE 3 Code-Reviewer | `tmux-pair:gate-3-code-reviewer` | Sonnet 4.6 | Read + Grep + Glob + Bash | Style nuance, security edge cases, anti-AI-slop detection need Sonnet's nuance. |
| RECON | built-in `Explore` | Haiku 4.5 | read-only | File-snippet lookups + pointer extraction. |

Each gate also runs a parallel `Bash(codex exec ...)` second-opinion (out-of-process, different model family) so adversarial review-quality stays high without coordination cost.

## Smart workflow (V1-V10)

- **V1 Inline-Fix-for-Trivial-Findings**: reviewer subagents may send isolated under-20-LOC cosmetic / typo / missing-doc patches as `INLINE-FIX`; solo applies and ACKs with `applied B<N> inline-fix (X lines)`.
- **V2 Direct-Decision-Threshold**: small repo-pattern decisions run autonomously by default and every self-decision is logged in `COMPLETE` AND persisted as a row in the consumer repo's `PROJECT.md` Implementation History. A solo run is not complete without that `PROJECT.md` entry.
- **V3 Adaptive GATE-Strictness**: `task_kind` in (`bug-fix`, `feature`, `refactor`); GATE 2 and GATE 3 verifier adapt deterministic checklist items per class.
- **V4 Auto-Resolve WARNINGs**: BLOCKER enters the fix-loop, WARNING goes to follow-up memory plus PROJECT.md when relevant, NOTE is log-only.
- **V5 Unattended-Default**: `/solo` and `/run` run unattended by default; `--interactive` turns V2 self-decisions into `AskUserQuestion` pause points.
- **V6 Readiness-Cache (helper only)**: cache helpers and schema exist in `tmux_pair.py`, keyed by project guidance (`.claude/rules/*.md` plus `.claude/skills/*/SKILL.md`) and commit. `cmd_solo` currently does a fresh readiness run and does not automatically read or write this cache.
- **V7 Test-Trust-Chain (TESTS-PROOF marker)**: solo bullet commits carry a `TESTS-PROOF:` block (test/lint/fmt commands + PASS counts + `COMMIT_SHA`). `gate-3-verifier` parses via `tmux_pair.py parse-tests-proof` and trusts when `HEAD == COMMIT_SHA`. Stale markers go to WARNING + narrow re-run; missing on 0.14+ runs goes to BLOCKER.
- **Per-Worktree Cargo Target (since 0.22.1)**: each spawn gets `CARGO_TARGET_DIR=~/.cache/tmux-pair/cargo-target/<repo>__<wt-slug>/` so parallel agents on the same project never collide on cargo's file-lock. Trade-off: cold rebuild per worktree (a few minutes amortised against a 30..90 min solo run). Since 0.22.4, Phase 7 removes this per-worktree target with `tmux_pair.py cleanup-target`, guarded so only children under `~/.cache/tmux-pair/cargo-target/` with a worktree slug are deleted. Opt back into the legacy single shared target (`~/.cache/tmux-pair/cargo-target/<repo>/`) with `--shared-target` when only one agent is active and maximum cache warmth matters; shared targets are not auto-deleted. Non-Cargo repos skip the env entirely.
- **V9 Recon-Cache with Delta-Mode (helper only)**: helper path and TTL are documented for future/runtime callers. `cmd_solo` currently performs fresh recon and does not automatically read `/tmp/tmux-pair-recon-*`.
- **V10 Inline-Gates for trivial plans**: when `task_kind=bug-fix` AND `bullets <= 3` AND `predicted files-touched <= 5`, solo runs GATE 2 inline in its own pane; `gate-3-verifier` may also inline when TESTS-PROOF is valid. `gate-3-code-reviewer` always stays as a subagent. Helper: `tmux_pair.py inline-gate-decide --plan-file <path> --task-kind <kind>`.

### Engineer subagents and parallel plans

The solo briefing tells the agent to keep its main pane lean by using subagents for bounded side work:

- parallel recon files, where each subagent reads an independent module and returns short `file:line` pointers
- parallel test suites, where unit, integration, lint, or browser-smoke checks can run without shared mutable state
- parallel fix branches, where independent plan bullets with disjoint files can use extra sub-worktrees

Codex subagent spawns use the installed `codex exec` default model and the requested reasoning effort from the spawning command or user config. Do not document a fixed model slug here: the CLI default changes independently of this plugin. Claude stays on the Task tool and uses the model from the subagent definition.

Plans must make parallelism visible. Use markers `B3 || B4 [parallel]` for independent work and `B3 -> B4 [sequential: shared file scripts/tmux_pair.py]` when ordering is required. GATE 2 warns when independent bullets are needlessly serial and blocks missing per-bullet markers.

### PROJECT.md care

The gated workflow treats project-local `PROJECT.md` care as mandatory for feature and refactor bullets that change the package map, feature surface, design decisions, or implementation history. Solo owns the update and the GATE-3 verifier checks that PROJECT.md was touched when the plan includes a feature, workflow, command, flag, package-map, architecture, or history-worthy change. If a repository has no `PROJECT.md`, solo asks during recon whether to bootstrap a human-maintained skeleton. This plugin's own `PROJECT.md` is a reference example for format and detail depth.

### Post-Merge Retro (mandatory)

After Phase 7 (`DONE-MERGED`), the run is not yet done. Worktree, branch, and per-worktree Cargo target are gone, but the tmux window stays intact while solo collects a 200-500 word factual retro from itself plus three parallel `Agent` personas (orchestrator-view, writer-view, reviewer-view) and one `codex exec "retro"` for an independent fourth view. Recurring issue classes are persisted either into the tmux-pair-orchestration skill (workflow-cross-cutting) or into consumer-repo rules / skills (repo-specific). Only after pattern-persist does `tmux kill-window` close the window.

### Recurring Pre-Flight Checks (Rust focus)

GATE 2 (`agents/gate-2-plan-check.md` Item 16) anchors and GATE 3 code-reviewer (`agents/gate-3-code-reviewer.md` Item 10) enforces:

- Decorator-Sweep on Trait-Default-Add: list all `impl <Trait> for`, decorators need forward-override or no-op rationale.
- Trait-Param-Honor: `_`-prefixed param vs effective trait-doc is silent-discard footgun.
- Method-Resolution-Collision: new trait-method with same name as inherent-impl on implementor gets shadowed.
- fmt-drift: `cargo fmt -p <crate>` without `--check` brushes neighbor files; "fmt clean" claims need `--check` evidence.
- Memory recon (mandatory): RECON reads `MEMORY.md` plus the relevant memory files before plan-write.
- API-Surface-Upfront: consumer-bullet must name the producer-bullet's exact public signature.

Aggregated from solo retros, falsifiable, additive to standard adversarial review.

### Reviewer-Readiness + rules-bootstrap (GATE 1.5)

A reviewer without project guidance says "looks fine": that is the failure mode GATE 1.5 prevents. Solo runs the readiness-check before planning. On `NEEDS-RULES`, it loops: per gap one `AskUserQuestion` in its own pane, then the bootstrap subagent generates `.claude/skills/<repo>-<topic>/SKILL.md` by default from one of seven shipped language templates (Rust, TypeScript, Python, Go, JavaScript, Java, generic skeleton) plus repo recon plus user answers. `.claude/rules/<topic>.md` is reserved for justified cross-cutting always-on guidance. Templates ship in `templates/rules/` and are sanitized: no company-specific naming, ADRs, or domain references.

Optional opt-in `/gepa` pass after fresh guidance; the plugin does not call `/gepa` automatically. If the user opts in, they trigger `/gepa` themselves out-of-band after the run.

## Token management (long-running runs)

Three helper subcommands let solo (or the human directly) refresh the agent in place:

```
python3 <plugin>/scripts/tmux_pair.py status <pane-id>
python3 <plugin>/scripts/tmux_pair.py compact <pane-id> --briefing-file <path> [--focus "<one-liner>"] [--timeout 300]
python3 <plugin>/scripts/tmux_pair.py monitor --orch-pane <id> --panes <id1> [--threshold-k <N>] [--cooldown-sec <N>]
```

`status` returns JSON with the detected agent, current token count (parsed from claude's footer; codex usually shows up as `null` so callers fall back to a time / event heuristic), and the raw matched footer line.

`compact` sends `/compact [focus]` to the pane (the official claude `/compact [instructions]` form), polls `capture-pane` for completion, then sends the re-brief from `--briefing-file` via the regular send path. The optional `--focus` hint shapes the summary so the agent retains plan + REVIEW-state + protocol context.

**Compact has two paths.** The helper-driven path uses `tmux_pair.py compact <pane>` (sends `/compact` plus re-brief). The solo self-compact path uses `tmux_pair.py send <own-pane> "/compact <focus>"`: same mechanic, agent-initiated. Self-compact discipline: between phases only, never mid-edit; prepare a self-re-brief file BEFORE sending. Codex panes have no known `/compact` form; self-compact is claude-only.

`monitor` runs as a background watcher. Solo does not auto-start it: the agent self-compacts between phases.

### Codex file-bridge for long messages (since 0.22.3)

Codex's TUI input widget glitches when very long text is pasted into it. To avoid that, briefings sent to codex panes are routed through a tempfile and a short pointer message:

- Initial solo briefings: `cmd_solo` writes the body to `/tmp/tmux-pair-msg-XXXX.md` before boot and passes the short *"read /tmp/... and execute it as your next instruction"* pointer as Codex's initial CLI prompt. This avoids the post-ready `tmux_pair.py send` path, so `/run ... --agent codex` returns the JSON receipt promptly. Claude / pi panes keep the direct paste path.
- Legacy spawn initial briefings: `cmd_spawn` still sends the pointer after all panes exist, because those briefings need peer pane IDs.
- Re-briefs and plan-updates: `tmux_pair.py send <pane> --from-file <path>` reads the body from a file. When the target pane runs codex and the body is multi-line, the helper auto-routes through the same file-bridge.

## Skills

The plugin ships three skills:

- **`tmux-pair-orchestration`**: documents the workflow, the 7-phase solo flow, briefing templates, the `/run` agent-pick heuristic, smart-workflow V1-V10, and failure modes. Triggers when the user asks for things like "spawn a solo with self-review", "use the tmux-pair workflow", or "/run for this task".
- **`/tmux-pair:gepa`**: Genetic-Pareto prompt / text-artifact optimization (paper arXiv:2507.19457). Used opt-in after rules-bootstrap to optimize freshly generated `.claude/skills/*/SKILL.md` or `.claude/rules/*.md` against user-supplied test diffs.
- **`/tmux-pair:dg`**: Dinesh-vs-Gilfoyle adversarial code review. Two AI personas (attacker + defender) debate a diff or file until convergence. Useful as an optional pre-GATE-3 step on security / concurrency / auth / crypto / migration bullets.

External companion (NOT bundled, install separately): the official `code-simplifier` plugin from `claude-plugins-official` for refactor passes after a feature lands.

## History

Multi-pane spawn modes (writer + reviewer panes, dual-review with two reviewers, parallel-writers with two writer panes) were retired in 0.19.0 for CARGO_TARGET_DIR contention under shared target dirs, git-index-lock races between parallel writers fighting `git add`, cross-writer PROJECT.md races forcing reactive plan-amendments, dual-review coordination overhead (per-bullet swap + peer-review + orchestrator-consolidate eating more wall-time than the extra review-quality bought), and pane-readiness races at boot. Solo + subagent fan-out + parallel `codex exec` second-opinion at each gate is the lean replacement: two independent minds without the coordination tax. The Phase 7 auto-squash-merge (0.20.0) replaced the manual human-driven merge that followed the older spawn-mode `COMPLETE` ping.

## License

Apache 2.0.
