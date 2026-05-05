# GEPA Optimization Patterns

## Evaluator Design

### Principle: Traces Over Scores

GEPA's advantage over trial-and-error comes from diagnostic traces that the reflection step reads. The evaluator's stdout lines (all except the last) are the "gradients" of text optimization. Invest in rich, specific diagnostic output.

### Pattern: Test Suite Evaluator

```bash
#!/usr/bin/env bash
CANDIDATE="$1"
PASS=0; FAIL=0; TOTAL=0

run_test() {
    local name="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [ "$expected" = "$actual" ]; then
        echo "PASS $name"
        PASS=$((PASS + 1))
    else
        echo "FAIL $name: expected '$expected', got '$actual'"
        FAIL=$((FAIL + 1))
    fi
}

# Run tests against the candidate
RESULT=$(python3 run_with_prompt.py "$CANDIDATE" "What is 2+2?")
run_test "basic_arithmetic" "4" "$RESULT"

RESULT=$(python3 run_with_prompt.py "$CANDIDATE" "Solve: 3x + 7 = 22")
run_test "linear_equation" "5" "$RESULT"

# Score as last line
echo "scale=4; $PASS / $TOTAL" | bc
```

### Pattern: Python Evaluator with Detailed Diagnostics

```python
#!/usr/bin/env python3
import sys

candidate = open(sys.argv[1]).read()
tests = load_test_cases()
passed = 0

for test in tests:
    result = run_system(candidate, test.input)
    if matches(result, test.expected):
        print(f"PASS {test.name}")
        passed += 1
    else:
        # Detailed failure info: what, why, context
        print(f"FAIL {test.name}: expected '{test.expected}', got '{result}'")
        if result.error:
            print(f"  ERROR: {result.error}")
        if result.reasoning:
            print(f"  REASONING: {result.reasoning[:200]}")

print(f"{passed / len(tests):.4f}")
```

### Pattern: Multi-Aspect Evaluation

```bash
#!/usr/bin/env bash
CANDIDATE="$1"

# Aspect 1: Correctness
CORRECT=$(python3 test_correctness.py "$CANDIDATE")
echo "Correctness: $CORRECT/10 tests passed"

# Aspect 2: Conciseness
TOKENS=$(wc -w < "$CANDIDATE")
echo "Candidate length: $TOKENS words"
if [ "$TOKENS" -gt 500 ]; then
    echo "WARNING: candidate exceeds 500 word budget"
fi

# Aspect 3: Format compliance
if grep -q "Step 1:" "$CANDIDATE"; then
    echo "Format: structured (has numbered steps)"
else
    echo "Format: unstructured (missing numbered steps)"
fi

# Combined score (primary metric)
echo "0.73"
```

### Anti-Pattern: Score-Only Evaluator

```bash
# BAD: no diagnostic output, Claude Code can't reflect
#!/usr/bin/env bash
python3 run_tests.py "$1" | tail -1
```

Without traces, mutations become random guessing. Always print diagnostic lines before the score.

## Reflection Patterns

### Pattern: Failure Clustering

When reflecting on traces, group failures by type:

- **Same error message** across tests -> systemic issue in the candidate
- **Same test category** fails -> missing capability (e.g., all math tests fail)
- **Regression from parent** -> last mutation introduced a problem

### Pattern: Minimal Mutation

Prefer small, targeted changes over rewrites. If 7/10 tests pass, changing the entire candidate risks breaking those 7. Instead:

1. Identify the 3 failing tests
2. Find what they have in common
3. Add or modify the minimal section that addresses the failure pattern
4. Verify the fix doesn't contradict passing test logic

### Pattern: Pareto-Aware Mutation

When the frontier has multiple candidates excelling on different test subsets:

1. Read traces from two Pareto candidates
2. Identify which tests each handles well
3. Merge strengths: take the section from candidate A that handles test group X, combine with candidate B's approach for test group Y

## Dataset Design

### Minimum Viable Test Set

The optimization works with as few as 3 test cases. For production quality:

- 10-20 tests covering core behaviors
- Edge cases and failure modes included
- Tests should be deterministic (same input = same output)

### Test Case Quality Checklist

- Does each test have a clear expected output?
- Are failure messages specific enough to diagnose the problem?
- Do tests cover different aspects of the optimization objective?
- Are there adversarial or edge cases?

## Budget Planning

| Scenario | Iterations | Rationale |
|----------|-----------|-----------|
| Quick experiment | 5-10 | Fast directional signal |
| Standard optimization | 15-30 | Good quality with targeted mutations |
| Thorough optimization | 30-50 | Full exploration, multiple mutation strategies |

With Claude Code as the reflection engine, each iteration involves reading traces + generating one mutation. Quality per iteration is high, so fewer iterations are needed compared to automated GEPA.

## Common Optimization Targets

### System Prompt

Seed: Plain instruction text. Evaluator: Run prompt against test inputs via API or local model, compare outputs.

### Code Templates

Seed: Starter code or skeleton. Evaluator: Run test suite, report pass/fail per test with error messages.

### Config Files

Seed: Default configuration. Evaluator: Run system with config, measure performance metrics, report per-metric scores.

### CLAUDE.md Instructions

Seed: Current project instructions. Evaluator: Run Claude Code on sample tasks, score output quality. This is meta-optimization: using GEPA to optimize the instructions that guide Claude Code itself.

### MCP Tool Descriptions

Seed: Current tool description text. Evaluator: Present tool options to a model, measure tool selection accuracy across diverse queries.

## Troubleshooting

### Score Not Improving

- Check evaluator trace quality (most common issue). Are failure messages specific?
- Try a different mutation strategy (rewrite section vs. add constraint vs. restructure)
- Examine if the seed is fundamentally wrong (sometimes start over with a different approach)

### Oscillating Scores

- Mutations are too aggressive, breaking passing tests. Use minimal mutations.
- Test set has contradictory requirements. Review and clean test cases.

### Regression After Mutation

- Read traces from both parent and child candidate
- Identify what the mutation broke
- Revert the breaking change, keep any improvements
- Try a more targeted mutation that preserves the parent's strengths
