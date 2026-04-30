# Failure modes

Common ways pair and triple runs go wrong, with diagnostics, recovery, and prevention.

## 1. Send didn't submit

**Symptom:** The peer's text is visible in the target pane's input area, but the cursor is still inside the input box. The agent never reacted.

**Cause:** Some agent TUIs ignore the first Enter when a tool call is in flight, or interpret newlines inside multi-line text as line breaks instead of submits.

**Diagnosis:**

```
python3 <plugin>/scripts/tmux_pair.py capture <pane-id> --lines 50
```

Look at the last few lines. If you see the message text but no agent response below it, the submit didn't happen.

**Recovery:** Re-run `send` against the same pane with no payload (just the Enter helper) by repeating the same command — or send Enter manually:

```
tmux send-keys -t <pane-id> C-m
```

**Prevention:** The bundled helper sends Enter three times with small gaps to work around the in-flight-tool case. For multi-line text it uses `load-buffer` + `paste-buffer -d` so the agent sees the whole block as one input. Don't bypass the helper with raw `tmux send-keys` for cross-pane messages — you'll re-introduce the bug.

## 2. Briefing landed before the agent booted

**Symptom:** The briefing text appears at the agent's shell prompt instead of inside the TUI. The shell tries to execute the first word as a command.

**Cause:** The 14-second boot delay was too short for the agent's startup (cold disk, slow initialization, prompt input).

**Recovery:** Wait until the agent is fully booted. Re-send the briefing from the tempfile if it still exists, or from the script's stdout if it was logged:

```
python3 <plugin>/scripts/tmux_pair.py send <pane-id> "$(cat /tmp/tmuxpair-briefing-XXXX.txt)"
```

If the tempfile is gone, regenerate the briefing manually using the templates in `examples/`.

**Prevention:** If you know the agents are slow to boot on a cold machine, add a wrapper that calls the spawn and sleeps longer before the first send. The 14 seconds is a heuristic that works for warm systems.

## 3. Engineers ping master directly in triple mode

**Symptom:** The master pane gets `REVIEW-READY`, `BLOCKER`, or other engineer-level events directly. Orchestrator sees nothing.

**Cause:** The engineer's briefing missed the "ping orchestrator at <pane-id>, not master" instruction, or the orchestrator's recon-phase briefing didn't propagate the right pane id.

**Diagnosis:** Look at the briefing the orchestrator sent. If it doesn't contain the orchestrator's pane id and an explicit "do not ping master directly" line, that's the bug.

**Recovery:** Orchestrator re-briefs the noisy engineer:

```
python3 <plugin>/scripts/tmux_pair.py send <engineer-pane> "PROCESS-NEEDS-FIX: All pings go to <orch-pane>, not master. Re-route any open ping you have to <orch-pane>."
```

**Prevention:** The orchestrator briefing template in `examples/orchestrator-briefing.md` has the explicit "your pane id, copy this into engineer briefings" line. Don't drop it.

## 4. tmux session crashed mid-run

**Symptom:** Panes are gone. The worktree is intact on disk. Branch may have uncommitted changes.

**Cause:** tmux server crash, terminal app crash, OS reboot, etc.

**Recovery:**

1. Check the worktree state:
   ```
   git -C <worktree-path> status
   git -C <worktree-path> log -5 --oneline
   ```
2. Re-create the tmux window manually:
   ```
   tmux new-window -t <session>: -n <window-name> -c <worktree-path>
   ```
3. Add panes for the missing roles (writer/reviewer/orchestrator) using the orchestrator script's `spawn` subcommand or raw `tmux split-window`.
4. Force the layout (`main-vertical` for pair, `main-horizontal` for triple).
5. Send recovery briefings that include a snapshot of the pre-crash state (uncommitted changes summary, last commit, last review event) so the agents pick up where they left off rather than starting over.

**Prevention:** None — this is rare. Recovery is the design.

## 5. Writer pushed without master OK

**Symptom:** A `git push` happened. The branch is on the remote.

**Cause:** Briefing missing or weakly worded on the push gate.

**Recovery (master decision):**

- Accept and review post-hoc. Open a PR or just `git log` the new commits and audit. If review is clean, no action. If not, commit fixes and push.
- Revert and rerun. `git push --force-with-lease origin <branch>:<branch>` after `git reset --hard <pre-push-sha>` is the destructive path; only use if the push contains real problems.

**Prevention:** Spell the gate explicitly in the writer briefing: "Do not run `git push` until master replies `PUSH-OK`. Commits are fine; pushes are not." Double-blanks like "wait for master before push" are too soft to override the writer's instinct to ship.

## 6. Reviewer drifts into nitpicking

**Symptom:** The pair loops on style and naming forever; substantive findings are buried or absent.

**Cause:** Reviewer briefing didn't constrain the review to falsifiable findings.

**Recovery:** Re-brief the reviewer:

```
PROCESS-NEEDS-FIX: Drop style nits. Findings must be falsifiable bugs, missed requirements, or correctness issues. Naming/formatting goes to a TODO comment, not a review event.
```

**Prevention:** The reviewer briefing template (`examples/reviewer-briefing.md`) has the falsifiable-findings rule with examples. Use it.

## 7. Subagent leak

**Symptom (triple mode):** The writer or reviewer used a sub-agent (their own delegate) to do recon, and the sub-agent's output is being used as the basis for `REVIEW-READY` or `REVIEW`.

**Cause:** The pair's value comes from direct file reads, greps, and git inspection — first-hand information. A sub-agent inserts a layer of summarization that hides things.

**Recovery (orchestrator):** Block the current event, demand a redo:

```
PROCESS-NEEDS-FIX: <event> rejected because it's based on a sub-agent's recon. Redo with direct read/grep/git-log; sub-agent output is not a basis for pair events.
```

**Prevention:** Add the rule to both engineer briefings explicitly: "Use direct reads/greps/git inspections. Do not delegate recon to a sub-agent."

## 8. Worktree contention

**Symptom:** Worktree creation fails with "fatal: '<path>' already exists" or the new worktree's branch is already checked out elsewhere.

**Cause:** A previous run of the same feature was not cleaned up, or the master ran the spawn twice with the same feature name.

**Recovery:**

```
git -C <main-repo> worktree list
git -C <main-repo> worktree remove <stale-path>
git -C <main-repo> branch -D feature/<feature>   # if the branch is also stale
```

Then re-run the spawn.

**Prevention:** Cleanup hygiene. After every `DONE`, remove the worktree and delete the branch (after merge). Stale worktrees pile up fast otherwise.
