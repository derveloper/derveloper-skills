# tmux-pair

Spawn coding-agent pairs or triples in tmux panes, each pinned to its own fresh `git worktree`.

## What it does

Two modes, both create a sibling worktree and a tmux window with one pane per agent:

| Mode | Panes | Layout | Use when |
|------|-------|--------|----------|
| **pair** | Writer + Reviewer | side by side | tasks small enough that the human directly relays between the two |
| **triple** | Writer + Reviewer + Orchestrator | Orchestrator on top, Writer/Reviewer below | tasks large enough that you want a dedicated agent doing recon, briefing the engineers, and filtering noise upward |

In both modes the agents talk peer-to-peer by running:

```
python3 <plugin>/scripts/tmux_pair.py send <pane-id> "<message>"
```

The helper handles the multi-line submit quirks of common agent TUIs (paste-buffer + extra Enters) so messages reliably land.

## Requirements

- `tmux` (running session — the script spawns into the current session)
- `git` 2.5+ (worktrees)
- `python3` 3.9+
- One or more agent CLIs on `PATH` (defaults assume `claude` and `codex`, configurable)

## Quick start

Inside an existing tmux session:

```
/pair <project-path> <base-ref> <feature-name> <task description>
```

or for a triple:

```
/triple <project-path> <base-ref> <feature-name> <task description>
```

Both create a worktree at `<project-parent>/<project-basename>-wt-<feature>`, branch `feature/<feature>` from `<base-ref>`, and brief the agents.

## Configuration

Override the default agents via flags:

```
--writer-agent codex      # default: codex
--reviewer-agent claude   # default: claude
--orchestrator-agent claude   # triple only, default: claude
```

Add or replace agent commands in `~/.config/tmux-pair/agents.json`:

```json
{
  "claude": "claude --dangerously-skip-permissions",
  "codex": "codex --dangerously-bypass-approvals-and-sandbox",
  "myagent": "my-agent-cli --some-flag"
}
```

The defaults baked into the script are deliberately minimal: a single command per agent, nothing project-specific.

## Token management (long-running pairs/triples)

Modern agent CLIs ship with very large context windows (1M for `claude opus 4.7` and `gpt-5.5`). Pairs/triples that run for hours can drift past the sweet spot (~200k tokens) where the model still reasons cleanly. Two helper subcommands let an orchestrator (or the human master) refresh an agent in place:

```
python3 <plugin>/scripts/tmux_pair.py status <pane-id>
```

Returns JSON with the detected agent, current token count (parsed from claude's footer; codex rarely prints one and shows up as `null`, so callers fall back to a time/event heuristic), and the raw matched footer line.

```
python3 <plugin>/scripts/tmux_pair.py compact <pane-id> --briefing-file <path> [--timeout 300]
```

Sends `/compact` to the pane, polls `capture-pane` for completion (claude prints `Conversation compacted`; for codex we accept a token-count drop ≥50% as a fallback signal), then sends the re-brief from `--briefing-file` via the regular send path (with the verify+retry loop).

The re-brief MUST be self-contained: after `/compact` the agent has lost the conversational state and only remembers the summary. Include role, task, current progress recap, the next concrete step, the peer protocol, and the standards. The orchestrator (which keeps its own progress log) is the natural place to author it; the master plays the same role for any orchestrators it spawns.

Trigger windows:

- between REVIEW cycles when the engineer is idle, never mid-edit or mid-tool-call
- claude pane > ~200k tokens (visible in the footer)
- codex pane: by feel — no inline counter, use elapsed wall-time + number of major events as a proxy

To compact both engineers in a triple in parallel, run two `compact` calls with `&` from the orchestrator's shell; each call blocks for the duration of its own poll loop.

## Skill

The bundled skill `tmux-pair-orchestration` documents:

- the pair protocol (`REVIEW-READY` → `REVIEW` → loop)
- when to choose pair vs. triple
- briefing templates for each role
- failure modes and how to recover

It triggers when the user asks for things like "spin up a writer/reviewer pair", "run two agents on this", "set up an orchestrator + pair", or names the workflow directly.

## License

Apache 2.0.
