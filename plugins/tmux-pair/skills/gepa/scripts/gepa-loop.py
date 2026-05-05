#!/usr/bin/env python3
"""GEPA optimization loop state manager for Claude Code.

Claude Code acts as the reflection/mutation LLM. This script handles:
- Candidate pool and Pareto frontier tracking
- Evaluator execution and trace collection
- State persistence (JSON) across iterations
- Score reporting and convergence detection

Usage:
    # Initialize a new optimization run
    python gepa-loop.py init --state run.json --seed seed.txt --objective "..."

    # Evaluate current candidate with a test script
    python gepa-loop.py eval --state run.json --evaluator ./eval.sh

    # Record a new mutated candidate (Claude provides the text)
    python gepa-loop.py mutate --state run.json --candidate new.txt

    # Show current status (best score, frontier size, history)
    python gepa-loop.py status --state run.json

    # Export best candidate to file
    python gepa-loop.py export --state run.json --output best.txt

    # Show full traces for reflection (Claude reads this)
    python gepa-loop.py traces --state run.json [--last N]
"""

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


def init(args):
    seed_text = Path(args.seed).read_text().strip()
    state = {
        "objective": args.objective,
        "created": datetime.now().isoformat(),
        "iteration": 0,
        "candidates": [
            {
                "id": 0,
                "text": seed_text,
                "score": None,
                "traces": [],
                "parent": None,
                "generation": 0,
            }
        ],
        "pareto_frontier": [],
        "best_id": None,
        "best_score": None,
        "history": [],
    }
    Path(args.state).write_text(json.dumps(state, indent=2, ensure_ascii=False))
    print(f"Initialized optimization run: {args.state}")
    print(f"Seed candidate loaded ({len(seed_text)} chars)")
    print(f"Objective: {args.objective}")


def eval_candidate(args):
    state = json.loads(Path(args.state).read_text())

    # Find candidate to evaluate (latest unevaluated, or specific ID)
    cid = args.candidate_id
    if cid is None:
        unevaluated = [c for c in state["candidates"] if c["score"] is None]
        if not unevaluated:
            print("ERROR: No unevaluated candidates. Run 'mutate' first.")
            sys.exit(1)
        candidate = unevaluated[-1]
    else:
        matches = [c for c in state["candidates"] if c["id"] == cid]
        if not matches:
            print(f"ERROR: Candidate {cid} not found.")
            sys.exit(1)
        candidate = matches[0]

    # Write candidate to temp file for evaluator
    tmp = Path(f"/tmp/gepa-candidate-{candidate['id']}.txt")
    tmp.write_text(candidate["text"])

    # Run evaluator script
    print(f"Evaluating candidate {candidate['id']}...")
    try:
        result = subprocess.run(
            [args.evaluator, str(tmp)],
            capture_output=True,
            text=True,
            timeout=args.timeout,
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        returncode = result.returncode
    except subprocess.TimeoutExpired:
        stdout = ""
        stderr = "TIMEOUT"
        returncode = -1
    except FileNotFoundError:
        print(f"ERROR: Evaluator not found: {args.evaluator}")
        sys.exit(1)

    # Parse score from last line of stdout (expected: float)
    score = 0.0
    traces = []
    if stdout:
        lines = stdout.split("\n")
        # Last line should be the numeric score
        try:
            score = float(lines[-1].strip())
            traces = lines[:-1]  # Everything else is trace/diagnostic output
        except ValueError:
            traces = lines
            print(f"WARNING: Could not parse score from last line: '{lines[-1]}'")
    if stderr:
        traces.append(f"STDERR: {stderr}")

    # Update candidate
    candidate["score"] = score
    candidate["traces"] = traces

    # Update Pareto frontier (simplified: single-objective, keep top candidates)
    scored = [c for c in state["candidates"] if c["score"] is not None]
    scored.sort(key=lambda c: c["score"], reverse=True)
    state["pareto_frontier"] = [c["id"] for c in scored[:5]]

    # Update best
    if state["best_score"] is None or score > state["best_score"]:
        state["best_id"] = candidate["id"]
        state["best_score"] = score
        improved = True
    else:
        improved = False

    state["iteration"] += 1
    state["history"].append(
        {
            "iteration": state["iteration"],
            "candidate_id": candidate["id"],
            "score": score,
            "improved": improved,
            "timestamp": datetime.now().isoformat(),
        }
    )

    Path(args.state).write_text(json.dumps(state, indent=2, ensure_ascii=False))
    tmp.unlink(missing_ok=True)

    print(f"Score: {score}")
    if improved:
        print(f"NEW BEST (previous: {state['history'][-2]['score'] if len(state['history']) > 1 else 'none'})")
    print(f"Iteration: {state['iteration']}")
    print(f"--- Traces ---")
    for t in traces:
        print(t)


def mutate(args):
    state = json.loads(Path(args.state).read_text())
    new_text = Path(args.candidate).read_text().strip()

    parent_id = args.parent
    if parent_id is None:
        # Default: mutate from best candidate
        parent_id = state["best_id"]
        if parent_id is None:
            parent_id = 0

    parent = next((c for c in state["candidates"] if c["id"] == parent_id), None)
    parent_gen = parent["generation"] if parent else 0

    new_id = max(c["id"] for c in state["candidates"]) + 1
    state["candidates"].append(
        {
            "id": new_id,
            "text": new_text,
            "score": None,
            "traces": [],
            "parent": parent_id,
            "generation": parent_gen + 1,
        }
    )

    Path(args.state).write_text(json.dumps(state, indent=2, ensure_ascii=False))
    print(f"Added candidate {new_id} (parent: {parent_id}, gen: {parent_gen + 1})")
    print(f"Pending evaluation. Run 'eval' next.")


def status(args):
    state = json.loads(Path(args.state).read_text())
    total = len(state["candidates"])
    evaluated = sum(1 for c in state["candidates"] if c["score"] is not None)
    pending = total - evaluated

    print(f"Objective: {state['objective']}")
    print(f"Iterations: {state['iteration']}")
    print(f"Candidates: {total} ({evaluated} evaluated, {pending} pending)")
    print(f"Best score: {state['best_score']} (candidate {state['best_id']})")
    print(f"Pareto frontier: {state['pareto_frontier']}")

    if state["history"]:
        print(f"\n--- Score History ---")
        for h in state["history"][-10:]:
            marker = " *" if h["improved"] else ""
            print(f"  iter {h['iteration']:3d}: {h['score']:.4f} (cand {h['candidate_id']}){marker}")


def traces(args):
    state = json.loads(Path(args.state).read_text())
    n = args.last or len(state["candidates"])

    scored = [c for c in state["candidates"] if c["score"] is not None]
    scored.sort(key=lambda c: c["id"], reverse=True)

    for c in scored[:n]:
        print(f"=== Candidate {c['id']} (score: {c['score']}, gen: {c['generation']}, parent: {c['parent']}) ===")
        print(f"--- Text ---")
        print(c["text"][:500])
        if len(c["text"]) > 500:
            print(f"... ({len(c['text'])} chars total)")
        print(f"--- Traces ---")
        for t in c["traces"]:
            print(f"  {t}")
        print()


def export(args):
    state = json.loads(Path(args.state).read_text())
    if args.candidate_id is not None:
        cid = args.candidate_id
    else:
        cid = state["best_id"]

    if cid is None:
        print("ERROR: No best candidate yet. Run eval first.")
        sys.exit(1)

    candidate = next((c for c in state["candidates"] if c["id"] == cid), None)
    if not candidate:
        print(f"ERROR: Candidate {cid} not found.")
        sys.exit(1)

    Path(args.output).write_text(candidate["text"])
    print(f"Exported candidate {cid} (score: {candidate['score']}) to {args.output}")


def main():
    parser = argparse.ArgumentParser(description="GEPA optimization loop for Claude Code")
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="Initialize optimization run")
    p_init.add_argument("--state", required=True, help="State file path (JSON)")
    p_init.add_argument("--seed", required=True, help="Seed candidate file")
    p_init.add_argument("--objective", required=True, help="Optimization objective")

    p_eval = sub.add_parser("eval", help="Evaluate a candidate")
    p_eval.add_argument("--state", required=True)
    p_eval.add_argument("--evaluator", required=True, help="Evaluator script path")
    p_eval.add_argument("--candidate-id", type=int, default=None)
    p_eval.add_argument("--timeout", type=int, default=120)

    p_mut = sub.add_parser("mutate", help="Add a mutated candidate")
    p_mut.add_argument("--state", required=True)
    p_mut.add_argument("--candidate", required=True, help="New candidate file")
    p_mut.add_argument("--parent", type=int, default=None)

    p_status = sub.add_parser("status", help="Show optimization status")
    p_status.add_argument("--state", required=True)

    p_traces = sub.add_parser("traces", help="Show evaluation traces for reflection")
    p_traces.add_argument("--state", required=True)
    p_traces.add_argument("--last", type=int, default=None, help="Show last N candidates")

    p_export = sub.add_parser("export", help="Export best candidate")
    p_export.add_argument("--state", required=True)
    p_export.add_argument("--output", required=True)
    p_export.add_argument("--candidate-id", type=int, default=None)

    args = parser.parse_args()
    {
        "init": init,
        "eval": eval_candidate,
        "mutate": mutate,
        "status": status,
        "traces": traces,
        "export": export,
    }[args.command](args)


if __name__ == "__main__":
    main()
