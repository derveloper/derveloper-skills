---
name: tmux-pair-orchestration
description: This skill should be used when the user asks to "spawn a solo with self-review", "run an agent on this with gates", "use the tmux-pair workflow", "/run for this task", or otherwise wants to run a single coding agent in a fresh git worktree with adversarial review gates. Solo is the only mode. Multi-pane spawn modes (writer + reviewer panes, dual-review, parallel-writers) were removed: shared CARGO_TARGET_DIR contention, git-index-lock races, cross-writer PROJECT.md races, and dual-review coordination outweighed the parallelism gain. Adversarial quality is preserved by running two independent minds at each gate: a claude subagent plus `codex exec` (different model family, fresh context, no pane setup). Sequential solo runs auto-squash-merge to base in Phase 7: each run produces ONE squash commit on the base branch, the feature branch + worktree are removed automatically, so chained runs always branch from a clean base. Covers the /run auto-entry, solo's 7-phase gated workflow (Recon -> Clarify -> Reviewer-Readiness -> Plan-Check -> Loop -> Final-Verify -> Persist -> Commit -> Auto-Squash-Merge), durable standards (claude --append-system-prompt-file + codex AGENTS.md), REVIEW-READY 3-field format, CLARIFY-NEEDED escalation, Plan-Update-Commit on drift, PROJECT.md care, DONE-MERGED format, sender identity prefixes, smart-workflow V1-V10, repo-specific subagent detection, Compact-Watcher, --claude-model / --no-worktree flags, briefing templates, and recovery from common failure modes. Mandatory Post-Merge Retro persists recurring patterns into tmux-pair-skill or consumer-repo rules / skills.
version: 0.20.0
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

Default agent: `claude` (recon-strong, follows briefings, integrates plan + subagent feedback cleanly). Override via `--agent codex` or `--agent pi` (the user's custom CLI). Reviewer subagents run at top reasoning tier regardless of solo agent's budget.

## Solo workflow (7 phases)

1. **Recon**: 4-6 parallel subagent spawns. Domain-experts when `.claude/agents/<repo>-*.md` exists; `Explore` otherwise. Each subagent <300 words with `file:line` pointers. Adds `MEMORY.md` freshness check (>3 day old memory files = stale-risk flag).
2. **Plan + GATE-2 Plan-Check**: bullet plan with parallel/sequential markers, then TWO independent adversarial checks in parallel:
   - `Agent(gate-2-plan-check)` (claude, adversarial, scoped read-only)
   - `Bash(codex exec --skip-git-repo-check "adversarial plan-attack against <plan>")` (codex, different model family, fresh context)
   Both must return PASS or WARNING-only. BLOCKER in either → fix-loop. Max 3 plan iterations; iteration 4+ asks the user.
3. **Implementation**: agent codes directly. Per-bullet runs nextest + clippy + per-crate gates inline. PROJECT.md care for feature/refactor bullets that change package map, feature surface, design decisions, or implementation history.
4. **GATE-3 Final-Verify**: THREE independent adversarial checks in parallel:
   - `Agent(gate-3-verifier)` (claude, Haiku 4.5, goal-backward against plan)
   - `Agent(gate-3-code-reviewer)` (claude, Sonnet 4.6, adversarial diff review)
   - `Bash(codex exec "adversarial diff-review against main..HEAD")` (codex)
   BLOCKER in any → fix-loop. WARNING-only → proceed with documented follow-up. Max 3 review cycles.
5. **PROJECT.md + Skill-Persist**: phase block in PROJECT.md, design decisions, domain knowledge as Skill under `.claude/skills/<repo>-<topic>/SKILL.md` (Persist-Convention; Rules only for cross-cutting always-on items).
6. **Commit**: per-bullet conventional commits (kein AI-co-author), per-crate gates green, worktree clean. KEIN DONE-Ping bevor Phase 7 durch ist.
7. **Auto-Squash-Merge + Cleanup**: solo squashes all bullet commits into one commit on `<base>`, deletes the feature branch, removes the worktree, then pings `DONE-MERGED`. Sequential chained runs always start from clean base. Steps the solo executes itself:
   - `git -C <project> status --porcelain` -> must be empty (else BLOCKER)
   - `git -C <project> checkout <base>`
   - `git -C <project> merge --squash <branch>`
   - `git -C <project> commit` (heredoc-Message: 1-Liner + Bullet-Body + Decisions + Test-Counts)
   - `git -C <project> branch -D <branch>`
   - `git -C <project> worktree remove <wt_path>` (skipped if `--no-worktree`)
   - `DONE-MERGED solo.<feature>: <squash-sha> on <base>` ping
   - Merge conflict in Phase 7 → BLOCKER ping with concrete error, human resolves, then solo retries.

Default flag set: `--no-gated` for trivial tasks where subagent-driven recon/plan/review is overkill (e.g. doc tweak, single-file rename). Gated is the default. Worktree is the default; `--no-worktree` opts out.

### Repo-specific subagents (auto-detected)

When the script sees `.claude/agents/<repo>-*.md` files in the target repo, it lists them in the briefing. The solo briefing instructs the agent to prefer those domain experts over `general-purpose` for Recon/Impl/Review subagent spawns. They know the repo's domain vocabulary, architecture constraints, and skill files.

Detection logic: filename stem starting with `<project.name>-` (e.g. `example-project-kernel.md` in a `example-project` repo). Falls back to "no repo-subagents listed" if the directory is missing or empty.

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
2. **Repo recon**: inspect size, language stack, `.claude/agents/`, `.claude/rules/`, grep for keywords from `<task>` to estimate affected file count.
3. **Pre-pick sensible solo flags**: `--with-standards` for repos lacking explicit rules, `--greenfield` for completely fresh repos.
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
| Verify-absent (already fixed in earlier phase) | rg-evidence in REVIEW-READY, single-pass verifier check |
| Doc-only (PROJECT.md, comment, skill text) | bundled with other doc-only bullets, one PROJECT.md-closeout review |
| Won't-fix (technically impossible or out-of-scope) | plan-amendment commit with rationale, no implementation |

Run one solo per class-batch (or split code-fix into 3-5-bullet sub-batches). Avoid the monolithic 22-bullet run.

## Durable standards

Standards survive `/compact` and context resets because they sit in the system prompt, not in the briefing user-message that gets summarised on compaction. Briefings are slim by default: task-focused and compact.

- **claude panes** boot with `--append-system-prompt-file <path>` pointing at `/tmp/tmux-pair-durable-<window>-<role>.md`. The file is generated per-spawn from a single in-script constant (`DURABLE_STANDARDS_PROMPT`) so updates to standards land in the next spawn automatically.
- **codex panes** read `AGENTS.md` from the worktree root. The plugin writes that file when a real worktree is created (i.e. not when `--no-worktree` is passed). If the repo already owns an `AGENTS.md`, the plugin leaves it alone: repo standards win.
- **pi panes** boot with `--append-system-prompt <path>` (the user's Custom-CLI, `~/.pi/agent/`). pi reads `AGENTS.md` and `CLAUDE.md` via default discovery, so the codex path works transitively. Default model `qwen3-coder-next` via default provider `cortecs`, default `--thinking high`. Override per spawn via `--pi-provider`, `--pi-model`, `--pi-thinking`. Known limits: no mid-session `/model` switch (pane-restart required), no `/compact` equivalent (Compact-Watcher does not ping pi panes).
- **`--with-standards`** appends the durable standards bundle (reviewer standards, recall discipline, bullet-start ritual).
- **`--greenfield`** enables `--with-standards` plus greenfield pre-flight.
- **`--no-worktree`**: if codex is the solo agent, standards are auto-enabled in the briefing so codex still receives durable standards context.
- **`agents.json` overrides** are respected: if the user has remapped `claude`, the plugin does NOT inject `--append-system-prompt-file` blindly. The wrapper can read the standards file itself.

The standards block covers: real Umlaute (no ASCII substitutes), Conventional Commits with no `--no-verify` and no AI-co-author trailer, the REVIEW-READY 3-field format, the honesty protocol (past-tense claims need same-turn tool evidence), drift signals (em-dashes, progress markers, ALL-CAPS headers, "should I"-after-clear-directive), the `incidental:` format for PostToolUse-hook fmt drift, the worktree-as-sandbox rule, the no-pre-existing-issues rule, recall-discipline (cite the relevant rule + memory before sensitive actions), and the bullet-start ritual (class + relevant rules + common BLOCKER-classes before the first edit on a bullet).

## Gated workflow (default)

```
Recon -> GATE 1 Clarify -> GATE 1.5 Reviewer-Readiness -> Plan -> GATE 2 Plan-Check -> Implementation Loop -> GATE 3 Final-Verify -> Commit -> Auto-Squash-Merge (Phase 7) -> DONE-MERGED -> Post-Merge Retro
```

- **GATE 1 (Clarify)**. The solo agent calls `AskUserQuestion` directly. The human only sees a `GATE-1-ESCALATE` if a question is outside the agent's authority.
- **GATE 1.5 (Reviewer-Readiness)**: one scoped subagent (`tmux-pair:reviewer-readiness-check`, Sonnet 4.6, Read+Grep+Glob+Bash, NO Edit/Write) reads `.claude/rules/*.md` and scores an 8-item checklist (style, tests, architecture, anti-patterns, naming, security, build, domain). On `NEEDS-RULES`, the agent runs a bootstrap loop: per gap one `AskUserQuestion`, then `tmux-pair:rules-bootstrap` bakes `.claude/rules/<topic>.md` from plugin language templates + repo recon + user answers, then re-run readiness-check. Loop terminates at READY or after iteration 3 with user-decided abort/partial-coverage/manual-amend. Optional opt-in `/gepa` pass after fresh rules; the plugin does not call `/gepa` automatically.
- **GATE 2 (Plan-Check)**: parallel two-mind check. `Agent(gate-2-plan-check)` (Sonnet 4.6, scoped read-only) verifies the plan goal-backward AND checks plan quality. Every bullet must carry either a parallel marker (`B3 || B4 [parallel]`) or a sequencing marker (`B3 -> B4 [sequenziell: shared file]`). In parallel: `Bash(codex exec "adversarial plan-attack")` for second-opinion. `BLOCKER` in either escalates to the agent's fix-loop; both PASS or WARNING-only proceeds.
- **Implementation Loop**: solo writes + per-bullet self-review via `Agent(gate-3-code-reviewer)` when bullets are non-trivial. Per-bullet test-budget per `test-budget.md` (crate-scoped, never `--workspace`). PROJECT.md care for feature and refactor bullets. Engineers use subagents for parallel recon, parallel test suites, and independent fix branches when that keeps the main pane lean.
- **GATE 3 (Final-Verify)**. Three parallel adversarial checks: `Agent(gate-3-verifier)` (Haiku 4.5, goal-backward against plan, runs build/test, checks plan-bullet coverage and PROJECT.md care), `Agent(gate-3-code-reviewer)` (Sonnet 4.6, adversarial diff review), and `Bash(codex exec "diff-review")` (codex, second-opinion). All PASS or WARNING-only: solo pings the human with `COMPLETE`.

The implementation loop adds six protocol elements:

- **REVIEW-READY 3 mandatory fields**: every `REVIEW-READY:` ping carries (1) what changed (file:line + LOC-diff), (2) verification (`crate-gate=PASS` + test counts, or `crate-gate=N/A doc-only`), (3) plan-bullet/pain reference. Pings without these fields are blocked.
- **CLARIFY-NEEDED**. When the agent hits a user-decision question mid-loop (scope, behavior, UX, architecture choice, naming conflict, trade-off not in the plan), it calls `AskUserQuestion` directly with 2-4 options. Engineers do NOT decide user-facing questions on their own.
- **Plan-Update-Commit**. If a bullet hits a hard cap (LOC limit, file-size cap) or the estimate drifts more than ~50%, the agent commits a `docs(plan-amendment): ...` BEFORE the implementation commit that breaks the cap. A bullet with documented drift but no preceding amendment commit fails verifier.
- **Parallel markers**. Plans mark independent bullets as `B3 || B4 [parallel]` and ordered bullets as `B3 -> B4 [sequenziell: <reason>]`. GATE 2 blocks missing markers.
- **PROJECT.md care**. The agent updates project-local `PROJECT.md` for feature and refactor bullets that change package map, feature surface, design decisions, or implementation history. Reviewers sign off on the update or on a justified skip for refactor, test, or docs-only bullets with no feature-surface change. If no `PROJECT.md` exists, the agent asks whether to bootstrap a human-maintained skeleton. `~/git/example-project/PROJECT.md` is the format and detail-depth example.
- **COMPLETE-Ping format**. `COMPLETE: <Phase>. gate-3=PASS via <verifier-name + code-reviewer-name + codex-cli>. <diff-stat>. Bezug: <plan goals all met>.` Only AFTER GATE 3 returned PASS, never before.
- **Recall-Discipline + Bullet-Start-Ritual**: cite the relevant rule + memory entry before any sensitive action (commit, push, external API), and post a class + rules + common BLOCKER-classes block before the first edit on each new plan-bullet.

Cross-cutting:

- **Plan quality is enforced.** A skeletal "implement X" plan blocks at GATE 2.
- **Context economy applies.** Heavy research, deep codebase reads, and web lookups go to subagents (one message, multiple parallel Task calls when independent). Diff-first reviews. Targeted Read-ranges over full-file dumps.
- **Edit efficiency is part of the plan.** Pattern replace at >3 sites is a `sed`-job. Boilerplate generation = template + substitution. The plan names the tool.
- **Few, descriptive commits.** The agent commits at logical-step granularity during the loop; the human squashes before merge to `main`. Commit messages must be substantial enough that a meaningful squash message can be distilled.

Greenfield repos (no `CLAUDE.md`, no `.claude/rules/`) are handled by GATE 1.5 automatically: the readiness-check returns `NEEDS-RULES` with all 8 topics as gaps, the bootstrap loop generates the full rules set from plugin templates + user answers + repo recon, and the agent proceeds only AFTER rules exist. Plan stays focused on the actual feature work; rules-generation is no longer a plan bullet.

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

### V6 Readiness-Cache (24h TTL)

`reviewer-readiness-check` is cached. Cache key: `sha256(.claude/rules/*.md content)` + commit-sha. Cache-hit (file exists + mtime < 24h + verdict=PASS): skip the subagent. Cache-miss / STALE: normal subagent spawn; PASS verdict gets cached atomically. `NEEDS-RULES` is never cached. Cache-bust: `--no-cache`.

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

### V8 Cargo-Target-Sharing

`tmux_pair.py` prepends `env CARGO_TARGET_DIR=~/.cache/tmux-pair/cargo-target/<repo-slug>/` to the boot command when the project is a Cargo workspace and `--no-shared-target` is not set. Single-solo runs see clean cache; cross-worktree parallelism from independent runs share the same target dir (cargo's lock-file handles concurrency, but brief block during peer-build is expected). Opt-out: `--no-shared-target`.

### V9 Recon-Cache with Delta-Mode (1h TTL)

Recon output (file map, crate list, PROJECT.md snapshot, key-function inventory) cached at `/tmp/tmux-pair-recon-<repo-slug>-<commit-sha>.json`. Subsequent runs on the same commit within 1h read the cache, then delta-recon for files with `mtime > cache-time`. Cache-bust: `--no-cache`.

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

## Token management and re-briefs

Default claude model: `claude-opus-4-7` (1M context). For 200k-context runs, use `--claude-model claude-opus-4-6`. Compact-watcher threshold scales automatically: 1M → 700k (70%), 200k → 140k.

Default reasoning effort: `medium` on both harnesses for the main pane; reviewer subagents always run at the top tier (claude `xhigh`, codex `high`). Override with `--claude-effort`, `--codex-effort`, `--reviewer-claude-effort`, `--reviewer-codex-effort`.

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

## Post-Merge Retro (Pflicht)

Default-Workflow nach `DONE-MERGED`-Ping vom Solo-Agent. Phase 7 des Solo-Workflows hat den Squash-Merge + Branch-Delete + Worktree-Remove bereits ausgeführt. Der Retro-Step bleibt:

1. **Retro**: Master schickt eine tailored Retro-Frage an den Solo-Pane (via `tmux_pair.py send`, Pane lebt noch nach Phase 7) UND spawnt parallel 2-3 `Agent` personas mit unterschiedlichen Blickwinkeln (orchestrator-view, writer-view, reviewer-view) plus eine `codex exec "retro"` für eine vierte unabhängige Sicht. Erwartet 200-500 Wörter Faktenanalyse pro Quelle (kein Lob, Schwächen direkt). Inhalt:

   - Phase-Wallclock pro 7-Phase-Schritt
   - GATE-2-Iterationen + welche Mid-Run-SDs bei Plan-Schreiben verhindert werden konnten
   - Drive-by/reactive-Commit-Anteil
   - Strukturelle Plan-Fehler
   - Schwierigstes Test-Pattern, fmt-drift-Ursache, Pre-Flight-Lücken
   - Bullet-Count-Retro (war monolithisch richtig oder zu groß?)
   - Phase-7-Konflikte / Cleanup-Friktionen

2. **Pattern-Synthese + Persist**: Master sammelt die Retros, identifiziert recurring issue classes (decorator-swallow, cancellation-root-mismatch, fmt-drift, plan-vs-reality-mismatch), persistiert:
   - tmux-pair-skill (diese Datei): wenn das Pattern workflow-cross-cutting ist (pre-flight-Klasse, Plan-Drift-Indikator)
   - Konsument-Repo: `.claude/rules/*.md` (always-on cross-cutting) oder `.claude/skills/<repo>-<topic>/SKILL.md` (path-scoped domain) per Persist-Convention

3. **Window-Cleanup**: nach Pattern-Persist:

```bash
tmux kill-window -t <window-name>
```

Worktree + Branch sind seit Phase 7 weg, nur das tmux-Window bleibt für den Retro übrig. Retro-Step ist Pflicht, nicht Optional. Ein Solo-Run ohne Retro persistiert nicht die teuersten Learnings des Runs.

## Recurring Pre-Flight Checks (aus Retros aggregiert)

Diese Checks gehören in `--with-standards` Briefings UND in Konsument-Repo `.claude/rules/pre-flight-checklists.md`. Aggregiert aus mehreren Solo-Retros, falsifizierbar:

- **Decorator-Sweep vor Trait-Default-Add**: Bei Hinzufügen einer Default-Body Trait-Methode (insbesondere lifecycle wie `shutdown`/`close`/`flush`): vor REVIEW-READY `rg "impl <Trait> for" --type rust` ausführen, alle Implementoren auflisten, jeden mit ≥2 forward-Methoden als Decorator markieren und explizit forward-Override hinzufügen ODER no-op rationale in Plan-Amendment dokumentieren. Anti-Pattern: trait-default no-op wird von Decorator silent geswallowed.

- **Trait-Param-Honor-Check**: Wenn Trait-Method-Param `_`-prefixed (`_grace`, `_token`) obwohl die Trait-Doc den Param als wirksam beschreibt: silent-discard footgun. Pre-Flight: `rg '_[a-z]+: ' <trait-file>` gegen Trait-Doc cross-checken. Default-Body soll Param entweder ehrlich ignorieren (Doc anpassen) oder honor + Test.

- **Method-Resolution-Collision-Check**: Neue Trait-Methode mit gleichem Namen wie bestehende inherent-impl auf einem Implementor: pre-flight `cargo check -p <crate>` zeigt die ambiguity-warning. Anti-Pattern: trait-method wird stillschweigend von inherent-method geschattet.

- **Format-Gate-Disziplin**: Writer-Claim "fmt clean" verlangt `cargo fmt -p <crate> --check` (NICHT `cargo fmt -p <crate>` ohne `--check`). Per-crate fmt ohne `--check` brushe neighbor-files silent und produziert drive-by-drift. Falsifizierbar: REVIEW-READY mit "fmt clean" + `--check`-Output, exit 0.

- **Memory-Recon als RECON-Pflicht-Schritt**: Vor Plan-Schreiben `MEMORY.md` plus die 3-5 relevantesten memory-files am `~/.claude/projects/<repo>/memory/` lesen. Mid-Run-SDs die durch Memory-Recon antizipierbar gewesen wären sind ein Drift-Indikator. **Memory-Freshness-Gate**: Memory-Files >3 Tage alt = stale-Risk-Flag, im Plan-Recon zitieren ob Memory aktuell gegen current code geprüft wurde.

- **Brief-vs-Reality-Validation vor Plan-Lock**: Brief auf altem Code-State ist die häufigste Plan-Drift-Quelle. Vor Plan-Lock: `cargo clippy -p <crate>` + `git grep -n "<keyword>"` + `rg-evidence` für jedes "verify-first" oder "should-be-X" Item im Brief. Falsifizierbar: Plan-Lock-Commit zitiert mindestens 2 Brief-Items mit current-code-Evidence-SHAs.

- **Target-Dir Hygiene vor llvm-cov**: `.gitignore` enthält `target-cov/` (und ähnliche Tool-Output-Dirs) BEVOR der erste `cargo llvm-cov` läuft. Reactive-Fix nach Crash kostet 30+ min Recovery.

## Cleanup (auto + manuell)

Der Solo-Agent removed Worktree + Branch automatisch in Phase 7 (Auto-Squash-Merge). Manuell bleibt nur das `tmux kill-window` nach Pattern-Persist.

Vor 0.20.0 war Cleanup vollständig manuell und Pflicht-Reihenfolge (Retro -> dann Cleanup). Seit 0.20.0 macht der Solo-Agent Squash + Branch-Delete + Worktree-Remove selbst und der Retro-Step ist die einzige verbleibende Human-Pflicht.

## Companion skills (bundled)

The plugin ships two companion skills, both plugin-namespaced:

- **`/tmux-pair:gepa`**: Genetic-Pareto prompt/text-artifact optimization (paper arXiv:2507.19457). Opt-in after rules-bootstrap to optimize the freshly generated `.claude/rules/*.md`. Skill files in `skills/gepa/`.
- **`/tmux-pair:dg`**: Dinesh-vs-Gilfoyle adversarial code review. Two AI personas (attacker + defender) debate a diff or file until the defender concedes, defends, or the round limit hits. Useful as an optional pre-GATE-3 step on security/concurrency/auth/crypto/migration bullets. Skill files in `skills/dg/`.

External companion (NOT bundled): `code-simplifier` from `claude-plugins-official` for refactor-passes after a feature lands.

## Additional resources

### References

- **`references/gated-workflow.md`**: 7-phase solo workflow, subagent prompt templates, gate event vocabulary, gate-specific failure modes.
- **`references/failure-modes.md`**: common failure modes with diagnostics, recovery, prevention.

### Examples

- **`examples/solo-briefing.md`**: solo briefing template.
