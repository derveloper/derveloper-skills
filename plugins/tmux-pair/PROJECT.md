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
- Adaptive GATE-Strictness: Orch klassifiziert task_kind
  (bug-fix/feature/refactor) im Recon; gate-2-plan-check, gate-3-verifier und
  gate-3-code-reviewer lockern/schärfen Checklist-Items per Klasse.
- --interactive Flag (Spawn): opt-in Decision-Pause-Points. Default off
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

### 0.15.0 (Solo-Mode + Repo-Subagent-Detection, 2026-05-14)

Drittes Spawn-Mode neben pair/triple: solo. Ein Agent, gated 6-Phase
Self-Driven-Workflow, Subagent-gestützte adversariale Reviews. Plus
automatische Erkennung repo-spezifischer Subagents in jedem Briefing.

- Solo-Mode: `/solo <project> <base> <feature> [task]` spawnt einen
  Agent in frischem Worktree. Default gated (6 Phasen: Recon -> Plan +
  GATE-2 -> Impl -> GATE-3 Self-Review -> PROJECT.md + Skill-Persist ->
  Commit + DONE-Ping). Recon, Plan-Check, Code-Review und Verifier laufen
  als Subagents (`tmux-pair:gate-2-plan-check`, `tmux-pair:gate-3-verifier`,
  `tmux-pair:gate-3-code-reviewer`). `--no-gated` schaltet auf Minimal-Spawn.
- Repo-Subagent-Detection: `_detect_repo_subagents(project)` scannt
  `.claude/agents/<project-name>-*.md` und listet alle Treffer im Briefing.
  Solo (und pair/triple) instruieren den Agent diese Domain-Experten
  gegenüber `general-purpose` zu bevorzugen. Detection-Logik: filename-stem
  beginnt mit `<project.name>-`.
- Companion-Files: `commands/solo.md` (Slash-Command), Solo-Block in
  SKILL.md, `cmd_solo` + `_briefing_solo` in `scripts/tmux_pair.py`,
  `solo` argparse-Subcommand mit allen Flags (--no-gated, --no-worktree,
  --interactive, --with-standards, --greenfield, --agent, --claude-*,
  --pi-*, --no-shared-target).
- Feedback-Memory: `feedback_repo_specific_subagents_first.md` als
  durable User-Regel zementiert: "Repo mit `.claude/agents/<repo>-*` ->
  IMMER diese im Briefing nennen, niemals general-purpose als Default".

V2 Decision-Log für 0.15.0:

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | Solo-Default gated ON | User-Decision GATE 1: Solo-Workflow soll standardmäßig die Gates durchlaufen, weil der ganze Wert in adversarialer Selbst-Review liegt. `--no-gated` als Opt-out für triviale Tasks. |
| D2 | Solo-Default Worktree ON | User-Decision GATE 1: Solo soll wie pair/triple in frischem Worktree spawnen, sonst zerstören Agents-Edits lokale Working-Dir-States. `--no-worktree` als Opt-out für Fortsetzung bestehender Branches. |
| D3 | Repo-Detection-Pattern: filename-stem-prefix `<project.name>-` | Konvention-Match mit existierendem `.claude/agents/`-Layout. Detection arbeitet sprachunabhängig und ohne YAML-Parsing. |
| D4 | Detection-Hint in Briefing UND Skill | User-Decision GATE 1 Both: Skill-Hint hilft Agent auch nach `/compact`, Briefing-Hint greift sofort beim Boot. Doppelt hält besser. |
| D5 | Skill-Persist (Phase 5) statt Rules-Persist | Path-scoped Skills (`.claude/skills/<repo>-<topic>/SKILL.md`) sind die neue Default-Konvention seit ebca198. Rules nur für Cross-Cutting-Always-On-Items. |

### 0.15.1 (No-Double-Work + TESTS-PROOF-Trust + Parallel-Default, 2026-05-15)

Patch-Bump: gate-3-verifier vertraut TESTS-PROOF-Markern und re-runned
NIEMALS workspace-weite Gates die Engineers bereits zertifiziert haben.
Plus harte PARALLEL-BY-DEFAULT-Regel in allen Briefings.

- `gate-3-verifier.md` Item 6 verschärft: Decision-Matrix per
  Bullet-Commit (`found=true + head_matches=true` -> trust + skip Re-Run;
  `head_matches=false` -> narrow Re-Run + WARNING; missing 0.14+ ->
  BLOCKER; missing legacy -> narrow Re-Run + WARNING). NIEMALS
  workspace-weiter "to be safe" Run wenn Marker valid.
- `gate-2-plan-check.md` Item 10: NARROW SCOPE Pflicht (cargo nextest -p
  <crate>, pytest <path>, pnpm test <glob>); Plan ohne TESTS-PROOF-Anchor
  in DONE-Definition jedes Bullets -> BLOCKER; Plan mit
  `cargo test --workspace` pro Bullet -> WARNING.
- `tmux_pair.py` ENGINEER_SUBAGENT_STRATEGY_BLOCK: PARALLEL BY DEFAULT +
  NO DOUBLE WORK Pflicht-Sektionen. Independent bullets serial =
  Anti-Pattern.
- `tmux_pair.py` TEST_STRATEGY_BLOCK: TESTS-PROOF-Marker Pflicht in
  jedem Bullet-Commit + DONE-Ping (Migration von "Schema steht" auf
  "Schema enforced").
- GATE-3-Orchestrator-Template (`_briefing_gate_prompts`): explizite
  Marker-Anweisung "Trusts engineers' TESTS-PROOF marker; runs tests
  ONLY if marker missing or stale, and only the narrowest scope".

V2 Decision-Log für 0.15.1:

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | Marker-Trust statt Re-Run als Default | User-Feedback "das nochmal die workspace tests komplett laufen im gate 3 ist doch unnötig, das haben doch die engineers schon gemacht". TESTS-PROOF-Schema steht seit 0.14.0 (V7), enforcement war fehlend. |
| D2 | Narrow-Scope per Bullet, workspace-gate nur pre-DONE | User-Feedback "möglichst viel parallel, pläne auf optimal, schnelle test ausführung optimiert". `cargo test --workspace` 10x in 10 Bullets ist Token+Wall-Clock-Waste. |
| D3 | BLOCKER auf 0.14+ commits ohne Marker | 0.14.0 Migrations-Pflicht abgeschlossen, neue Spawns müssen den Block setzen. Legacy-Commits bleiben WARNING (Backward-Compat). |

### 0.16.0 (BREAKING: /pair raus, /triple zu /spawn, dynamic team-size, /run auto-entry, 2026-05-15)

Major-Bump mit Breaking-Changes auf Slash-Command-Surface + Python-CLI. Pair-
Mode (writer + reviewer ohne Orchestrator, Human-als-Orchestrator) wird hart
entfernt: das Konzept "Human-als-Orchestrator" hat in der Praxis nicht
zuverlässig funktioniert (Human ist meist nicht da oder beschäftigt; Engineers
warteten auf Decisions ohne Flow-Control). Triple-Mode wird zu `/spawn` mit
dynamischer Größenwahl umbenannt und um `--size 3..5` plus `--parallel-writers`
erweitert. Neue `/run` Auto-Entry: kurze Recon, empfiehlt solo oder spawn (mit
recommended `--size`), delegiert.

- BREAKING: `/pair` slash-command entfernt. `commands/pair.md` gelöscht. Kein
  Deprecation-Alias.
- BREAKING: `/triple` -> `/spawn`. `commands/triple.md` umbenannt zu
  `commands/spawn.md` mit überarbeitetem Content.
- BREAKING: `--dual-review` Flag entfernt. Stattdessen `--size 4` (default
  dual-review preset) oder `--size 4 --parallel-writers` (2-writer preset).
- NEW: `commands/run.md` Auto-Entry. Skill-Logik: clarify intent, repo-recon,
  recommend solo vs spawn (mit `--size`), invoke `/solo` oder `/spawn`.
  Explicit user-mode overrides recommendation.
- NEW: `/spawn --size N` (default 3, choices 3/4/5). Mapping: 3 = 1W/1R/1O.
  4 = 1W/2R/1O (dual-review). 4 + `--parallel-writers` = 2W/1R/1O. 5 = 2W/2R/1O.
- NEW: `--parallel-writers` flag mit argparse-Validation (`--size 3 +
  --parallel-writers` -> argparse-error).
- NEW: `--writer-2-agent` flag analog `--reviewer-2-agent`.
- NEW: Python-Helper `_spawn_layout(size, parallel_writers) -> {writers,
  reviewers, orchestrator}` als Single-Source-of-Truth für Team-Size-Logik.
- BREAKING: Primitive single-pane subcommand umbenannt `spawn` -> `pane`. Der
  `spawn`-Slot ist jetzt der Team-Spawn (vorher `triple`); der primitive
  Single-Pane-Spawner heißt jetzt `pane`.
- NEW: `_peer_writer_block` Helper in Engineer-Briefings; Writer-Briefing bei
  parallel-writers bekommt disjoint-bullets-Directive, Reviewer-Briefing
  bekommt two-stream-tracking-Directive.
- NEW: Orchestrator-Briefing PARALLEL-WRITERS-Direktive (analog DUAL-REVIEW)
  mit Plan-Partition-Anleitung und Datei-Kollision-Protokoll.
- JSON Output: `mode: "triple"` + `dual_review: bool` -> `mode: "spawn"` +
  `size: int` + `writers: int` + `reviewers: int` + `parallel_writers: bool` +
  `dual_review: bool`.
- Versions-Sync: `plugin.json`, `.claude-plugin/marketplace.json`, und
  `skills/tmux-pair-orchestration/SKILL.md` frontmatter alle auf 0.16.0.

V2 Decision-Log für 0.16.0:

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | Slash-Command-Name: `/spawn` (nicht `/team`, `/agents`) | User-Decision: "spawn" passt zur bestehenden Vokabular-Linie (tmux_pair.py spawn als Subcommand-Synonym für Worktree+Pane+Brief; neuer pane-Subcommand löst die Kollision). |
| D2 | Slash-Command für Auto-Entry: zusätzlich `/run` neben Skill-Trigger | User-Decision: explicit slash-command ist diskoverable für User die nicht via Skill-Phrase einsteigen; Skill-Trigger bleibt parallel für natural-language Aufruf. |
| D3 | Team-Size dynamisch ab 3, Skill recommends nach Recon, `--size` als explicit Override | User-Decision: 3 als kleinstes sinnvolles Team (orchestrator + 1W + 1R), Recon kann größer empfehlen wenn parallel-bullets oder dual-review nötig; User kann recommendation überstimmen. |
| D4 | Hard removal `/pair`, kein Deprecation-Alias | User-Decision: Pair-Mode mit Human-als-Orchestrator hat strukturell nicht funktioniert; clean break ohne Alias-Confusion. Major-Bump rechtfertigt Breaking-Change. |
| D5 | Plugin-Name bleibt "tmux-pair" trotz Removal von /pair | User-Decision: Etablierter Name, "pair protocol" bleibt als Konzept-Begriff für Writer+Reviewer-Loop innerhalb eines Spawns; Rename des Plugins würde Marketplace-URL und User-Memory brechen. |
| D6 | `--dual-review` Flag hart entfernen, durch `--size` ersetzen | Cleanest API: --size ist die einzige Quelle für Team-Layout, dual-review folgt aus `reviewers >= 2`. Backward-Compat-Alias wäre Verwirrungs-Quelle. |
| D7 | `cmd_spawn` (primitive) -> `cmd_pane`; `cmd_triple` -> `cmd_spawn` | Naming-Kollision-Auflösung: alter primitiver Single-Pane-Spawner kollidiert mit neuem Team-Spawn-Namen. `pane` beschreibt den primitiven Slot präziser. |
| D8 | argparse-error für `--parallel-writers --size 3` statt silent-ignore | Plan-Check-Subagent-Finding: silent-ignore wäre Failure-Klasse; argparse-time-error scheitert früh und falsifizierbar. |
| D9 | Writer-2 partner_pane = reviewer (gleich wie Writer-1), peer_writer_pane = Writer-1 als Cross-Awareness | Plan-Check-Finding: writer-2 muss disambig sein. Disjoint-bullets bedeutet kein direkter Sync zwischen Writern; Coordination via Orchestrator. peer_writer_pane nur als Awareness-Hint für Datei-Kollisions-Detection. |
| D10 | PROJECT.md frontmatter SKILL.md version-Bump weiterhin manuell (kein automatischer Check) | check-plugin-versions.py prüft heute nur plugin.json + marketplace.json. SKILL.md frontmatter-Validation bleibt Follow-up (siehe 0.14.0 D10). 0.16.0 dokumentiert das im Acceptance-Block, fixt es aber nicht (Scope-Begrenzung). |

### 0.18.0 (BREAKING: Multi-Writer raus, Subagent-Worktree-Pattern, 2026-05-19)

the user-Anweisung: "multiwriter fliegen komplett raus, die machen probleme und
overhead. wenn mehrere subagents in einem writer arbeiten können (so sollen ja
plände gebaut sein), dann müssen die jeweils in eigenen worktrees arbeiten,
damit die nicht konflikten, es gibt dann also einen baum von worktrees, der vom
feature/aufgabe selbst und dann ggf. die der subagents, die dann gemerged
werden, fast-forward wenns geht, squash nur für den abschließenden merge auf
main".

- BREAKING: `--parallel-writers` Flag komplett entfernt.
- BREAKING: `--writer-2-agent` Flag komplett entfernt.
- BREAKING: `--pi-writer-2-*` Flags komplett entfernt.
- BREAKING: `--size 5` entfernt (war 2W/2R, nicht mehr komponierbar).
  Valid sizes jetzt nur noch 3 (1W/1R/1O) und 4 (1W/2R/1O dual-review).
- BREAKING: Output-JSON-Felder `parallel_writers`, `writer_2_pane`,
  `writer_2_agent`, `writer_2_name`, `writer_2_ready` entfernt.
- REMOVED: `_peer_writer_block` Helper (war Engineer-Briefing-Inject für
  Writer-2-Awareness). Ersetzt durch `_subagent_worktree_block`.
- REMOVED: PARALLEL-WRITERS-Direktive im Orchestrator-Briefing.
- NEW: Orchestrator-Briefing SUBAGENT-WORKTREE-Direktive: Writer fan-out via
  `git worktree add ../<feature>-sub-<bullet-id>`, ein Task-Subagent pro
  Sub-WT, FF-merge zurück in Feature-WT, Cleanup pro Sub-Bullet.
- NEW: Writer-Briefing SUBAGENT-WORKTREE-Block (`_subagent_worktree_block`):
  exakte Git-Befehle für Add/Merge/Remove, Fallback-Pfad (FF-Failure ->
  CLARIFY-NEEDED an Orch, kein automatischer Merge-Commit), explizite
  Trennung sequenzielle vs parallele Bullets.
- NEW: README, spawn.md, SKILL.md, solo-vs-spawn.md, pair-protocol.md
  Sektionen zur Subagent-Worktree-Pattern + Squash-Final-Merge-Discipline.
- Versions-Sync: `plugin.json`, `.claude-plugin/marketplace.json`, und
  `skills/tmux-pair-orchestration/SKILL.md` frontmatter alle auf 0.18.0.

V2 Decision-Log für 0.18.0:

| ID | Decision | Rationale |
|----|----------|-----------|
| D1 | Multi-Writer-Pane hart entfernen statt deprecaten | User-Anweisung "komplett raus", 0.16.0 hatte Multi-Writer ohnehin als opt-in eingeführt; clean break passt zu Plugin-Major-Cadence. |
| D2 | Subagent-Worktree-Pattern auf Briefing-Ebene, nicht im Plugin-Code automatisiert | Sub-Worktree-Erzeugung ist LLM-/Plan-driven, nicht statisch. Plugin gibt Pattern + Git-Snippets vor; Writer entscheidet pro Plan welche Bullets fan-out wert sind. Keine extra CLI-Subcommands nötig. |
| D3 | FF-Merge per Sub-Bullet, Squash nur für Feature->main | User-Anweisung. FF behält Sub-Branch-History für Audit ohne main zu polluten; Squash am Ende ergibt einen sauberen Conventional-Commit pro Feature. |
| D4 | Bei FF-Failure: CLARIFY-NEEDED an Orchestrator, kein automatischer Merge-Commit | Sicherheitsnetz: automatische Merge-Commits können Conflict-Resolution-Bugs maskieren. Orchestrator entscheidet rebase|merge-commit|abort. |
| D5 | `--size 5` mit-entfernen statt nur deprecaten | Mit 1-Writer-Constraint ist 2W/2R nicht mehr möglich; weiteres Size hätte keine andere Semantik mehr. Reduktion auf 3+4 hält API klar. |
| D6 | Plan-Marker bleiben: `B3 || B4 [parallel]` triggert Sub-Worktree-Fan-Out statt Writer-2-Briefing | Plan-Vokabular ist gleich, nur der Mechanismus dahinter wechselt. Writer ersetzt Orchestrator-Bullet-Partitionierung durch eigene Subagent-Spawns. |
