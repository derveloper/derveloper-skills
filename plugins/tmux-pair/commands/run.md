---
description: Auto-entry to tmux-pair. Inspects the repo + task, recommends solo or spawn (with a recommended team size), then invokes the picked mode.
argument-hint: <project-path> <base> <feature> [task...] [--solo|--spawn] [--size 3|4] [<any mode-specific flag>]
---

# run

Default tmux-pair entry-point. `/run` performs a short repo + task recon, recommends solo or spawn (with a recommended `--size` for spawn), and invokes the picked mode. Use this when you are not sure which mode fits.

Explicit mode flags override the recommendation:

- `--solo`: skip recommendation, invoke `/solo` directly.
- `--spawn`: skip recommendation, invoke `/spawn` directly. Pair this with `--size` if you already know the layout.

## Invocation

`/run <project-path> <base> <feature> [task...] [--solo|--spawn] [...mode-specific flags]`

- `<project-path>`: path to the git repository
- `<base>`: ref to branch from (default `origin/main`)
- `<feature>`: short feature name
- `[task...]`: free-form task description. Used as recon input for the recommendation, then forwarded to the picked mode.

## Examples

- `/run ~/code/myapp origin/main retry-budget add a per-tenant retry budget to the webhook dispatcher` (Claude recons, recommends mode + size)
- `/run ~/code/myapp main session-tokens migrate session tokens to redis cluster --spawn --size 4` (skip recommendation, run spawn-4)
- `/run ~/code/myapp main typo-fix fix typo in README --solo` (force solo, skip recommendation)
- `/run ~/code/myapp main parallel-rewrite split storage module into 3 backends --spawn --size 3` (single writer fans out via subagent-worktrees per backend)

## Decision logic

Claude runs the following before invoking a mode (skipped when the user passes `--solo` or `--spawn` explicitly):

1. **Task clarification**: if `<task>` is missing or ambiguous (single keyword, no verb, etc.), ask the user once via `AskUserQuestion`. Continue with the clarified intent.
2. **Repo recon**: inspect `<project-path>` for size, language stack, `.claude/agents/`, `.claude/rules/`, and a small grep against the keywords in `<task>` to estimate affected file count.
3. **Mode recommendation**:
   - **solo** when: task is self-contained (rename, doc cleanup, single-file fix, lint/format pass), affected file count is small (<= 5), no deep cross-module recon required, and adversarial gate-subagents are enough oversight.
   - **spawn --size 3** when: task spans multiple files, needs upfront recon, but a single writer + reviewer is enough. This is the default for non-trivial features.
   - **spawn --size 4** (dual-review) when: task is security-sensitive, touches auth/crypto/migrations/distributed-systems, or the user explicitly asks for cross-checking. Reviewers consolidate.
   - Parallel-friendly sub-tasks (split a module into N backends, bulk migration across independent areas) do NOT need a second writer-pane anymore. The single writer fans out via subagent-worktrees per parallel bullet (FF-merge back, squash-merge feature->main at GATE-3-PASS).
4. **Confirm with the user** (single `AskUserQuestion` with the recommendation as Option 1 (Recommended), plus 1-2 alternatives) when the recommendation is non-obvious. Trivially-obvious recommendations may proceed without confirmation; flag the recommendation clearly in the spawn output.
5. **Invoke** the picked mode by running its action block (same arguments as a direct `/solo` or `/spawn` invocation).

## Optional flags

- `--solo`: invoke `/solo` directly, skip recommendation. All `/solo` flags are forwarded.
- `--spawn`: invoke `/spawn` directly, skip recommendation. All `/spawn` flags (including `--size`, `--writer-agent`, etc.) are forwarded.
- Any other flag: forwarded to the picked mode after the recommendation.

## Action

Parse arguments. If `--solo` or `--spawn` is present, skip the recommendation and dispatch directly via the matching mode's action block (see `commands/solo.md` and `commands/spawn.md`).

Otherwise run the decision logic above and dispatch to either:

```bash
# recommended: solo
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/tmux_pair.py solo \
  --project <project-path> --base <base> --feature <feature> --task "<task>" \
  [...forwarded flags]

# recommended: spawn
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/tmux_pair.py spawn \
  --project <project-path> --base <base> --feature <feature> --task "<task>" \
  --size <recommended> \
  [...forwarded flags]
```

If feature or task is ambiguous after the recon step, ask the user before spawning.

## Output

JSON from the invoked mode (`/solo` or `/spawn` format), prefixed by a one-line recommendation note (e.g. `recommended: spawn --size 4 (dual-review)` followed by the rationale).

## Cleanup (manual)

Same as the invoked mode (`/solo` or `/spawn`).
