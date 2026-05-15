# Solo vs. pair vs. triple — choosing the mode

All three modes solve the same shape of problem (coding agents collaborating in a worktree) but trade off the human's attention, per-task overhead, and continuous-review-vs-self-review against each other.

## Decision matrix

| Signal | Solo | Pair | Triple |
|--------|------|------|--------|
| Task scope | self-contained, one logical change | one to a few files | many files, multiple subsystems |
| Recon needed | shallow or done via parallel subagents | shallow or already done | non-trivial: docs to read, code to grep, tests to map |
| Human availability | wants to step away after spawn | will sit at terminal and relay | wants to step away, only see major events |
| Review style | adversarial gate-subagents only (`gate-2-plan-check`, `gate-3-verifier`, `gate-3-code-reviewer`) | continuous human-mediated reviewer | continuous orchestrator-mediated reviewer |
| Expected duration | minutes to ~30 min | minutes | hours |
| Failure mode "engineer briefs itself and misses the real problem" | medium (subagent gates catch a lot, not all) | unlikely (reviewer reads every change) | plausible without orchestrator (orchestrator briefs) |
| Number of review cycles | one to a few subagent passes | one or two pair loops | several pair loops |
| External docs to read | none or one quick page | none or one quick page | multiple specs/RFCs/internal docs |
| Cost in panes/tokens | cheapest (1 main pane + ephemeral subagents) | medium (2 panes) | highest (3 panes + dual-review optional) |

If the matrix says `solo` for most rows (esp. self-contained scope + subagent-review is enough), use solo. If it says `pair` for most rows, use pair. If it says `triple` for several including the recon row, use triple.

## Worked examples

### Example 0 — solo fits

> "Migrate the `.claude/rules/*.md` to path-scoped skills under `.claude/skills/<topic>/SKILL.md`."

- Scope: repo-wide doc move, mechanical
- Recon: trivial (one directory, known structure)
- Duration: minutes
- Review: adversarial gate-subagents on diff are enough; no continuous human relay needed
- Human attention: zero after spawn

Use solo. Agent runs the 6-phase workflow, gate-3 subagents review the diff, agent commits and pings DONE.

### Example 1 — pair fits

> "Add an `--ignore-case` flag to the search command. Existing `--invert` flag in the same file is the model."

- Scope: one file
- Recon: trivial (point at the existing flag)
- Duration: minutes
- Human attention: low cost to relay

Use pair. Writer adds the flag and a test, reviewer checks the flag plumbing and the test, done in one or two loops.

### Example 2 — triple fits

> "We have errors and panics in the production logs across three subsystems. Find the real causes, fix each, and push a clean bundle. Loki query attached."

- Scope: spans logging, the panicking subsystem, and the test suite
- Recon: non-trivial — read the logs, classify by failure mode, locate each in code
- Duration: hours
- Human attention: high cost if relayed

Use triple. Orchestrator does the log triage and writes a focused briefing per failure mode. Writer fixes one mode at a time, reviewer checks each in isolation. Human sees `MAJOR-STEP` once per fixed mode.

### Example 3 — pair would be cheaper than triple

> "Reproduce a flaky test, find the race, fix it. Repro is documented in the issue."

- Scope: one test, one or two source files
- Recon: already done (issue contains the repro)
- Duration: medium

This looks like a case for triple but the recon is already done. A triple here adds an idle orchestrator. Use pair.

### Example 4 — neither fits cleanly

> "Investigate whether we should migrate from library X to library Y."

This is a research task. There is no commit at the end of it. Don't use either mode; have a single agent (or you) do the research and produce a recommendation. Mode-pick the implementation work after the recommendation lands.

## Hybrid: pair started, triple needed

If a pair stalls because the recon was thinner than expected:

1. The writer pings `BLOCKER: recon insufficient, need <what>`.
2. Human decides: do the recon themselves, or `kill-window` the pair and re-spawn as triple.

This is fine. Pair-to-triple promotion is a normal failure mode, not a sign of poor planning. Don't punish the agents for asking.

## Hybrid: triple started, downgrade to pair

The orchestrator can decide their job is done after recon and the first round of briefings, and step out. If the engineers run cleanly without further orchestration, the orchestrator's pane just sits there. That's fine; don't treat it as overhead waste. The orchestrator's value was in the recon and the briefings, not in the watching.
