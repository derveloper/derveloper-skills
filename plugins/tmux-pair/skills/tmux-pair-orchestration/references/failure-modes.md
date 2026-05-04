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

## 3. Engineers ping human directly in triple mode

**Symptom:** The human pane gets `REVIEW-READY`, `BLOCKER`, or other engineer-level events directly. Orchestrator sees nothing.

**Cause:** The engineer's briefing missed the "ping orchestrator at <pane-id>, not human" instruction, or the orchestrator's recon-phase briefing didn't propagate the right pane id.

**Diagnosis:** Look at the briefing the orchestrator sent. If it doesn't contain the orchestrator's pane id and an explicit "do not ping human directly" line, that's the bug.

**Recovery:** Orchestrator re-briefs the noisy engineer:

```
python3 <plugin>/scripts/tmux_pair.py send <engineer-pane> "PROCESS-NEEDS-FIX: All pings go to <orch-pane>, not human. Re-route any open ping you have to <orch-pane>."
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

## 5. Writer pushed without human OK

**Symptom:** A `git push` happened. The branch is on the remote.

**Cause:** Briefing missing or weakly worded on the push gate.

**Recovery (human decision):**

- Accept and review post-hoc. Open a PR or just `git log` the new commits and audit. If review is clean, no action. If not, commit fixes and push.
- Revert and rerun. `git push --force-with-lease origin <branch>:<branch>` after `git reset --hard <pre-push-sha>` is the destructive path; only use if the push contains real problems.

**Prevention:** Spell the gate explicitly in the writer briefing: "Do not run `git push` until human replies `PUSH-OK`. Commits are fine; pushes are not." Double-blanks like "wait for human before push" are too soft to override the writer's instinct to ship.

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

**Cause:** A previous run of the same feature was not cleaned up, or the human ran the spawn twice with the same feature name.

**Recovery:**

```
git -C <main-repo> worktree list
git -C <main-repo> worktree remove <stale-path>
git -C <main-repo> branch -D feature/<feature>   # if the branch is also stale
```

Then re-run the spawn.

**Prevention:** Cleanup hygiene. After every `DONE`, remove the worktree and delete the branch (after merge). Stale worktrees pile up fast otherwise.

## 9. Compact-Watcher exited silently

**Symptom:** Engineer-pane has crossed the threshold token-count (visible in claude footer or via `status`-subcommand) but no `[Compact-Watcher] %X bei Yk tokens`-ping arrived at the orchestrator. The orchestrator never triggered a `compact`-Re-Brief, the engineer drifts.

**Cause:** Watcher process died (orchestrator-pane disappeared earlier than expected, watcher's auto-exit triggered after 5 empty captures; OR the original `Bash(run_in_background=true)` lost its handle on tmux-restart; OR the watcher was never spawned because DUTY 0 was skipped).

**Diagnosis:**

```
ps -ef | grep tmux_pair.py | grep monitor
```

If no process shows up, the watcher is gone.

**Recovery:** Orchestrator restarts the watcher manually:

```
python3 <plugin>/scripts/tmux_pair.py monitor \
  --orch-pane <orch-pane> \
  --panes <writer-pane> <reviewer-pane> \
  --threshold-k <model-aware-value>
```

Use the model-aware threshold (140k for 200k-context models, 700k for 1M-context). Override per-call if the model is unusual.

**Prevention:** Orchestrator briefing makes the watcher-spawn DUTY 0 (the very first action post-recon, before GATE 1). The watcher is fire-and-forget but the orchestrator should `ps` for it once after Gate 2 plan-lock to confirm it's still running.

## 10. Repo-owned AGENTS.md conflicts with plugin standards

**Symptom:** Codex pane (in worktree-mode) does not reference the plugin's standards (no Umlaut-discipline, no REVIEW-READY 3-field format, no recall-discipline). Engineers' codex partner contradicts the writer's own standards.

**Cause:** The repo already shipped an `AGENTS.md` at its root. The plugin sees a pre-existing file and respects it (does NOT overwrite, does NOT append) so the worktree carries the repo's standards but not the plugin's. Codex reads the repo file and never sees the plugin standards. Documented behaviour in `_write_codex_standards_to_worktree`.

**Diagnosis:**

```
ls -la <worktree>/AGENTS.md
head -5 <worktree>/AGENTS.md
```

If the file exists and looks like a project-specific standards file (not the plugin-generated one), the plugin skipped its write.

**Recovery (per-run):** orchestrator copies the plugin standards into the briefing user-message anyway (the `STANDARDS_BLOCK` + `RECALL_DISCIPLINE_BLOCK` + `BULLET_START_RITUAL_BLOCK` + `PAIR_PROTOCOL_BLOCK` are still injected via the briefing). Codex sees them once at boot but loses them at `/compact`.

**Recovery (long-term):** append the plugin's standards to the repo's AGENTS.md as a tagged subsection (`## Plugin: tmux-pair durable standards`) and commit. Future runs in that repo carry both standards.

**Prevention:** plugin-side append-mode is on the backlog. For now, repos that own AGENTS.md should consume the plugin standards manually (or the user does the merge once per repo).

## 11. Durable-standards file missing for claude

**Symptom:** Claude pane boots without `--append-system-prompt-file` argument, or the argument points at a nonexistent file. Standards do not survive `/compact`.

**Cause:** (a) `agents.json` override that doesn't start with the bare `claude`-token (the plugin then leaves the boot command unchanged on purpose); OR (b) `/tmp` got cleared between spawn and read (rare, OS-level cleanup); OR (c) the plugin ran out of disk space and `_write_durable_standards_file` failed silently (write_text raises but caller doesn't catch).

**Diagnosis:**

```
ls -la /tmp/tmux-pair-durable-<window>-*.md
ps -ef | grep claude | grep append-system-prompt
```

**Recovery:** regenerate the file from the running plugin process and re-spawn the claude pane:

```
python3 -c "
import sys
sys.path.insert(0, '<plugin>/scripts')
import tmux_pair
print(tmux_pair.DURABLE_STANDARDS_PROMPT)
" > /tmp/tmux-pair-durable-<window>-<role>.md
```

Then kill and re-spawn the pane, or pass the path manually via `claude --append-system-prompt-file <path>`.

**Prevention:** none mid-run. For (a), if you intentionally use a wrapper, point it at the standards file yourself. For (b)/(c), the plugin should be hardened to fail loudly; that's on the backlog.
