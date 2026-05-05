# GEPA Python Library (External API Keys)

This reference covers using the `gepa` pip package directly. Requires LLM API keys (OpenAI, Anthropic, or other LiteLLM-compatible providers). For the Claude Code-native approach without API keys, see the main SKILL.md.

## Installation

```bash
pip install gepa          # stable
pip install gepa[full]    # all optional deps (DSPy, wandb, mlflow)
```

Set API keys:
```bash
export OPENAI_API_KEY="sk-..."
# or
export ANTHROPIC_API_KEY="sk-ant-..."
```

## gepa.optimize() — Prompt Optimization

```python
import gepa

trainset = [
    {"question": "What is 2+2?", "answer": "4"},
    {"question": "Capital of France?", "answer": "Paris"},
]

result = gepa.optimize(
    seed_candidate={"system_prompt": "Answer concisely."},
    trainset=trainset,
    task_lm="openai/gpt-4o-mini",
    reflection_lm="openai/gpt-4o",
    max_metric_calls=50,
)
print(result.best_candidate["system_prompt"])
print(result.best_score)
```

Parameters:
- `seed_candidate`: dict with text fields to optimize
- `trainset` / `valset`: list of input-output dicts
- `task_lm`: LiteLLM model ID for task execution
- `reflection_lm`: LiteLLM model ID for reflection (use stronger model here)
- `max_metric_calls`: evaluation budget (50 = quick, 150-500 = production)

## optimize_anything() — Universal Optimization

```python
import gepa.optimize_anything as oa
from gepa.optimize_anything import optimize_anything, GEPAConfig, EngineConfig

def evaluate(candidate: str) -> float:
    result = run_my_system(candidate)
    oa.log(f"Output: {result.output}")
    oa.log(f"Error: {result.error}")
    return result.score

result = optimize_anything(
    seed_candidate="<initial artifact>",
    evaluator=evaluate,
    objective="Describe optimization goal.",
    config=GEPAConfig(engine=EngineConfig(max_metric_calls=100)),
)
```

`oa.log()` calls become Actionable Side Information (ASI) that the reflection LLM reads.

## dspy.GEPA — DSPy Pipeline Optimization

```python
import dspy

def metric_with_feedback(example, pred, trace=None):
    correct = example.answer.lower() in pred.answer.lower()
    feedback = f"Correct" if correct else f"Expected {example.answer}, got {pred.answer}"
    return dspy.Prediction(score=1.0 if correct else 0.0, feedback=feedback)

optimizer = dspy.GEPA(
    metric=metric_with_feedback,
    reflection_lm=dspy.LM("openai/gpt-4o"),
    auto="light",
    num_threads=8,
)
optimized = optimizer.compile(MyProgram(), trainset=trainset)
```

Metrics MUST return `dspy.Prediction(score=..., feedback=...)`. Plain scalar metrics disable the reflection advantage.

## Built-in Adapters

| Adapter | Use Case |
|---------|----------|
| DefaultAdapter | Single-turn system prompt (used by `gepa.optimize()`) |
| DSPyFullProgramAdapter | Full DSPy program evolution (used by `dspy.GEPA`) |
| GenericRAGAdapter | RAG pipeline (Chroma, Weaviate, Qdrant, Pinecone) |
| MCPAdapter | MCP tool description optimization |
| TerminalBenchAdapter | Terminal agent refinement |
| AnyMathsAdapter | Math reasoning tasks |

## Configuration

```python
from gepa import MaxMetricCallsStopper, TimeoutStopCondition, NoImprovementStopper

result = gepa.optimize(
    max_metric_calls=100,
    candidate_selection_strategy="pareto",  # or "current_best", "epsilon_greedy"
    stop_callbacks=[
        TimeoutStopCondition(seconds=3600),
        NoImprovementStopper(patience=10),
    ],
    use_wandb=True,
    run_dir="./gepa_runs/my_exp",
)
```

## GEPAResult

```python
result.best_candidate    # dict of optimized text
result.best_score        # float
result.pareto_frontier   # list of Pareto-optimal candidates
result.history           # full optimization trajectory
```

## Model Specification

GEPA uses LiteLLM identifiers:
```
openai/gpt-4o-mini          anthropic/claude-sonnet-4-20250514
openai/gpt-4o               anthropic/claude-haiku-4-20250514
openai/gpt-5                together_ai/meta-llama/...
```
