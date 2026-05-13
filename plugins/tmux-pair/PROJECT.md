# tmux-pair Project Map

## Project Overview

`tmux-pair` is a Claude Code plugin for running writer/reviewer pairs and
writer/reviewer/orchestrator triples in tmux panes. It creates isolated git
worktrees, starts agent CLIs, sends role briefings, and provides helper commands
for cross-pane messaging, compaction, monitoring, and cleanup.

## Architecture

- `scripts/tmux_pair.py`: main runtime. Owns tmux pane spawning, worktree
  creation, generated briefings, durable standards, send/compact/status/monitor
  subcommands, and pane identity handling.
- `commands/pair.md` and `commands/triple.md`: Claude slash command wrappers
  that parse user arguments and invoke the script.
- `agents/*.md`: scoped subagent definitions for reviewer-readiness,
  rules-bootstrap, plan-check, final verifier, and final code-reviewer gates.
- `skills/tmux-pair-orchestration/`: long-form workflow documentation,
  briefing references, failure modes, and orchestration guidance.
- `skills/gepa/` and `skills/dg/`: bundled companion skills for prompt
  optimization and adversarial review.
- `templates/rules/`: language rule skeletons used by rules-bootstrap.

## Feature Surface

- Pair mode: writer + reviewer in a fresh worktree, with the human as
  orchestrator.
- Triple mode: orchestrator + writer + reviewer in a fresh worktree, with the
  orchestrator handling recon, user clarification, plan-check, loop supervision,
  and final verification.
- Dual-review mode: optional second reviewer with independent review,
  findings-swap, and orchestrator consolidation.
- Gated workflow: Clarify, Reviewer-Readiness, Plan-Check, Implementation Loop,
  Final-Verify.
- Adaptive GATE-Strictness: Orch klassifiziert task_kind
  (bug-fix/feature/refactor) im Recon; gate-2-plan-check, gate-3-verifier und
  gate-3-code-reviewer lockern/schärfen Checklist-Items per Klasse.
- --interactive Flag (Pair + Triple): opt-in Decision-Pause-Points. Default off
  (unattended-by-default mit V2-Threshold-Self-Decisions, alle geloggt im
  COMPLETE-Ping).
- Inline-Fix-Spec: Reviewer darf <20-LOC-Findings als INLINE-FIX im
  REVIEW-Output mitsenden (Trigger: cosmetic/typo/missing-doc; Anti-Trigger:
  Architektur/Sicherheit/Test-Logik). Writer auto-applied stumm + ACK.
- WARNING/NOTE-Schema: BLOCKER = fix-loop pflicht, WARNING =
  followup-memory + PROJECT.md (kein fix-loop), NOTE = log-only.
- Durable standards: Claude receives `--append-system-prompt-file`; Codex reads
  generated worktree `AGENTS.md` when applicable.
- PROJECT.md care: feature and refactor bullets update project maps when package
  map, feature surface, design decisions, or implementation history change.
- Engineer subagent strategy: Writer, Reviewer, and Orchestrator delegate
  bounded side work such as parallel recon files, parallel test suites, and
  independent fix branches.
- Parallel-plan markers: every plan bullet carries either a parallel marker
  such as `B3 || B4 [parallel]` or a sequencing marker with a reason.
- Sender identity: `tmux_pair.py send` prefixes normal messages with
  `[FROM: <pane-name>]` using stable tmux pane user options.

## Design Decisions

- `tmux_pair.py send` is the only supported pair communication path because it
  handles multi-line pastes and Enter retries for agent TUIs.
- Sender names are stored in `@tmux-pair-sender` at spawn time. `pane_title` is
  only a fallback because agent TUIs can overwrite it with spinner or working
  directory status.
- Gate subagents are scoped and read-only where possible. This prevents a
  plan-check or final verifier from accidentally editing code.
- Codex engineer subagent spawns should default to `gpt-5.3-codex-spark` with
  high reasoning while user limits allow it, with fallback to `gpt-5.5` high on
  rate limits. Claude continues through the Task tool and subagent definitions.
- Version fields in `plugin.json`, `.claude-plugin/marketplace.json`, and the
  orchestration skill frontmatter must stay aligned for plugin updates.
- `gate-3-code-reviewer` receives `task_kind` for audit context but keeps
  code-review strictness invariant across bug-fix, feature, and refactor.
  Adaptive relaxation belongs to plan coverage and verifier checks, while
  correctness, security, maintainability, and standards review stay stable.
- Pi engineer panes boot in a minimal mode by default (`PI_BASELINE_DISABLED=1
  PI_MEMORY_DISABLED=1 PI_MODE_DISABLED=1`) so the user's main-Pi workflow
  extensions (baseline system-prompt, MEMORY.md auto-load, /mode layer) do not
  contaminate engineer context. Durable standards arrive via
  `--append-system-prompt` regardless. Opt-out for a full-stack engineer Pi:
  `TMUX_PAIR_PI_FULL=1`.

## Implementation History

- 0.9.0: Added PROJECT.md care to the gated workflow, slim default briefings,
  model-aware compaction, and dual-review support.
- 0.10.0: Added engineer subagent strategy, required explicit parallel-plan
  markers at GATE 2, and automatic sender identity prefixes for `send` pings.
- 0.11.x: Added Pi as third engineer-agent (`--writer-agent pi` etc.) with
  per-role provider/model/thinking overrides; Pi engineer panes default to
  minimal extension-stack via `env PI_BASELINE_DISABLED=1 PI_MEMORY_DISABLED=1
  PI_MODE_DISABLED=1`, opt-out via `TMUX_PAIR_PI_FULL=1`.
- 0.12.0: Pi engineer default switched from `cortecs/glm-5.1` to
  `claude-bridge/claude-opus-4-7` (via pi-claude-bridge wrapping the Claude
  Pro/Max subscription). Token-cost effectively $0 within subscription rate
  limits; OSS/EU stack still reachable via `--pi-provider cortecs`.
- 0.13.0: Workflow-Smartness (V1 Inline-Fix-Spec, V2
  Orch-Decision-Threshold mit Decision-Log im COMPLETE, V3 Adaptive
  GATE-Strictness per task_kind, V4 WARNING/NOTE-Auto-Resolve, V5
  Unattended-Default mit --interactive Flag).
- 0.13.x: Pi engineer default switched back to Cortecs, this time
  `cortecs/qwen3-coder-next` (256k ctx, coder-spec, ~0.15/0.80 EUR per 1M
  tokens). Anthropic-API-Pricing-Druck macht Cortecs-Bulk-Work attraktiv;
  Quality kommt aus Review-Loop (Reviewer/Orchestrator bleiben claude
  bzw. claude-bridge/claude-opus-4-7 als Top-Gate). Anthropic-Subscription
  weiter via `--pi-provider claude-bridge --pi-model claude-opus-4-7`.
