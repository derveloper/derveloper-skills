# Pair protocol — full event vocabulary

This is the long version of the loop summarised in `SKILL.md`. Use this when drafting a briefing, debugging a stalled pair, or deciding how to phrase a ping. Briefings use a slim default and include optional standards/procedure blocks only when `--with-standards` or `--greenfield` is enabled.

## Identifiers

Every message between panes is one line, prefixed with an event keyword in ALL CAPS. The keyword is the contract — humans and tools both grep for it.

```
EVENT: payload
EVENT: <multi-line payload, fine, but the first line carries the keyword>
```

The orchestrator additionally prefixes its messages to the human pane with `[Orchestrator <window-name>]` so the human can attribute pings at a glance.

## Writer events

| Event | When | Payload |
|-------|------|---------|
| `REVIEW-READY` | Writer finished one logical step, local checks green | THREE mandatory fields (sonst BLOCK ohne Code-Review): (1) what changed (file:line + LOC-diff), (2) verification (`workspace-gate=PASS` + test counts, or `workspace-gate=N/A doc-only`), (3) plan-bullet/pain reference |
| `DONE` | After `REVIEW: APPROVE` and commit | commit SHA + branch state (e.g. `pushed`, `local only`) |
| `BLOCKER` | Stuck on something the reviewer can't unblock — broken build, broken test, missing dependency | what is blocked, what was tried |
| `CLARIFY-NEEDED` | Stuck on a question only the user can answer (scope, behavior, UX, architecture choice, naming conflict, trade-off not in plan) | the question + 2-4 concrete options with trade-offs. In a pair sent to the master; in a triple sent to the orchestrator. The receiver translates this into an `AskUserQuestion` call — engineers do NOT decide user-facing questions on their own. |
| `STATUS` | Reviewer asks for an update | one-line state |

## Reviewer events

| Event | When | Payload |
|-------|------|---------|
| `REVIEW: APPROVE` | Change is good as-is, all Pre-APPROVE checks pass | optional one-line note. Pre-APPROVE checks: `git status` clean, REVIEW-READY had the 3 mandatory fields, no `--no-verify` / AI-co-author, no Drift-Signale (em-dashes, progress markers, etc.) |
| `REVIEW: BLOCK <reason>` | Findings exist OR Pre-APPROVE check fails | numbered, falsifiable: file:line, problem, suggested direction. No vague "consider improving" |
| `BLOCKER` | Reviewer can't review (missing info, can't reproduce) | what is needed |
| `CLARIFY-NEEDED` | Reviewer hits a user-decision question (e.g. accept-as-is vs require fix) | same shape as writer's CLARIFY-NEEDED — question + options. Receiver triggers `AskUserQuestion` |

## Orchestrator events (triple mode only)

| Event | When | Payload |
|-------|------|---------|
| `BRIEF` | After recon, sent to writer and reviewer separately | role-specific briefing |
| `NUDGE` | Pair silent > 10 min | "stand?" or a sharper question |
| `PROCESS-NEEDS-FIX` | Engineer broke the protocol (e.g. used a sub-agent for recon when not allowed) | what was wrong, what to do instead |
| `MAJOR-STEP` | Phase done, sent to human | what completed, next phase |
| `BLOCKER` | Pair can't resolve, escalated to human | what's blocked, what was tried |
| `DONE` | Pair finished, branch ready | commit SHA, branch state, gates passed |
| `ABORT` | Pair is wedged, ending the run | why |

The orchestrator does NOT send `REVIEW-READY` or `REVIEW: ...` events. Those are engineer-to-engineer.

## Gate events

These extend the base events above. They drive the gated workflow described in `references/gated-workflow.md`. In triple mode they go between orchestrator and human; in pair mode the human originates and consumes them directly (the human IS the orchestrator).

| Event | From | To | When | Payload |
|-------|------|-----|------|---------|
| `GATE-1-ESCALATE <window>` | orchestrator | human | Triple only. Orchestrator can't decide a clarify question alone (budget, scope shift, stakeholder dependency, user unreachable) | reason + question(s) needing human input |
| `GATE-1-DECISION` | human | orchestrator | Triple only. After human answered the escalation | answer(s), context |
| `GATE-2-BLOCKER` | orchestrator/human | human/user | Plan-check subagent returned `VERDICT: BLOCKER` | consolidated subagent BLOCKERS, suggested next step |
| `PLAN-LOCKED:` | orchestrator/human | engineers | After Gate 2 PASS | full plan bullets, GATE-1 answers, recon pointers, pair protocol with peer pane id, escalation pane id |
| `GATE-3-PASS <window>` | orchestrator/human | human/user | Both Gate-3 subagents returned `VERDICT: PASS` | diff-stat (`git diff --stat base..HEAD`), commit list (`git log --oneline base..HEAD`) |
| `GATE-3-BLOCKER` | orchestrator/human | human/user | At least one Gate-3 subagent returned `VERDICT: BLOCKER` | consolidated BLOCKERS from verifier + code-reviewer, suggested fix-loop or abort |
| `COMPLETE: <Phase>` | orchestrator/human | human/user | After GATE-3-PASS, ready for merge | `gate-3=PASS via <verifier-name + code-reviewer-name>` (mandatory field), diff-stat, plan-bullet coverage. Sent only AFTER GATE 3 returned PASS, never before — a prior run sent COMPLETE pre-GATE-3 and came back with three real bugs 30 minutes later, costing trust |
| `PLAN-AMENDMENT:` | engineer/orchestrator | engineers (in-loop) | mid-run plan change without invalidating loop state. Required when a bullet hits a hard cap (LOC limit, file-size cap) or estimate drifts >50% | what changed in the plan, why. Must be preceded by a `docs(plan-amendment): ...` commit on the branch. `REVIEW-READY` on a bullet with documented drift but no preceding amendment commit is a `BLOCK` |

GATE-1 events are exceptional. Default GATE-1 traffic stays inside the orchestrator's pane (it calls `AskUserQuestion` directly). The orchestrator only crosses pane boundaries when escalating; the human only sees `GATE-1-DECISION`-shaped events when it gets pinged with `GATE-1-ESCALATE` first.

**Engineers only see `PLAN-LOCKED:`.** All other gate events are between the higher layers. Engineers respond to PLAN-LOCKED with the standard pair loop (`REVIEW-READY`, `REVIEW`, `DONE`, `BLOCKER`).

**Auto-retry forbidden.** A `GATE-2-BLOCKER` or `GATE-3-BLOCKER` always escalates to human. The orchestrator never re-runs the same subagent without a human decision: same plan failing twice means the planner's mental model is broken, not the plan.

## Dual-Review events (opt-in via `--dual-review`)

When `/pair` or `/triple` was spawned with `--dual-review`, two reviewers run in parallel and the loop adds three reviewer-to-reviewer events plus one orchestrator-to-writer event. Single-reviewer mode keeps the base vocabulary unchanged.

| Event | From | To | When | Payload |
|-------|------|-----|------|---------|
| `REVIEW-READY` | writer | BOTH reviewers (parallel) | Same trigger as single-reviewer mode (one logical step + 3 mandatory fields) | The writer pings reviewer-1 AND reviewer-2 in two separate `send` calls. Both reviewers see the same payload. |
| `REVIEWER-FINDINGS:` | reviewer | peer reviewer | After independent review (no crosstalk before this) | Numbered, falsifiable findings list (BLOCKER / WARNING / NIT). The peer uses this as input for `PEER-REVIEW`. |
| `PEER-REVIEW:` | reviewer | peer reviewer | After receiving counterpart's `REVIEWER-FINDINGS:` | Comments on counterpart's list: agree, disagree, missed-this, dedupe. Falsifiable, file:line. |
| `REVIEW-FINAL (Reviewer):` | reviewer | orchestrator (= human in pair, = orchestrator agent in triple) | After both `REVIEWER-FINDINGS:` + `PEER-REVIEW:` cycles complete | Merged final findings from this reviewer's perspective + APPROVE or BLOCK verdict. |
| `REVIEW-CONSOLIDATED:` | orchestrator | writer | After both reviewers sent their `REVIEW-FINAL` | One merged review: all unique BLOCKERs preserved, overlaps deduped, contradictions surfaced with context. EXACTLY one ping per cycle, never two. |

Reviewers in dual-review mode never speak directly to the writer. The writer only ever sees the consolidated review from the orchestrator. This is what makes the cross-check work: contradictions get surfaced and resolved at the orchestrator layer instead of confusing the writer.

`REVIEW: APPROVE` and `REVIEW: BLOCK` (single-reviewer events from `## Reviewer events`) are NOT sent in dual-review mode. The closest equivalent is `REVIEW-CONSOLIDATED:` from the orchestrator carrying an APPROVE or BLOCK verdict in its payload.

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
5. In triple mode: orchestrator forwards `[Orchestrator <window>] DONE: <sha> <branch state>` to human.

Push happens only after human OK. Whether the briefing said so explicitly or not, the orchestrator (or the writer in pair mode) waits.

## Common edge cases

### Disagreement that won't resolve

If writer and reviewer go three rounds on the same finding without converging, escalate:

- Pair mode: writer pings human with `BLOCKER: <one-paragraph framing of the disagreement>`.
- Triple mode: writer pings orchestrator with the same. Orchestrator decides: ask human, or break the tie themselves if the disagreement is about style and not correctness.

Style tie-breaks are valid orchestrator output. Correctness tie-breaks go to human.

### Reviewer wants to write code

Reviewer code is anti-pattern. If reviewer thinks the writer is wrong, reviewer phrases the finding precisely enough that the writer can implement it. If the writer can't, the writer pings `BLOCKER`. Reviewer never edits files in the worktree.

### Writer wants to skip the review

The pair loses its value the moment writer commits without `REVIEW: APPROVE`. The briefing should say this explicitly: "do not commit without an APPROVE event from the reviewer". If the writer skips anyway, the reviewer pings `PROCESS-NEEDS-FIX` (triple mode: to the writer, copy to orchestrator).

### Push without human OK

The writer's briefing should explicitly say: "push only after human OK". If the writer pushes anyway, the human decides:

- accept the push and review post-hoc, or
- revert and rerun the review

This is a human decision, not an orchestrator decision.
