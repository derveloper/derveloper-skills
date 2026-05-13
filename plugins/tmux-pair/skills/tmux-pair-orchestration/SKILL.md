---
name: tmux-pair-orchestration
description: This skill should be used when the user asks to "spin up a writer/reviewer pair", "run two agents on this", "pair these agents", "set up an orchestrator + pair", "launch a triple", "use the tmux-pair workflow", or otherwise wants to run two or three coding agents collaboratively in tmux panes wired up via git worktrees. Covers the pair protocol, when to choose pair vs. triple, durable standards (claude --append-system-prompt-file + codex AGENTS.md), gated workflow (Clarify → Reviewer-Readiness → Plan-Check → Loop → Final-Verify with rules-bootstrap loop, PROJECT.md care, language templates for 7 stacks, REVIEW-READY-3-Felder, CLARIFY-NEEDED, Plan-Update-Commit, COMPLETE-Format), sender identity prefixes, explicit parallel-plan markers, engineer subagent strategy, bundled companion skills (gepa for prompt-optimization, dg for adversarial code review), Compact-Watcher with model-aware threshold, --claude-model + --no-worktree flags, briefing templates, and recovery from common failure modes.
version: 0.12.1
---

# tmux-pair-orchestration

Run two or three coding agents collaboratively on a single task. Each agent lives in its own tmux pane, all panes share a fresh `git worktree`, and the agents talk peer-to-peer through a small Python helper.

This skill applies whenever the user wants to set up such a pair or triple, monitor it, draft briefings, recover from a stuck loop, or decide between the two modes.

## The two modes

| Mode | Agents | Layout | Human role |
|------|--------|--------|-------------|
| **pair** | Writer + Reviewer | side by side (`main-vertical`) | active relay between the two agents, hands-on |
| **triple** | Writer + Reviewer + Orchestrator | Orchestrator on top (full width), Writer/Reviewer below (`main-horizontal`) | hands-off after spawn, only sees major-event pings |

Default agent assignments (overridable):

- writer: `codex` (terminal-driven, sharp on implementation, fast turnaround)
- reviewer: `claude` (strong at adversarial review, follows checklists, gives falsifiable findings)
- orchestrator: `claude` (recon + briefing + filtering)

These are defaults baked into the bundled script. Different agent CLIs work fine: point `--writer-agent`, `--reviewer-agent`, `--orchestrator-agent` at any name registered in `~/.config/tmux-pair/agents.json`. Built-in: `claude`, `codex`, `pi` (the users Custom-CLI). pi unterstützt alle drei Rollen, bringt aber zwei Einschränkungen: kein mid-session Model-Switch (kein `/model` Slash-Command, nur Pane-Restart) und kein `/compact`-Equivalent (Compact-Watcher pingt pi-Panes nicht; bei langen Runs Pane-Restart einplanen).

## Dual-Review (opt-in)

Both modes accept `--dual-review` to spawn TWO reviewers (default: claude as reviewer-1, codex as reviewer-2) instead of one. The default is OFF; you only get the second reviewer when you ask for it.

| Mode | Layout with `--dual-review` |
|------|------------------------------|
| **pair** | Writer left (main pane), Reviewer-1 top right, Reviewer-2 bottom right (right side vertically split) |
| **triple** | Orchestrator on top full width, Writer bottom left, Reviewer-1 + Reviewer-2 stacked on the bottom right |

Reviewer protocol per cycle:

1. Writer pings `REVIEW-READY` to BOTH reviewers in parallel.
2. Both reviewers review independently — no crosstalk before they have their own findings.
3. Reviewers swap findings (`REVIEWER-FINDINGS:` to peer), give each other a `PEER-REVIEW:` (agree, disagree, missed-this).
4. Each reviewer sends a final `REVIEW-FINAL (Reviewer):` to the Orchestrator (= human in pair, = orchestrator agent in triple).
5. Orchestrator consolidates both reports into ONE merged review (keep all unique BLOCKERs, dedupe overlaps, surface contradictions with context).
6. Orchestrator sends ONE `REVIEW-CONSOLIDATED:` to the writer. Reviewers never speak directly to the writer.

Override the second reviewer with `--reviewer-2-agent <agent>`. Without `--dual-review` the default single-reviewer flow stays exactly as before — no change for existing users.

When to opt in: risky refactors, security-sensitive code, blast-radius changes, anything where you want diversity of opinions on the diff. Cost: one extra agent token-burn and one extra review-merge step in the orchestrator.

## When to use which mode

Choose **pair** when:

- the task is small and well-scoped (one to a few files)
- the human is willing to be the relay between writer and reviewer
- recon is shallow or already done

Choose **triple** when:

- the task spans many files or unfamiliar code
- the human wants to step away and only get pinged on real events
- a dedicated agent doing recon and writing briefings will save more time than it costs
- the feedback "engineers brief themselves and miss the real problem" is plausible

A triple is overhead for trivial tasks. A pair leaks too much into the human's attention for big ones. See `references/triple-vs-pair.md` for a longer decision matrix with worked examples.

## Durable standards

Standards survive `/compact` and context resets because they sit in the system prompt, not in the briefing user-message that gets summarised on compaction.
Briefings are slim by default: task-focused and compact.

- **claude panes** boot with `--append-system-prompt-file <path>` pointing at `/tmp/tmux-pair-durable-<window>-<role>.md`. The file is generated per-spawn from a single in-script constant (`DURABLE_STANDARDS_PROMPT`) so updates to standards land in the next spawn automatically.
- **codex panes** read `AGENTS.md` from the worktree root. The plugin writes that file when a real worktree is created (i.e. not when `--no-worktree` is passed). If the repo already owns an `AGENTS.md`, the plugin leaves it alone: repo standards win.
- **pi panes** boot with `--append-system-prompt <path>` (the users Custom-CLI, `~/.pi/agent/`). pi liest zusätzlich `AGENTS.md` und `CLAUDE.md` via Default-Discovery, also wirkt der codex-Pfad transitiv mit. Default-Model `claude-opus-4-7` via Default-Provider `claude-bridge` (pi-claude-bridge wrappt die Claude Pro/Max-Subscription), default `--thinking high` (Mapping aus claude `--effort max`). Override per Spawn via `--pi-provider`, `--pi-model`, `--pi-thinking`. Bekannte Beschränkungen: kein mid-session `/model`-Wechsel (Pane-Restart nötig) und kein `/compact`-Equivalent (Compact-Watcher pingt pi-Panes nicht).
- **`--with-standards`** appends the durable standards bundle to briefings (reviewer standards, recall discipline, bullet-start ritual, pair protocol).
- **`--greenfield`** enables `--with-standards` plus greenfield pre-flight.
- **`--no-worktree`**: if codex is one of the spawned roles, standards are auto-enabled in the briefing so codex still receives durable standards context even without a workspace `AGENTS.md` write.
- **`agents.json` overrides** are respected: if the user has remapped `claude` to a wrapper or alternative binary, the plugin does NOT inject `--append-system-prompt-file` blindly. The wrapper can read the standards file itself.

The standards block covers: real Umlaute (no ASCII substitutes), Conventional Commits with no `--no-verify` and no AI-co-author trailer, the REVIEW-READY 3-field format, the honesty protocol (past-tense claims need same-turn tool evidence), drift signals (em-dashes, progress markers, ALL-CAPS headers, "should I"-after-clear-directive, etc.), the `incidental:` format for PostToolUse-hook fmt drift, the worktree-as-sandbox rule, the no-pre-existing-issues rule, recall-discipline (cite the relevant rule + memory before sensitive actions), and the bullet-start ritual (class + relevant rules + common BLOCKER-classes before the first edit on a bullet).

## Gated workflow (default)

Both `/pair` and `/triple` enforce five quality gates before code lands on the branch. The bundled briefings encode the gates plus the task-specific flow; optional standards/gate procedure blocks are included with `--with-standards` or `--greenfield`; this is the high-level shape:

```
Recon -> GATE 1 Clarify -> GATE 1.5 Reviewer-Readiness -> Plan -> GATE 2 Plan-Check -> Implementation Loop -> GATE 3 Final-Verify -> Human merges
```

- **GATE 1 (Clarify)**. Whoever owns the gate (orchestrator in triple, human in pair) calls `AskUserQuestion` directly in their own pane. The triple orchestrator does NOT ping the human for clarify: human only sees a `GATE-1-ESCALATE` if a question is outside the orchestrator's authority. Engineers wait for `PLAN-LOCKED:`.
- **GATE 1.5 (Reviewer-Readiness)**: one scoped subagent (`tmux-pair:reviewer-readiness-check`, Sonnet 4.6, Read+Grep+Glob+Bash, NO Edit/Write) reads `.claude/rules/*.md` and scores an 8-item checklist (style, tests, architecture, anti-patterns, naming, security, build, domain). On `NEEDS-RULES`, the orchestrator runs a bootstrap loop: per gap one `AskUserQuestion`, then `tmux-pair:rules-bootstrap` (Sonnet 4.6, R+G+G+B+Edit+Write) bakes `.claude/rules/<topic>.md` from plugin language templates (Rust, TypeScript, Python, Go, JavaScript, Java, generic) + repo recon + user answers, then re-run readiness-check. Loop terminates at READY or after iteration 3 with user-decided abort/partial-coverage/manual-amend. Optional opt-in `/gepa` pass after fresh rules; the plugin does not call `/gepa` automatically.
- **GATE 2 (Plan-Check)**: one scoped subagent (`tmux-pair:gate-2-plan-check`, Sonnet 4.6, Read+Grep+Glob+Bash, NO Edit/Write tools) verifies the plan goal-backward AND checks plan quality. Every bullet must carry either a parallel marker such as `B3 || B4 [parallel]` or a sequencing marker such as `B3 -> B4 [sequenziell: shared file]`. `BLOCKER` escalates to human, no auto-retry. Scoped tools = the agent structurally cannot commit code instead of just verdicting.
- **Implementation Loop**: standard pair protocol (`REVIEW-READY` -> `REVIEW` -> fix -> `DONE`). Smart test subset per cycle (only diff-touched tests), full suite + lint + build pre-DONE. PROJECT.md care is mandatory for feature and refactor bullets that change package map, feature surface, design decisions, or implementation history. Engineers use subagents for parallel recon files, parallel test suites, and independent fix branches when that keeps the main pane lean. Mid-run findings are persisted to memory + rules + engineer-briefing-amendment, not just discussed in-pane.
- **GATE 3 (Final-Verify)**. Two parallel scoped subagents check the diff: `tmux-pair:gate-3-verifier` (Haiku 4.5, runs build/test, checks plan-bullet coverage and PROJECT.md care) + `tmux-pair:gate-3-code-reviewer` (Sonnet 4.6, adversarial diff review). Both PASS or human pings the master.

The implementation loop adds six protocol elements that the briefings enforce:

- **REVIEW-READY 3 mandatory fields**: every `REVIEW-READY:` ping carries (1) what changed (file:line + LOC-diff), (2) verification (`workspace-gate=PASS` + test counts, or `workspace-gate=N/A doc-only`), (3) plan-bullet/pain reference. Pings without these fields are blocked by the reviewer without code review.
- **CLARIFY-NEEDED**. When an engineer hits a user-decision question mid-loop (scope, behavior, UX, architecture choice, naming conflict, trade-off not in the plan), they ping `CLARIFY-NEEDED: <question + 2-4 options>`. In a pair the master receives this and forwards via `AskUserQuestion`. In a triple the orchestrator handles it with its own `AskUserQuestion`. Engineers do NOT decide user-facing questions on their own.
- **Plan-Update-Commit**. If a bullet hits a hard cap (LOC limit, file-size cap) or the estimate drifts more than ~50%, the writer commits a `docs(plan-amendment): ...` BEFORE the implementation commit that breaks the cap. `REVIEW-READY` on a bullet with documented drift but no preceding amendment commit is a `BLOCK`.
- **Parallel markers**. Plans mark independent bullets as `B3 || B4 [parallel]` and ordered bullets as `B3 -> B4 [sequenziell: <reason>]`. GATE 2 blocks missing markers and warns when independent work is needlessly serial.
- **PROJECT.md care**. Writers update project-local `PROJECT.md` for feature and refactor bullets that change package map, feature surface, design decisions, or implementation history. Reviewers sign off on the update or on a justified skip for refactor, test, or docs-only bullets with no feature-surface change. If no `PROJECT.md` exists, the orchestrator asks whether to bootstrap a human-maintained skeleton. `~/git/example-project/PROJECT.md` is the format and detail-depth example.
- **COMPLETE-Ping format**. Orchestrator/master sends `COMPLETE: <Phase>. gate-3=PASS via <verifier-name + code-reviewer-name>. <diff-stat>. Bezug: <plan goals all met>.` only AFTER GATE 3 returned PASS, never before.
- **Recall-Discipline + Bullet-Start-Ritual**: engineers cite the relevant rule + memory entry before any sensitive action (commit, push, external API), and post a class + rules + common BLOCKER-classes block before the first edit on each new plan-bullet.

Cross-cutting:

- **Plan quality is enforced.** A skeletal "implement X" plan blocks at GATE 2.
- **Context economy applies to every agent.** Heavy research, deep codebase reads, and web lookups go to subagents (one message, multiple parallel Task calls when independent). Diff-first reviews. Targeted Read-ranges over full-file dumps.
- **Edit efficiency is part of the plan.** Pattern replace at >3 sites is a `sed`-job. Boilerplate generation = template + substitution. The plan names the tool.
- **Few, descriptive commits.** Engineers commit at logical-step granularity during the loop; the human squashes before merge to `main`. Commit messages must be substantial enough that a meaningful squash message can be distilled.

Greenfield repos (no `CLAUDE.md`, no `.claude/rules/`) are handled by GATE 1.5 automatically: the readiness-check returns `NEEDS-RULES` with all 8 topics as gaps, the bootstrap loop generates the full rules set from plugin templates + user answers + repo recon, and engineers are briefed only AFTER rules exist. Plan stays focused on the actual feature work; rules-generation is no longer a plan bullet.

The full workflow with subagent prompt templates, gate event vocabulary, and failure modes is in `references/gated-workflow.md`. Gate events extend the base pair-protocol vocabulary documented in `references/pair-protocol.md`.

## Pair protocol (the core loop)

The protocol is identical for both modes. Only the addressing differs.

1. Writer makes a meaningful change (one logical step), runs build/lint/tests locally if cheap, and pings the reviewer:

   ```
   python3 <plugin>/scripts/tmux_pair.py send <reviewer-pane> "REVIEW-READY: <one-line summary>"
   ```

2. Reviewer reads the change, the tests, and the writer's summary. Replies with one of:

   - `REVIEW: APPROVE`: change is good as-is.
   - `REVIEW: <findings>`: concrete, falsifiable findings (file:line, problem, suggested direction). No vague "consider improving".

3. If `APPROVE`, writer commits (Conventional Commits, no `--no-verify`, no AI co-author trailer) and pings `DONE: <commit-sha> <branch-state>`.

   If findings, writer fixes, pings `REVIEW-READY` again. Loop.

4. If the pair stalls (disagreement, missing info, suspected upstream bug) either side pings `BLOCKER: <what>` (in pair mode: to human; in triple mode: to orchestrator).

The full protocol with all event types and edge cases lives in `references/pair-protocol.md`.

## Human-offload (triple mode)

The point of the triple is that the human delegates the relay to the orchestrator. The human:

- sends the initial task only to the orchestrator, NOT to the engineers
- sees only orchestrator-tagged pings: `[Orchestrator <window>] MAJOR-STEP / BLOCKER / DONE / ABORT`
- does NOT relay between writer and reviewer
- does NOT clean up worktrees during the run; cleanup decisions stay with the human, but only after `DONE`

The orchestrator does:

- recon (read upstream docs, grep the codebase, identify pointers)
- write writer briefing AND reviewer briefing as separate messages
- watch the pair loop at high level (capture-pane + nudge if silent > 10 min)
- filter engineer pings: only forward MAJOR-STEP, BLOCKER, DONE, ABORT to human

The orchestrator does NOT code, does NOT review, does NOT commit, does NOT decide on cleanup.

## Layout details

**Pair (`main-vertical`):**

```
+---------+---------+
|         |         |
| Writer  | Reviewer|
|         |         |
+---------+---------+
```

**Triple (`main-horizontal`):**

```
+---------------------+
|    Orchestrator     |
+----------+----------+
|  Writer  | Reviewer |
+----------+----------+
```

Both layouts are forced via `select-layout` after spawning, so pane order matters: the orchestrator (in triple mode) or the writer (in pair mode) must be the first pane in the window.

## Quick start

Both commands assume the human is already inside a tmux session.

```
/pair <project-path> <base> <feature> [task...]
/triple <project-path> <base> <feature> [task...]
```

The script:

1. Creates a sibling worktree at `<project-parent>/<project-basename>-wt-<feature>`, branch `feature/<feature>`, from `<base>`. If the branch already exists, it is reused.
2. Opens a tmux window named `<project-basename>-<feature>` (truncated to 30 chars).
3. Spawns the agent panes and forces the chosen layout.
4. Schedules the briefing(s) via `sleep 14 && send`, so the agents have time to boot before the message lands.
5. Prints a JSON receipt with all pane IDs.

## Briefing templates

Each role has a template in `examples/`:

- **`examples/writer-briefing.md`**. Implementation brief: pointers, deliverables, pair protocol with reviewer pane id, standards.
- **`examples/reviewer-briefing.md`**. Review brief: what to check (falsifiable), how to phrase findings, pair protocol with writer pane id.
- **`examples/orchestrator-briefing.md`**. Full duty list: recon, brief engineers, watch loop, report to human.

These are starting points. Adapt to the task at hand. The bundled script generates a baseline briefing automatically; the templates are useful when overriding the briefing or when the orchestrator writes one from scratch after recon.

## Sending messages between panes

The cross-pane primitive is `tmux_pair.py send`:

```
python3 <plugin>/scripts/tmux_pair.py send <pane-id> "<message>"
```

Multi-line messages are submitted via `load-buffer` + `paste-buffer` to avoid the issue where some agent TUIs interpret each newline as a submit. Single-line messages use plain `send-keys -l`. After the text, the helper sends Enter three times with small gaps; this works around agent TUIs that ignore the first Enter when a tool call is in flight. Override with `--no-enter` if needed.

Normal messages get a sender identity prefix automatically. Example: a writer pane with sender `wr.channel-slack` sending `REVIEW-READY: B2 ...` arrives as `[FROM: wr.channel-slack] REVIEW-READY: B2 ...`. Messages already starting with `[FROM:` are left unchanged, so manual prefixes are idempotent. Slash commands such as `/compact <focus>` are command traffic and are not prefixed. Spawned panes store their stable sender name in `@tmux-pair-sender`; `pane_title` is only a fallback because agent TUIs can overwrite it with spinner text.

## Token management & re-briefs

The default claude model is `claude-opus-4-7` (1M context). For 200k-context runs (cheaper, faster turn-around), use `--claude-model claude-opus-4-6` on `/pair` or `/triple`. The compact-watcher threshold scales automatically: 1M → 700k threshold (70%), 200k → 140k threshold. Override per-call with `python3 <plugin>/scripts/tmux_pair.py monitor --threshold-k <N>`.

The default claude reasoning effort is `max`, set as `--effort max` directly in the claude boot-command (race-free vs. the `/effort` slash, which can fail with "unknown or future model" right after a `/model` switch). Override per spawn with `--claude-effort <low|medium|high|xhigh|max>`; pass an empty string to skip the flag entirely so `claude` uses its own default or the `CLAUDE_CODE_EFFORT_LEVEL` env-var. Codex pane boot follows the user's configured CLI default; Codex engineer subagents use the documented Spark-first policy in the workflow briefing.

Long-running pairs/triples drift past the model-specific sweet spot where the agent still reasons cleanly. Three helper subcommands let any layer refresh the layer below:

```
python3 <plugin>/scripts/tmux_pair.py status <pane-id>
python3 <plugin>/scripts/tmux_pair.py compact <pane-id> --briefing-file <path> [--focus "<one-liner>"] [--timeout 300]
python3 <plugin>/scripts/tmux_pair.py monitor --orch-pane <id> --panes <id1> <id2> [...] [--threshold-k <N>] [--cooldown-sec <N>]
```

The orchestrator briefing kicks off `monitor` automatically as DUTY 0 (background watcher polls every 180s, pings the orchestrator when an engineer crosses the threshold; cooldown 600s between repeat pings on the same pane). Pair-mode does not auto-start the watcher: the human is in the loop and notices manually.

`status` returns JSON with the detected agent and the parsed token count. Claude prints `N tokens` in its footer, so the count is reliable. Codex usually does not, so its `tokens` field comes back `null`: fall back to a feel-based heuristic (elapsed wall-time, number of REVIEW cycles, whether the agent is repeating itself).

`compact` sends `/compact [focus]` to the pane (claude's official `/compact [instructions]` form), polls `capture-pane` for completion (claude prints `Conversation compacted`; for codex we accept a token-count drop ≥50% as a fallback), and then sends the re-brief from `--briefing-file` through the regular submit-with-retry path. The optional `--focus` hint shapes the summary so the agent retains plan + REVIEW-state + peer-protocol — without it the summary is generic and important context can drop.

**Authoring the re-brief.** After `/compact` the agent has lost the conversational state and only remembers the summary. The re-brief MUST stand on its own. Include:

- the agent's role (writer / reviewer / orchestrator)
- the concrete current task, phrased as if the agent is hearing it the first time
- a short progress recap (what the layer above has seen, what the agent has shipped)
- the next concrete step the agent should take
- the peer-protocol for this run, with current pane IDs
- the standards (commits, no `--no-verify`, language conventions)

Where the recap comes from depends on the layer:

- the orchestrator keeps a running progress log and authors re-briefs for its writer and reviewer
- the human keeps the same kind of log for any orchestrator it spawns; orchestrators get the richest re-brief because they own the most state
- at the topmost layer the person handles their own compact; a hand-authored re-brief there is fine

**Self-compact (engineer-driven).** Engineers may compact themselves between cycles. Pattern:

1. Write a self-re-brief file at `/tmp/self-compact-<role>-<window>.md` with plan-bullet, REVIEW-state, next step, peer pane ids, relevant standards.
2. Send to your own pane: `python3 <plugin>/scripts/tmux_pair.py send <eigener_pane> "/compact <focus>"`. The focus hint MUST mention plan + REVIEW-state + peer-protocol so claude's summary preserves them.
3. After settle (claude prints `Conversation compacted`), read the self-re-brief file and continue.
4. Signal `SELF-COMPACT-PLANNED: <bullet> <focus>` to the orchestrator/master once before triggering, so the watcher does not race with a parallel compact on the same pane.

Self-compact is the proactive path; orchestrator-compact is the reactive backstop driven by the watcher in DUTY 0. Codex panes have no `/compact` form; self-compact is claude-only.

**When to trigger.**

- between REVIEW cycles, never mid-edit or mid-tool-call
- claude pane > ~200k tokens (visible in footer)
- codex pane: by feel
- before a known long phase (e.g. starting Wave N) so the agent enters it fresh

**Parallelism.** To compact both engineers in a triple at once, run two `compact` calls with `&` from the orchestrator's shell; each call blocks for the duration of its poll loop.

## Common failure modes (summary)

The full list with diagnostics and recovery steps lives in `references/failure-modes.md`. The most common ones:

- **Send didn't submit.** Symptom: message visible in pane but cursor still in input. Cause: agent TUI ignored the Enter. Fix: re-send with the helper, which retries Enter; or send Enter manually.
- **Briefing landed before agent booted.** Symptom: message appears at the shell prompt instead of inside the TUI. Cause: 14-second delay too short for slow boot. Fix: re-send manually after the agent is ready.
- **Engineers ping human directly in triple mode.** Symptom: human inbox floods. Cause: briefing missed the "ping orchestrator, not human" instruction. Fix: orchestrator re-briefs the noisy engineer with the explicit pane id.
- **tmux session crashed mid-run.** Symptom: panes gone, worktree intact. Recovery: re-spawn the panes manually, point them at the existing worktree, and re-send the briefings with the current state attached.
- **Writer pushed without human OK.** Symptom: `git push` happened despite the brief saying "wait for human". Cause: briefing missing or weakly worded. Fix: spell out the push gate explicitly in the briefing template.

## Cleanup

After `DONE`:

```bash
cd <project-path>
git worktree remove ../<project-name>-wt-<feature>
git branch -d feature/<feature>      # after merge
tmux kill-window -t <window-name>
```

Cleanup is the human's call. Neither the orchestrator nor the engineers should remove worktrees, kill windows, or delete branches during a run.

## Companion skills (bundled)

The plugin ships two companion skills, both plugin-namespaced so they do not collide with user-local installs of the same names:

- **`/tmux-pair:gepa`**: Genetic-Pareto prompt/text-artifact optimization (paper arXiv:2507.19457). Used opt-in after rules-bootstrap to optimize the freshly generated `.claude/rules/*.md` against user-supplied test diffs. The orchestrator suggests it after a fresh bootstrap; the user runs it in their own pane (GEPA needs test diffs the orchestrator does not have). Skill files live under `skills/gepa/` (SKILL.md, scripts/gepa-loop.py, references/{patterns,gepa-library}.md).
- **`/tmux-pair:dg`**: Dinesh-vs-Gilfoyle adversarial code review. Two AI personas (one attacker, one defender) debate a diff or file until the defender concedes, defends, or the round limit hits. Useful as an optional pre-GATE-3 step on security/concurrency/auth/crypto/migration bullets where extra adversarial pressure pays off. Skill files live under `skills/dg/` (SKILL.md, gilfoyle-agent.md, dinesh-agent.md).

External companion (NOT bundled, install separately if you want it): the official `code-simplifier` plugin from `claude-plugins-official` for refactor-passes after a feature lands.

## Additional resources

### References

- **`references/gated-workflow.md`**: 5-gate workflow (Clarify, Reviewer-Readiness, Plan-Check, Loop, Final-Verify), subagent prompt templates, gate event vocabulary, gate-specific failure modes.
- **`references/pair-protocol.md`**: full event vocabulary, edge cases, escalation rules, and end-of-run handshake.
- **`references/triple-vs-pair.md`**: decision matrix with worked examples for choosing the mode.
- **`references/failure-modes.md`**: common failure modes with diagnostics, recovery steps, and prevention.

### Examples

- **`examples/writer-briefing.md`**: writer briefing template.
- **`examples/reviewer-briefing.md`**: reviewer briefing template.
- **`examples/orchestrator-briefing.md`**: orchestrator briefing template (the largest of the three).
