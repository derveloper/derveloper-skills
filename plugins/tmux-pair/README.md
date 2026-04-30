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

## Skill

The bundled skill `tmux-pair-orchestration` documents:

- the pair protocol (`REVIEW-READY` → `REVIEW` → loop)
- when to choose pair vs. triple
- briefing templates for each role
- failure modes and how to recover

It triggers when the user asks for things like "spin up a writer/reviewer pair", "run two agents on this", "set up an orchestrator + pair", or names the workflow directly.

## License

Apache 2.0.
