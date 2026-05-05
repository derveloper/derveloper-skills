---
name: gepa
description: >
  This skill should be used when the user asks about GEPA, prompt optimization,
  or text artifact evolution. Typical triggers: "optimize a prompt", "improve a
  system prompt", "tune a prompt with GEPA", "run GEPA optimization", "evolve a
  prompt", "optimize anything with LLMs", "create a GEPA evaluator",
  "optimize MCP tool descriptions", "optimize RAG", "set up GEPA",
  "auto-tune my prompt". Implements the GEPA algorithm natively in Claude Code
  without external LLM API keys. Claude Code acts as the reflection and
  mutation engine.
---

# GEPA: Text Artifact Optimization in Claude Code

GEPA (Genetic-Pareto) optimizes any text artifact (prompts, code, configs, agent architectures, tool descriptions) through evolutionary search guided by LLM reflection. This skill implements the GEPA loop natively: Claude Code acts as the reflection and mutation engine. No external LLM API keys needed.

Paper: arXiv:2507.19457 | Repo: github.com/gepa-ai/gepa

## Core Concept

The GEPA cycle: **Select** candidate from Pareto frontier -> **Execute** evaluator, capture traces -> **Reflect** on traces (Claude Code reads diagnostics, diagnoses failures) -> **Mutate** (Claude Code generates improved candidate) -> **Accept** if score improved.

The key insight: optimization quality depends on **evaluator feedback quality**, not model size. Rich diagnostic output ("Test 3 failed: expected 42, got -1, division by zero at line 8") gives Claude Code enough signal to propose targeted fixes. Generic "score: 0.3" does not.

## Architecture

```
User provides:          Claude Code does:           Script manages:
  - seed artifact         - reads traces              - candidate pool
  - evaluator script      - diagnoses failures        - Pareto frontier
  - objective             - generates mutations       - score history
                          - decides when to stop      - state persistence
```

`scripts/gepa-loop.py` manages optimization state (candidates, scores, traces, Pareto frontier) as JSON. No pip install required, pure stdlib Python.

## Workflow

### 1. Setup

Create three files:

**Seed candidate** (`seed.txt`): The starting text artifact to optimize.

**Evaluator script** (`eval.sh`): Takes candidate file path as `$1`, prints diagnostic lines to stdout, prints numeric score as **last line**. Exit 0. All output lines before the score become traces that Claude Code reads for reflection.

```bash
#!/usr/bin/env bash
CANDIDATE="$1"
# Run tests, capture diagnostics
python3 run_tests.py --prompt-file "$CANDIDATE" 2>&1
# Last line MUST be the numeric score
echo "0.73"
```

**Objective**: Natural language description of what "better" means.

### 2. Initialize

```bash
python3 scripts/gepa-loop.py init \
  --state /tmp/gepa-run.json \
  --seed seed.txt \
  --objective "Maximize accuracy on math word problems while keeping responses under 200 tokens"
```

### 3. Evaluate

```bash
python3 scripts/gepa-loop.py eval \
  --state /tmp/gepa-run.json \
  --evaluator ./eval.sh
```

Runs the evaluator against the current candidate. Captures score + diagnostic traces.

### 4. Reflect + Mutate

Read traces, then generate an improved candidate:

```bash
python3 scripts/gepa-loop.py traces --state /tmp/gepa-run.json --last 3
```

Claude Code reads the traces, diagnoses what went wrong, and writes an improved candidate. Key reflection questions:

- What specific failures occurred? (read trace lines)
- What pattern connects the failures?
- What targeted change would fix the most failures without breaking passing cases?

Write the mutation to a file, then register it:

```bash
python3 scripts/gepa-loop.py mutate \
  --state /tmp/gepa-run.json \
  --candidate /tmp/gepa-mutation.txt
```

### 5. Loop

Repeat steps 3-4. Check progress:

```bash
python3 scripts/gepa-loop.py status --state /tmp/gepa-run.json
```

### 6. Export

```bash
python3 scripts/gepa-loop.py export \
  --state /tmp/gepa-run.json \
  --output optimized.txt
```

## gepa-loop.py Commands

| Command | Purpose |
|---------|---------|
| `init` | Create state file with seed candidate and objective |
| `eval` | Run evaluator, capture score + traces |
| `mutate` | Register a new candidate (written by Claude Code) |
| `status` | Show scores, frontier, convergence |
| `traces` | Print traces for Claude Code to reflect on |
| `export` | Write best candidate to file |

Full CLI docs: `python3 scripts/gepa-loop.py --help`

## Evaluator Design

The evaluator is the most important component. Its diagnostic output directly determines optimization quality.

**Contract**: Receives candidate file path as `$1`. Prints diagnostic lines. Last line is the numeric score (float).

```bash
#!/usr/bin/env bash
# Good: specific, actionable diagnostics
echo "PASS test_basic_arithmetic: 2+2=4"
echo "FAIL test_word_problem: expected 42, got 'I cannot solve this'"
echo "FAIL test_fractions: division by zero in step 3"
echo "PASS test_geometry: correct area calculation"
echo "0.50"
```

Python evaluators work the same way:

```python
#!/usr/bin/env python3
import sys
candidate_text = open(sys.argv[1]).read()
# ... run tests, print diagnostics ...
print(f"PASS basic: correct")
print(f"FAIL edge_case: expected X, got Y because Z")
print(f"{passed / total:.4f}")
```

**Anti-pattern**: Evaluators that only print a score. Without traces, Claude Code has nothing to reflect on and mutations become random guessing.

## Reflection Protocol

When performing the reflect step, follow this structure:

1. **Read traces** via `gepa-loop.py traces --last 3`
2. **Identify failure pattern**: What do failing test cases have in common?
3. **Diagnose root cause**: Why does the current candidate produce these failures?
4. **Propose targeted fix**: Minimal change that addresses the root cause
5. **Write mutation**: Preserve what works, fix what fails
6. **Avoid regression**: Check that the fix won't break passing test cases

## Stopping Criteria

Stop the loop when any of these conditions hold:

- Score plateau (no improvement for 3+ iterations)
- Target score reached (user-defined threshold)
- Budget exhausted (user-defined max iterations)
- Diminishing returns (improvements < 0.01 per iteration)

## Common Optimization Targets

| Target | Seed | Evaluator tests |
|--------|------|-----------------|
| System prompt | Plain instruction text | Run prompt against test cases, check output quality |
| Code template | Starter code / skeleton | Run test suite, check pass rate + error messages |
| Config file | Default config | Run system with config, measure performance metrics |
| Agent instructions | Step-by-step procedure | Run agent on benchmark tasks, score outcomes |
| MCP tool description | Current description | Test tool selection accuracy across queries |
| CLAUDE.md rules | Current instructions | Test Claude Code behavior on sample tasks |

## Additional Resources

### Reference Files

- **`references/patterns.md`** — Evaluator design patterns, feedback quality, multi-objective optimization, troubleshooting
- **`references/gepa-library.md`** — Using the `gepa` Python library with external API keys (advanced, for users who have LLM API access)

### Scripts

- **`scripts/gepa-loop.py`** — State manager for the optimization loop (no dependencies, stdlib Python)
- **`scripts/validate-gepa-setup.sh`** — Check gepa library installation (only needed for library mode)

### External

- Paper: arXiv:2507.19457
- Repo: github.com/gepa-ai/gepa
- Docs: gepa-ai.github.io/gepa/
