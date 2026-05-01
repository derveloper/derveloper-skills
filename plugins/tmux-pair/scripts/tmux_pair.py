#!/usr/bin/env python3
"""tmux-pair: spawn coding-agent pairs or triples in tmux + git worktrees.

Subcommands:
  spawn         single agent in a window (existing or new)
  send          send text to a pane (handles multi-line + agent-TUI Enter quirks)
  pair          writer + reviewer in a fresh worktree, side by side
  triple        writer + reviewer + orchestrator in a fresh worktree
  list          list panes managed in the current session
  capture       capture-pane snapshot for one pane

Designed to run from inside a tmux session. The script spawns into whichever
session it currently lives in (`tmux display-message -p '#S'`).

Configure agent launch commands by writing JSON to
  ~/.config/tmux-pair/agents.json
keyed by agent name. Defaults below are intentionally minimal.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

DEFAULT_AGENTS: dict[str, str] = {
    "claude": "claude --dangerously-skip-permissions",
    "codex": "codex --dangerously-bypass-approvals-and-sandbox",
}

CONFIG_PATH = Path.home() / ".config" / "tmux-pair" / "agents.json"


def load_agents() -> dict[str, str]:
    agents = dict(DEFAULT_AGENTS)
    if CONFIG_PATH.exists():
        try:
            agents.update(json.loads(CONFIG_PATH.read_text()))
        except json.JSONDecodeError as exc:
            print(f"warning: {CONFIG_PATH} is not valid JSON: {exc}",
                  file=sys.stderr)
    return agents


def tmux(*args: str) -> str:
    proc = subprocess.run(["tmux", *args], capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"tmux {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def tmux_safe(*args: str) -> tuple[int, str, str]:
    proc = subprocess.run(["tmux", *args], capture_output=True, text=True)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def current_session() -> str:
    if "TMUX" not in os.environ:
        sys.exit("error: not inside a tmux session")
    return tmux("display-message", "-p", "#S")


def window_exists(session: str, window_name: str) -> bool:
    rc, _, _ = tmux_safe("list-windows", "-t", session, "-F", "#{window_name}")
    if rc != 0:
        return False
    out = tmux("list-windows", "-t", session, "-F", "#{window_name}")
    return window_name in out.splitlines()


def slugify(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "-", s.strip().lstrip("/"))


def cmd_send(args: argparse.Namespace) -> int:
    """Send `args.text` to pane `args.pane`, handling multi-line + Enter quirks.

    Single-line: send-keys -l, then Enter.
    Multi-line:  load-buffer + paste-buffer (avoids per-newline submit issues
                 in agent TUIs), then Enter.

    Some agent TUIs ignore the first Enter when a tool call is in flight, so we
    send Enter three times with small gaps. Override with --no-enter.
    """
    pane = args.pane
    text = args.text
    if "\n" in text:
        buf = f"tmuxpair-{os.getpid()}-{int(time.time() * 1000) % 100000}"
        proc = subprocess.run(
            ["tmux", "load-buffer", "-b", buf, "-"],
            input=text, text=True, capture_output=True,
        )
        if proc.returncode != 0:
            print(f"error: load-buffer failed: {proc.stderr}", file=sys.stderr)
            return 1
        rc, _, err = tmux_safe("paste-buffer", "-b", buf, "-t", pane, "-d")
        if rc != 0:
            print(f"error: paste-buffer failed: {err}", file=sys.stderr)
            return 1
    else:
        rc, _, err = tmux_safe("send-keys", "-t", pane, "-l", text)
        if rc != 0:
            print(f"error: send-keys failed: {err}", file=sys.stderr)
            return 1

    if args.no_enter:
        return 0

    time.sleep(0.2 if "\n" not in text else 0.3)
    for i in range(3):
        tmux_safe("send-keys", "-t", pane, "C-m")
        if i < 2:
            time.sleep(0.5)
    return 0


def _schedule_slash_command(pane_id: str, slash: str, delay_s: int) -> None:
    """Background-schedule a single slash-command into a TUI pane after delay.

    Used to inject /effort max (claude) and /rename <name> (both) post-boot,
    before the briefing lands at 14s.
    """
    bg = (
        f"sleep {delay_s} && "
        f"tmux send-keys -t {shlex.quote(pane_id)} -l {shlex.quote(slash)} && "
        f"sleep 0.3 && "
        f"tmux send-keys -t {shlex.quote(pane_id)} C-m"
    )
    subprocess.Popen(
        ["bash", "-c", bg], start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def spawn_pane(
    *,
    session: str,
    window_name: str,
    cwd: str,
    agent: str,
    boot_command: str,
    split: str,
    display_name: str = "",
) -> str:
    """Spawn a pane, return its pane-id. `split` ∈ {none, h, v}.

    `display_name`, when set, is applied two ways post-boot:
      - tmux pane-title (visible when pane-border-status=top)
      - `/rename <name>` slash-command (claude + codex; visible in TUI header
        + /resume picker)
    """
    target = f"{session}:{window_name}"
    if not window_exists(session, window_name):
        pane_id = tmux(
            "new-window", "-t", f"{session}:", "-n", window_name,
            "-c", cwd, "-d", "-P", "-F", "#{pane_id}",
        )
    else:
        if split == "none":
            sys.exit(f"error: window '{window_name}' exists, need split=h|v")
        flag = "-h" if split == "h" else "-v"
        pane_id = tmux(
            "split-window", "-t", target, flag, "-c", cwd,
            "-P", "-F", "#{pane_id}",
        )

    if display_name:
        tmux_safe("select-pane", "-t", pane_id, "-T", display_name)
        # Make pane titles visible. Server-wide setting, idempotent. Users who
        # don't want it can override in their .tmux.conf.
        tmux_safe("set-option", "-g", "pane-border-status", "top")

    if boot_command:
        time.sleep(0.5)  # shell needs boot time, otherwise first char is eaten
        tmux("send-keys", "-t", pane_id, "-l", boot_command)
        tmux("send-keys", "-t", pane_id, "C-m")

    # Post-boot slash-commands. Schedule order:
    #   t+8s  /effort max  (claude only; reasoning-level for initial briefing)
    #   t+10s /rename ...  (claude + codex; readable session label)
    #   t+14s briefing send (caller via _schedule_send)
    if boot_command:
        if agent == "claude":
            _schedule_slash_command(pane_id, "/effort max", delay_s=8)
        if display_name:
            _schedule_slash_command(pane_id, f"/rename {display_name}", delay_s=10)

    return pane_id


def cmd_spawn(args: argparse.Namespace) -> int:
    agents = load_agents()
    if args.agent not in agents:
        sys.exit(f"error: unknown agent '{args.agent}'. "
                 f"known: {', '.join(sorted(agents))}. "
                 f"Add custom agents to {CONFIG_PATH}.")
    cwd = args.cwd or os.getcwd()
    if not Path(cwd).is_dir():
        sys.exit(f"error: cwd not a directory: {cwd}")

    session = args.session or current_session()
    window_name = args.window
    boot = agents[args.agent]
    if args.task:
        boot = f"{boot} {shlex.quote(args.task)}"

    pane_id = spawn_pane(
        session=session,
        window_name=window_name,
        cwd=cwd,
        agent=args.agent,
        boot_command=boot,
        split=args.split,
        display_name=args.name or "",
    )
    print(json.dumps({"pane_id": pane_id, "window": window_name,
                      "session": session, "agent": args.agent,
                      "display_name": args.name or None}, indent=2))
    return 0


def fetch_if_remote_ref(repo: Path, base: str) -> None:
    if base.startswith("origin/") or base.startswith("upstream/"):
        remote = base.split("/", 1)[0]
        proc = subprocess.run(
            ["git", "-C", str(repo), "fetch", remote],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            sys.exit(f"error: git fetch {remote}: {proc.stderr.strip()}")


def make_worktree(project_root: Path, feature: str, base: str) -> tuple[Path, str]:
    feature_slug = slugify(feature)
    wt_path = project_root.parent / f"{project_root.name}-wt-{feature_slug}"
    branch = f"feature/{feature_slug}"

    if wt_path.exists():
        sys.exit(f"error: worktree path exists: {wt_path}")

    fetch_if_remote_ref(project_root, base)

    branch_ref_check = subprocess.run(
        ["git", "-C", str(project_root), "show-ref", "--verify",
         f"refs/heads/{branch}"],
        capture_output=True,
    )
    if branch_ref_check.returncode == 0:
        wt_args = ["worktree", "add", str(wt_path), branch]
    else:
        wt_args = ["worktree", "add", str(wt_path), "-b", branch, base]

    proc = subprocess.run(
        ["git", "-C", str(project_root), *wt_args],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        sys.exit(f"error: worktree add: {proc.stderr.strip()}")

    return wt_path, branch


def _common_pair_setup(args: argparse.Namespace) -> tuple[Path, Path, str, str, str]:
    """Resolve project root, create worktree, return (project_root, wt_path,
    branch, window_name, master_pane)."""
    project = Path(args.project).expanduser().resolve()
    if not (project / ".git").exists():
        sys.exit(f"error: {project} is not a git repository "
                 f"(no .git directory or file)")

    wt_path, branch = make_worktree(project, args.feature, args.base)
    window_name = f"{project.name}-{slugify(args.feature)}"[:30]

    master_pane = os.environ.get("TMUX_PANE", "")
    if not master_pane:
        rc, out, _ = tmux_safe("display-message", "-p", "-F", "#{pane_id}")
        master_pane = out if rc == 0 else "?"

    return project, wt_path, branch, window_name, master_pane


def _scripts_dir() -> Path:
    return Path(__file__).resolve().parent


def _send_command(pane: str) -> str:
    """Format the cross-pane send command this script's peers should use."""
    return f"python3 {_scripts_dir() / 'tmux_pair.py'} send {pane}"


def _briefing_pair(
    *, role: str, partner_role: str, partner_pane: str,
    wt_path: Path, branch: str, base: str, project: str,
    task: str,
) -> str:
    send_cmd = _send_command(partner_pane)
    return (
        f"[ROLE: {role}]\n\n"
        f"You are paired with the {partner_role} ({partner_pane}).\n\n"
        f"WORKTREE: {wt_path}\n"
        f"BRANCH:   {branch}\n"
        f"BASE:     {base}\n"
        f"PROJECT:  {project}\n\n"
        f"TASK\n{task or '(none — wait for further instructions)'}\n\n"
        f"PAIR PROTOCOL\n"
        f"  Writer codes; reviewer reads. After each meaningful change the\n"
        f"  writer pings: {send_cmd} \"REVIEW-READY: <one-line summary>\"\n"
        f"  Reviewer responds with REVIEW: APPROVE or REVIEW: <findings>.\n"
        f"  Loop until APPROVE; then writer commits and pings DONE.\n\n"
        f"  Send peer messages with:\n"
        f"    {send_cmd} \"<message>\"\n\n"
        f"STANDARDS\n"
        f"  - Conventional Commits.\n"
        f"  - No --no-verify, no skipping hooks.\n"
        f"  - No AI co-author trailer in commit messages.\n"
        f"  - Tests must pass before commit.\n"
    )


def _briefing_orchestrator(
    *, writer_pane: str, writer_agent: str,
    reviewer_pane: str, reviewer_agent: str,
    orchestrator_pane: str, master_pane: str,
    wt_path: Path, branch: str, base: str, project: str, window_name: str,
    task: str,
) -> str:
    send_writer = _send_command(writer_pane)
    send_reviewer = _send_command(reviewer_pane)
    send_master = _send_command(master_pane)
    return (
        f"[ROLE: Orchestrator]\n\n"
        f"You orchestrate a writer + reviewer pair. You do NOT code, you do\n"
        f"NOT review. You do recon, brief the engineers, watch the pair loop\n"
        f"at high level, and surface major events to the master pane.\n\n"
        f"WORKTREE: {wt_path}\n"
        f"BRANCH:   {branch}\n"
        f"BASE:     {base}\n"
        f"PROJECT:  {project}\n"
        f"WINDOW:   {window_name}\n\n"
        f"PANES\n"
        f"  {orchestrator_pane}  YOU (orchestrator)        - top, full width\n"
        f"  {writer_pane}    Writer ({writer_agent})    - bottom-left\n"
        f"  {reviewer_pane}  Reviewer ({reviewer_agent}) - bottom-right\n"
        f"  {master_pane}    Master (human)              - other window/pane\n\n"
        f"TASK (from master)\n{task or '(none — ask master to clarify)'}\n\n"
        f"DUTIES IN ORDER\n\n"
        f"1. RECON\n"
        f"   - Read upstream docs/specs relevant to the task.\n"
        f"   - Codebase recon: search for relevant files, functions, tests.\n"
        f"   - Outcome: concrete pointers (file + function + line) for the writer.\n\n"
        f"2. ENGINEER BRIEFINGS\n"
        f"   Write two separate briefings, one per engineer, and send them:\n"
        f"     {send_writer} \"<writer briefing>\"\n"
        f"     {send_reviewer} \"<reviewer briefing>\"\n"
        f"   Briefings should include: pointers from recon, concrete deliverables,\n"
        f"   the pair protocol (REVIEW-READY -> REVIEW loop), and your pane id\n"
        f"   ({orchestrator_pane}) for escalation.\n\n"
        f"3. WATCH THE LOOP\n"
        f"   Engineers ping you on: REVIEW DONE / BLOCKER / ESCALATION / STATUS.\n"
        f"   On silence > 10 minutes, capture-pane on writer/reviewer and nudge.\n"
        f"   Do not micromanage.\n\n"
        f"4. REPORT TO MASTER (sparingly)\n"
        f"   {send_master} \"[Orchestrator {window_name}] <short, max 4 lines>\"\n"
        f"   Only for: MAJOR-STEP, BLOCKER, DONE, ABORT. Not for trivia.\n\n"
        f"5. CLEANUP\n"
        f"   You do NOT decide on cleanup. After DONE, ping master and wait.\n\n"
        f"ANTI-PATTERNS\n"
        f"- Don't open code files for editing.\n"
        f"- Don't run builds/tests/linters yourself (engineers do).\n"
        f"- Don't write reviews. Reviewer does that.\n"
        f"- Don't flood master.\n\n"
        f"START. Step 1 recon. Step 2 brief engineers. Step 3-5 loop + report."
    )


def _schedule_send(pane: str, body: str, delay_s: int = 14) -> None:
    """Write briefing to a tempfile, schedule a delayed `send` so the agent
    has time to boot before the message lands."""
    tf = tempfile.NamedTemporaryFile(
        mode="w", delete=False, prefix="tmuxpair-briefing-", suffix=".txt",
    )
    tf.write(body)
    tf.close()

    self_path = shlex.quote(str(_scripts_dir() / "tmux_pair.py"))
    bg = (
        f"sleep {delay_s} && "
        f"python3 {self_path} send {pane} \"$(cat {shlex.quote(tf.name)})\" "
        f"&& rm -f {shlex.quote(tf.name)}"
    )
    subprocess.Popen(
        ["bash", "-c", bg], start_new_session=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def cmd_pair(args: argparse.Namespace) -> int:
    """Writer + reviewer in a fresh worktree, side by side."""
    agents = load_agents()
    for a in (args.writer_agent, args.reviewer_agent):
        if a not in agents:
            sys.exit(f"error: unknown agent '{a}'")

    project, wt_path, branch, window_name, master_pane = _common_pair_setup(args)
    session = current_session()

    writer_name = f"wr.{window_name}"
    reviewer_name = f"rv.{window_name}"

    writer_pane = spawn_pane(
        session=session, window_name=window_name, cwd=str(wt_path),
        agent=args.writer_agent, boot_command=agents[args.writer_agent],
        split="none", display_name=writer_name,
    )
    reviewer_pane = spawn_pane(
        session=session, window_name=window_name, cwd=str(wt_path),
        agent=args.reviewer_agent, boot_command=agents[args.reviewer_agent],
        split="h", display_name=reviewer_name,
    )

    target_window = f"{session}:{window_name}"
    tmux_safe("select-layout", "-t", target_window, "main-vertical")

    writer_brief = _briefing_pair(
        role="Writer", partner_role="reviewer", partner_pane=reviewer_pane,
        wt_path=wt_path, branch=branch, base=args.base, project=str(project),
        task=args.task or "",
    )
    reviewer_brief = _briefing_pair(
        role="Reviewer", partner_role="writer", partner_pane=writer_pane,
        wt_path=wt_path, branch=branch, base=args.base, project=str(project),
        task=args.task or "",
    )

    _schedule_send(writer_pane, writer_brief)
    _schedule_send(reviewer_pane, reviewer_brief)

    print(json.dumps({
        "mode": "pair",
        "worktree": str(wt_path),
        "branch": branch,
        "base": args.base,
        "window": window_name,
        "writer_pane": writer_pane,
        "writer_agent": args.writer_agent,
        "writer_name": writer_name,
        "reviewer_pane": reviewer_pane,
        "reviewer_agent": args.reviewer_agent,
        "reviewer_name": reviewer_name,
        "master_pane": master_pane,
        "briefing_dispatch": "scheduled in 14s (boot delay)",
    }, indent=2))
    return 0


def cmd_triple(args: argparse.Namespace) -> int:
    """Orchestrator + writer + reviewer in a fresh worktree."""
    agents = load_agents()
    for a in (args.writer_agent, args.reviewer_agent, args.orchestrator_agent):
        if a not in agents:
            sys.exit(f"error: unknown agent '{a}'")

    project, wt_path, branch, window_name, master_pane = _common_pair_setup(args)
    session = current_session()

    orchestrator_name = f"or.{window_name}"
    writer_name = f"wr.{window_name}"
    reviewer_name = f"rv.{window_name}"

    # Layout: orchestrator on top full width, writer bottom-left, reviewer bottom-right.
    orchestrator_pane = spawn_pane(
        session=session, window_name=window_name, cwd=str(wt_path),
        agent=args.orchestrator_agent,
        boot_command=agents[args.orchestrator_agent], split="none",
        display_name=orchestrator_name,
    )
    writer_pane = spawn_pane(
        session=session, window_name=window_name, cwd=str(wt_path),
        agent=args.writer_agent, boot_command=agents[args.writer_agent],
        split="v", display_name=writer_name,
    )
    reviewer_pane = spawn_pane(
        session=session, window_name=window_name, cwd=str(wt_path),
        agent=args.reviewer_agent, boot_command=agents[args.reviewer_agent],
        split="h", display_name=reviewer_name,
    )

    target_window = f"{session}:{window_name}"
    tmux_safe("select-layout", "-t", target_window, "main-horizontal")

    orchestrator_brief = _briefing_orchestrator(
        writer_pane=writer_pane, writer_agent=args.writer_agent,
        reviewer_pane=reviewer_pane, reviewer_agent=args.reviewer_agent,
        orchestrator_pane=orchestrator_pane, master_pane=master_pane,
        wt_path=wt_path, branch=branch, base=args.base, project=str(project),
        window_name=window_name, task=args.task or "",
    )

    # Engineers stay idle: only the orchestrator gets briefed; orchestrator
    # writes the engineer briefings after recon.
    _schedule_send(orchestrator_pane, orchestrator_brief)

    print(json.dumps({
        "mode": "triple",
        "worktree": str(wt_path),
        "branch": branch,
        "base": args.base,
        "window": window_name,
        "orchestrator_pane": orchestrator_pane,
        "orchestrator_agent": args.orchestrator_agent,
        "orchestrator_name": orchestrator_name,
        "writer_pane": writer_pane,
        "writer_agent": args.writer_agent,
        "writer_name": writer_name,
        "reviewer_pane": reviewer_pane,
        "reviewer_agent": args.reviewer_agent,
        "reviewer_name": reviewer_name,
        "master_pane": master_pane,
        "briefing_dispatch": "orchestrator only, scheduled in 14s; engineers idle until orchestrator briefs them",
    }, indent=2))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    session = args.session or current_session()
    rc, out, err = tmux_safe(
        "list-panes", "-s", "-t", session,
        "-F", "#{window_name}\t#{pane_id}\t#{pane_current_command}",
    )
    if rc != 0:
        print(err, file=sys.stderr)
        return 1
    print(out)
    return 0


def cmd_capture(args: argparse.Namespace) -> int:
    rc, out, err = tmux_safe(
        "capture-pane", "-t", args.pane, "-p", "-S", str(-args.lines),
    )
    if rc != 0:
        print(err, file=sys.stderr)
        return 1
    print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="tmux_pair", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("spawn", help="single agent in a window")
    sp.add_argument("--agent", required=True)
    sp.add_argument("--window", required=True)
    sp.add_argument("--cwd")
    sp.add_argument("--session")
    sp.add_argument("--split", choices=["none", "h", "v"], default="none")
    sp.add_argument("--task", default="")
    sp.add_argument("--name", default="",
                    help="display name; sent as /rename + tmux pane-title post-boot")
    sp.set_defaults(func=cmd_spawn)

    se = sub.add_parser("send", help="send text to a pane")
    se.add_argument("pane")
    se.add_argument("text")
    se.add_argument("--no-enter", action="store_true",
                    help="don't press Enter after sending")
    se.set_defaults(func=cmd_send)

    pa = sub.add_parser("pair", help="writer + reviewer in a fresh worktree")
    pa.add_argument("--project", required=True,
                    help="path to the git repo to base the worktree on")
    pa.add_argument("--feature", required=True,
                    help="short feature name, used in branch + window")
    pa.add_argument("--base", default="origin/main",
                    help="base ref (default: origin/main)")
    pa.add_argument("--task", default="",
                    help="task description sent to both agents")
    pa.add_argument("--writer-agent", default="codex")
    pa.add_argument("--reviewer-agent", default="claude")
    pa.set_defaults(func=cmd_pair)

    tr = sub.add_parser("triple",
                        help="orchestrator + writer + reviewer in a fresh worktree")
    tr.add_argument("--project", required=True)
    tr.add_argument("--feature", required=True)
    tr.add_argument("--base", default="origin/main")
    tr.add_argument("--task", default="",
                    help="task description sent to the orchestrator only")
    tr.add_argument("--writer-agent", default="codex")
    tr.add_argument("--reviewer-agent", default="claude")
    tr.add_argument("--orchestrator-agent", default="claude")
    tr.set_defaults(func=cmd_triple)

    li = sub.add_parser("list", help="list panes in the current session")
    li.add_argument("--session")
    li.set_defaults(func=cmd_list)

    ca = sub.add_parser("capture", help="capture-pane snapshot")
    ca.add_argument("pane")
    ca.add_argument("--lines", type=int, default=100)
    ca.set_defaults(func=cmd_capture)

    return p


def main() -> int:
    if shutil.which("tmux") is None:
        sys.exit("error: tmux not on PATH")
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
