---
name: tmux-pair-orchestration
description: This skill should be used when the user asks to "spin up a writer/reviewer pair", "run two agents on this", "pair these agents", "set up an orchestrator + pair", "launch a triple", "use the tmux-pair workflow", or otherwise wants to run two or three coding agents collaboratively in tmux panes wired up via git worktrees. Covers the pair protocol, when to choose pair vs. triple, briefing templates, and recovery from common failure modes.
version: 0.1.0
---

# tmux-pair-orchestration

Run two or three coding agents collaboratively on a single task. Each agent lives in its own tmux pane, all panes share a fresh `git worktree`, and the agents talk peer-to-peer through a small Python helper.

This skill applies whenever the user wants to set up such a pair or triple, monitor it, draft briefings, recover from a stuck loop, or decide between the two modes.

## The two modes

| Mode | Agents | Layout | Master role |
|------|--------|--------|-------------|
| **pair** | Writer + Reviewer | side by side (`main-vertical`) | active relay between the two agents, hands-on |
| **triple** | Writer + Reviewer + Orchestrator | Orchestrator on top (full width), Writer/Reviewer below (`main-horizontal`) | hands-off after spawn, only sees major-event pings |

Default agent assignments (overridable):

- writer: `codex` (terminal-driven, fast on pure code)
- reviewer: `claude` (good at structural review, asks falsifiable questions)
- orchestrator: `claude` (recon + briefing + filtering)

These are defaults baked into the bundled script. Different agent CLIs work fine — point `--writer-agent`, `--reviewer-agent`, `--orchestrator-agent` at any name registered in `~/.config/tmux-pair/agents.json`.

## When to use which mode

Choose **pair** when:

- the task is small and well-scoped (one to a few files)
- the master is willing to be the relay between writer and reviewer
- recon is shallow or already done

Choose **triple** when:

- the task spans many files or unfamiliar code
- the master wants to step away and only get pinged on real events
- a dedicated agent doing recon and writing briefings will save more time than it costs
- the feedback "engineers brief themselves and miss the real problem" is plausible

A triple is overhead for trivial tasks. A pair leaks too much into the master's attention for big ones. See `references/triple-vs-pair.md` for a longer decision matrix with worked examples.

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

4. If the pair stalls — disagreement, missing info, suspected upstream bug — either side pings `BLOCKER: <what>` (in pair mode: to master; in triple mode: to orchestrator).

The full protocol with all event types and edge cases lives in `references/pair-protocol.md`.

## Master-offload (triple mode)

The point of the triple is that the master delegates the relay to the orchestrator. The master:

- sends the initial task only to the orchestrator, NOT to the engineers
- sees only orchestrator-tagged pings: `[Orchestrator <window>] MAJOR-STEP / BLOCKER / DONE / ABORT`
- does NOT relay between writer and reviewer
- does NOT clean up worktrees during the run; cleanup decisions stay with the master, but only after `DONE`

The orchestrator does:

- recon (read upstream docs, grep the codebase, identify pointers)
- write writer briefing AND reviewer briefing as separate messages
- watch the pair loop at high level (capture-pane + nudge if silent > 10 min)
- filter engineer pings: only forward MAJOR-STEP, BLOCKER, DONE, ABORT to master

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

Both commands assume the master is already inside a tmux session.

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
- **`examples/orchestrator-briefing.md`** — full duty list: recon, brief engineers, watch loop, report to master.

These are starting points. Adapt to the task at hand. The bundled script generates a baseline briefing automatically; the templates are useful when overriding the briefing or when the orchestrator writes one from scratch after recon.

## Sending messages between panes

The cross-pane primitive is `tmux_pair.py send`:

```
python3 <plugin>/scripts/tmux_pair.py send <pane-id> "<message>"
```

Multi-line messages are submitted via `load-buffer` + `paste-buffer` to avoid the issue where some agent TUIs interpret each newline as a submit. Single-line messages use plain `send-keys -l`. After the text, the helper sends Enter three times with small gaps; this works around agent TUIs that ignore the first Enter when a tool call is in flight. Override with `--no-enter` if needed.

## Common failure modes (summary)

The full list with diagnostics and recovery steps lives in `references/failure-modes.md`. The most common ones:

- **Send didn't submit.** Symptom: message visible in pane but cursor still in input. Cause: agent TUI ignored the Enter. Fix: re-send with the helper, which retries Enter; or send Enter manually.
- **Briefing landed before agent booted.** Symptom: message appears at the shell prompt instead of inside the TUI. Cause: 14-second delay too short for slow boot. Fix: re-send manually after the agent is ready.
- **Engineers ping master directly in triple mode.** Symptom: master inbox floods. Cause: briefing missed the "ping orchestrator, not master" instruction. Fix: orchestrator re-briefs the noisy engineer with the explicit pane id.
- **tmux session crashed mid-run.** Symptom: panes gone, worktree intact. Recovery: re-spawn the panes manually, point them at the existing worktree, and re-send the briefings with the current state attached.
- **Writer pushed without master OK.** Symptom: `git push` happened despite the brief saying "wait for master". Cause: briefing missing or weakly worded. Fix: spell out the push gate explicitly in the briefing template.

## Cleanup

After `DONE`:

```bash
cd <project-path>
git worktree remove ../<project-name>-wt-<feature>
git branch -d feature/<feature>      # after merge
tmux kill-window -t <window-name>
```

Cleanup is the master's call. Neither the orchestrator nor the engineers should remove worktrees, kill windows, or delete branches during a run.

## Additional resources

### References

- **`references/pair-protocol.md`** — full event vocabulary, edge cases, escalation rules, and end-of-run handshake.
- **`references/triple-vs-pair.md`** — decision matrix with worked examples for choosing the mode.
- **`references/failure-modes.md`** — common failure modes with diagnostics, recovery steps, and prevention.

### Examples

- **`examples/writer-briefing.md`** — writer briefing template.
- **`examples/reviewer-briefing.md`** — reviewer briefing template.
- **`examples/orchestrator-briefing.md`** — orchestrator briefing template (the largest of the three).
