# Pair protocol — full event vocabulary

This is the long version of the loop summarised in `SKILL.md`. Use this when drafting a briefing, debugging a stalled pair, or deciding how to phrase a ping.

## Identifiers

Every message between panes is one line, prefixed with an event keyword in ALL CAPS. The keyword is the contract — humans and tools both grep for it.

```
EVENT: payload
EVENT: <multi-line payload, fine, but the first line carries the keyword>
```

The orchestrator additionally prefixes its messages to the master pane with `[Orchestrator <window-name>]` so the master can attribute pings at a glance.

## Writer events

| Event | When | Payload |
|-------|------|---------|
| `REVIEW-READY` | Writer finished one logical step, local checks green | one-line summary of the change |
| `DONE` | After `REVIEW: APPROVE` and commit | commit SHA + branch state (e.g. `pushed`, `local only`) |
| `BLOCKER` | Stuck on something the reviewer can't unblock | what is blocked, what was tried |
| `STATUS` | Reviewer asks for an update | one-line state |

## Reviewer events

| Event | When | Payload |
|-------|------|---------|
| `REVIEW: APPROVE` | Change is good as-is | optional one-line note |
| `REVIEW: <findings>` | Findings exist | numbered, falsifiable: file:line, problem, suggested direction |
| `BLOCKER` | Reviewer can't review (missing info, can't reproduce) | what is needed |

## Orchestrator events (triple mode only)

| Event | When | Payload |
|-------|------|---------|
| `BRIEF` | After recon, sent to writer and reviewer separately | role-specific briefing |
| `NUDGE` | Pair silent > 10 min | "stand?" or a sharper question |
| `PROCESS-NEEDS-FIX` | Engineer broke the protocol (e.g. used a sub-agent for recon when not allowed) | what was wrong, what to do instead |
| `MAJOR-STEP` | Phase done, sent to master | what completed, next phase |
| `BLOCKER` | Pair can't resolve, escalated to master | what's blocked, what was tried |
| `DONE` | Pair finished, branch ready | commit SHA, branch state, gates passed |
| `ABORT` | Pair is wedged, ending the run | why |

The orchestrator does NOT send `REVIEW-READY` or `REVIEW: ...` events. Those are engineer-to-engineer.

## What "falsifiable" means in a review

A finding is falsifiable if both writer and reviewer agree on a check that decides whether the finding is real.

Bad: "this could be cleaner"
Good: "src/auth.rs:42 — `User::from_token` swallows expired-token errors as `None`; downstream caller treats `None` as anonymous user. Suggest returning `Result<Option<User>, AuthError>` so the caller can distinguish."

Bad: "consider improving error handling"
Good: "src/handler.rs:120 — `unwrap()` on `serde_json::from_str` will panic on malformed input from the public webhook. Either return a 400 or document why malformed input is impossible."

Briefings should explicitly tell the reviewer to phrase findings like the second column. Without that nudge, reviews drift toward generic advice.

## End-of-run handshake

The pair is done when:

1. Writer commits the final change (Conventional Commits, no `--no-verify`, no AI co-author trailer).
2. Local gates pass: build, lint, tests. The set of gates should be in the briefing.
3. Reviewer responds `REVIEW: APPROVE` to the final `REVIEW-READY`.
4. Writer pings `DONE: <sha> <branch state>`.
5. In triple mode: orchestrator forwards `[Orchestrator <window>] DONE: <sha> <branch state>` to master.

Push happens only after master OK. Whether the briefing said so explicitly or not, the orchestrator (or the writer in pair mode) waits.

## Common edge cases

### Disagreement that won't resolve

If writer and reviewer go three rounds on the same finding without converging, escalate:

- Pair mode: writer pings master with `BLOCKER: <one-paragraph framing of the disagreement>`.
- Triple mode: writer pings orchestrator with the same. Orchestrator decides: ask master, or break the tie themselves if the disagreement is about style and not correctness.

Style tie-breaks are valid orchestrator output. Correctness tie-breaks go to master.

### Reviewer wants to write code

Reviewer code is anti-pattern. If reviewer thinks the writer is wrong, reviewer phrases the finding precisely enough that the writer can implement it. If the writer can't, the writer pings `BLOCKER`. Reviewer never edits files in the worktree.

### Writer wants to skip the review

The pair loses its value the moment writer commits without `REVIEW: APPROVE`. The briefing should say this explicitly: "do not commit without an APPROVE event from the reviewer". If the writer skips anyway, the reviewer pings `PROCESS-NEEDS-FIX` (triple mode: to the writer, copy to orchestrator).

### Push without master OK

The writer's briefing should explicitly say: "push only after master OK". If the writer pushes anyway, the master decides:

- accept the push and review post-hoc, or
- revert and rerun the review

This is a master decision, not an orchestrator decision.
