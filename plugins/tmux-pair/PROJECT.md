# tmux-pair Project Map

## Project Overview

`tmux-pair` is a Claude Code plugin for running coding-agent solos or
coordinated spawn-teams (orchestrator + ONE writer + 1-2 reviewers, sized 3..4)
in tmux panes. It creates isolated git worktrees, starts agent CLIs, sends role
briefings, and provides helper commands for cross-pane messaging, compaction,
monitoring, and cleanup. Parallel work happens via subagent-worktrees the
writer spawns from its Task tool (FF-merge per sub-bullet, squash-merge feature
-> main at GATE-3-PASS). The `/run` slash-command auto-recommends solo vs spawn
from a short repo + task recon.

## Architecture

- `scripts/tmux_pair.py`: main runtime. Owns tmux pane spawning, worktree
  creation, generated briefings, durable standards, send/compact/status/monitor
  subcommands, and pane identity handling.
- `commands/solo.md`, `commands/spawn.md`, `commands/run.md`: Claude slash
  command wrappers that parse user arguments and invoke the script (`run`
  delegates to `/solo` or `/spawn` after a recon-driven recommendation).
- `agents/*.md`: scoped subagent definitions for reviewer-readiness,
  rules-bootstrap, plan-check, final verifier, and final code-reviewer gates.
- `skills/tmux-pair-orchestration/`: long-form workflow documentation,
  briefing references, failure modes, and orchestration guidance.
- `skills/gepa/` and `skills/dg/`: bundled companion skills for prompt
  optimization and adversarial review.
- `templates/rules/`: language rule skeletons used by rules-bootstrap.

## Feature Surface

- Solo mode: single agent in a fresh worktree, gated 6-phase self-driven
  workflow (recon, plan + GATE-2, impl, GATE-3 self-review, PROJECT.md + skill
  persist, commit). Adversarial gates run as subagents.
- Spawn mode: orchestrator + ONE writer + 1-2 reviewers in a fresh worktree,
  with the orchestrator handling recon, user clarification, plan-check, loop
  supervision, and final verification. Sized via `--size 3..4`:
  - size 3 (default): 1 writer + 1 reviewer + 1 orchestrator.
  - size 4: 1 writer + 2 reviewers + 1 orchestrator (dual-review preset).
- Parallel work via subagent-worktrees (single writer fans out): one sub-WT
  per parallel plan-bullet, FF-merge back to the feature-WT per subagent,
  squash-merge feature -> main at GATE-3-PASS done by the master.
- Run mode (`/run` slash-command): repo + task recon, recommends solo vs spawn
  (and recommended `--size`), delegates to `/solo` or `/spawn`. Explicit
  user-mode overrides the recommendation.
- Dual-review (reviewers >= 2): independent review, findings-swap, orchestrator
  consolidation into one APPROVE/BLOCK.
- Parallel-writers (writers >= 2): orchestrator partitions plan-bullets into
  disjoint sub-sets per writer; no direct sync between writers.
- Gated workflow: Clarify, Reviewer-Readiness, Plan-Check, Implementation Loop,
  Final-Verify.
- Adaptive GATE strictness: the orchestrator classifies task_kind
  (bug-fix/feature/refactor) during recon; gate-2-plan-check, gate-3-verifier,
  and gate-3-code-reviewer relax or tighten checklist items per class.
- `--interactive` flag (spawn): opt-in decision pause points. Off by default
  (unattended-by-default with V2 threshold self-decisions, all logged in the
  COMPLETE ping).
- Inline-fix spec: reviewer may include findings under 20 LOC as INLINE-FIX in
  the REVIEW output (trigger: cosmetic/typo/missing-doc; anti-trigger:
  architecture/security/test-logic). Writer applies silently with ACK.
- WARNING/NOTE schema: BLOCKER = fix-loop required, WARNING =
  followup-memory + PROJECT.md (no fix-loop), NOTE = log-only.
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

- `tmux_pair.py send` is the only supported spawn-mode communication path
  because it handles multi-line pastes and Enter retries for agent TUIs.
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
  PI_MEMORY_DISABLED=1 PI_MODE_DISABLED=1`) so the main pi workflow extensions
  (baseline system-prompt, MEMORY.md auto-load, /mode layer) do not contaminate
  engineer context. Durable standards arrive via `--append-system-prompt`
  regardless. Opt-out for a full-stack engineer pi: `TMUX_PAIR_PI_FULL=1`.

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
- 0.13.0: Workflow smartness (V1 inline-fix spec, V2 orchestrator decision
  threshold with decision log in COMPLETE, V3 adaptive GATE strictness per
  task_kind, V4 WARNING/NOTE auto-resolve, V5 unattended default with
  `--interactive` flag).
- 0.13.x: Pi engineer default switched back to Cortecs, this time
  `cortecs/qwen3-coder-next` (256k ctx, coder-spec, ~0.15/0.80 EUR per 1M
  tokens). Anthropic API pricing pressure makes Cortecs bulk work attractive;
  quality comes from the review loop (reviewer and orchestrator stay on
  claude or claude-bridge/claude-opus-4-7 as the top gate). The Anthropic
  subscription remains reachable via `--pi-provider claude-bridge --pi-model
  claude-opus-4-7`.

### 0.14.0 (Workflow caching: V6-V10, 2026-05-14)

Smart workflow extensions V6-V10. Backward-compat is mandatory: every old
spawn without the new flags runs identically (cache-miss = classic flow).
Plugin API stable, no breaking changes on subagent inputs or CLI flags.
Version bump 0.13.2 -> 0.14.0 (minor, additive).

- V6 readiness cache (24h TTL): `~/.cache/tmux-pair/readiness/<slug>-<rules-hash[:16]>-<commit>.json`. Orchestrator skips the `reviewer-readiness-check` subagent on cache-hit + PASS. `NEEDS-RULES` is not cached. Cache-bust via `--no-cache` or `rm`.
- V7 test trust chain: `TESTS-PROOF:` block in the commit-message body of the bullet commit. `gate-3-verifier` reads it via the `parse-tests-proof` subcommand. HEAD == COMMIT_SHA -> trust + skip re-run. Legacy without marker -> re-run + WARNING (no BLOCKER, backward-compat).
- V8 cargo target sharing: `env CARGO_TARGET_DIR=~/.cache/tmux-pair/cargo-target/<repo-slug>/` as prefix in every boot command. Repo slug = basename with non-alphanumerics replaced by `_`. Non-cargo repos skip the env automatically. Opt-out: `--no-shared-target`.
- V9 recon cache with delta mode (1h TTL): `/tmp/tmux-pair-recon-<slug>-<commit>.json`. Follow-up spawns on the same commit read the cache and run delta recon only for `mtime > cache-time`. Cache-bust via `--no-cache`.
- V10 inline gates for trivial plans: `task_kind=bug-fix` + bullets <= 3 + predicted files-touched <= 5 -> orchestrator runs GATE 2 (and optionally GATE 3 verifier) inline instead of spawning a subagent. `gate-3-code-reviewer` always stays a subagent. CLI helper: `inline-gate-decide --plan-file <path> --task-kind <kind>` returns a JSON decision.

New CLI surface:
- `tmux_pair.py parse-tests-proof --repo <path> --commit <sha-or-HEAD>` (JSON output with `found`, `commit_sha`, `head_matches`, `entries`).
- `tmux_pair.py inline-gate-decide --plan-file <path-or-dash> --task-kind <kind>` (JSON decision payload).
- `pair` and `triple` accept `--no-cache` and `--no-shared-target`.

V2 decision log for 0.14.0:

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | CARGO_TARGET_DIR path = `~/.cache/tmux-pair/cargo-target/<slug>/` | User decision GATE 1 option A; matches V6/V9 convention (`~/.cache/` user-persistent), shared cross-worktree, cargo lock-file handles concurrency. |
| D2 | TESTS-PROOF persisted in the commit-message body | User decision GATE 1 option A; the marker travels with the code, verifier reads via `git log --format=%B`, no extra repo artifact. |
| D3 | Rules-bootstrap skipped for this run | User override; reviewer strictness runs against AGENTS.md plus common sense instead of a freshly built `.claude/rules/`. Risk: reviewer has fewer falsifiable hooks, accepted for an exploratory repo. |
| D4 | User pivot: solo implementation instead of triple-spawn | User asked to finish it directly; GATE-3 subagents still run for adversarial diff review and the verify cycle. |
| D5 | V8 injection site = `_wrap_with_cargo_env` helper, every boot branch wraps before return | GATE-2 BLOCKER B3 required commitment to a single site; the helper encapsulates env prepend, the codex branch and claude/pi branches share logic, non-cargo path = `None` -> helper passthrough. |
| D6 | V7 caller = new CLI subcommand `parse-tests-proof` | GATE-2 BLOCKER B2 required a call-site for `_parse_tests_proof`; subagent calls the Python helper via bash instead of maintaining its own regex. |
| D7 | V10 caller = new CLI subcommand `inline-gate-decide` | GATE-2 BLOCKER B4 required clarity between the Python-CLI path and the agent-briefing path; CLI helper returns JSON, orchestrator agent consumes it via bash. |
| D8 | `_cache_repo_slug` as a new helper with `[^A-Za-z0-9]->_`, distinct from the existing `slugify` (hyphen variant) | GATE-2 NOTE flagged a slug-convention mismatch; cache filenames must be stable under shell quoting, hyphens collide with `-` in optional suffixes. |
| D9 | V8 only activates for cargo repos (`Cargo.toml` detection), otherwise env is not set | Self-decision repo-pattern match: setting an ignored env does nothing, but an empty path in the pane display looks confusing; `None` return keeps the boot command readable. |
| D10 | Bump SKILL.md frontmatter `version:` together | GATE-2 BLOCKER B5/wiring gap; PROJECT.md design decision requires version sync between `plugin.json`, `marketplace.json`, and the skill frontmatter. `check-plugin-versions.py` currently checks only 2 of 3 -> follow-up: extend the script (NOTE, no hard block in 0.14.0). |
| D11 | TESTS-PROOF block not yet enforced via writer-briefing templates in 0.14.0 | Backward-compat phase: old DONEs without the marker are re-run with WARNING, new writer briefings can require the block in 0.15+. Schema is in place; migration is phased. |

### 0.15.0 (Solo mode + repo-subagent detection, 2026-05-14)

A third spawn mode next to pair/triple: solo. One agent, gated 6-phase
self-driven workflow, subagent-backed adversarial reviews. Plus automatic
detection of repo-specific subagents in every briefing.

- Solo mode: `/solo <project> <base> <feature> [task]` spawns one
  agent in a fresh worktree. Default gated (6 phases: recon -> plan +
  GATE-2 -> impl -> GATE-3 self-review -> PROJECT.md + skill-persist ->
  commit + DONE-ping). Recon, plan-check, code-review, and verifier run
  as subagents (`tmux-pair:gate-2-plan-check`, `tmux-pair:gate-3-verifier`,
  `tmux-pair:gate-3-code-reviewer`). `--no-gated` switches to a minimal spawn.
- Repo-subagent detection: `_detect_repo_subagents(project)` scans
  `.claude/agents/<project-name>-*.md` and lists every match in the briefing.
  Solo (and pair/triple) instruct the agent to prefer these domain experts
  over `general-purpose`. Detection logic: filename stem starts with
  `<project.name>-`.
- Companion files: `commands/solo.md` (slash command), solo block in
  SKILL.md, `cmd_solo` + `_briefing_solo` in `scripts/tmux_pair.py`,
  `solo` argparse subcommand with all flags (--no-gated, --no-worktree,
  --interactive, --with-standards, --greenfield, --agent, --claude-*,
  --pi-*, --no-shared-target).
- Feedback memory: `feedback_repo_specific_subagents_first.md` codifies a
  durable user rule: "repo with `.claude/agents/<repo>-*` -> ALWAYS list
  these in the briefing, never general-purpose as the default".

V2 decision log for 0.15.0:

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | Solo default gated ON | User decision GATE 1: solo workflow should run through the gates by default, because the entire value sits in adversarial self-review. `--no-gated` as opt-out for trivial tasks. |
| D2 | Solo default worktree ON | User decision GATE 1: solo should spawn in a fresh worktree like pair/triple, otherwise agent edits destroy local working-dir state. `--no-worktree` as opt-out for continuing existing branches. |
| D3 | Repo-detection pattern: filename-stem prefix `<project.name>-` | Convention match with the existing `.claude/agents/` layout. Detection works language-independent and without YAML parsing. |
| D4 | Detection hint in briefing AND skill | User decision GATE 1 both: skill hint helps the agent even after `/compact`, briefing hint kicks in immediately at boot. Belt and suspenders. |
| D5 | Skill-persist (phase 5) instead of rules-persist | Path-scoped skills (`.claude/skills/<repo>-<topic>/SKILL.md`) have been the new default convention since ebca198. Rules only for cross-cutting always-on items. |

### 0.15.1 (No-double-work + TESTS-PROOF trust + parallel default, 2026-05-15)

Patch bump: gate-3-verifier trusts TESTS-PROOF markers and NEVER re-runs
workspace-wide gates that engineers have already certified. Plus a hard
PARALLEL-BY-DEFAULT rule in all briefings.

- `gate-3-verifier.md` item 6 tightened: decision matrix per
  bullet-commit (`found=true + head_matches=true` -> trust + skip re-run;
  `head_matches=false` -> narrow re-run + WARNING; missing 0.14+ ->
  BLOCKER; missing legacy -> narrow re-run + WARNING). NEVER a
  workspace-wide "to be safe" run when the marker is valid.
- `gate-2-plan-check.md` item 10: NARROW SCOPE required (cargo nextest -p
  <crate>, pytest <path>, pnpm test <glob>); plan without TESTS-PROOF anchor
  in DONE definition of each bullet -> BLOCKER; plan with
  `cargo test --workspace` per bullet -> WARNING.
- `tmux_pair.py` ENGINEER_SUBAGENT_STRATEGY_BLOCK: PARALLEL BY DEFAULT +
  NO DOUBLE WORK as mandatory sections. Independent bullets running
  serially = anti-pattern.
- `tmux_pair.py` TEST_STRATEGY_BLOCK: TESTS-PROOF marker required in
  every bullet commit + DONE ping (migration from "schema in place" to
  "schema enforced").
- GATE-3 orchestrator template (`_briefing_gate_prompts`): explicit
  marker instruction "Trusts engineers' TESTS-PROOF marker; runs tests
  ONLY if marker missing or stale, and only the narrowest scope".

V2 decision log for 0.15.1:

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | Marker trust instead of re-run as default | User feedback: running the full workspace tests again in gate 3 is wasteful because the engineers already ran them. TESTS-PROOF schema has existed since 0.14.0 (V7), enforcement was missing. |
| D2 | Narrow scope per bullet, workspace gate only pre-DONE | User feedback: maximize parallelism, optimize plans, optimize fast test execution. `cargo test --workspace` 10x across 10 bullets is token and wall-clock waste. |
| D3 | BLOCKER on 0.14+ commits without marker | 0.14.0 migration obligation completed, new spawns must set the block. Legacy commits stay WARNING (backward-compat). |

### 0.16.0 (BREAKING: /pair removed, /triple becomes /spawn, dynamic team size, /run auto-entry, 2026-05-15)

Major bump with breaking changes on the slash-command surface and the
Python CLI. Pair mode (writer + reviewer without orchestrator, human as
orchestrator) is hard-removed: the "human-as-orchestrator" concept did not
work reliably in practice (the human is usually absent or busy; engineers
waited on decisions without flow control). Triple mode is renamed to
`/spawn` with dynamic size selection and extended by `--size 3..5` plus
`--parallel-writers`. New `/run` auto-entry: short recon, recommends solo or
spawn (with a recommended `--size`), delegates.

- BREAKING: `/pair` slash command removed. `commands/pair.md` deleted. No
  deprecation alias.
- BREAKING: `/triple` -> `/spawn`. `commands/triple.md` renamed to
  `commands/spawn.md` with reworked content.
- BREAKING: `--dual-review` flag removed. Use `--size 4` (default dual-review
  preset) or `--size 4 --parallel-writers` (2-writer preset) instead.
- NEW: `commands/run.md` auto-entry. Skill logic: clarify intent, repo recon,
  recommend solo vs spawn (with `--size`), invoke `/solo` or `/spawn`.
  Explicit user mode overrides the recommendation.
- NEW: `/spawn --size N` (default 3, choices 3/4/5). Mapping: 3 = 1W/1R/1O.
  4 = 1W/2R/1O (dual-review). 4 + `--parallel-writers` = 2W/1R/1O. 5 = 2W/2R/1O.
- NEW: `--parallel-writers` flag with argparse validation (`--size 3 +
  --parallel-writers` -> argparse error).
- NEW: `--writer-2-agent` flag analogous to `--reviewer-2-agent`.
- NEW: Python helper `_spawn_layout(size, parallel_writers) -> {writers,
  reviewers, orchestrator}` as single source of truth for team-size logic.
- BREAKING: primitive single-pane subcommand renamed `spawn` -> `pane`. The
  `spawn` slot is now the team spawn (previously `triple`); the primitive
  single-pane spawner is now called `pane`.
- NEW: `_peer_writer_block` helper in engineer briefings; writer briefing
  with parallel-writers gets the disjoint-bullets directive, reviewer briefing
  gets the two-stream-tracking directive.
- NEW: orchestrator briefing PARALLEL-WRITERS directive (analogous to
  DUAL-REVIEW) with a plan-partition guide and file-collision protocol.
- JSON output: `mode: "triple"` + `dual_review: bool` -> `mode: "spawn"` +
  `size: int` + `writers: int` + `reviewers: int` + `parallel_writers: bool` +
  `dual_review: bool`.
- Version sync: `plugin.json`, `.claude-plugin/marketplace.json`, and
  `skills/tmux-pair-orchestration/SKILL.md` frontmatter all on 0.16.0.

V2 decision log for 0.16.0:

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | Slash command name: `/spawn` (not `/team`, `/agents`) | User decision: "spawn" fits the existing vocabulary line (tmux_pair.py spawn as a subcommand synonym for worktree+pane+brief; the new pane subcommand resolves the collision). |
| D2 | Slash command for auto-entry: `/run` in addition to the skill trigger | User decision: an explicit slash command is discoverable for users who do not enter via the skill phrase; the skill trigger stays in parallel for natural-language invocation. |
| D3 | Team size dynamic from 3 upward, skill recommends after recon, `--size` as explicit override | User decision: 3 is the smallest sensible team (orchestrator + 1W + 1R), recon can recommend larger when parallel bullets or dual-review are needed; the user can override the recommendation. |
| D4 | Hard removal of `/pair`, no deprecation alias | User decision: pair mode with human-as-orchestrator did not work structurally; clean break without alias confusion. The major bump justifies the breaking change. |
| D5 | Plugin name stays "tmux-pair" despite the removal of /pair | User decision: established name, "pair protocol" stays as the conceptual term for the writer+reviewer loop inside a spawn; renaming the plugin would break marketplace URLs and user memory. |
| D6 | Hard-remove `--dual-review` flag, replace with `--size` | Cleanest API: `--size` is the single source for team layout, dual-review follows from `reviewers >= 2`. A backward-compat alias would only cause confusion. |
| D7 | `cmd_spawn` (primitive) -> `cmd_pane`; `cmd_triple` -> `cmd_spawn` | Naming-collision resolution: the old primitive single-pane spawner collides with the new team-spawn name. `pane` describes the primitive slot more precisely. |
| D8 | argparse error for `--parallel-writers --size 3` instead of silent ignore | Plan-check subagent finding: silent ignore would be a failure class; argparse-time error fails fast and falsifiably. |
| D9 | Writer-2 partner_pane = reviewer (same as writer-1), peer_writer_pane = writer-1 as cross-awareness | Plan-check finding: writer-2 must be disambiguated. Disjoint bullets means no direct sync between writers; coordination via orchestrator. peer_writer_pane only as an awareness hint for file-collision detection. |
| D10 | SKILL.md frontmatter version bump still manual (no automated check) | check-plugin-versions.py currently checks only plugin.json + marketplace.json. SKILL.md frontmatter validation stays as follow-up (see 0.14.0 D10). 0.16.0 documents this in the acceptance block but does not fix it (scope-limited). |

### 0.18.0 (BREAKING: Multi-writer removed, subagent-worktree pattern, 2026-05-19)

User direction: multi-writer is removed entirely because it caused problems
and overhead. When multiple subagents can work inside one writer (as plans
are meant to be built), each must operate in its own worktree so they do not
conflict. This produces a tree of worktrees: the feature/task worktree plus
optional subagent worktrees that merge back fast-forward where possible,
with squash reserved for the final merge to main.

- BREAKING: `--parallel-writers` flag removed entirely.
- BREAKING: `--writer-2-agent` flag removed entirely.
- BREAKING: `--pi-writer-2-*` flags removed entirely.
- BREAKING: `--size 5` removed (was 2W/2R, no longer composable).
  Valid sizes now: 3 (1W/1R/1O) and 4 (1W/2R/1O dual-review).
- BREAKING: output JSON fields `parallel_writers`, `writer_2_pane`,
  `writer_2_agent`, `writer_2_name`, `writer_2_ready` removed.
- REMOVED: `_peer_writer_block` helper (used to inject writer-2 awareness
  into engineer briefings). Replaced by `_subagent_worktree_block`.
- REMOVED: PARALLEL-WRITERS directive in the orchestrator briefing.
- NEW: orchestrator-briefing SUBAGENT-WORKTREE directive: writer fans out via
  `git worktree add ../<feature>-sub-<bullet-id>`, one Task subagent per
  sub-WT, FF-merge back into the feature-WT, cleanup per sub-bullet.
- NEW: writer-briefing SUBAGENT-WORKTREE block (`_subagent_worktree_block`):
  exact git commands for add/merge/remove, fallback path (FF failure ->
  CLARIFY-NEEDED to orchestrator, no automatic merge-commit), explicit
  separation of sequential vs parallel bullets.
- NEW: README, spawn.md, SKILL.md, solo-vs-spawn.md, pair-protocol.md
  sections on the subagent-worktree pattern + squash-final-merge discipline.
- Version sync: `plugin.json`, `.claude-plugin/marketplace.json`, and
  `skills/tmux-pair-orchestration/SKILL.md` frontmatter all on 0.18.0.

V2 decision log for 0.18.0:

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | Hard-remove multi-writer pane instead of deprecating | User direction to remove it entirely; 0.16.0 had introduced multi-writer as opt-in anyway, a clean break fits the plugin major cadence. |
| D2 | Subagent-worktree pattern at the briefing level, not automated in plugin code | Sub-worktree creation is LLM- and plan-driven, not static. The plugin provides the pattern and git snippets; the writer decides per plan which bullets are worth fanning out. No extra CLI subcommands needed. |
| D3 | FF-merge per sub-bullet, squash only for feature->main | User direction. FF preserves sub-branch history for audit without polluting main; squash at the end yields one clean conventional commit per feature. |
| D4 | On FF failure: CLARIFY-NEEDED to orchestrator, no automatic merge commit | Safety net: automatic merge commits can mask conflict-resolution bugs. The orchestrator decides rebase, merge-commit, or abort. |
| D5 | Remove `--size 5` alongside the other changes instead of just deprecating | With the one-writer constraint, 2W/2R is no longer possible; another size would carry no distinct semantics. Reducing to 3+4 keeps the API clear. |
| D6 | Plan markers remain: `B3 || B4 [parallel]` triggers sub-worktree fan-out instead of a writer-2 briefing | Plan vocabulary stays the same, only the mechanism behind it changes. The writer replaces orchestrator-driven bullet partitioning with its own subagent spawns. |

### 0.21.0 (BREAKING UX: English-only plugin source + user-language-aware briefings, 2026-05-21)

User direction: the plugin source becomes 100 percent English (briefings,
comments, docstrings, decision logs, history entries, rule templates,
README), all personal and company-specific references are scrubbed for
publication, and every spawned agent gets a runtime directive at the top of
its briefing that tells it to mirror the human operator's language and to
default to English when unclear. Plugin internals stay deterministic English;
multilingual UX is delivered at runtime through the agent, not through
source-level translation.

- BREAKING UX: orchestrator, writer, and solo briefings now start with the
  line `Language: respond to the human in the language the human writes in.
  Default English.`. Existing automation that pinned spawned-agent output to
  German will see English unless the human writes in German first.
- Translated: `scripts/tmux_pair.py` (~262 umlaut hits across briefing
  templates, docstrings, help text, comments).
- Translated: `PROJECT.md` history blocks for 0.13.0 through 0.18.0,
  decision tables, and intro prose. Direct German user-quotes paraphrased.
- Translated: `skills/tmux-pair-orchestration/SKILL.md`,
  `references/gated-workflow.md`, and `examples/solo-briefing.md` (the last
  carries the language-aware directive at the top of its writer template).
- Translated: 7 rule templates under `templates/rules/` plus 5 scoped agent
  definitions under `agents/`.
- Depersonalized: removed all personal names, the author's home-directory
  absolute paths, and former-employer organisation/project namespaces from
  the plugin tree. Replacements use `the user`, generic example
  placeholders, or the `${CLAUDE_PLUGIN_ROOT}` indirection where the
  context demanded a path-like token.
- Dropped (genuinely obsolete): the language-specific anti-AI-slop token
  list, the language-specific trailing-participle exemplar, and the
  umlaut-mandate rules in gate-3-code-reviewer, gate-3-verifier, and
  rules-bootstrap. With English-only output none of these have an
  equivalent target.
- Preserved: every function name, class, dict key, CLI flag, JSON field,
  environment variable, regex pattern, magic constant. The diff is text-only.
- Verification gate: a single ripgrep pass over `plugins/tmux-pair/`
  matching the umlaut characters plus the depersonalization token set
  returns zero matches; `python3 -c "import ast;
  ast.parse(open(...).read())"` on `tmux_pair.py` succeeds.
- Version sync: `plugin.json`, `.codex-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`, and SKILL.md frontmatter all on 0.21.0.

V2 decision log for 0.21.0:

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | Plugin source is 100 percent English, multilingual UX is runtime-only | Source-level translation per language would duplicate every briefing and rot fast. A single English source plus the language-aware briefing directive lets each spawned agent mirror the operator in flight without divergent maintenance. |
| D2 | The language-aware directive lives at the TOP of each briefing body, not deep in a standards block | Briefings are long; placement at the top guarantees the directive lands in the agent's first response context window before any specific instructions narrow its attention. |
| D3 | German-specific anti-AI-slop tokens removed instead of translated | They were guardrails against German AI-slop. With English-only output they have no equivalent target; translating them would create false positives against legitimate English text. |
| D4 | Generic placeholders (`example-repo`, `~/code/example-project`, `${CLAUDE_PLUGIN_ROOT}`) instead of leaving anonymized references | The depersonalized text must still convey what the original example meant (a consumer repo path, the plugin root, a third-party tool). Generic placeholders carry the structural meaning without leaking identity. |
| D5 | Version bump 0.20.2 -> 0.21.0 (minor) with `refactor!` commit subject | The diff is text-only and preserves all logic, but the UX-default flip (English instead of whichever language the briefing template happened to use) is observable to existing users, so the `!` marker is honest. Minor bump because the feature surface gains the language-aware directive without removing any flag. |
| D6 | Existing pre-merge git history left untouched | Out of scope for this refactor: a separate `git filter-repo` pass will rewrite history for PII and language after the squash-merge. The bullet commits in this run are English from the start, so the squash commit on `main` is already clean. |
