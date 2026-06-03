# Solo briefing template

The bundled script generates a baseline solo briefing automatically (`_briefing_solo` in `scripts/tmux_pair.py`). This template is what an operator writes from scratch when overriding the default, or when the task has a shape the default does not cover. It mirrors the gated-7-phase flow that the script generates.

```
Language: respond to the human in the language the human writes in. Default English.

[ROLE: Solo (gated, self-driven via subagents)]

WORKTREE: <worktree-path>
BRANCH:   <branch>
BASE:     <base-ref>
PROJECT:  <project-path>

TASK
<one-paragraph statement of the deliverable. Be concrete. Reference files,
functions, line numbers when known.>

User pane: <%H>. Phase 7 DONE-MERGED is the ONLY back-channel ping:
    python3 <plugin>/scripts/tmux_pair.py send <%H> "DONE-MERGED solo.<feature>: <squash-sha on <base> + phase summary>"
All human input (questions, decisions, hard-fail recovery) uses
AskUserQuestion in THIS pane. No BLOCKER ping to master. See
SOLO USER INPUT RULE below.

SOLO GATED WORKFLOW (subagent-centric)
  Phase 1 - Recon (parallel subagents): 4-6 independent recon
    questions, one subagent per question. Each subagent under 300
    words with file:line pointers. Domain-experts from
    `.claude/agents/<repo>-*.md` when present.

  Phase 2 - Plan + GATE-2: bullets B1..Bn with DONE definitions and
    parallel markers (`B3 || B4 [parallel]` or
    `B3 -> B4 [sequential: <reason>]`). Two parallel adversarial
    checks: `Agent(gate-2-plan-check)` AND
    `Bash(codex exec "adversarial plan-attack")`. BLOCKER in either
    -> fix loop, max 2 iterations.

  Phase 3 - Implementation + bullet commits: parallel subagents per independent
    bullet (disjoint files, plan markers). Sequential bullets stay
    in the main pane. Per bullet: affected tests + clippy + fmt,
    then a Conventional Commit with TESTS-PROOF.

  Phase 4 - GATE-3 (self-review): three parallel checks:
    `Agent(gate-3-verifier)` (goal-backward, plan coverage),
    `Agent(gate-3-code-reviewer)` (adversarial diff),
    `Bash(codex exec "diff-review")` (second opinion). Verifier
    reads bullet commits and TESTS-PROOF receipts. BLOCKER in any
    -> fix loop, max 3 iterations.

  Phase 5 - PROJECT.md + skill-persist: phase block + decisions
    (D<n>a..f). Domain insights as
    `.claude/skills/<repo>-<topic>/SKILL.md` (default) or
    `.claude/rules/<key>.md` (cross-cutting always-on, justified).

  Phase 6 - Commit hygiene: all intended bullet commits and
    guidance/docs commits exist, use Conventional Commits, carry
    enough detail for the squash body, and leave the worktree clean.
    No push.

  Phase 7 - Auto-squash-merge + cleanup:
    1. git status --porcelain empty? Otherwise AskUserQuestion in
       own pane.
    2. git checkout <base>
    3. git merge --squash <branch>
    4. git commit (heredoc: subject + body with B1..Bn summary,
       decisions, test counts).
    5. git worktree remove <wt_path>
    6. tmux_pair.py cleanup-target --project <project> --worktree <wt_path>
    7. git branch -D <branch>
    8. DONE-MERGED ping to user pane.
    On merge conflict: AskUserQuestion in own pane with concrete
    error + 2-4 recovery options. No BLOCKER ping to master.

SOLO USER INPUT RULE (MANDATORY)
  All human input lands inside YOUR OWN pane via AskUserQuestion.
  Phase 1 Clarify, GATE 2 scope decisions, GATE 3 BLOCKER triage,
  Phase 7 merge conflict, every unexpected situation: AskUserQuestion
  here with 2-4 concrete options, recommended on position 1.
  Subagent fan-out follows the same rule: subagents return results
  to YOU, YOU decide via AskUserQuestion when human input is needed.
  Exception: Phase 7 DONE-MERGED is the ONLY back-channel signal.

ANTI-PATTERNS
- Skipping Phase 2 or Phase 4 without subagent self-check.
- Using general-purpose instead of a repo subagent when a matching
  domain subagent exists.
- Pinging the spawning master pane for human input.
- Touching pre-existing dirty files (respect the allowlist).
- Pushing without the user's OK.

START. Read POINTERS, plan, code, gate, persist, commit, squash-merge,
DONE-MERGED.
```

## Notes on adaptation

- **Pointers are mandatory.** A briefing without pointers is a briefing without recon. If pointers are absent, the agent does recon first via Phase 1 subagents.
- **Phase 7 is mandatory.** Solo runs that stop at Phase 6 (commit hygiene) leave a feature branch and worktree behind; sequential chained runs then stack on top of an old base. Phase 7 squashes and cleans up.
- **AskUserQuestion is the only human-input path inside solo.** The script-generated briefing puts the SOLO USER INPUT RULE near the top so it lands in the agent's first response context.
- **Push gate is mandatory.** Even if you trust the agent, the gate is cheap and catches one of the most common failure modes (see `references/failure-modes.md`).
