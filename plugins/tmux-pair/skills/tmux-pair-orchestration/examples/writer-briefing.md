# Writer briefing template

Adapt the bracketed fields to the task. The bundled script generates a baseline version automatically; this template is what an orchestrator (or master) writes from scratch when overriding the default or when the task has shape that the default doesn't cover.

```
[ROLE: Writer]

You are paired with the reviewer at pane <REVIEWER-PANE-ID>.

WORKTREE: <worktree-path>
BRANCH:   <branch>
BASE:     <base-ref>

TASK
<one-paragraph statement of the deliverable. Be concrete. Reference files,
functions, line numbers when known.>

POINTERS (from recon)
- <file:line> — <what's there, why it matters>
- <file:line> — <what's there, why it matters>
- Existing analogue: <file>::<function> does <thing>; the new code should follow this shape.

DELIVERABLES
- <change 1, e.g. "Add `foo` field to `Bar` struct in src/bar.rs">
- <change 2, e.g. "Wire `foo` through to the request handler in src/api.rs">
- Tests: <which tests prove the change works; whether to add new ones>

GATES
- Build:  <command, e.g. `cargo build --workspace`>
- Lint:   <command, e.g. `cargo clippy --workspace --all-targets -- -D warnings`>
- Tests:  <command, e.g. `cargo test --workspace`>
All gates green before `REVIEW-READY`.

PAIR PROTOCOL
- After each meaningful change, run gates locally, then ping reviewer:
    python3 <plugin>/scripts/tmux_pair.py send <REVIEWER-PANE-ID> "REVIEW-READY: <one-line summary>"
- Reviewer replies REVIEW: APPROVE or REVIEW: <findings>.
- If APPROVE: commit (Conventional Commits, no --no-verify, no AI co-author trailer).
  Then ping: ... send <REVIEWER-PANE-ID> "DONE: <commit-sha> <branch state>"
- If findings: fix, gates again, REVIEW-READY again. Loop.
- BLOCKER: ping reviewer (and orchestrator if triple mode) with what is blocked
  and what was tried.

PUSH GATE
Do NOT run `git push` until master replies `PUSH-OK`. Commits are fine; pushes
are not.

STANDARDS
- Conventional Commits.
- No --no-verify, no skipping pre-commit hooks.
- No AI co-author trailer in commit messages.
- Tests must pass before commit.
- Use sub-agents for big code searches if you want, but the basis for
  REVIEW-READY claims must be direct reads/greps/git-inspection. Don't relay
  a sub-agent's summary as fact.

START. Read POINTERS, plan one logical step, code, run gates, REVIEW-READY.
```

## Notes on adaptation

- **Pointers are mandatory.** A briefing without pointers is a briefing without recon. If you don't have pointers, do recon first or ask master.
- **Gates are mandatory.** "Tests must pass" without naming the command is too soft.
- **Push gate is mandatory.** Even if you trust the writer, the gate is cheap and catches one of the most common failure modes (see `references/failure-modes.md` §5).
- **The pane id of the reviewer must be in the briefing.** Not "the other pane", not "the reviewer", but `%N`.
