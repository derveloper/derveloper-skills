---
name: tmux-pair-orchestration
description: >
  Use when the user wants to run, monitor, or recover a tmux-pair solo coding
  workflow through `/run` or `/solo`: one agent in a fresh git worktree, gated
  recon, plan checks, implementation, final verify, commit hygiene, and
  auto-squash-merge. Covers durable standards, review-ledger evidence,
  CLARIFY-NEEDED, plan drift handling, PROJECT.md care, DONE-MERGED, compact
  recovery, repo-specific subagents, and mandatory post-merge retro.
version: 0.22.9
---

# tmux-pair-orchestration

Run a single coding agent on a task. The agent lives in its own tmux pane in a fresh `git worktree`, executes a 7-phase gated workflow, and uses subagents plus `codex exec` for adversarial review at each gate.

This skill applies whenever the user wants to set up such a run, monitor it, draft briefings, recover from a stuck loop, or do the post-merge retro. The default entry-point is `/run`.

## The mode

Solo is the only mode. One agent, one pane, one worktree.

Multi-pane spawn modes (separate writer + reviewer panes, dual-review with two reviewer panes, parallel-writers with two writer panes) were removed in 0.18.0. They consistently lost on:

- **Cargo target contention** under shared CARGO_TARGET_DIR; cold-cache rebuilds and llvm-cov ran twice
- **Git index lock races**: parallel writers fighting `git add` produced cross-bullet commit pollution (e.g. one writer's 12k target-cov files landing in another writer's commit)
- **PROJECT.md cross-writer races**: two writers updating the same active roadmap section forced reactive plan-amendments
- **Dual-review coordination overhead**: per-bullet swap + peer-review + orchestrator-consolidate eats more wall-time than the extra review-quality buys at 15+ bullet sweeps
- **Pane-readiness races** at boot (70s timeout, manual rebrief common)

Adversarial review-quality is preserved by parallel two-mind gates inside the single pane: a claude subagent (`Agent(gate-2-plan-check)` etc.) plus `codex exec` (out-of-process, fresh context, different model family). Two independent minds without the coordination tax.

Default agent: `codex`. `/run` defaults to `codex` when the user does not pass `--agent` explicitly, and only switches to `claude` for profiles that clearly need Claude-specific strengths; `pi` is opt-in only. Reviewer subagents run at top reasoning tier regardless of solo agent's budget.

Agent pick heuristic (used by `/run`):

| Task profile | Pick | Reason |
|---|---|---|
| Recon-heavy, multi-file, plan-integration, AskUserQuestion-heavy, design work, briefings, greenfield scaffolding, compliance/PII | `claude` | Plan integration + Subagent-Spawn (Task tool) + AskUserQuestion structured. Explicit exception to the codex default. |
| Single-file edits, code translation (lang A → B), mechanic refactor, bulk-rename, codemod | `codex` | Terminal-driven, direct file-ops, fast turnaround per file. |
| Adversarial bug-hunt, debugging mystery panics, race-condition tracing, "find the real cause" | `codex` | Installed Codex CLI default model with `xhigh` reasoning, sharp on adversarial logic. |
| Cost-sensitive bulk work (mass renames, mechanic migrations) | `pi` (opt-in via `--agent pi`) | Cortecs/qwen3 fits bulk; expensive top-tier models would burn budget. |

Ambiguous → `codex` (default). User can override anytime with `--agent claude` / `--agent pi`. The picked agent is surfaced in the `/run` recon note.

**Same heuristic applies to subagent spawns inside the solo run.** The solo agent has two subagent mechanisms with different strength profiles, and picks per task:

| Mechanism | Tool | Strength profile |
|---|---|---|
| claude subagent | `Agent(general-purpose)` or `Agent(<repo>-*)` (Task tool) | Plan-integration, multi-step recon with `AskUserQuestion` chaining, design + briefing-driven impl, structured output (XML / JSON / markdown), repo-domain experts (`.claude/agents/<repo>-*.md`). |
| codex subagent | `Bash(codex exec --skip-git-repo-check --cd <wt> "...")` | Single-file edits, code translation, mechanic refactors, codemods, adversarial bug-hunt, race-condition tracing, "find the real cause" prompts. Out-of-process, no context pollution. |

Per phase:

- **Phase 1 (Recon)**: usually `claude` subagents (4-6 parallel `Agent` calls). One `Bash(codex exec "recon-attack")` in parallel for second-opinion when the task is ambiguous or domain-unfamiliar.
- **Phase 3 (Implementation)**: parallel sub-bullets → pick per bullet profile.
  - Recon-heavy / multi-file / plan-driven bullet → `Agent` in a sub-worktree.
  - Single-file mechanic / codemod / lang-translation bullet → `Bash(codex exec --cd <sub-wt> "<task>")`. Lean, no setup, direct file-ops.
  - Adversarial bug-hunt sub-bullet → codex exec.
  - Sequential bullet stays in the main pane (no subagent).
- **Phase 2/4 (Gates)**: already parallel both-minds (claude `Agent` + codex `Bash(codex exec)`). No new pick logic needed.
- **Phase 5 (Persist) / Phase 7 (Auto-Squash-Merge)**: no subagents, main pane handles directly.

Default tie-breaker for subagents stays `claude` (recon-strong, structured). Codex picks itself when the profile is mechanic / single-file / adversarial: those are codex's home turf.

## Solo workflow (7 phases)

1. **Recon**: 4-6 parallel subagent spawns. Domain-experts when `.claude/agents/<repo>-*.md` exists; `Explore` otherwise. Each subagent <300 words with `file:line` pointers. Adds `MEMORY.md` freshness check (>3 day old memory files = stale-risk flag).
2. **Plan + GATE-2 Plan-Check**: bullet plan with parallel/sequential markers, then TWO independent adversarial checks in parallel:
   - `Agent(gate-2-plan-check)` (claude, adversarial, scoped read-only)
   - `Bash(codex exec --skip-git-repo-check "adversarial plan-attack against <plan>")` (codex, different model family, fresh context)
   Both must return PASS or WARNING-only. BLOCKER in either → fix-loop. Max 3 plan iterations; iteration 4+ asks the user.
3. **Implementation + bullet commits**: agent codes directly. Per-bullet runs nextest + clippy + per-crate gates inline, then commits the logical step with a `TESTS-PROOF` block. PROJECT.md care applies for feature/refactor bullets that change package map, feature surface, design decisions, or implementation history.
4. **GATE-3 Final-Verify**: THREE independent adversarial checks in parallel:
   - `Agent(gate-3-verifier)` (claude, Haiku 4.5, goal-backward against plan)
   - `Agent(gate-3-code-reviewer)` (claude, Sonnet 4.6, adversarial diff review)
   - `Bash(codex exec "adversarial diff-review against main..HEAD")` (codex)
   The verifier reads the bullet commits and their `TESTS-PROOF` receipts. BLOCKER in any → fix-loop. WARNING-only → proceed with documented follow-up. Max 3 review cycles.
5. **PROJECT.md + Skill-Persist**: phase block in PROJECT.md, design decisions, domain knowledge as Skill under `.claude/skills/<repo>-<topic>/SKILL.md` (Persist-Convention; Rules only for cross-cutting always-on items).
6. **Commit hygiene**: all intended bullet commits and guidance/docs commits exist, use Conventional Commits, carry enough detail for the squash body, and leave the worktree clean. No completion ping before Phase 7 has finished.
7. **Auto-Squash-Merge + Cleanup**: solo squashes all bullet commits into one commit on `<base>`, removes the feature worktree, deletes the feature branch, then pings `DONE-MERGED`. Sequential chained runs always start from clean base. Steps the solo executes itself:
   - `git -C <project> status --porcelain` -> must be empty (else BLOCKER)
   - `git -C <project> checkout <base>`
   - `git -C <project> merge --squash <branch>`
   - `git -C <project> commit` (heredoc message: one-line subject + bullet body + decisions + test counts + phase/gate ledger)
   - `git -C <project> worktree remove <wt_path>` (skipped if `--no-worktree`)
   - `tmux_pair.py cleanup-target --project <project> --worktree <wt_path>` for per-worktree Cargo targets
   - `git -C <project> branch -D <branch>`
   - `DONE-MERGED solo.<feature>: <squash-sha> on <base>` ping
   - Merge conflict in Phase 7 -> AskUserQuestion in own pane with the concrete error and 2-4 recovery options (rebase + retry, abort, manual resolve + retry). No BLOCKER ping to master. See SOLO USER INPUT RULE in the briefing.

Default flag set: `--no-gated` for trivial tasks where subagent-driven recon/plan/review is overkill (e.g. doc tweak, single-file rename). Gated is the default. Worktree is the default; `--no-worktree` opts out.

**Base ref rule:** the user-provided `<base>` / `--base` value is the
authority for worktree creation. It may be a local ref such as `main` or a
remote ref such as `origin/main`. Do not require `origin`, `origin/HEAD`, or
remote tracking when `--base main` was provided and resolves locally. Missing
remote metadata is not a reason to use `--no-worktree`. Worktree mode is the
default and must be preserved unless the user explicitly passes `--no-worktree`
or the supplied base ref cannot be resolved by `git worktree add`.

### Repo-specific subagents (auto-detected)

When the script sees `.claude/agents/<repo>-*.md` files in the target repo, it lists them in the briefing. The solo briefing instructs the agent to prefer those domain experts over `general-purpose` for Recon/Impl/Review subagent spawns. They know the repo's domain vocabulary, architecture constraints, and skill files.

Detection logic: filename stem starting with `<project.name>-` (e.g. `example-repo-kernel.md` in an `example-repo` repo). Falls back to "no repo-subagents listed" if the directory is missing or empty.

### Codex-CLI integration concrete

`codex exec --skip-git-repo-check --cd <wt>` is invoked by the solo agent via Bash for plan-attack and diff-review gates. The agent passes the plan or diff as part of the prompt; codex runs read-only, returns VERDICT=PASS|WARNING|BLOCKER plus falsifiable findings to stdout. The solo agent reads stdout, integrates findings with the claude-subagent verdict, and decides loop/proceed.

Sample shape for the plan-attack call:

```bash
codex exec --skip-git-repo-check --cd <wt> "$(cat <<'EOF'
Adversarial plan reviewer. Read PLAN.md and the proposed bullet list.
Report VERDICT=PASS|WARNING|BLOCKER with falsifiable findings (file:line,
problem, fix-direction). Read-only. No edits.
EOF
)"
```

## /run auto-entry

`/run <project> <base> <feature> [task]` is the default entry-point. It performs a short clarify + repo recon, then invokes solo.

Decision logic:

1. **Task clarification**: if `<task>` is missing or ambiguous, ask once via `AskUserQuestion`.
2. **Repo recon**: inspect size, language stack, `.claude/agents/`, `.claude/rules/`, `.claude/skills/`, grep for keywords from `<task>` to estimate affected file count.
3. **Pre-pick sensible solo flags**: `--with-standards` for repos lacking explicit guidance, `--greenfield` for completely fresh repos.
4. **Invoke solo** with the resolved flags.

There is no spawn-mode anymore. All `/solo` flags are forwarded.

## Bullet-Sweep Sizing

Plan-drift correlates strongly with bullet count in one run.

| Bullet count | Recommendation |
|---|---|
| 1-3 | solo, monolithic |
| 4-10 | solo, monolithic, gated |
| 11+ | chain 3-5-bullet solo runs back-to-back, each its own squash-merge + retro |

For an 11+ sweep: do a pre-plan triage of all candidate bullets into four classes:

| Class | Per-bullet review pattern |
|---|---|
| Code-fix (real change) | full GATE-2 + GATE-3 + codex-CLI second-opinion |
| Verify-absent (already fixed in earlier phase) | rg-evidence in review ledger, single-pass verifier check |
| Doc-only (PROJECT.md, comment, skill text) | bundled with other doc-only bullets, one PROJECT.md-closeout review |
| Won't-fix (technically impossible or out-of-scope) | plan-amendment commit with rationale, no implementation |

Run one solo per class-batch (or split code-fix into 3-5-bullet sub-batches). Avoid the monolithic 22-bullet run.

## Durable standards

Standards survive `/compact` and context resets because they sit in the system prompt, not in the briefing user-message that gets summarised on compaction. Briefings are slim by default: task-focused and compact.

- **claude panes** boot with `--append-system-prompt-file <path>` pointing at `/tmp/tmux-pair-durable-<window>-<role>.md`. The file is generated per-spawn from a single in-script constant (`DURABLE_STANDARDS_PROMPT`) so updates to standards land in the next spawn automatically.
- **codex panes** read `AGENTS.md` from the worktree root. The plugin writes that file when a real worktree is created (i.e. not when `--no-worktree` is passed). If the repo already owns an `AGENTS.md`, the plugin leaves it alone: repo standards win.
- **pi panes** boot with `--append-system-prompt <path>` (a third-party custom CLI, config under `~/.pi/agent/`). pi reads `AGENTS.md` and `CLAUDE.md` via default discovery, so the codex path works transitively. Default model `qwen3-coder-next` via default provider `cortecs`, default `--thinking high`. Override per spawn via `--pi-provider`, `--pi-model`, `--pi-thinking`. Known limits: no mid-session `/model` switch (pane-restart required), no `/compact` equivalent (Compact-Watcher does not ping pi panes).
- **`--with-standards`** appends the durable standards bundle (reviewer standards, recall discipline, bullet-start ritual).
- **`--greenfield`** enables `--with-standards` plus greenfield pre-flight.
- **`--no-worktree`**: if codex is the solo agent, standards are auto-enabled in the briefing so codex still receives durable standards context.
- **`agents.json` overrides** are respected: if the user has remapped `claude`, the plugin does NOT inject `--append-system-prompt-file` blindly. The wrapper can read the standards file itself.

The standards block covers: real Umlaute (no ASCII substitutes), Conventional Commits with no `--no-verify` and no AI-co-author trailer, phase-ledger evidence format, the honesty protocol (past-tense claims need same-turn tool evidence), drift signals (em-dashes, progress markers, ALL-CAPS headers, "should I"-after-clear-directive), the `incidental:` format for PostToolUse-hook fmt drift, the worktree-as-sandbox rule, the no-pre-existing-issues rule, recall-discipline (cite the relevant guidance + memory before sensitive actions), and the bullet-start ritual (class + relevant guidance + common BLOCKER-classes before the first edit on a bullet).

## Gated workflow (default)

```
Recon -> GATE 1 Clarify -> GATE 1.5 Reviewer-Readiness -> Plan -> GATE 2 Plan-Check -> Implementation Loop with bullet commits -> GATE 3 Final-Verify -> Commit-Hygiene -> Auto-Squash-Merge (Phase 7) -> DONE-MERGED -> Post-Merge Retro
```

- **GATE 1 (Clarify)**. The solo agent calls `AskUserQuestion` directly. The human only sees a `GATE-1-ESCALATE` if a question is outside the agent's authority.
- **GATE 1.5 (Reviewer-Readiness)**: one scoped subagent (`tmux-pair:reviewer-readiness-check`, Sonnet 4.6, Read+Grep+Glob+Bash, NO Edit/Write) reads `.claude/rules/*.md`, `.claude/skills/*/SKILL.md`, and root project docs, then scores an 8-item checklist (style, tests, architecture, anti-patterns, naming, security, build, domain). On `NEEDS-RULES`, the agent runs a bootstrap loop: per gap one `AskUserQuestion`, then `tmux-pair:rules-bootstrap` bakes `.claude/skills/<repo>-<topic>/SKILL.md` by default from plugin language templates + repo recon + user answers. `.claude/rules/<topic>.md` is reserved for justified cross-cutting guidance. Then re-run readiness-check. Loop terminates at READY or after iteration 3 with user-decided abort/partial-coverage/manual-amend. Optional opt-in `/gepa` pass after fresh guidance; the plugin does not call `/gepa` automatically.
- **GATE 2 (Plan-Check)**: parallel two-mind check. `Agent(gate-2-plan-check)` (Sonnet 4.6, scoped read-only) verifies the plan goal-backward AND checks plan quality. Every bullet must carry either a parallel marker (`B3 || B4 [parallel]`) or a sequencing marker (`B3 -> B4 [sequential: shared file]`). In parallel: `Bash(codex exec "adversarial plan-attack")` for second-opinion. `BLOCKER` in either escalates to the agent's fix-loop; both PASS or WARNING-only proceeds.
- **Implementation Loop**: solo writes + per-bullet self-review via `Agent(gate-3-code-reviewer)` when bullets are non-trivial. Per-bullet test-budget is crate-scoped (`cargo nextest -p <crate>`, never `--workspace`). PROJECT.md care for feature and refactor bullets. The solo agent uses subagents for parallel recon, parallel test suites, and independent fix branches when that keeps the main pane lean.
- **GATE 3 (Final-Verify)**. Three parallel adversarial checks: `Agent(gate-3-verifier)` (Haiku 4.5, goal-backward against plan, runs build/test, checks plan-bullet coverage and PROJECT.md care), `Agent(gate-3-code-reviewer)` (Sonnet 4.6, adversarial diff review), and `Bash(codex exec "diff-review")` (codex, second-opinion). All PASS or WARNING-only: solo proceeds to Phase 5 (Persist), Phase 6 (Commit), and Phase 7 (Auto-Squash-Merge + DONE-MERGED). No interim ping to the human.

The implementation loop adds six protocol elements:

- **Review ledger 3 mandatory fields**: every internal review entry carries (1) what changed (file:line + LOC-diff), (2) verification (`crate-gate=PASS` + test counts, or `crate-gate=N/A doc-only`), (3) plan-bullet/pain reference. Missing fields are blocked.
- **CLARIFY-NEEDED**. When the agent hits a user-decision question mid-loop (scope, behavior, UX, architecture choice, naming conflict, trade-off not in the plan), it calls `AskUserQuestion` directly with 2-4 options. Engineers do NOT decide user-facing questions on their own.
- **Plan-Update-Commit**. If a bullet hits a hard cap (LOC limit, file-size cap) or the estimate drifts more than ~50%, the agent commits a `docs(plan-amendment): ...` BEFORE the implementation commit that breaks the cap. A bullet with documented drift but no preceding amendment commit fails verifier.
- **Parallel markers**. Plans mark independent bullets as `B3 || B4 [parallel]` and ordered bullets as `B3 -> B4 [sequential: <reason>]`. GATE 2 blocks missing markers.
- **PROJECT.md care**. The agent updates project-local `PROJECT.md` for feature and refactor bullets that change package map, feature surface, design decisions, or implementation history. Reviewers sign off on the update or on a justified skip for refactor, test, or docs-only bullets with no feature-surface change. If no `PROJECT.md` exists, the agent asks whether to bootstrap a human-maintained skeleton. Use the PROJECT.md in your own repo (or this plugin's PROJECT.md, if present) as the format and detail-depth reference.
- **COMPLETE marker (internal phase log)**. After GATE 3 returns PASS the solo agent emits a one-line COMPLETE marker in its own output: `COMPLETE: <Phase>. gate-3=PASS via <verifier-name + code-reviewer-name + codex-cli>. <diff-stat>. Reference: <plan goals all met>.` Logged in own pane for the human reader and for the eventual squash-commit body. Never sent as a back-channel ping; DONE-MERGED at Phase 7 is the only back-channel signal.
- **Recall-Discipline + Bullet-Start-Ritual**: cite the relevant rule + memory entry before any sensitive action (commit, push, external API), and post a class + rules + common BLOCKER-classes block before the first edit on each new plan-bullet.

Cross-cutting:

- **Plan quality is enforced.** A skeletal "implement X" plan blocks at GATE 2.
- **Context economy applies.** Heavy research, deep codebase reads, and web lookups go to subagents (one message, multiple parallel Task calls when independent). Diff-first reviews. Targeted Read-ranges over full-file dumps.
- **Edit efficiency is part of the plan.** Pattern replace at >3 sites is a `sed`-job. Boilerplate generation = template + substitution. The plan names the tool.
- **Few, descriptive commits.** The agent commits at logical-step granularity during the loop. Phase 7 auto-squashes those bullet commits onto the base branch. Commit messages must be substantial enough that a meaningful squash body can be distilled.

Greenfield repos (no `CLAUDE.md`, no `.claude/rules/`, no `.claude/skills/`) are handled by GATE 1.5 automatically: the readiness-check returns `NEEDS-RULES` with all 8 topics as gaps, the bootstrap loop generates the full guidance set from plugin templates + user answers + repo recon, and the agent proceeds only AFTER guidance exists. Plan stays focused on the actual feature work; guidance-generation is no longer a plan bullet.

Full workflow with subagent prompt templates, gate event vocabulary, and failure modes in `references/gated-workflow.md`.

## Smart workflow (V1-V10)

The workflow is unattended by default. The agent handles small, reversible decisions inside the documented threshold, logs every self-decision in `COMPLETE` AND persists every self-decision in the consumer repo's `PROJECT.md` under Implementation History. Only pauses for decisions that change scope, budget, external dependencies, or security posture. Pass `--interactive` when the user wants every self-decision to become a pause point.

### V1 Inline-Fix-for-Trivial-Findings

When a self-review subagent surfaces a trivial finding under 20 LOC and clearly isolated (cosmetic, typo, missing doc), the agent applies it silently instead of escalating to the user. Anti-trigger: architecture, security, test-logic, >20 LOC.

### V2 Direct-Decision-Threshold

| Decision class | Default action |
|---|---|
| Style finding already APPROVE-worthy | Self-decide and log rationale in `COMPLETE`. |
| Test coverage edge case with clear risk assessment | Self-decide and log the risk note. |
| Optional-vs-required default with existing repo precedent | Self-decide by repo pattern. |
| Naming convention with repo-pattern match | Self-decide by local convention. |
| Plan revision after GATE-2-BLOCKER with clear fix direction | Self-decide and send the revised plan. |
| Budget, stakeholder approval, external service status, real scope expansion, security trade-off | Escalate to the user. |

Every self-decision is recorded in the final `COMPLETE` ping as a one-line rationale AND persisted as a row in the consumer repo's `PROJECT.md` under a new Implementation-History phase heading (phase marker, anchor SHA, Markdown table `ID | Decision | Rationale`). A run is not considered complete without the `PROJECT.md` entry.

### V3 Adaptive GATE-Strictness

`task_kind` has three classes: `bug-fix`, `feature`, `refactor`. The agent classifies during recon and passes to GATE 2 + GATE 3 subagents.

| task_kind | Subagent impact |
|---|---|
| `bug-fix` | Keep core coverage, specificity, rules, plan quality, test checks active. Skip wiring, parallel markers, UI-smoke, PROJECT.md only for one-file fixes with no new surface. |
| `feature` | Default strictness. All checklist items stay active. |
| `refactor` | Treat coverage as preservation, tests as regression evidence. Skip wiring + UI-smoke if no behavior/UI surface change. Keep design-decision + implementation-history checks. |

### V4 Auto-Resolve WARNINGs

GATE 3 verdicts use three severities: BLOCKER (correctness, security, maintainability, project-rule violation, dirty worktree, failed verification → fix-loop), WARNING (preference or nice-to-have → may ignore, follow-up-memory recorded), NOTE (info-only).

### V5 Unattended-Default

Default mode is unattended. Without `--interactive`, V2 self-decisions proceed autonomously and are logged in both `COMPLETE` and `PROJECT.md`. With `--interactive`, the agent pauses before every self-decision and asks the user via `AskUserQuestion`.

### V6 Readiness-Cache (helper only)

Cache helper code exists in `tmux_pair.py`, keyed by `sha256(.claude/rules/*.md + .claude/skills/*/SKILL.md content)` plus commit-sha. `cmd_solo` currently performs a fresh readiness run and does not automatically read or write this cache. Workflows that pass a cache payload into `reviewer-readiness-check` may skip the subagent on cache-hit with verdict=PASS. `NEEDS-RULES` is never cached.

### V7 Test-Trust-Chain (TESTS-PROOF marker)

Writer-DONE is extended with a structured commit-body marker:

```
TESTS-PROOF:
  <test-cmd>: PASS (<N> tests)
  <lint-cmd>: clean
  <fmt-cmd>: clean
  COMMIT_SHA: <sha-of-HEAD-at-test-time>
```

`gate-3-verifier` reads it via `git log -1 --format=%B`. HEAD == COMMIT_SHA: trust, skip re-run. HEAD moved: WARNING + re-run. No marker on 0.14+: BLOCKER. Marker present pre-0.14: WARNING legacy.

### Per-Worktree Cargo Target (since 0.22.1)

`tmux_pair.py` prepends `env CARGO_TARGET_DIR=~/.cache/tmux-pair/cargo-target/<repo-slug>__<wt-slug>/` to the boot command when the project is a Cargo workspace. Each worktree gets its own target directory, so parallel solos on the same project never block on cargo's file-lock. Trade-off: cold rebuild per worktree (a few minutes amortised against a 30..90 min solo run). Since 0.22.4, Phase 7 runs `tmux_pair.py cleanup-target --project <project> --worktree <wt_path>` after worktree removal. The helper refuses paths outside `~/.cache/tmux-pair/cargo-target/` and refuses shared-looking target names without a worktree slug. Pass `--shared-target` to opt back into the legacy single-shared-target behaviour (`<repo-slug>/`) when only one agent is active and maximum cache warmth matters; shared targets are not auto-deleted. Non-Cargo repos skip the env entirely.

### V9 Recon-Cache with Delta-Mode (helper only)

Recon cache paths and TTL are defined for workflow callers at `/tmp/tmux-pair-recon-<repo-slug>-<commit-sha>.json`. `cmd_solo` currently performs fresh recon and does not automatically read the cache or run delta-mode.

### V10 Inline-Gates for Trivial Plans

`task_kind=bug-fix` AND `plan-bullets <= 3` AND `predicted files-touched <= 5`: the agent runs GATE 2 inline in its own context with the 8-item checklist instead of spawning the subagent. `gate-3-verifier` may also run inline when the same trivial-plan condition holds AND the TESTS-PROOF marker is valid for HEAD. `gate-3-code-reviewer` always stays in a subagent. Anti-triggers (force subagent): dirty worktree, formatter failures, ambiguous plan text, `task_kind` in (`feature`, `refactor`). Helper: `python3 scripts/tmux_pair.py inline-gate-decide --plan-file <path> --task-kind bug-fix`.

## Layout

Single pane in the worktree window. No layout-forcing.

## Quick start

```
/run    <project-path> <base> <feature> [task...]
/solo   <project-path> <base> <feature> [task...]
```

The script:

1. Creates a sibling worktree at `<project-parent>/<project-basename>-wt-<feature>`, branch `feature/<feature>`, from `<base>`. If the branch already exists, it is reused.
2. Opens a tmux window named `<project-basename>-<feature>` (truncated to 30 chars).
3. Spawns the agent pane.
4. Schedules the briefing via `sleep 14 && send`, so the agent has time to boot before the message lands.
5. Prints a JSON receipt with the pane id.

## Briefing template

`examples/solo-briefing.md` is the starting template (pointers, deliverables, gates, standards). The bundled script generates a baseline briefing automatically; the template is useful when overriding or hand-authoring after recon.

## Sending messages

The cross-pane primitive is `tmux_pair.py send`:

```
python3 <plugin>/scripts/tmux_pair.py send <pane-id> "<message>"
```

Multi-line messages are submitted via `load-buffer` + `paste-buffer` to avoid the issue where some agent TUIs interpret each newline as a submit. Single-line messages use plain `send-keys -l`. After the text, the helper sends Enter three times with small gaps; this works around agent TUIs that ignore the first Enter when a tool call is in flight. Override with `--no-enter` if needed.

Normal messages get a sender identity prefix automatically. Example: `wr.<feature>` sending `REVIEW-READY: ...` arrives as `[FROM: wr.<feature>] REVIEW-READY: ...`. Messages already starting with `[FROM:` are left unchanged. Slash commands such as `/compact <focus>` are command traffic and are not prefixed. Spawned panes store their stable sender name in `@tmux-pair-sender`.

### Codex file-bridge for long messages (since 0.22.3)

The codex TUI input widget glitches when very long text is pasted into it (visible artifacts: half-rendered lines, mis-wrapped boxes, stuck spinner). For codex panes we skip the paste entirely and route long bodies through a tempfile.

- **Boot commands and shell history**: agent boot commands start as tmux pane
  shell-commands, not as typed input in an interactive zsh prompt. Full
  claude/codex/pi launch lines therefore stay out of `~/.zsh_history`.
- **Initial solo briefings**: `cmd_solo` writes the briefing body to `/tmp/tmux-pair-msg-XXXX.md` before boot and passes the short pointer as Codex's initial CLI prompt. This avoids the post-ready `tmux_pair.py send` path entirely, so `/run ... --agent codex` returns its JSON receipt promptly and Codex starts reading the briefing without a manual re-send. The pane title still carries the solo name; `/rename` is skipped for this boot-prompt path because Codex is already processing the task.
- **Legacy spawn initial briefings**: `cmd_spawn` still uses `_send_briefing_for_agent` after all panes exist, because its briefings need the peer pane IDs. For `codex`, the body is written to `/tmp/tmux-pair-msg-XXXX.md` and a short pointer message is sent into the pane.
- **Re-briefs and plan-updates**: `tmux_pair.py send <pane> --from-file <path>` reads the body from a file. When the target pane runs codex AND the body is multi-line, the helper auto-routes through the same file-bridge.
- **claude / pi panes**: unchanged. Their input widgets handle long pastes via `load-buffer` + `paste-buffer` without rendering bugs, so the direct send path stays.
- **Agent lookup**: every spawned pane stores its agent in the `@tmux-pair-agent` tmux pane option at spawn time. `cmd_send` reads it to decide.

The tempfile is left as-is if codex does not delete it; `/tmp` clears on reboot. The file is world-readable by design so a human can `less` it for debugging.

## Token management and re-briefs

Default claude model: `claude-opus-4-8` (1M context). For 200k-context runs, use `--claude-model claude-opus-4-6`. Compact-watcher threshold scales automatically: 1M → 700k (70%), 200k → 140k.

Default reasoning effort: `xhigh` on both harnesses for the main pane AND reviewer subagents. Codex uses `-c model_reasoning_effort=xhigh` when the installed CLI supports it. Override with `--claude-effort`, `--codex-effort`, `--reviewer-claude-effort`, `--reviewer-codex-effort`.

Long-running runs drift past the model's sweet spot. Helper subcommands:

```
python3 <plugin>/scripts/tmux_pair.py status <pane-id>
python3 <plugin>/scripts/tmux_pair.py compact <pane-id> --briefing-file <path> [--focus "<one-liner>"]
python3 <plugin>/scripts/tmux_pair.py monitor --orch-pane <id> --panes <id> [--threshold-k <N>]
```

Solo does not auto-start the watcher: the agent self-compacts between phases when appropriate.

**Self-compact pattern**: write a self-re-brief file at `/tmp/self-compact-<window>.md` (plan-bullet, current state, next step, relevant standards), send `/compact <focus>` to own pane, after settle read the file and continue.

## Common failure modes

The full list lives in `references/failure-modes.md`. The most common:

- **Send didn't submit.** Symptom: message visible in pane but cursor still in input. Cause: agent TUI ignored the Enter. Fix: re-send with the helper, which retries Enter.
- **Briefing landed before agent booted.** Symptom: message appears at the shell prompt instead of inside the TUI. Cause: 14-second delay too short. Fix: re-send manually after the agent is ready.
- **tmux session crashed mid-run.** Symptom: panes gone, worktree intact. Recovery: re-spawn the pane manually, point it at the existing worktree, re-send the briefing with the current state attached.
- **Pushed without human OK.** Symptom: `git push` happened despite the brief saying "wait for human". Cause: briefing missing or weakly worded. Fix: spell out the push gate explicitly in the briefing template.

## Post-Merge Retro (mandatory)

Default workflow after the solo agent sends `DONE-MERGED`. Phase 7 of the solo workflow has already executed the squash-merge, worktree removal, per-worktree Cargo target cleanup, and branch delete. The retro step remains:

1. **Retro**: solo asks itself a tailored retro question (the pane is still alive after Phase 7) AND spawns 2-3 `Agent` personas in parallel with different perspectives (orchestrator view, writer view, reviewer view), plus one `codex exec "retro"` for an independent fourth view. Expect 200-500 words of factual analysis per source (no praise, weaknesses stated directly). Topics:

   - Phase wall-clock per 7-phase step
   - GATE-2 iterations and which mid-run self-decisions could have been prevented at plan-write time
   - Drive-by / reactive commit share
   - Structural plan errors
   - Hardest test pattern, fmt-drift root cause, Pre-Flight gaps
   - Bullet-count retro (was monolithic correct, or too large?)
   - Phase 7 conflicts and cleanup friction

2. **Pattern synthesis + persist**: solo collects the retros, identifies recurring issue classes (decorator-swallow, cancellation-root-mismatch, fmt-drift, plan-vs-reality-mismatch), and persists:
   - tmux-pair skill (this file): when the pattern is workflow-cross-cutting (Pre-Flight class, plan-drift indicator).
   - Consumer repo: `.claude/rules/*.md` (always-on cross-cutting) or `.claude/skills/<repo>-<topic>/SKILL.md` (path-scoped domain) per Persist-Convention.

3. **Window cleanup**: after pattern-persist:

```bash
tmux kill-window -t <window-name>
```

Worktree, branch, and per-worktree Cargo target are gone since Phase 7; only the tmux window remains for the retro. The retro step is mandatory, not optional. A solo run without a retro fails to persist the most expensive learnings of the run.

## Recurring Pre-Flight Checks (aggregated from retros)

These checks belong in `--with-standards` briefings AND in consumer-repo `.claude/rules/pre-flight-checklists.md`. Aggregated from multiple solo retros, all falsifiable:

- **Decorator-Sweep before Trait-Default-Add**: when adding a default-body trait method (especially lifecycle methods like `shutdown`/`close`/`flush`), run `rg "impl <Trait> for" --type rust` before the review entry, list every implementor, mark each one with two or more forward methods as a decorator, and either add an explicit forward override OR document a no-op rationale in a plan-amendment. Anti-pattern: trait-default no-op is silently swallowed by a decorator.

- **Trait-Param-Honor check**: a trait-method param prefixed with `_` (`_grace`, `_token`) while the trait doc declares the param effective is a silent-discard footgun. Pre-flight: `rg '_[a-z]+: ' <trait-file>` cross-checked against the trait doc. The default body should either honestly ignore the param (and the doc gets updated) or honor it (with a test).

- **Method-Resolution-Collision check**: a new trait method with the same name as an existing inherent impl on an implementor: pre-flight `cargo check -p <crate>` surfaces the ambiguity warning. Anti-pattern: the trait method is silently shadowed by the inherent method.

- **Format-gate discipline**: a "fmt clean" claim requires `cargo fmt -p <crate> --check` (NOT `cargo fmt -p <crate>` without `--check`). Per-crate fmt without `--check` silently rewrites neighbor files and produces drive-by drift. Falsifiable: review entry with "fmt clean" plus `--check` output and exit 0.

- **Mechanical lint-fix pass BEFORE manual LLM edits (hard rule)**: every clippy-cleanup bullet MUST start with `cargo clippy -p <crate> --fix --allow-dirty --lib --bins --examples -- -D warnings`. Run the test-target `--fix` variant only when the repo's lint matrix is known not to generate forbidden test idioms; otherwise run test clippy without `--fix` and fix test-target findings by hand. Pattern from graph-rag retro: test-target `--fix` rewrote result assertions into `unwrap()`, then `unwrap_used` failed. Falsifiable: for every clippy bullet the review entry cites the production `--fix` output (even if zero changes) BEFORE manual fixes, and if test-target `--fix` ran it also cites a same-turn `rg "unwrap\\(|expect\\(" <touched-tests>` audit or the repo-specific reason those calls are allowed. Missing = BLOCK from gate-3-code-reviewer.

- **Source-first Plan-Lock for trait/store/schema/pipeline features**: before Plan-Lock on any task that changes a trait, store backend, migration, policy action, tool op, or consolidation pipeline, the solo agent must read the exact source files, not only recon summaries. Minimum evidence: trait file, one in-memory impl, every production backend impl/migration touched by the plan, and the domain pipeline/tool entrypoint. Falsifiable: the GATE-2 plan includes `file:line` evidence for each irreversible decision such as default-bodied trait methods, no-FK cascade, natural key shape, or fail-open behavior. If a GATE-2 BLOCKER points at an unread source file, the revised plan must cite that file before proceeding.

- **Gate-fix recheck discipline**: after a GATE-2 BLOCKER changes the plan, rerun both plan-check minds on the revised plan. After a GATE-3 reviewer WARNING changes code, rerun at least the reviewer that raised it, plus the smallest relevant tests. Tests alone are not an adversarial recheck. Falsifiable: the phase/gate ledger names the original finding, the changed files, the second verdict, and the test command. If the recheck is skipped, the squash body must carry an explicit WARNING with rationale.

- **Memory-Recon as a mandatory RECON step**: before plan-write, read `MEMORY.md` plus the 3-5 most relevant memory files under `~/.claude/projects/<repo>/memory/`. Mid-run self-decisions that would have been preventable by memory-recon are a drift indicator. **Memory-Freshness Gate**: memory files older than 3 days are a stale-risk flag; the plan-recon must state whether memory was re-validated against current code.

- **Brief-vs-Reality validation before Plan-Lock**: a brief written against an old code state is the most common plan-drift source. Before Plan-Lock: run `cargo clippy -p <crate>` plus `git grep -n "<keyword>"` plus `rg`-evidence for every "verify-first" or "should-be-X" item in the brief. Falsifiable: the Plan-Lock commit cites at least two brief items with current-code evidence SHAs.

- **Parent-worktree dirty gate before solo spawn and Phase 7**: before creating a worktree, the launcher runs `git -C <project> status --porcelain`. If the parent worktree is dirty, stop immediately and ask the user before spawning. The base ref is the user-provided `<base>` / `--base` value and may be local (`main`) or remote (`origin/main`); do not replace it with `origin/HEAD` for preflight. Do not defer this to Phase 7, because a long run turns a simple dirty-tree choice into pressure to commit unrelated files. Phase 7 repeats the same check before `merge --squash`. Pre-existing files may be committed only after an explicit user answer naming that action; then they get a separate commit, separate review note, and separate validation. Falsifiable: the run log contains the pre-spawn status output, a local base such as `main` is accepted without an `origin` remote, and a dirty parent has an AskUserQuestion/answer before any `git worktree add`.

- **Target-dir hygiene before llvm-cov**: `.gitignore` contains `target-cov/` (and similar tool-output dirs) BEFORE the first `cargo llvm-cov` runs. Reactive fix after a crash costs 30+ minutes of recovery.

- **Cross-boundary checks for tool / mcp / hook crates**: on top of the backend-bullet class, a cross-boundary class triggers as soon as the diff touches `<repo>-tool-*`, `<repo>-mcp-*`, or `<repo>-hook-*` crates with message mutation. Three falsifiable checks: (1) tool-output audit (`rg "reqwest::Error|reqwest::Url|::Url\b" <touched-crate>/src/` plus a visual audit of all `output:` / `Value::String(...)` sites in the error path), (2) provider-turn alternation (any hook that returns `Decision::Replace(Vec<Message>)` or `Decision::Inject(Message)` MUST keep user/assistant alternation; test against `validate_turn_sequence(&msgs)`), (3) cap single-source (exactly one enforcing site per resource cap per call-path). Pattern from a past mcp-split retro: url-leak, double-validation, and broken apology-turn alternation only surfaced in the adversarial gate.

- **Squash-body phase/gate ledger**: Phase 7 squash commits must preserve enough review evidence for post-merge retro. Commit body includes approximate wall-clock per phase, GATE-2 iteration count, GATE-3 cycle count, fix-loop causes, final verifier names, and whether incidental lint/fmt cleanup occurred. If incidental clippy cleanup appears, cite the production and test-target `cargo clippy --fix --allow-dirty` passes or state that the cleanup came from a final hard gate with no manual lint-edit class. After the squash commit and before branch/worktree cleanup or DONE-MERGED, run `git log -1 --format=%B` and verify the ledger plus test proof survived; missing proof means amend the squash commit, not "retro can reconstruct it". Stale incidental entries that do not match `git show --name-only HEAD` are a retro BLOCKER. PROJECT.md phase/history anchors must not rely only on feature branch names deleted during Phase 7; include the final squash SHA or a durable base..squash range.

- **PROJECT.md conflict pre-check before Phase 7**: when a run updates PROJECT.md, Phase 7 must check whether base moved on PROJECT.md since branch creation before `merge --squash`. Falsifiable shape: `git -C <project> log --oneline <branch>.. <base> -- PROJECT.md` plus `git -C <project> diff --name-only <base>...<branch> -- PROJECT.md`. If both sides touched it, the solo plans the ordered merge of history blocks before committing instead of discovering it as an unstructured squash conflict.

- **LLM-boundary sink matrix**: any run that changes LLM-facing XML/message boundaries must plan and review every producer and sink before implementation: live request path, injection path, reaction synth path, text attachments, typed media/file pass-through, source-attribute escaping, idempotency trust boundary, and legacy strip/migration behavior. Missing a non-primary producer is a plan-quality BLOCKER, because primary-path tests can pass while a secondary text path still bypasses the boundary.

## Build / compile-speed findings (mcp-split retro)

From a bench pass at the end of a recent mcp-split round. Single-crate compile/link on macOS is NOT the dominant bottleneck:

| Configuration | Wallclock (example-crate nextest) |
|---|---:|
| Baseline warm | 3.54s |
| Touch-rebuild | 4.01s |
| Cold-clean | 4.60s |
| sccache + CARGO_INCREMENTAL=0 warm cache | 2.56s |
| lld swap | 26.22s (RUSTFLAGS breaks all caches, not meaningful) |

Findings:

- **shared-target-dir (V8) already delivers the main win** cross-worktree (~80% deps-cache hit between chained runs). Per-crate cold-clean lands at 4-5s, which is fine.
- **sccache is marginal** when shared-target-dir is active. sccache only helps with `CARGO_INCREMENTAL=0`, which slows the edit loop. Trade-off: only worth it for fresh-target-dir cold starts (CI, branch swap).
- **lld on macOS not recommended**: Apple's ld64 is already optimized for Mach-O. The RUSTFLAGS swap forces a full deps recompile and breaks all caches.
- **mold on macOS: skip**. mold is Linux-focused; macOS support is not a reliable path.

**Real time sinks in the solo workflow** (not build):

1. **Cargo invocations x bullet count**: 8-12 cargo calls per bullet (test, clippy-lib, clippy-tests, fmt, coverage) x ~4s cargo overhead = ~40s of pure cargo overhead per bullet. At 8 bullets that is ~320s purely on cargo-resolve loops.
2. **Adversarial-gate latency**: ~30 minutes per solo run (GATE-2 subagent + codex CLI + GATE-3 verifier + code-reviewer + codex). Token-throughput bound.
3. **Subagent token throughput**: model bound.

**Possible workflow levers** (higher impact than build-tuning):

- Parallelize per-bullet gates (clippy + test in parallel instead of sequential). Achievable via separate background bash calls.
- nextest archive for CI reuse (`cargo nextest archive`).
- sccache only as opt-in env (`RUSTC_WRAPPER=sccache CARGO_INCREMENTAL=0`) for cold-worktree starts, NOT default.
- Cut bullets by API surface rather than by crate: fewer round-2 fixes thanks to clean layer decisions upfront.

**Anti-pattern**: build bench without workflow bench. If cargo invocations x bullet count plus gate latency are not measured alongside, the wrong lever is being optimized.

## Cleanup (auto + manual)

The solo agent removes the worktree, per-worktree Cargo target, and branch automatically in Phase 7 (Auto-Squash-Merge). Worktree removal comes before `git branch -D`: Git refuses to delete a branch that is still checked out in any worktree. Cargo target cleanup runs through `tmux_pair.py cleanup-target`, not raw `rm -rf`, so shared targets and non-tmux-pair paths are protected. The only manual step left is `tmux kill-window` after pattern-persist.

Before 0.20.0 cleanup was fully manual and order-sensitive (retro first, then cleanup). Since 0.20.0 the solo agent performs the squash, branch-delete, and worktree-remove itself, and the retro step is the only remaining human duty.

## Companion skills (bundled)

The plugin ships two companion skills, both plugin-namespaced:

- **`/tmux-pair:gepa`**: Genetic-Pareto prompt/text-artifact optimization (paper arXiv:2507.19457). Opt-in after rules-bootstrap to optimize freshly generated `.claude/skills/*/SKILL.md` or `.claude/rules/*.md`. Skill files in `skills/gepa/`.
- **`/tmux-pair:dg`**: Dinesh-vs-Gilfoyle adversarial code review. Two AI personas (attacker + defender) debate a diff or file until the defender concedes, defends, or the round limit hits. Useful as an optional pre-GATE-3 step on security/concurrency/auth/crypto/migration bullets. Skill files in `skills/dg/`.

External companion (NOT bundled): `code-simplifier` from `claude-plugins-official` for refactor-passes after a feature lands.

## Additional resources

### References

- **`references/gated-workflow.md`**: 7-phase solo workflow, subagent prompt templates, gate event vocabulary, gate-specific failure modes.
- **`references/failure-modes.md`**: common failure modes with diagnostics, recovery, prevention.

### Examples

- **`examples/solo-briefing.md`**: solo briefing template.
