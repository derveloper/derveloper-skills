#!/usr/bin/env python3
"""Check that plugin.json versions match the marketplace.json listing.

Two sources of truth must stay in sync:

  - .claude-plugin/marketplace.json (plugins[].version) — what claude-code
    renders in /plugin and uses for cache-keying.
  - plugins/<name>/plugin.json (version) — the plugin's own manifest.

A mismatch means /plugin update will silently keep showing the old version
even after a plugin bumps internally.

Exit codes:
  0 - all good
  1 - one or more mismatches, orphans, or missing files
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE_FILE = REPO_ROOT / ".claude-plugin" / "marketplace.json"
PLUGINS_DIR = REPO_ROOT / "plugins"


def fail(msg: str) -> None:
    print(f"check-plugin-versions: {msg}", file=sys.stderr)


def main() -> int:
    if not MARKETPLACE_FILE.exists():
        fail(f"missing {MARKETPLACE_FILE.relative_to(REPO_ROOT)}")
        return 1

    marketplace = json.loads(MARKETPLACE_FILE.read_text())
    listing = {p["name"]: p for p in marketplace.get("plugins", [])}

    plugin_dirs = (
        sorted(p for p in PLUGINS_DIR.iterdir() if p.is_dir())
        if PLUGINS_DIR.is_dir()
        else []
    )

    issues: list[str] = []
    seen_dirs: set[str] = set()

    for plugin_dir in plugin_dirs:
        manifest = plugin_dir / "plugin.json"
        name = plugin_dir.name
        seen_dirs.add(name)

        if not manifest.exists():
            issues.append(f"plugins/{name}/plugin.json missing")
            continue

        try:
            data = json.loads(manifest.read_text())
        except json.JSONDecodeError as e:
            issues.append(f"plugins/{name}/plugin.json invalid JSON: {e}")
            continue

        manifest_name = data.get("name")
        manifest_version = data.get("version")

        if manifest_name != name:
            issues.append(
                f"plugins/{name}/plugin.json: name='{manifest_name}' "
                f"does not match directory '{name}'"
            )

        if name not in listing:
            issues.append(
                f"plugins/{name}/plugin.json exists but no entry in "
                f"marketplace.json plugins[]"
            )
            continue

        listing_version = listing[name].get("version")
        if listing_version != manifest_version:
            issues.append(
                f"version mismatch for '{name}': "
                f"marketplace.json={listing_version} vs "
                f"plugin.json={manifest_version}"
            )

    for name in listing.keys() - seen_dirs:
        source = listing[name].get("source", "")
        issues.append(
            f"marketplace.json lists '{name}' (source={source}) but "
            f"no plugins/{name}/ directory exists"
        )

    if issues:
        fail("found {n} issue(s):".format(n=len(issues)))
        for i in issues:
            print(f"  - {i}", file=sys.stderr)
        print(
            "\nFix: bump both files together. The marketplace listing is what "
            "/plugin update reads.",
            file=sys.stderr,
        )
        return 1

    print(f"check-plugin-versions: {len(plugin_dirs)} plugin(s) consistent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
