---
name: dg
description: >
  Adversarial code review mit Dinesh vs Gilfoyle (Silicon Valley).
  Aufruf: /dg (git diff), /dg 3 (3 Runden), /dg src/foo.rs (Datei),
  /dg src/foo.rs 3 (Datei + Runden). Zwei Agenten debattieren ueber
  Code-Qualitaet: Gilfoyle greift an, Dinesh verteidigt. Bestaetigte
  Issues werden im Final Summary gesammelt.
---

# Dinesh vs Gilfoyle — Adversarial Code Review

Inspiriert von HBO Silicon Valley. Gilfoyle (Angreifer) findet Bugs, Dinesh (Verteidiger) verteidigt oder gibt zu. Wenn Dinesh einen Punkt nicht verteidigen kann, ist das ein bestaetigtes Problem.

## Invocation Parsing

Parse the user's `/dg` invocation:

| Input | Target | Max Rounds |
|-------|--------|------------|
| `/dg` | `git diff HEAD` + `git diff --staged` | 5 |
| `/dg 3` | `git diff HEAD` + `git diff --staged` | 3 |
| `/dg src/auth.rs` | Read that file | 5 |
| `/dg src/auth.rs 3` | Read that file | 3 |

If the diff is empty and no file was given, tell the user there's nothing to review.

## Step 1: Collect Code

- **Git diff mode**: Run `git diff HEAD` and `git diff --staged`. Combine both.
- **File mode**: Read the specified file(s).

Store the result as `CODE_UNDER_REVIEW`.

## Step 2: Debate Loop

Initialize: `round = 0`, `debate_history = []`

### Loop:

**2a. Dispatch Gilfoyle** (Agent tool, research only)

Send to Agent with the full content of `gilfoyle-agent.md` from this skill directory as system context. Include:
- `CODE_UNDER_REVIEW`
- `debate_history` (all previous rounds)
- Current round number
- Instruction: "research only, do NOT edit any files"

Display Gilfoyle's BANTER to the user immediately.

**2b. Check Gilfoyle Convergence**

If all findings are repeats from previous rounds: stop loop.
Announce: *"Gilfoyle has run out of things to hate. Unprecedented."*

**2c. Dispatch Dinesh** (Agent tool, research only)

Send to Agent with the full content of `dinesh-agent.md` from this skill directory as system context. Include:
- `CODE_UNDER_REVIEW`
- Gilfoyle's response from this round
- `debate_history`
- Current round number
- Instruction: "research only, do NOT edit any files"

Display Dinesh's BANTER to the user immediately.

**2d. Check Dinesh Convergence**

If ALL responses are `[concede]` with zero `[defend]` or `[dismiss]`: stop loop.
Announce: *"Dinesh has conceded defeat. As expected."*

If both agents are repeating themselves: stop loop.
Announce: *"These two are going in circles. Separating them before it gets physical."*

**2e. Continue**

Append both responses to `debate_history`. Increment `round`.

If `round >= max_rounds`: ask the user if they want more rounds or stop.

## Step 3: Final Summary

Generate this exact format:

```
## Dinesh vs Gilfoyle Review — [target]
### [N] rounds of mass destruction

### Best of the Banter
2-4 highlights from the debate (the funniest or most brutal exchanges)

### Verdict
Categorize each finding:
- **Critical** (Gilfoyle won, Dinesh conceded) — these need fixing
- **Important** (Gilfoyle won after debate) — should fix
- **Contested** (Dinesh held his ground) — judgment call
- **Dismissed** (Gilfoyle was nitpicking) — ignore

### Strengths
What both agreed was solid (if anything)

### Score: Gilfoyle X | Dinesh Y
Count wins per category above.

### Recommended Changes
- [ ] Actionable checklist of confirmed issues (Critical + Important)
```

## Rules

- Both agents must NEVER edit files. Research and review only.
- The debate must stay technically grounded. Entertainment is the vehicle, not the goal.
- Findings sections are the structured interface. Banter is for the user.
- If the code is genuinely good: Gilfoyle should struggle, Dinesh should be smug, and the summary should reflect that.
