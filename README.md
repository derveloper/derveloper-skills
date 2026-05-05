# derveloper-skills

Personal Claude Code plugin marketplace.

## Plugins

- **[tmux-pair](plugins/tmux-pair/)** — Spawn writer/reviewer agent pairs (or writer/reviewer/orchestrator triples) in fresh git worktrees, wired up via tmux.

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
