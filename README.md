# derveloper-skills

Personal Claude Code plugin marketplace.

## Plugins

- **[tmux-pair](plugins/tmux-pair/)** (v0.15.1) — Spawn solo (single agent + gated 6-phase subagent-driven self-review), pair (writer/reviewer), or triple (writer/reviewer/orchestrator) agent runs in fresh git worktrees, wired up via tmux. Features: 5-gate workflow for pair/triple plus 6-phase workflow for solo, V1-V5 smart-workflow primitives (inline-fix, decision-threshold, adaptive strictness, BLOCKER/WARNING/NOTE, unattended default), V6-V10 caching + trust-chains (readiness-cache, TESTS-PROOF marker enforced as trust-source for gate-3 verifier, cargo-target sharing, recon-cache with delta, inline-gates for trivial plans), PROJECT.md care, repo-specific subagent auto-detection (`.claude/agents/<repo>-*.md`), durable standards, parallel-plan markers, dual-review, pi as third coding-agent alongside claude + codex.

## Install

Add this marketplace to Claude Code:

```
/plugin marketplace add derveloper/derveloper-skills
```

Then install plugins individually:

```
/plugin install tmux-pair@derveloper-skills
```

## Contributing

Two version fields must stay in sync per plugin:

- `plugins/<name>/plugin.json` — the plugin's own manifest
- `.claude-plugin/marketplace.json` `plugins[].version` — what `/plugin update` reads (and what claude-code uses for cache-keying)

A pre-commit hook enforces this. Activate once after cloning:

```bash
git config core.hooksPath hooks
```

The hook runs `scripts/check-plugin-versions.py` and blocks the commit on any mismatch, missing manifest, name/dir disagreement, or orphan entry. Bypass via `--no-verify` only when intentional, with a reason in the commit body.

## License

Apache 2.0. See [LICENSE](LICENSE).
