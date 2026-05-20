# Python Rules Skeleton

Template for Python projects. The bootstrap agent adapts tool set, type strictness, and framework specifics.

## 1. Style & Format

- `ruff format` as the formatter, `ruff check` as the linter (checked-in `pyproject.toml`).
- If `black` + `isort` are in place historically, keep them, but prefer ruff for new setups.
- `mypy --strict` or `pyright` in `strict` mode as the default.
- `[tool.ruff.lint]` with `select = ["E", "F", "W", "I", "B", "UP", "RUF"]` as the minimum set.

## 2. Tests

- `pytest` is the standard, config lives in `pyproject.toml` or `pytest.ini`.
- Tests in `tests/`, naming `test_*.py`, functions `test_*`.
- `pytest-cov` with a threshold via `--cov-fail-under`.
- Property tests via `hypothesis` for parsing and data invariants.
- Fixtures in `conftest.py`, no cross-cutting mocks.

## 3. Architecture & Boundaries

- Package layout: `src/<package>/` (src-layout) rather than a flat layout.
- Public API is explicit via `__all__` plus re-exports in the top-level `__init__.py`.
- Imports go at the top of the file; no lazy imports without a performance justification.
- No circular imports (the linter checks this).
- External dependencies: every new dependency requires PR-level justification, `pyproject.toml` with version ranges.

## 4. Anti-Patterns

- `except:` or `except Exception:` without re-raise: BLOCK. Catch a concrete exception.
- Mutable default args (`def foo(x=[])`): BLOCK.
- `from x import *`: BLOCK except in a top-level `__init__.py` for API re-export.
- Global state / singletons via module-level variables: only with justification.
- `print()` in committed code (scripts only). Otherwise use `logging`.
- Ignoring type hints (`# type: ignore` without justification): BLOCK.

## 5. Naming

- Functions, variables, modules: `snake_case`.
- Classes and type aliases: `PascalCase`.
- Constants: `SCREAMING_SNAKE_CASE`.
- Private members with a `_prefix`, "really private" with `__name` (only for the name-mangling use case).
- Files: `snake_case.py`.

## 6. Security & Privacy

- Secrets via env / Vault, never in the repo.
- Input validation via `pydantic` (v2) at HTTP/CLI boundaries.
- SQL: parameterized queries are mandatory, no string interpolation in queries.
- Unsafe deserialization (such as `yaml.load` without SafeLoader, arbitrary `eval`, or other code-loading formats) on user input: BLOCK. Only safe, documented formats (JSON, msgpack, vetted YAML SafeLoader).
- Logging: PII filter, no tokens, no unfiltered request bodies.

## 7. Build & Verification

- `uv sync` or `poetry install --sync` for reproducible installs.
- `ruff check`: clean.
- `ruff format --check`: clean.
- `mypy` / `pyright`: clean.
- `pytest`: all green.
- Optional: `bandit`, `pip-audit` in CI.

## 8. Domain (project-specific)

- Purpose of the repo in one sentence.
- Domain vocabulary.
- Compliance requirements.
- Stakeholder reviewers.
