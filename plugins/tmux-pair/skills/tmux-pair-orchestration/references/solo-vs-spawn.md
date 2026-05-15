# Solo vs spawn: choosing the mode

Both modes solve the same shape of problem (coding agents collaborating in a worktree) but trade off the human's attention, per-task overhead, and continuous-review-vs-self-review against each other. `/run` performs a short recon and recommends one; this page is the underlying rubric.

## Decision matrix

| Signal | Solo | Spawn |
|--------|------|-------|
| Task scope | self-contained, one logical change | multiple files, multiple subsystems |
| Recon needed | shallow or done via parallel subagents | non-trivial: docs to read, code to grep, tests to map |
| Human availability | wants to step away after spawn | wants to step away, only see major events |
| Review style | adversarial gate-subagents only (`gate-2-plan-check`, `gate-3-verifier`, `gate-3-code-reviewer`) | continuous orchestrator-mediated reviewer (or two reviewers consolidating, see `--size 4`) |
| Expected duration | minutes to ~30 min | minutes to hours |
| Failure mode "engineer briefs itself and misses the real problem" | medium (subagent gates catch a lot, not all) | low (orchestrator briefs, reviewer reads every change) |
| Number of review cycles | one to a few subagent passes | several REVIEW-READY/REVIEW loops |
| External docs to read | none or one quick page | multiple specs/RFCs/internal docs |
| Cost in panes/tokens | cheapest (1 main pane + ephemeral subagents) | 3 to 5 panes (orchestrator + 1-2 writers + 1-2 reviewers) |

If the matrix says `solo` for most rows (esp. self-contained scope + subagent-review is enough), use solo. Otherwise use spawn, and pick `--size` from the spawn sub-matrix below.

## Spawn size sub-matrix

| Signal | `--size 3` | `--size 4` (default) | `--size 4 --parallel-writers` | `--size 5` |
|--------|-----------|----------------------|-------------------------------|-----------|
| Composition | 1W + 1R + 1O | 1W + 2R + 1O | 2W + 1R + 1O | 2W + 2R + 1O |
| Use when | standard task, one reviewer is enough | security-sensitive, want cross-checking | parallel-friendly plan-bullets with disjoint files | big feature with both signals |
| Plan structure | sequential or mixed | sequential or mixed | bullets must be partitionable into disjoint sub-sets | mixed |
| Risk of false-APPROVE | base | reduced (consolidation) | base | reduced |
| Risk of writer-collision | n/a | n/a | medium (orchestrator must re-partition on file overlap) | medium |
| Cost in panes/tokens | base | +1 reviewer | +1 writer | +2 |

`--parallel-writers` requires `--size 4` or `--size 5` (argparse-enforced).

## Worked examples

### Example 0: solo fits

> "Migrate the `.claude/rules/*.md` to path-scoped skills under `.claude/skills/<topic>/SKILL.md`."

- Scope: repo-wide doc move, mechanical
- Recon: trivial (one directory, known structure)
- Duration: minutes
- Review: adversarial gate-subagents on diff are enough; no continuous reviewer needed
- Human attention: zero after spawn

Use solo. Agent runs the 6-phase workflow, gate-3 subagents review the diff, agent commits and pings DONE.

### Example 1: spawn --size 3 fits

> "Add an `--ignore-case` flag to the search command. Existing `--invert` flag in the same file is the model. Also update README and the integration tests."

- Scope: one main file + tests + docs
- Recon: trivial (point at the existing flag)
- Duration: medium
- Continuous review valuable so the doc update follows the flag plumbing

Use spawn --size 3. Writer plumbs the flag and writes tests, reviewer checks the flag wiring and the README, done in two to three REVIEW cycles.

### Example 2: spawn --size 3 fits (recon-heavy)

> "We have errors and panics in the production logs across three subsystems. Find the real causes, fix each, and push a clean bundle. Loki query attached."

- Scope: spans logging, the panicking subsystem, and the test suite
- Recon: non-trivial: read the logs, classify by failure mode, locate each in code
- Duration: hours
- Human attention: high cost if relayed

Use spawn --size 3. Orchestrator does the log triage and writes a focused briefing per failure mode. Writer fixes one mode at a time, reviewer checks each in isolation. Human sees MAJOR-STEP once per fixed mode.

### Example 3: spawn --size 4 (dual-review)

> "Rewrite the token-issuance flow to use the new refresh-token rotation scheme. Auth code, JWT signing, session store."

- Security-sensitive: blast radius across auth + sessions
- Risk of subtle bug: high; one reviewer might miss a race or omission
- Plan-bullets sequential (token flow must stay coherent)

Use spawn --size 4. Two reviewers cross-check the diff: one focuses on flow correctness (sequencing of refresh + revoke), the other on security boundary cases (replay, exfil, downgrade). Orchestrator consolidates.

### Example 4: spawn --size 4 --parallel-writers

> "Split the storage module into three pluggable backends (filesystem, S3, GCS). Each backend in its own file, common interface unchanged."

- Plan-bullets disjoint: each backend in its own file
- Two writers can split: writer-1 = filesystem + interface, writer-2 = S3 + GCS
- One reviewer reads both streams sequentially

Use spawn --size 4 --parallel-writers. Orchestrator partitions plan-bullets and briefs each writer separately with their bullet-subset. Reviewer trackt both REVIEW-READY streams.

### Example 5: spawn --size 5

> "Migrate the persistence layer to a new ORM AND swap the auth provider in the same release. Plan-bullets cover both areas and the project is security-sensitive."

- Both parallel-writers (disjoint persistence vs auth files) AND dual-review (auth = security-sensitive) warranted.

Use spawn --size 5. Writer-1 takes persistence bullets, writer-2 takes auth bullets. Reviewers 1 + 2 cross-check both streams with consolidation.

### Example 6: neither fits cleanly

> "Investigate whether we should migrate from library X to library Y."

This is a research task. There is no commit at the end of it. Don't spawn a worktree-based mode; have a single agent (or you) do the research and produce a recommendation. Mode-pick the implementation work after the recommendation lands.

## When `/run` recommends what

`/run` makes the recommendation via a quick repo + task recon. Rough heuristics it follows:

- Trivial / single-file / mechanical -> solo
- Non-trivial scope but one reviewer suffices -> spawn --size 3
- Security/auth/crypto/migrations keywords detected -> spawn --size 4 (dual-review)
- Task language implies disjoint sub-tasks ("split", "for each", "across N backends") -> spawn --size 4 --parallel-writers (or 5 if also security-flagged)

The user can always override with explicit `--solo` / `--spawn --size N --parallel-writers` flags.

## Hybrid: solo started, spawn needed

If a solo stalls because the recon was thinner than expected:

1. The agent pings `BLOCKER: recon insufficient, need <what>`.
2. Human decides: do the recon themselves, or `kill-window` the solo and re-spawn as `/spawn` with appropriate `--size`.

Solo-to-spawn promotion is a normal failure mode, not a sign of poor planning.

## Hybrid: spawn started, downgrade possible

The orchestrator can decide their job is done after recon and the first round of briefings, and step out. If the engineers run cleanly without further orchestration, the orchestrator's pane just sits there. That's fine; don't treat it as overhead waste. The orchestrator's value was in the recon and the briefings, not in the watching.
