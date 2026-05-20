---
description: Auto-entry to tmux-pair. Inspects the repo + task and invokes solo with the right flags. Solo is the only mode.
argument-hint: <project-path> <base> <feature> [task...] [<any solo flag>]
---

# run

Default tmux-pair entry-point. `/run` performs a short repo + task recon, then invokes solo. Multi-pane spawn modes were removed: shared CARGO_TARGET_DIR contention, git-index-lock races, cross-writer PROJECT.md races, and dual-review coordination consistently outweighed the parallelism gain. The lean replacement is solo + subagent fan-out + adversarial codex-CLI second-opinion at each gate (see `commands/solo.md`).

## Invocation

`/run <project-path> <base> <feature> [task...] [<any solo flag>]`

- `<project-path>`: path to the git repository
- `<base>`: ref to branch from (default `origin/main`)
- `<feature>`: short feature name
- `[task...]`: free-form task description forwarded to solo.

All `/solo` flags are forwarded unchanged.

## Examples

- `/run ~/code/myapp origin/main retry-budget add a per-tenant retry budget to the webhook dispatcher`
- `/run ~/code/myapp main typo-fix fix typo in README --no-gated`
- `/run ~/code/myapp main migrate-rules-to-skills --no-worktree`

## Decision logic

1. **Task clarification**: if `<task>` is missing or ambiguous (single keyword, no verb), ask the user once via `AskUserQuestion`. Continue with the clarified intent.
2. **Repo recon**: inspect `<project-path>` for size, language stack, `.claude/agents/`, `.claude/rules/`. Used to pre-pick a sensible `--with-standards` / `--greenfield` flag if appropriate.
3. **Agent pick** (if the user did NOT pass `--agent` explicitly): pick `claude` or `codex` based on task profile. Heuristic:

   | Task profile | Pick | Reason |
   |---|---|---|
   | Recon-heavy, multi-file, plan-integration, lots of `AskUserQuestion` decisions, design work, briefings | `claude` | Plan integration + Subagent-Spawn (Task tool) + AskUserQuestion structured. Default tie-breaker. |
   | Single-file edits, code translation (lang A → B), mechanic refactor, bulk-rename, codemod | `codex` | Terminal-driven, direct file-ops, fast turnaround per file. |
   | Adversarial bug-hunt, debugging mystery panics, race-condition tracing, "find the real cause" | `codex` | gpt-5.5 + xhigh reasoner sharp on adversarial logic. |
   | Greenfield scaffolding, brand-new module, architecture-first | `claude` | Plan-driven + standards integration cleaner. |
   | Compliance/PII/security review with stakeholder interaction | `claude` | AskUserQuestion + decision-log integration. |
   | Cost-sensitive bulk work (mass renames, mechanic migrations on cheap models) | `pi` (opt-in, user must pass `--agent pi`) | Cortecs/qwen3 fits bulk, expensive top-tier models would burn budget. |

   Ambiguous task → claude (safer default, recon-strong). User can always override with `--agent codex` / `--agent pi`.

   **The same heuristic applies inside the solo run to subagent spawns**: `Agent(...)` (claude Task tool) for recon-heavy / plan-driven / repo-domain sub-bullets; `Bash(codex exec --cd <sub-wt> "...")` for single-file / mechanic / codemod / adversarial bug-hunt sub-bullets. Default tie-breaker stays claude. See `skills/tmux-pair-orchestration/SKILL.md` "Same heuristic applies to subagent spawns" for the per-phase mapping.

4. **Surface the pick** in the recon note (e.g. `recon: 12 affected files, .claude/rules/ present, agent=codex (bug-hunt profile)`). One line, no AskUserQuestion unless the user typed something contradictory like "use claude" in the task but the heuristic picked codex.
5. **Invoke solo** with the resolved flags + `--agent <pick>`.

For tasks that look like 15+ bullet sweeps: batch into 3-5 bullets per solo run and chain them, rather than packing everything into one monolithic solo. Plan-drift correlates strongly with bullet count per run.

## Optional flags

All `/solo` flags are forwarded. There is no `--spawn`-style mode anymore.

## Action

Parse arguments. If feature or task is ambiguous, ask the user once. Then run:

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/tmux_pair.py solo \
  --project <project-path> --base <base> --feature <feature> --task "<task>" \
  [...forwarded solo flags]
```

## Output

JSON from `/solo`, prefixed by a one-line recon note (e.g. `recon: 12 affected files, .claude/rules/ present`).

## Cleanup (auto, Phase 7)

Same as `/solo`: Phase 7 auto-squash-merges + cleans up. Only `tmux kill-window` is manual. See `commands/solo.md`.
