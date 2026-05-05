---
name: tmux-pair-orchestration
description: This skill should be used when the user asks to "spin up a writer/reviewer pair", "run two agents on this", "pair these agents", "set up an orchestrator + pair", "launch a triple", "use the tmux-pair workflow", or otherwise wants to run two or three coding agents collaboratively in tmux panes wired up via git worktrees. Covers the pair protocol, when to choose pair vs. triple, durable standards (claude --append-system-prompt-file + codex AGENTS.md), gated workflow (Clarify → Reviewer-Readiness → Plan-Check → Loop → Final-Verify with rules-bootstrap loop, language templates for 7 stacks, REVIEW-READY-3-Felder, CLARIFY-NEEDED, Plan-Update-Commit, COMPLETE-Format), Compact-Watcher with model-aware threshold, --claude-model + --no-worktree flags, briefing templates, and recovery from common failure modes.
version: 0.5.0
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

- writer: `claude` (strong at structured implementation, follows briefings closely)
- reviewer: `codex` (terminal-driven, sharp on diff-level critique and edge cases)
- orchestrator: `claude` (recon + briefing + filtering)

These are defaults baked into the bundled script. Different agent CLIs work fine — point `--writer-agent`, `--reviewer-agent`, `--orchestrator-agent` at any name registered in `~/.config/tmux-pair/agents.json`.

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

- **claude panes** boot with `--append-system-prompt-file <path>` pointing at `/tmp/tmux-pair-durable-<window>-<role>.md`. The file is generated per-spawn from a single in-script constant (`DURABLE_STANDARDS_PROMPT`) so updates to standards land in the next spawn automatically.
- **codex panes** read `AGENTS.md` from the worktree root. The plugin writes that file when a real worktree is created (i.e. not when `--no-worktree` is passed). If the repo already owns an `AGENTS.md`, the plugin leaves it alone — repo standards win.
- **`--no-worktree` runs** (direct on the project branch) skip the AGENTS.md write to avoid polluting the repo. Codex in that mode receives standards via the briefing only — same behaviour as before durable standards existed.
- **`agents.json` overrides** are respected: if the user has remapped `claude` to a wrapper or alternative binary, the plugin does NOT inject `--append-system-prompt-file` blindly. The wrapper can read the standards file itself.

The standards block covers: real Umlaute (no ASCII substitutes), Conventional Commits with no `--no-verify` and no AI-co-author trailer, the REVIEW-READY 3-field format, the honesty protocol (past-tense claims need same-turn tool evidence), drift signals (em-dashes, progress markers, ALL-CAPS headers, "should I"-after-clear-directive, etc.), the `incidental:` format for PostToolUse-hook fmt drift, the worktree-as-sandbox rule, the no-pre-existing-issues rule, recall-discipline (cite the relevant rule + memory before sensitive actions), and the bullet-start ritual (class + relevant rules + common BLOCKER-classes before the first edit on a bullet).

## Gated workflow (default)

Both `/pair` and `/triple` enforce four quality gates before code lands on the branch. The bundled briefings already encode them; this is the high-level shape:

```
Recon -> GATE 1 Clarify -> GATE 1.5 Reviewer-Readiness -> Plan -> GATE 2 Plan-Check -> Implementation Loop -> GATE 3 Final-Verify -> Human merges
```

- **GATE 1 (Clarify)** — whoever owns the gate (orchestrator in triple, human in pair) calls `AskUserQuestion` directly in their own pane. The triple orchestrator does NOT ping the human for clarify — human only sees a `GATE-1-ESCALATE` if a question is outside the orchestrator's authority. Engineers wait for `PLAN-LOCKED:`.
- **GATE 1.5 (Reviewer-Readiness)** — one scoped subagent (`tmux-pair:reviewer-readiness-check`, Sonnet 4.6, Read+Grep+Glob+Bash, NO Edit/Write) reads `.claude/rules/*.md` and scores an 8-item checklist (style, tests, architecture, anti-patterns, naming, security, build, domain). On `NEEDS-RULES`, the orchestrator runs a bootstrap loop: per gap one `AskUserQuestion`, then `tmux-pair:rules-bootstrap` (Sonnet 4.6, R+G+G+B+Edit+Write) bakes `.claude/rules/<topic>.md` from plugin language templates (Rust, TypeScript, Python, Go, JavaScript, Java, generic) + repo recon + user answers, then re-run readiness-check. Loop terminates at READY or after iteration 3 with user-decided abort/partial-coverage/manual-amend. Optional opt-in `/gepa` pass after fresh rules; the plugin does not call `/gepa` automatically.
- **GATE 2 (Plan-Check)** — one scoped subagent (`tmux-pair:gate-2-plan-check`, Sonnet 4.6, Read+Grep+Glob+Bash, NO Edit/Write tools) verifies the plan goal-backward AND checks plan quality. `BLOCKER` escalates to human, no auto-retry. Scoped tools = the agent structurally cannot commit code instead of just verdicting.
- **Implementation Loop** — standard pair protocol (`REVIEW-READY` -> `REVIEW` -> fix -> `DONE`). Smart test subset per cycle (only diff-touched tests), full suite + lint + build pre-DONE. Mid-run findings persisted to memory + rules + engineer-briefing-amendment, not just discussed in-pane.
- **GATE 3 (Final-Verify)** — two parallel scoped subagents check the diff: `tmux-pair:gate-3-verifier` (Haiku 4.5, runs build/test, checks plan-bullet coverage) + `tmux-pair:gate-3-code-reviewer` (Sonnet 4.6, adversarial diff review). Both PASS or human pings the master.

The implementation loop adds five protocol elements that the briefings enforce:

- **REVIEW-READY 3 mandatory fields** — every `REVIEW-READY:` ping carries (1) what changed (file:line + LOC-diff), (2) verification (`workspace-gate=PASS` + test counts, or `workspace-gate=N/A doc-only`), (3) plan-bullet/pain reference. Pings without these fields are blocked by the reviewer without code review.
- **CLARIFY-NEEDED** — when an engineer hits a user-decision question mid-loop (scope, behavior, UX, architecture choice, naming conflict, trade-off not in the plan), they ping `CLARIFY-NEEDED: <question + 2-4 options>`. In a pair the master receives this and forwards via `AskUserQuestion`. In a triple the orchestrator handles it with its own `AskUserQuestion`. Engineers do NOT decide user-facing questions on their own.
- **Plan-Update-Commit** — if a bullet hits a hard cap (LOC limit, file-size cap) or the estimate drifts more than ~50%, the writer commits a `docs(plan-amendment): ...` BEFORE the implementation commit that breaks the cap. `REVIEW-READY` on a bullet with documented drift but no preceding amendment commit is a `BLOCK`.
- **COMPLETE-Ping format** — orchestrator/master sends `COMPLETE: <Phase>. gate-3=PASS via <verifier-name + code-reviewer-name>. <diff-stat>. Bezug: <plan goals all met>.` only AFTER GATE 3 returned PASS, never before.
- **Recall-Discipline + Bullet-Start-Ritual** — engineers cite the relevant rule + memory entry before any sensitive action (commit, push, external API), and post a class + rules + common BLOCKER-classes block before the first edit on each new plan-bullet.

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

   - `REVIEW: APPROVE` — change is good as-is.
   - `REVIEW: <findings>` — concrete, falsifiable findings (file:line, problem, suggested direction). No vague "consider improving".

3. If `APPROVE`, writer commits (Conventional Commits, no `--no-verify`, no AI co-author trailer) and pings `DONE: <commit-sha> <branch-state>`.

   If findings, writer fixes, pings `REVIEW-READY` again. Loop.

4. If the pair stalls — disagreement, missing info, suspected upstream bug — either side pings `BLOCKER: <what>` (in pair mode: to human; in triple mode: to orchestrator).

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

- **`examples/writer-briefing.md`** — implementation brief: pointers, deliverables, pair protocol with reviewer pane id, standards.
- **`examples/reviewer-briefing.md`** — review brief: what to check (falsifiable), how to phrase findings, pair protocol with writer pane id.
- **`examples/orchestrator-briefing.md`** — full duty list: recon, brief engineers, watch loop, report to human.

These are starting points. Adapt to the task at hand. The bundled script generates a baseline briefing automatically; the templates are useful when overriding the briefing or when the orchestrator writes one from scratch after recon.

## Sending messages between panes

The cross-pane primitive is `tmux_pair.py send`:

```
python3 <plugin>/scripts/tmux_pair.py send <pane-id> "<message>"
```

Multi-line messages are submitted via `load-buffer` + `paste-buffer` to avoid the issue where some agent TUIs interpret each newline as a submit. Single-line messages use plain `send-keys -l`. After the text, the helper sends Enter three times with small gaps; this works around agent TUIs that ignore the first Enter when a tool call is in flight. Override with `--no-enter` if needed.

## Token management & re-briefs

The default claude model is `claude-opus-4-7` (1M context). For 200k-context runs (cheaper, faster turn-around), use `--claude-model claude-opus-4-6` on `/pair` or `/triple`. The compact-watcher threshold scales automatically: 1M → 700k threshold (70%), 200k → 140k threshold. Override per-call with `python3 <plugin>/scripts/tmux_pair.py monitor --threshold-k <N>`.

Long-running pairs/triples drift past the model-specific sweet spot where the agent still reasons cleanly. Three helper subcommands let any layer refresh the layer below:

```
python3 <plugin>/scripts/tmux_pair.py status <pane-id>
python3 <plugin>/scripts/tmux_pair.py compact <pane-id> --briefing-file <path>
python3 <plugin>/scripts/tmux_pair.py monitor --orch-pane <id> --panes <id1> <id2> [...]
```

The orchestrator briefing kicks off `monitor` automatically as DUTY 0 (background watcher polls every 180s, pings the orchestrator when an engineer crosses the threshold; cooldown 600s between repeat pings on the same pane). Pair-mode does not auto-start the watcher — the human is in the loop and notices manually.

`status` returns JSON with the detected agent and the parsed token count. Claude prints `N tokens` in its footer, so the count is reliable. Codex usually does not, so its `tokens` field comes back `null` — fall back to a feel-based heuristic (elapsed wall-time, number of REVIEW cycles, whether the agent is repeating itself).

`compact` sends `/compact` to the pane, polls `capture-pane` for completion (claude prints `Conversation compacted`; for codex we accept a token-count drop ≥50% as a fallback), and then sends the re-brief from `--briefing-file` through the regular submit-with-retry path.

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

## Additional resources

### References

- **`references/gated-workflow.md`** — 4-gate workflow (Clarify, Plan-Check, Loop, Final-Verify), subagent prompt templates, gate event vocabulary, gate-specific failure modes.
- **`references/pair-protocol.md`** — full event vocabulary, edge cases, escalation rules, and end-of-run handshake.
- **`references/triple-vs-pair.md`** — decision matrix with worked examples for choosing the mode.
- **`references/failure-modes.md`** — common failure modes with diagnostics, recovery steps, and prevention.

### Examples

- **`examples/writer-briefing.md`** — writer briefing template.
- **`examples/reviewer-briefing.md`** — reviewer briefing template.
- **`examples/orchestrator-briefing.md`** — orchestrator briefing template (the largest of the three).
