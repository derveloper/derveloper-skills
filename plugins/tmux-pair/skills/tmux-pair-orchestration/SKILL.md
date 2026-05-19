---
name: tmux-pair-orchestration
description: This skill should be used when the user asks to "spawn a solo with self-review", "spawn a coordinated agent team", "run multiple agents on this", "set up an orchestrator + writers + reviewers", "use the tmux-pair workflow", "/run for this task", or otherwise wants to run a single agent or a coordinated 3-to-5-pane spawn-team (orchestrator + writers + reviewers) in tmux panes wired up via git worktrees. Covers solo (single agent + gated subagent-driven self-review) and spawn (coordinated team sized 3..5 via --size and --parallel-writers), plus the /run auto-entry that recommends solo vs spawn from a short repo + task recon. Includes the pair protocol (REVIEW-READY -> REVIEW loop inside a spawn), when to choose solo vs spawn (and which --size), durable standards (claude --append-system-prompt-file + codex AGENTS.md), gated workflow (Clarify -> Reviewer-Readiness -> Plan-Check -> Loop -> Final-Verify with rules-bootstrap loop, PROJECT.md care, language templates for 7 stacks, REVIEW-READY-3-Felder, CLARIFY-NEEDED, Plan-Update-Commit, COMPLETE-Format), sender identity prefixes, explicit parallel-plan markers, engineer subagent strategy with repo-specific subagent detection (`.claude/agents/<repo>-*.md` listed in briefings), bundled companion skills (gepa for prompt-optimization, dg for adversarial code review), Compact-Watcher with model-aware threshold, --claude-model + --no-worktree flags, briefing templates, and recovery from common failure modes.
version: 0.17.0
---

# tmux-pair-orchestration

Run one to five coding agents on a single task. Each agent lives in its own tmux pane, all panes share a fresh `git worktree`, and the agents talk peer-to-peer through a small Python helper.

This skill applies whenever the user wants to set up such a solo/spawn, monitor it, draft briefings, recover from a stuck loop, or decide between modes. The default entry-point is `/run`, which performs a short recon and recommends solo vs spawn (with a recommended `--size` for spawn).

## The two modes

| Mode | Agents | Layout | Human role |
|------|--------|--------|-------------|
| **solo** | one agent (gated 6-phase, subagent-driven self-review) | single pane in a fresh worktree | hands-off after spawn; sees only DONE / BLOCKER pings |
| **spawn** | orchestrator + 1-2 writers + 1-2 reviewers, sized via `--size 3..5` | orchestrator on top (full width), engineers below; second writer / reviewer stacked vertically under their primary | hands-off after spawn, only sees major-event pings via the orchestrator |

A third top-level entry-point, `/run`, performs a quick repo + task recon and dispatches to solo or spawn with a recommended `--size`. Explicit user-mode flags (`--solo`, `--spawn`) override the recommendation.

Default agent assignments (overridable):

- writer: `claude` (recon-strong, follows briefings, integrates plan + subagent feedback cleanly)
- writer-2 (when `--parallel-writers`): `claude`
- reviewer: `codex` (terminal-driven, sharp on adversarial review with high reasoning effort, produces falsifiable findings)
- reviewer-2 (when reviewers >= 2): `codex`
- orchestrator: `claude` (recon + briefing + filtering)

Reviewer panes always boot at the harness top reasoning tier regardless of writer/orchestrator budget (claude-reviewer `xhigh`, codex-reviewer `high`). Effort defaults section below has the override flags.

These are defaults baked into the bundled script. Different agent CLIs work fine: point `--writer-agent`, `--writer-2-agent`, `--reviewer-agent`, `--reviewer-2-agent`, `--orchestrator-agent` at any name registered in `~/.config/tmux-pair/agents.json`. Built-in: `claude`, `codex`, `pi` (the users Custom-CLI). pi unterstützt alle Rollen, bringt aber zwei Einschränkungen: kein mid-session Model-Switch (kein `/model` Slash-Command, nur Pane-Restart) und kein `/compact`-Equivalent (Compact-Watcher pingt pi-Panes nicht; bei langen Runs Pane-Restart einplanen).

## Dynamic team sizing (spawn)

`/spawn --size N` picks one of four presets. `--parallel-writers` toggles between two-reviewers-and-one-writer and one-reviewer-and-two-writers when `--size 4` is chosen. `--size 5` activates both presets.

| `--size` | `--parallel-writers` | Writers | Reviewers | Orchestrator | Use when |
|----------|----------------------|---------|-----------|--------------|----------|
| 3 (default) | n/a | 1 | 1 | 1 | standard task, one reviewer is enough |
| 4 | off (default) | 1 | 2 | 1 | security-sensitive / risky: two reviewers consolidate |
| 4 | on | 2 | 1 | 1 | parallel-friendly bullets, writers split disjoint files |
| 5 | n/a | 2 | 2 | 1 | big feature with both signals |

`--parallel-writers` requires `--size 4` or `--size 5`; passing it with `--size 3` errors out at argparse time.

### Dual-review (reviewers >= 2)

Per cycle:

1. Writer pings `REVIEW-READY` to BOTH reviewers in parallel.
2. Both reviewers review independently: no crosstalk before they have their own findings.
3. Reviewers swap findings (`REVIEWER-FINDINGS:` to peer), give each other a `PEER-REVIEW:` (agree, disagree, missed-this).
4. Each reviewer sends a final `REVIEW-FINAL (Reviewer):` to the orchestrator.
5. Orchestrator consolidates both reports into ONE merged review (keep all unique BLOCKERs, dedupe overlaps, surface contradictions with context).
6. Orchestrator sends ONE `REVIEW-CONSOLIDATED:` to the writer. Reviewers never speak directly to the writer.

When to opt in (size 4 default, or size 5): risky refactors, security-sensitive code, blast-radius changes, anything where you want diversity of opinions on the diff.

### Parallel-writers (writers >= 2)

Per plan:

1. Orchestrator partitions plan-bullets into DISJUNKT sub-sets per writer (`B3 -> wr1`, `B4 -> wr2`). Disjoint means no shared files (sonst Merge-Konflikt im Worktree).
2. Orchestrator briefs writer-1 and writer-2 SEPARATELY, each with their bullet-subset.
3. Both writers ping REVIEW-READY independently to the reviewer. No direct sync between writers.
4. Reviewer trackt zwei Writer-Streams. Sequential REVIEW cycles per bullet, not batched.
5. Bei impliziter File-Kollision: writer pingt `CLARIFY-NEEDED` an Orchestrator, der re-partitioniert.

When to opt in (size 4 + `--parallel-writers`, or size 5): plan has parallel-friendly bullets with disjoint files (split a module into N backends, bulk migration across independent areas).

## Solo (gated, self-driven)

Solo runs ONE agent in a fresh worktree with a 6-phase self-driven workflow:

1. **Recon**: 4-6 parallel subagent spawns, each <300 words with Datei:Zeile pointers.
2. **Plan + Self-Check**: bullet plan with parallel-markers, adversarial GATE-2 via `tmux-pair:gate-2-plan-check` subagent. Max 2 plan iterations.
3. **Implementation**: parallel subagents per independent bullet (disjoint files); sequential bullets in the main pane.
4. **Self-Review**: two subagents in parallel: `tmux-pair:gate-3-code-reviewer` (diff review for bugs/security/anti-patterns) and `tmux-pair:gate-3-verifier` (plan coverage + workspace gates). Max 3 review cycles.
5. **PROJECT.md + Skill-Persist**: Phase block in PROJECT.md, Decisions, domain knowledge as Skill under `.claude/skills/<repo>-<topic>/SKILL.md` (Persist-Convention; Rules only for cross-cutting always-on items).
6. **Commit + DONE-Ping**: conventional commit, workspace-gate green, worktree clean, then ping the human.

Default flag set: `--no-gated` for trivial tasks where subagent-driven recon/plan/review is overkill (e.g. doc tweak, single-file rename). Default ON. Worktree default; `--no-worktree` opts out.

### Repo-specific subagents (auto-detected)

When the spawn script sees `.claude/agents/<repo>-*.md` files in the target repo, it lists those subagents in the briefing. The solo (and spawn) briefings instruct the agent to prefer those domain experts over `general-purpose` for Recon/Impl/Review subagent spawns. They know the repo's domain vocabulary, architecture-constraints, and skill files.

Detection logic: filename stem starting with `<project.name>-` (e.g. `example-project-kernel.md` in a `example-project` repo). Falls back to "no repo-subagents listed" if the directory is missing or empty.

## `/run` auto-entry

`/run <project> <base> <feature> [task]` is the default entry-point. It performs a short clarify + repo recon + recommendation, then dispatches to `/solo` or `/spawn`.

Decision logic (skipped when the user passes `--solo` or `--spawn` explicitly):

1. **Task clarification**: if `<task>` is missing or ambiguous, ask once via `AskUserQuestion`.
2. **Repo recon**: inspect size, language stack, `.claude/agents/`, `.claude/rules/`, and grep for keywords from `<task>` to estimate affected file count.
3. **Mode recommendation**:
   - **solo** for self-contained tasks (rename, doc cleanup, single-file fix, lint/format pass) with small affected file count and shallow recon.
   - **spawn --size 3** for non-trivial tasks where one writer + one reviewer suffices (default for most features).
   - **spawn --size 4** (dual-review) for security-sensitive code, auth/crypto/migration territory, or when cross-checking is explicitly wanted.
   - **spawn --size 4 --parallel-writers** for tasks with obvious parallel-friendly sub-tasks on disjoint files.
   - **spawn --size 5** when both dual-review and parallel-writers are warranted.
4. **Confirm with user** (single `AskUserQuestion` with the recommendation as Option 1 (Recommended)) when the recommendation is non-obvious. Trivially-obvious cases proceed without confirmation; the recommendation is flagged in the spawn output.
5. **Invoke** the picked mode with the appropriate flags.

`/run --solo` / `/run --spawn` skip the recommendation and dispatch directly. Useful when the user already knows the mode but wants the same flag-forwarding convenience as `/run`.

## When to use which mode

Choose **solo** when:

- the task is self-contained and adversarial self-review via subagents is enough
- the human wants to step away and trust the gates (`gate-2-plan-check`, `gate-3-code-reviewer`, `gate-3-verifier`)
- doc cleanup, rule-to-skill migration, repo-wide rename, plugin-update with workflow consistency check

Choose **spawn** when:

- the task spans many files or unfamiliar code
- continuous orchestrator-mediated review is worth the extra panes
- the human wants to step away and only get pinged on real events
- a dedicated agent doing recon and writing briefings will save more time than it costs
- the failure mode "engineer briefs itself and misses the real problem" is plausible

Pick the spawn `--size` from the dynamic-sizing matrix above. See `references/solo-vs-spawn.md` for a longer decision matrix with worked examples.

## Durable standards

Standards survive `/compact` and context resets because they sit in the system prompt, not in the briefing user-message that gets summarised on compaction.
Briefings are slim by default: task-focused and compact.

- **claude panes** boot with `--append-system-prompt-file <path>` pointing at `/tmp/tmux-pair-durable-<window>-<role>.md`. The file is generated per-spawn from a single in-script constant (`DURABLE_STANDARDS_PROMPT`) so updates to standards land in the next spawn automatically.
- **codex panes** read `AGENTS.md` from the worktree root. The plugin writes that file when a real worktree is created (i.e. not when `--no-worktree` is passed). If the repo already owns an `AGENTS.md`, the plugin leaves it alone: repo standards win.
- **pi panes** boot with `--append-system-prompt <path>` (the users Custom-CLI, `~/.pi/agent/`). pi liest zusätzlich `AGENTS.md` und `CLAUDE.md` via Default-Discovery, also wirkt der codex-Pfad transitiv mit. Default-Model `qwen3-coder-next` via Default-Provider `cortecs`, default `--thinking high`. Override per Spawn via `--pi-provider`, `--pi-model`, `--pi-thinking`. Bekannte Beschränkungen: kein mid-session `/model`-Wechsel (Pane-Restart nötig) und kein `/compact`-Equivalent (Compact-Watcher pingt pi-Panes nicht).
- **`--with-standards`** appends the durable standards bundle to briefings (reviewer standards, recall discipline, bullet-start ritual, pair protocol).
- **`--greenfield`** enables `--with-standards` plus greenfield pre-flight.
- **`--no-worktree`**: if codex is one of the spawned roles, standards are auto-enabled in the briefing so codex still receives durable standards context even without a workspace `AGENTS.md` write.
- **`agents.json` overrides** are respected: if the user has remapped `claude` to a wrapper or alternative binary, the plugin does NOT inject `--append-system-prompt-file` blindly. The wrapper can read the standards file itself.

The standards block covers: real Umlaute (no ASCII substitutes), Conventional Commits with no `--no-verify` and no AI-co-author trailer, the REVIEW-READY 3-field format, the honesty protocol (past-tense claims need same-turn tool evidence), drift signals (em-dashes, progress markers, ALL-CAPS headers, "should I"-after-clear-directive), the `incidental:` format for PostToolUse-hook fmt drift, the worktree-as-sandbox rule, the no-pre-existing-issues rule, recall-discipline (cite the relevant rule + memory before sensitive actions), and the bullet-start ritual (class + relevant rules + common BLOCKER-classes before the first edit on a bullet).

## Gated workflow (default)

`/spawn` enforces five quality gates before code lands on the branch; `/solo` enforces the 6-phase self-driven variant (Recon -> Plan+GATE-2 -> Impl -> GATE-3-self-review -> PROJECT.md+Skill-Persist -> Commit). The bundled briefings encode the gates plus the task-specific flow; optional standards/gate procedure blocks are included with `--with-standards` or `--greenfield`. This is the high-level shape for spawn:

```
Recon -> GATE 1 Clarify -> GATE 1.5 Reviewer-Readiness -> Plan -> GATE 2 Plan-Check -> Implementation Loop -> GATE 3 Final-Verify -> Human merges
```

- **GATE 1 (Clarify)**. The orchestrator calls `AskUserQuestion` directly in its own pane. The human only sees a `GATE-1-ESCALATE` if a question is outside the orchestrator's authority. Engineers wait for `PLAN-LOCKED:`.
- **GATE 1.5 (Reviewer-Readiness)**: one scoped subagent (`tmux-pair:reviewer-readiness-check`, Sonnet 4.6, Read+Grep+Glob+Bash, NO Edit/Write) reads `.claude/rules/*.md` and scores an 8-item checklist (style, tests, architecture, anti-patterns, naming, security, build, domain). On `NEEDS-RULES`, the orchestrator runs a bootstrap loop: per gap one `AskUserQuestion`, then `tmux-pair:rules-bootstrap` (Sonnet 4.6, R+G+G+B+Edit+Write) bakes `.claude/rules/<topic>.md` from plugin language templates (Rust, TypeScript, Python, Go, JavaScript, Java, generic) + repo recon + user answers, then re-run readiness-check. Loop terminates at READY or after iteration 3 with user-decided abort/partial-coverage/manual-amend. Optional opt-in `/gepa` pass after fresh rules; the plugin does not call `/gepa` automatically.
- **GATE 2 (Plan-Check)**: one scoped subagent (`tmux-pair:gate-2-plan-check`, Sonnet 4.6, Read+Grep+Glob+Bash, NO Edit/Write tools) verifies the plan goal-backward AND checks plan quality. Every bullet must carry either a parallel marker such as `B3 || B4 [parallel]` or a sequencing marker such as `B3 -> B4 [sequenziell: shared file]`. `BLOCKER` escalates to human, no auto-retry. Scoped tools = the agent structurally cannot commit code instead of just verdicting.
- **Implementation Loop**: standard pair protocol (`REVIEW-READY` -> `REVIEW` -> fix -> `DONE`). Smart test subset per cycle (only diff-touched tests), full suite + lint + build pre-DONE. PROJECT.md care is mandatory for feature and refactor bullets that change package map, feature surface, design decisions, or implementation history. Engineers use subagents for parallel recon files, parallel test suites, and independent fix branches when that keeps the main pane lean. Mid-run findings are persisted to memory + rules + engineer-briefing-amendment, not just discussed in-pane.
- **GATE 3 (Final-Verify)**. Two parallel scoped subagents check the diff: `tmux-pair:gate-3-verifier` (Haiku 4.5, runs build/test, checks plan-bullet coverage and PROJECT.md care) + `tmux-pair:gate-3-code-reviewer` (Sonnet 4.6, adversarial diff review). Both PASS: orchestrator pings the human with `COMPLETE` (spawn) or the solo agent pings the human directly.

The implementation loop adds six protocol elements that the briefings enforce:

- **REVIEW-READY 3 mandatory fields**: every `REVIEW-READY:` ping carries (1) what changed (file:line + LOC-diff), (2) verification (`workspace-gate=PASS` + test counts, or `workspace-gate=N/A doc-only`), (3) plan-bullet/pain reference. Pings without these fields are blocked by the reviewer without code review.
- **CLARIFY-NEEDED**. When an engineer hits a user-decision question mid-loop (scope, behavior, UX, architecture choice, naming conflict, trade-off not in the plan), they ping `CLARIFY-NEEDED: <question + 2-4 options>`. The orchestrator handles it with its own `AskUserQuestion`. Engineers do NOT decide user-facing questions on their own.
- **Plan-Update-Commit**. If a bullet hits a hard cap (LOC limit, file-size cap) or the estimate drifts more than ~50%, the writer commits a `docs(plan-amendment): ...` BEFORE the implementation commit that breaks the cap. `REVIEW-READY` on a bullet with documented drift but no preceding amendment commit is a `BLOCK`.
- **Parallel markers**. Plans mark independent bullets as `B3 || B4 [parallel]` and ordered bullets as `B3 -> B4 [sequenziell: <reason>]`. GATE 2 blocks missing markers and warns when independent work is needlessly serial.
- **PROJECT.md care**. Writers update project-local `PROJECT.md` for feature and refactor bullets that change package map, feature surface, design decisions, or implementation history. Reviewers sign off on the update or on a justified skip for refactor, test, or docs-only bullets with no feature-surface change. If no `PROJECT.md` exists, the orchestrator asks whether to bootstrap a human-maintained skeleton. `~/git/example-project/PROJECT.md` is the format and detail-depth example.
- **COMPLETE-Ping format**. Orchestrator sends `COMPLETE: <Phase>. gate-3=PASS via <verifier-name + code-reviewer-name>. <diff-stat>. Bezug: <plan goals all met>.` only AFTER GATE 3 returned PASS, never before.
- **Recall-Discipline + Bullet-Start-Ritual**: engineers cite the relevant rule + memory entry before any sensitive action (commit, push, external API), and post a class + rules + common BLOCKER-classes block before the first edit on each new plan-bullet.

Cross-cutting:

- **Plan quality is enforced.** A skeletal "implement X" plan blocks at GATE 2.
- **Context economy applies to every agent.** Heavy research, deep codebase reads, and web lookups go to subagents (one message, multiple parallel Task calls when independent). Diff-first reviews. Targeted Read-ranges over full-file dumps.
- **Edit efficiency is part of the plan.** Pattern replace at >3 sites is a `sed`-job. Boilerplate generation = template + substitution. The plan names the tool.
- **Few, descriptive commits.** Engineers commit at logical-step granularity during the loop; the human squashes before merge to `main`. Commit messages must be substantial enough that a meaningful squash message can be distilled.

Greenfield repos (no `CLAUDE.md`, no `.claude/rules/`) are handled by GATE 1.5 automatically: the readiness-check returns `NEEDS-RULES` with all 8 topics as gaps, the bootstrap loop generates the full rules set from plugin templates + user answers + repo recon, and engineers are briefed only AFTER rules exist. Plan stays focused on the actual feature work; rules-generation is no longer a plan bullet.

The full workflow with subagent prompt templates, gate event vocabulary, and failure modes is in `references/gated-workflow.md`. Gate events extend the base pair-protocol vocabulary documented in `references/pair-protocol.md`.

## Smart workflow (V1-V5)

The workflow is unattended by default. The orchestrator handles small, reversible decisions inside the documented threshold, logs every self-decision in `COMPLETE` AND persists every self-decision in the consumer repo's `PROJECT.md` under Implementation History, and only pauses for decisions that change scope, budget, external dependencies, or security posture. Pass `--interactive` to `/spawn` when the user wants every self-decision to become a pause point.

### V1 Reviewer-Trivial-Fix-Inline

Reviewers may include an inline patch when a finding is under 20 LOC and is clearly isolated.

Trigger:
- cosmetic change
- typo
- missing-doc addition

Anti-trigger:
- architecture question
- security finding
- test-logic error
- more than 20 LOC

Format:

````text
INLINE-FIX: <bullet>
```diff
<unified-diff>
```
END-INLINE-FIX
````

Writer behavior: apply the patch silently with `git apply`, then ACK `applied B<N> inline-fix (X lines)`. The writer may also fix a WARNING when it matches the same trivial pattern.

### V2 Orchestrator-Direct-Decision-Threshold

| Decision class | Default action |
|----------------|----------------|
| Style finding already APPROVE-worthy | Self-decide and log rationale in `COMPLETE`. |
| Test coverage edge case with clear risk assessment | Self-decide and log the risk note. |
| Optional-vs-required default with existing repo precedent | Self-decide by repo pattern. |
| Naming convention with repo-pattern match | Self-decide by local convention. |
| Plan revision after GATE-2-BLOCKER with clear fix direction | Self-decide and send the revised plan. |
| Budget, stakeholder approval, external service status, real scope expansion, security trade-off | Escalate to the user. |

Every self-decision is recorded in the final `COMPLETE` ping as a one-line rationale AND persisted as a row in the consumer repo's `PROJECT.md` under a new Implementation-History phase heading (with phase marker, implementation anchor SHA, and a Markdown table of `ID | Decision | Rationale`). This is a full audit trail, not a sample. The `COMPLETE` ping is ephemeral context; `PROJECT.md` is the permanent record. A spawn run is not considered complete without the `PROJECT.md` entry.

### V3 Adaptive GATE-Strictness

`task_kind` has three allowed classes: `bug-fix`, `feature`, and `refactor`. The orchestrator classifies it during recon and passes it to GATE 2, GATE 3 verifier, and GATE 3 code-reviewer subagents.

| task_kind | Subagent impact |
|-----------|-----------------|
| `bug-fix` | Keep core coverage, specificity, rules, plan quality, and test checks active. Skip wiring, parallel markers, UI-smoke, and PROJECT.md only for one-file fixes with no new surface. |
| `feature` | Default strictness. All checklist items stay active. |
| `refactor` | Treat coverage as preservation and tests as regression evidence. Skip wiring and UI-smoke only when the diff has no behavior or UI surface change. Keep design-decision and implementation-history checks where relevant. |

### V4 Engineer-Auto-Resolve WARNINGs

GATE 3 verdicts use three severities:

- BLOCKER: correctness, security, maintainability, explicit project-rule violation, dirty worktree, or failed verification. Engineers enter the fix-loop.
- WARNING: preference or nice-to-have. Engineers may ignore it, but the orchestrator records follow-up-memory and PROJECT.md when relevant.
- NOTE: info-only context for reviewer or verifier memory.

### V5 Unattended-Default

Default mode is unattended in both solo and spawn. Without `--interactive`, V2 self-decisions proceed autonomously and are logged in both `COMPLETE` and `PROJECT.md`. With `--interactive`, the orchestrator (or solo agent) pauses before every self-decision and asks the user via `AskUserQuestion`. The flag changes briefing text only; it does not add a Python runtime branch after spawn.

## Smart workflow (V6-V10)

V6-V10 introduce caching, trust-chains, and inline decisions for trivial plans. All five are additive: every existing spawn continues to work; the smart-features only kick in when caches are present or thresholds are met. Two new spawn flags govern opt-out:

- `--no-cache`: disables readiness-cache (V6) and recon-cache (V9) reads and writes. Cache files on disk are left untouched.
- `--no-shared-target`: disables CARGO_TARGET_DIR sharing (V8). Each agent builds into the worktree-local `target/`.

### V6 Readiness-Cache (24h TTL)

`reviewer-readiness-check` is the most expensive recurring gate: it scans `.claude/rules/*.md` and scores the 8-item checklist on every spawn even when the rules and commit haven't moved. V6 caches the verdict.

- Cache key: `sha256(.claude/rules/*.md content concatenated, sorted by filename)` + `<commit-sha>`.
- Storage: `~/.cache/tmux-pair/readiness/<repo-slug>-<rules-hash[:16]>-<commit>.json` with `{verdict, timestamp, missing-items}`.
- Cache-Hit (file exists + mtime < 24h + verdict=PASS): the orchestrator skips spawning the subagent and logs `readiness cached from <ts>, key <rules-hash[:8]>`.
- Cache-Miss or STALE (>24h): normal subagent spawn. On PASS the orchestrator writes the cache atomically (same-dir tmp+rename) so the next run sees the hit.
- `NEEDS-RULES` verdicts are never cached: the rules-bootstrap loop must always run when rules are missing.
- Cache-Bust: `--no-cache` (also disables V7 marker trust at the agent layer when the agent uses it for a sanity check, plus V9 recon-cache).

### V7 Test-Trust-Chain (TESTS-PROOF marker)

Writer-DONE is extended with a structured marker that the gate-3 verifier can trust without re-running the full suite when HEAD hasn't moved.

```
TESTS-PROOF:
  <test-cmd>: PASS (<N> tests)
  <lint-cmd>: clean
  <fmt-cmd>: clean
  COMMIT_SHA: <sha-of-HEAD-at-test-time>
```

The marker lives in the commit-message body of the bullet commit. `gate-3-verifier` reads it via `git log -1 --format=%B` (or the helper subcommand `python3 scripts/tmux_pair.py parse-tests-proof --commit HEAD`):

- HEAD == `COMMIT_SHA`: trust, skip re-run, log `tests trusted from sha <sha>`.
- HEAD has new commits since the marker: re-run + `WARNING test-marker stale, re-run needed`.
- No marker present and the commit is from a 0.14+ run: `BLOCKER missing test-marker`.
- No marker present and the commit predates 0.14: re-run + `WARNING legacy commit, no marker`. Backward-compat for older sessions.

Reviewer panes inside the spawn use the marker for spot-checks and skip clippy/test re-runs by default. Optional spot-checks against touched files stay possible.

### V8 Cargo-Target-Sharing

`tmux_pair.py` prepends `env CARGO_TARGET_DIR=~/.cache/tmux-pair/cargo-target/<repo-slug>/` to every boot command in `cmd_spawn` when the project is a Cargo workspace and `--no-shared-target` is not set. The target dir is shared across worktrees of the same repo; cargo's own lock-file handles concurrency.

- `<repo-slug>` is `basename(repo-root)` with non-alphanumeric replaced by `_`.
- Non-Cargo repos skip the env entirely (the helper returns `None` when no `Cargo.toml` or `crates/*/Cargo.toml` is found within two levels).
- Parallel worktrees racing on the same target may experience short `cargo build` blocks while a peer holds the lock. This is expected and preferable to N independent rebuilds.
- Opt-out per spawn: `--no-shared-target`.

### V9 Recon-Cache with Delta-Mode (1h TTL)

The orchestrator's recon output (file map, crate list, PROJECT.md snapshot, key-function inventory) is dumped as structured JSON to `/tmp/tmux-pair-recon-<repo-slug>-<commit-sha>.json`.

- Subsequent spawn invocations on the same commit within 1h read the cache, then run a delta-recon for files with `mtime > cache-time`.
- The reviewer-readiness subagent may also consume the recon JSON to skip its own scan of unchanged files.
- Cache-Bust: `--no-cache`.

### V10 Inline-Gates for Trivial Plans

When `task_kind=bug-fix` AND `plan-bullets <= 3` AND `predicted files-touched <= 5`, the orchestrator runs GATE 2 (Plan-Check) inline in its own pane with the 8-item checklist instead of spawning the subagent.

- `gate-3-verifier` may also run inline when the same trivial-plan condition holds AND the TESTS-PROOF marker is valid for HEAD.
- `gate-3-code-reviewer` always stays in a subagent: inline adversarial review eats too many tokens and benefits from a fresh context.
- Anti-Triggers (always force the subagent path): dirty worktree, formatter failures, ambiguous plan text, task_kind in (`feature`, `refactor`).
- Helper: `python3 scripts/tmux_pair.py inline-gate-decide --plan-file <path> --task-kind bug-fix` returns a JSON decision payload with `inline` plus the count rationale.

## Pair protocol (the core loop inside a spawn)

Inside a spawn, the writer-reviewer loop is called the pair protocol. The vocabulary is identical regardless of `--size`; only the addressing differs when dual-review or parallel-writers are active.

1. Writer makes a meaningful change (one logical step), runs build/lint/tests locally if cheap, and pings the reviewer:

   ```
   python3 <plugin>/scripts/tmux_pair.py send <reviewer-pane> "REVIEW-READY: <one-line summary>"
   ```

   With dual-review: writer pings BOTH reviewers in parallel.

2. Reviewer reads the change, the tests, and the writer's summary. Replies with one of:

   - `REVIEW: APPROVE`: change is good as-is.
   - `REVIEW: <findings>`: concrete, falsifiable findings (file:line, problem, suggested direction). No vague "consider improving".

   With dual-review: reviewers send `REVIEW-FINAL` to the orchestrator, who sends one consolidated `REVIEW-CONSOLIDATED:` back to the writer.

3. If `APPROVE`, writer commits (Conventional Commits, no `--no-verify`, no AI co-author trailer) and pings `DONE: <commit-sha> <branch-state>`.

   If findings, writer fixes, pings `REVIEW-READY` again. Loop.

4. If the loop stalls (disagreement, missing info, suspected upstream bug) either side pings `BLOCKER: <what>` to the orchestrator.

The full protocol with all event types and edge cases lives in `references/pair-protocol.md`.

## Human-offload (spawn mode)

The point of spawn mode is that the human delegates the relay to the orchestrator. The human:

- sends the initial task only to the orchestrator, NOT to the engineers
- sees only orchestrator-tagged pings: `[Orchestrator <window>] MAJOR-STEP / BLOCKER / DONE / ABORT`
- does NOT relay between writers and reviewers
- does NOT clean up worktrees during the run; cleanup decisions stay with the human, but only after `DONE`

The orchestrator does:

- recon (read upstream docs, grep the codebase, identify pointers)
- write writer briefing(s) AND reviewer briefing(s) as separate messages
- watch the loop at high level (capture-pane + nudge if silent > 10 min)
- partition plan-bullets between writers when parallel-writers is active
- consolidate reviews when dual-review is active
- filter engineer pings: only forward MAJOR-STEP, BLOCKER, DONE, ABORT to human

The orchestrator does NOT code, does NOT review, does NOT commit, does NOT decide on cleanup.

## Layout details

**Solo:** single pane in the worktree window. No layout-forcing needed.

**Spawn (`main-horizontal`, base layout for `--size 3`):**

```
+---------------------+
|    Orchestrator     |
+----------+----------+
|  Writer  | Reviewer |
+----------+----------+
```

**Spawn `--size 4` (dual-review, reviewer-2 stacked under reviewer-1):**

```
+---------------------+
|    Orchestrator     |
+----------+----------+
|          |Reviewer-1|
|  Writer  +----------+
|          |Reviewer-2|
+----------+----------+
```

**Spawn `--size 4 --parallel-writers` (writer-2 stacked under writer-1):**

```
+---------------------+
|    Orchestrator     |
+----------+----------+
| Writer-1 |          |
+----------+ Reviewer |
| Writer-2 |          |
+----------+----------+
```

**Spawn `--size 5` (both stacked):**

```
+---------------------+
|    Orchestrator     |
+----------+----------+
| Writer-1 |Reviewer-1|
+----------+----------+
| Writer-2 |Reviewer-2|
+----------+----------+
```

The base layout is forced via `select-layout main-horizontal` when neither dual-review nor parallel-writers is active. With either stack-extension, the plugin skips the automatic layout-force so the manual vertical splits stay intact.

## Quick start

All commands assume the human is already inside a tmux session.

```
/run    <project-path> <base> <feature> [task...]     # auto-recommends solo vs spawn
/solo   <project-path> <base> <feature> [task...]
/spawn  <project-path> <base> <feature> [task...] [--size 3|4|5] [--parallel-writers]
```

The script:

1. Creates a sibling worktree at `<project-parent>/<project-basename>-wt-<feature>`, branch `feature/<feature>`, from `<base>`. If the branch already exists, it is reused.
2. Opens a tmux window named `<project-basename>-<feature>` (truncated to 30 chars).
3. Spawns the agent panes and forces the chosen layout.
4. Schedules the briefing(s) via `sleep 14 && send`, so the agents have time to boot before the message lands.
5. Prints a JSON receipt with all pane IDs (plus `mode`, `size`, `writers`, `reviewers`, `parallel_writers`, `dual_review` flags for spawn).

## Briefing templates

Each role has a template in `examples/`:

- **`examples/writer-briefing.md`**: implementation brief: pointers, deliverables, pair protocol with reviewer pane id, standards.
- **`examples/reviewer-briefing.md`**: review brief: what to check (falsifiable), how to phrase findings, pair protocol with writer pane id.
- **`examples/orchestrator-briefing.md`**: full duty list: recon, brief engineers, watch loop, report to human.

These are starting points. Adapt to the task at hand. The bundled script generates a baseline briefing automatically; the templates are useful when overriding the briefing or when the orchestrator writes one from scratch after recon.

## Sending messages between panes

The cross-pane primitive is `tmux_pair.py send`:

```
python3 <plugin>/scripts/tmux_pair.py send <pane-id> "<message>"
```

Multi-line messages are submitted via `load-buffer` + `paste-buffer` to avoid the issue where some agent TUIs interpret each newline as a submit. Single-line messages use plain `send-keys -l`. After the text, the helper sends Enter three times with small gaps; this works around agent TUIs that ignore the first Enter when a tool call is in flight. Override with `--no-enter` if needed.

Normal messages get a sender identity prefix automatically. Example: a writer pane with sender `wr.channel-slack` sending `REVIEW-READY: B2 ...` arrives as `[FROM: wr.channel-slack] REVIEW-READY: B2 ...`. Messages already starting with `[FROM:` are left unchanged, so manual prefixes are idempotent. Slash commands such as `/compact <focus>` are command traffic and are not prefixed. Spawned panes store their stable sender name in `@tmux-pair-sender`; `pane_title` is only a fallback because agent TUIs can overwrite it with spinner text.

## Token management and re-briefs

The default claude model is `claude-opus-4-7` (1M context). For 200k-context runs (cheaper, faster turn-around), use `--claude-model claude-opus-4-6` on `/spawn`. The compact-watcher threshold scales automatically: 1M to 700k threshold (70%), 200k to 140k threshold. Override per-call with `python3 <plugin>/scripts/tmux_pair.py monitor --threshold-k <N>`.

The default reasoning effort for non-reviewer panes is `medium` on both harnesses: claude panes (writer, orchestrator, solo) start with `--effort medium` (race-free vs. the `/effort` slash, which can fail with "unknown or future model" right after a `/model` switch), codex panes with `-c model_reasoning_effort=medium`. Reviewer panes override this regardless of harness and run on the top tier so review quality stays high while writer/orchestrator budget stays modest: claude-reviewers default to `xhigh`, codex-reviewers default to `high` (codex top tier). Override per spawn with `--claude-effort`, `--codex-effort`, `--reviewer-claude-effort`, `--reviewer-codex-effort`; pass an empty string to skip the flag entirely so the harness uses its own default or the `CLAUDE_CODE_EFFORT_LEVEL` env-var. Codex engineer subagents still follow the documented Spark-first policy in the workflow briefing.

Long-running spawns drift past the model-specific sweet spot where the agent still reasons cleanly. Three helper subcommands let any layer refresh the layer below:

```
python3 <plugin>/scripts/tmux_pair.py status <pane-id>
python3 <plugin>/scripts/tmux_pair.py compact <pane-id> --briefing-file <path> [--focus "<one-liner>"] [--timeout 300]
python3 <plugin>/scripts/tmux_pair.py monitor --orch-pane <id> --panes <id1> <id2> [...] [--threshold-k <N>] [--cooldown-sec <N>]
```

The orchestrator briefing kicks off `monitor` automatically as DUTY 0 (background watcher polls every 180s, pings the orchestrator when an engineer crosses the threshold; cooldown 600s between repeat pings on the same pane). Solo mode does not auto-start the watcher: the agent self-compacts between phases when appropriate.

`status` returns JSON with the detected agent and the parsed token count. Claude prints `N tokens` in its footer, so the count is reliable. Codex usually does not, so its `tokens` field comes back `null`: fall back to a feel-based heuristic (elapsed wall-time, number of REVIEW cycles, whether the agent is repeating itself).

`compact` sends `/compact [focus]` to the pane (claude's official `/compact [instructions]` form), polls `capture-pane` for completion (claude prints `Conversation compacted`; for codex we accept a token-count drop of 50% or more as a fallback), and then sends the re-brief from `--briefing-file` through the regular submit-with-retry path. The optional `--focus` hint shapes the summary so the agent retains plan + REVIEW-state + peer-protocol; without it the summary is generic and important context can drop.

**Authoring the re-brief.** After `/compact` the agent has lost the conversational state and only remembers the summary. The re-brief MUST stand on its own. Include:

- the agent's role (writer / reviewer / orchestrator)
- the concrete current task, phrased as if the agent is hearing it the first time
- a short progress recap (what the layer above has seen, what the agent has shipped)
- the next concrete step the agent should take
- the peer-protocol for this run, with current pane IDs
- the standards (commits, no `--no-verify`, language conventions)

Where the recap comes from depends on the layer:

- the orchestrator keeps a running progress log and authors re-briefs for its writers and reviewers
- the human keeps the same kind of log for any orchestrator it spawns; orchestrators get the richest re-brief because they own the most state
- at the topmost layer the person handles their own compact; a hand-authored re-brief there is fine

**Self-compact (engineer-driven).** Engineers may compact themselves between cycles. Pattern:

1. Write a self-re-brief file at `/tmp/self-compact-<role>-<window>.md` with plan-bullet, REVIEW-state, next step, peer pane ids, relevant standards.
2. Send to your own pane: `python3 <plugin>/scripts/tmux_pair.py send <eigener_pane> "/compact <focus>"`. The focus hint MUST mention plan + REVIEW-state + peer-protocol so claude's summary preserves them.
3. After settle (claude prints `Conversation compacted`), read the self-re-brief file and continue.
4. Signal `SELF-COMPACT-PLANNED: <bullet> <focus>` to the orchestrator once before triggering, so the watcher does not race with a parallel compact on the same pane.

Self-compact is the proactive path; orchestrator-compact is the reactive backstop driven by the watcher in DUTY 0. Codex panes have no `/compact` form; self-compact is claude-only.

**When to trigger.**

- between REVIEW cycles, never mid-edit or mid-tool-call
- claude pane > ~200k tokens (visible in footer)
- codex pane: by feel
- before a known long phase (e.g. starting Wave N) so the agent enters it fresh

**Parallelism.** To compact both engineers in a spawn at once, run two `compact` calls with `&` from the orchestrator's shell; each call blocks for the duration of its poll loop.

## Common failure modes (summary)

The full list with diagnostics and recovery steps lives in `references/failure-modes.md`. The most common ones:

- **Send didn't submit.** Symptom: message visible in pane but cursor still in input. Cause: agent TUI ignored the Enter. Fix: re-send with the helper, which retries Enter; or send Enter manually.
- **Briefing landed before agent booted.** Symptom: message appears at the shell prompt instead of inside the TUI. Cause: 14-second delay too short for slow boot. Fix: re-send manually after the agent is ready.
- **Engineers ping human directly.** Symptom: human inbox floods. Cause: briefing missed the "ping orchestrator, not human" instruction. Fix: orchestrator re-briefs the noisy engineer with the explicit pane id.
- **tmux session crashed mid-run.** Symptom: panes gone, worktree intact. Recovery: re-spawn the panes manually, point them at the existing worktree, and re-send the briefings with the current state attached.
- **Writer pushed without human OK.** Symptom: `git push` happened despite the brief saying "wait for human". Cause: briefing missing or weakly worded. Fix: spell out the push gate explicitly in the briefing template.

## Post-Merge Retro (Pflicht)

Default-Workflow nach `COMPLETE`-Ping vom Orchestrator/Solo-Agent:

1. **Squash-Merge auf `main`**: `git merge --squash` aus dem Worktree-Branch, dann ein commit auf `main` mit zusammengefasstem Body. Squash ist die Default-Strategie in jedem Fall: lineare main-History, eine commit pro Feature, Plan-Amendments und Reactive-Fixes verschwinden aus der main-Sicht. (Fast-forward oder `--no-ff` nur wenn der User explizit den Review-Trail behalten will.)

2. **KEEP wt + panes**: nach dem Squash NICHT sofort cleanen. Worktree, Branch und tmux-Panes (orchestrator + writer + reviewers) bleiben für den Retro-Step intakt.

3. **Retro mit team**: Master schickt per `tmux_pair.py send <pane>` an JEDEN aktiven Pane eine tailored Retro-Frage. Erwartet 200-500 Wörter Faktenanalyse pro Agent (kein Lob, Schwächen direkt). Konkret:

   - **Orchestrator**: Phase-Wallclock (RECON/GATE-1/GATE-1.5/GATE-2/IMPL/GATE-3), GATE-2-Iterationen, welche Mid-Run-SDs hätten beim ersten Plan-Schreiben verhindert werden können, drive-by/reactive-Commit-Anteil, strukturelle Plan-Fehler, mode-choice-Retro.
   - **Writer**: Compile-vs-Test-Time pro Bullet, Public-API-Touch-Impact, reactive-fix-Trigger pro Commit, schwierigstes Test-Pattern, fmt-drift-Ursache, Pre-Flight-Lücken die Zeit gekostet haben.
   - **Reviewer 1+2** (bei dual-review): konkrete BLOCKER/WARNING pro file:line, Review-Round-Count, Divergenz-vs-Peer-Findings, dual-review-Wert (was nur durch Zweiten gefangen), Issue-Klasse die in zukünftigen Tasks vermeidbar wäre.

4. **Pattern-Synthese + Persist**: Master sammelt die Retros, identifiziert recurring issue classes (z.B. decorator-swallow, cancellation-root-mismatch, fmt-drift), und persistiert die Learnings in:
   - tmux-pair-skill (diese Datei): wenn das Pattern workflow-cross-cutting ist (Pre-Flight-Klasse, Mode-Choice-Heuristik, dual-review-Wert).
   - Konsument-Repo-Rules (`.claude/rules/*.md` oder `.claude/skills/<repo>-<topic>/SKILL.md`): wenn das Pattern repo-spezifisch ist (z.B. example-project decorator-chain-recon, trait-param-honor-check).

5. **Cleanup**: erst nach Pattern-Persist:

```bash
cd <project-path>
git worktree remove ../<project-name>-wt-<feature>
git branch -D feature/<feature>      # -D weil Squash-Merge git-perspektivisch "unmerged" ist
tmux kill-window -t <window-name>
```

Retro-Step ist Pflicht, nicht Optional. Ein Spawn-Run ohne Retro persistiert nicht die teuersten Learnings des Runs.

## Recurring Pre-Flight Checks (aus Retros aggregiert)

Diese Checks gehören in `--with-standards` Briefings UND in Konsument-Repo `.claude/rules/pre-flight-checklists.md`. Aggregiert aus mehreren Spawn-Retros, falsifizierbar:

- **Decorator-Sweep vor Trait-Default-Add**: Bei Hinzufügen einer Default-Body Trait-Methode (insbesondere lifecycle wie `shutdown`/`close`/`flush`): vor REVIEW-READY `rg "impl <Trait> for" --type rust` ausführen, alle Implementoren auflisten, jeden mit ≥2 forward-Methoden als Decorator markieren und explizit zwingend forward-Override hinzufügen ODER explizit no-op rationale in Plan-Amendment dokumentieren. Anti-Pattern: trait-default no-op wird von Decorator silent geswallowed.

- **Trait-Param-Honor-Check**: Wenn Trait-Method-Param `_`-prefixed (`_grace`, `_token`, etc.) obwohl die Trait-Doc den Param als wirksam beschreibt: silent-discard footgun. Pre-Flight: `rg '_[a-z]+: ' <trait-file>` gegen Trait-Doc cross-checken. Default-Body soll Param entweder ehrlich ignorieren (Doc anpassen) oder honor + Test.

- **Method-Resolution-Collision-Check**: Neue Trait-Methode mit gleichem Namen wie bestehende inherent-impl auf einem Implementor: pre-flight `cargo check -p <crate>` decked die ambiguity-warning. Anti-Pattern: trait-method wird stillschweigend von inherent-method geschattet.

- **Format-Gate-Disziplin**: Writer-Claim "fmt clean" verlangt `cargo fmt -p <crate> --check` (NICHT `cargo fmt -p <crate>` ohne `--check`). Per-crate fmt ohne `--check` brushe neighbor-files silent und produziert drive-by-drift. Falsifizierbar: REVIEW-READY mit "fmt clean" + `--check`-Output, exit 0.

- **Memory-Recon als RECON-Pflicht-Schritt**: Vor Plan-Schreiben `MEMORY.md` plus die 3-5 relevantesten memory-files am `~/.claude/projects/<repo>/memory/` lesen. Mid-Run-SDs die durch Memory-Recon antizipierbar gewesen wären sind ein Drift-Indikator.

## Cleanup (manuell, NACH Retro)

Cleanup ist der human's call und passiert erst nach Retro + Pattern-Persist. Neither the orchestrator nor the engineers should remove worktrees, kill windows, or delete branches during a run.

## Companion skills (bundled)

The plugin ships two companion skills, both plugin-namespaced so they do not collide with user-local installs of the same names:

- **`/tmux-pair:gepa`**: Genetic-Pareto prompt/text-artifact optimization (paper arXiv:2507.19457). Used opt-in after rules-bootstrap to optimize the freshly generated `.claude/rules/*.md` against user-supplied test diffs. The orchestrator suggests it after a fresh bootstrap; the user runs it in their own pane (GEPA needs test diffs the orchestrator does not have). Skill files live under `skills/gepa/` (SKILL.md, scripts/gepa-loop.py, references/{patterns,gepa-library}.md).
- **`/tmux-pair:dg`**: Dinesh-vs-Gilfoyle adversarial code review. Two AI personas (one attacker, one defender) debate a diff or file until the defender concedes, defends, or the round limit hits. Useful as an optional pre-GATE-3 step on security/concurrency/auth/crypto/migration bullets where extra adversarial pressure pays off. Skill files live under `skills/dg/` (SKILL.md, gilfoyle-agent.md, dinesh-agent.md).

External companion (NOT bundled, install separately if you want it): the official `code-simplifier` plugin from `claude-plugins-official` for refactor-passes after a feature lands.

## Additional resources

### References

- **`references/gated-workflow.md`**: 5-gate workflow (Clarify, Reviewer-Readiness, Plan-Check, Loop, Final-Verify), subagent prompt templates, gate event vocabulary, gate-specific failure modes.
- **`references/pair-protocol.md`**: full event vocabulary, edge cases, escalation rules, and end-of-run handshake.
- **`references/solo-vs-spawn.md`**: decision matrix (solo vs spawn vs which `--size`) with worked examples.
- **`references/failure-modes.md`**: common failure modes with diagnostics, recovery steps, and prevention.

### Examples

- **`examples/writer-briefing.md`**: writer briefing template.
- **`examples/reviewer-briefing.md`**: reviewer briefing template.
- **`examples/orchestrator-briefing.md`**: orchestrator briefing template (the largest of the three).
