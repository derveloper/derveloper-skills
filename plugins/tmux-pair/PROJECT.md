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

### 0.14.0 (Workflow-Caching: V6-V10, 2026-05-14)

Smart-Workflow-Erweiterungen V6-V10. Backward-Compat-Pflicht: alle alten
Spawns ohne neue Flags laufen identisch (Cache-Miss = klassischer Flow).
Plugin-API stabil, keine Breaking-Changes auf Subagent-Inputs oder
CLI-Flags. Versions-Bump 0.13.2 -> 0.14.0 (Minor, additiv).

- V6 Readiness-Cache (24h TTL): `~/.cache/tmux-pair/readiness/<slug>-<rules-hash[:16]>-<commit>.json`. Orchestrator skipt das `reviewer-readiness-check` Subagent bei Cache-Hit + PASS. `NEEDS-RULES` wird nicht gecached. Cache-Bust per `--no-cache` oder `rm`.
- V7 Test-Trust-Chain: `TESTS-PROOF:` Block im Commit-Message-Body des Bullet-Commits. `gate-3-verifier` liest via `parse-tests-proof` Subcommand. HEAD == COMMIT_SHA -> trust + skip Re-Run. Legacy ohne Marker -> Re-Run + WARNING (kein BLOCKER, backward-compat).
- V8 Cargo-Target-Sharing: `env CARGO_TARGET_DIR=~/.cache/tmux-pair/cargo-target/<repo-slug>/` als Prefix in jedem Boot-Command. Repo-Slug = basename mit non-alphanumeric -> `_`. Non-Cargo-Repos skippen Env automatisch. Opt-out: `--no-shared-target`.
- V9 Recon-Cache mit Delta-Mode (1h TTL): `/tmp/tmux-pair-recon-<slug>-<commit>.json`. Folge-Spawns auf gleichem Commit lesen Cache + machen Delta-Recon nur für mtime > cache-time. Cache-Bust per `--no-cache`.
- V10 Inline-Gates für Trivial-Plans: `task_kind=bug-fix` + bullets <= 3 + predicted files-touched <= 5 -> Orchestrator macht GATE 2 (und ggf. GATE 3 verifier) inline statt Subagent-Spawn. `gate-3-code-reviewer` bleibt immer Subagent. CLI-Helper: `inline-gate-decide --plan-file <path> --task-kind <kind>` liefert JSON-Decision.

Neue CLI-Surface:
- `tmux_pair.py parse-tests-proof --repo <path> --commit <sha-or-HEAD>` (JSON-Output mit `found`, `commit_sha`, `head_matches`, `entries`).
- `tmux_pair.py inline-gate-decide --plan-file <path-or-dash> --task-kind <kind>` (JSON-Decision-Payload).
- `pair` und `triple` akzeptieren `--no-cache` und `--no-shared-target`.

V2 Decision-Log für 0.14.0:

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | CARGO_TARGET_DIR-Pfad = `~/.cache/tmux-pair/cargo-target/<slug>/` | User-Decision GATE 1 Option A; matched V6/V9-Convention (`~/.cache/` user-persistent), shared cross-worktree, cargo lock-file handhabt Concurrency. |
| D2 | TESTS-PROOF persistiert im Commit-Message-Body | User-Decision GATE 1 Option A; Marker reist mit Code, Verifier liest via `git log --format=%B`, kein zusätzliches Repo-Artefakt. |
| D3 | Rules-Bootstrap skipped für diesen Run | User-Override ("scheiss auf rules"); Reviewer-Strictness läuft gegen AGENTS.md + Common-Sense statt frisch-gebackener `.claude/rules/`. Risk: Reviewer hat weniger falsifizierbare Hooks, akzeptiert für Frickel-OK-Repo. |
| D4 | User-Pivot: Solo-Implementation statt Triple-Spawn | User: "mach selbst fertig"; GATE-3-Subagents werden weiterhin ausgeführt für adversarial Diff-Review + Verify-Cycle. |
| D5 | V8 Injection-Site = `_wrap_with_cargo_env` Helper, jeder Boot-Branch wrappt vor return | GATE-2-BLOCKER B3 verlangte Commitment auf eine Stelle; Helper kapselt Env-Prepend, codex-Branch + claude/pi-Branches teilen Logic, non-Cargo-Path = `None` -> Helper passthrough. |
| D6 | V7 Caller = neues CLI-Subcommand `parse-tests-proof` | GATE-2-BLOCKER B2 verlangte Call-Site für `_parse_tests_proof`; Subagent ruft Python-Helper via Bash auf statt Regex selbst zu pflegen. |
| D7 | V10 Caller = neues CLI-Subcommand `inline-gate-decide` | GATE-2-BLOCKER B4 verlangte Eindeutigkeit zwischen Python-CLI- und Agent-Briefing-Pfad; CLI-Helper liefert JSON, Orchestrator-Agent konsumiert via Bash. |
| D8 | `_cache_repo_slug` als neuer Helper mit `[^A-Za-z0-9]->_`, distinkt von bestehender `slugify` (Hyphen-Variante) | GATE-2-NOTE wies auf Slug-Konvention-Mismatch hin; Cache-Filenames müssen shell-quoting-stabil sein, Hyphens kollidieren mit `-` in optionalen suffixen. |
| D9 | V8 nur für Cargo-Repos aktivieren (`Cargo.toml` Detection), sonst Env nicht setzen | Self-Decision Repo-Pattern-Match: setzen einer ignorierten Env tut nichts, aber ein leerer Pfad in der Pane-Anzeige wirkt verwirrend; `None`-Return hält Boot-Cmd lesbar. |
| D10 | SKILL.md frontmatter `version:` mit-bumpen | GATE-2-BLOCKER B5/wiring-gap; PROJECT.md Design-Decision verlangt Versions-Sync zwischen `plugin.json`, `marketplace.json` und Skill-Frontmatter. `check-plugin-versions.py` prüft heute nur 2 von 3 -> Follow-up: Script erweitern (NOTE, kein Hard-Block in 0.14.0). |
| D11 | TESTS-PROOF-Block in 0.14.0 noch nicht durch Writer-Briefing-Templates erzwungen | Backward-Compat-Phase: alte DONEs ohne Marker werden mit WARNING re-runned, neue Writer-Briefings können den Block in 0.15+ als Pflicht aufnehmen. Schema steht; Migration phasenweise. |
