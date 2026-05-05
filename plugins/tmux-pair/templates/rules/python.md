# Python Rules Skeleton

Vorlage für Python-Projekte. Bootstrap-Agent passt Tool-Set, Type-Strictness und Framework-Spezifika an.

## 1. Style & Format

- `ruff format` als Formatter, `ruff check` als Linter (eingecheckte `pyproject.toml`).
- Falls `black` + `isort` historisch: dann diese, aber neu starten lieber mit ruff.
- `mypy --strict` oder `pyright` mit `strict` als Default.
- `[tool.ruff.lint]` mit `select = ["E", "F", "W", "I", "B", "UP", "RUF"]` als Mindest-Set.

## 2. Tests

- `pytest` als Standard, Konfig in `pyproject.toml` oder `pytest.ini`.
- Tests in `tests/`, Naming `test_*.py`, Funktion `test_*`.
- `pytest-cov` mit Threshold via `--cov-fail-under`.
- Property-Tests via `hypothesis` für Parsing/Daten-Invarianten.
- Fixtures in `conftest.py`, keine querliegenden Mocks.

## 3. Architecture & Boundaries

- Package-Layout: `src/<package>/` (src-layout) statt flat layout.
- Public-API explizit via `__all__` + Re-Exports im Top-Level `__init__.py`.
- Imports: nur top-of-file, keine Lazy-Imports außer mit Performance-Begründung.
- Keine zirkulären Imports (Linter prüft).
- Externe Dependencies: jede neue Dependency PR-begründet, `pyproject.toml` mit Version-Ranges.

## 4. Anti-Patterns

- `except:` oder `except Exception:` ohne Re-Raise: BLOCK. Konkrete Exception fangen.
- Mutable Default-Args (`def foo(x=[])`): BLOCK.
- `from x import *`: BLOCK außer in `__init__.py` Top-Level für API-Reexport.
- Globale State / Singletons über Modul-Level-Variablen: nur mit Begründung.
- `print()` in committed Code (nur Scripts erlaubt). Sonst `logging`.
- Type-Hints ignorieren (`# type: ignore` ohne Begründung): BLOCK.

## 5. Naming

- Funktionen, Variablen, Module: `snake_case`.
- Klassen + Type-Aliases: `PascalCase`.
- Konstanten: `SCREAMING_SNAKE_CASE`.
- Private mit `_prefix`, "really private" mit `__name` (nur für Name-Mangling-Use-Case).
- Files: `snake_case.py`.

## 6. Security & Privacy

- Secrets via Env / Vault, nie im Repo.
- Input-Validation via `pydantic` (v2) an HTTP-/CLI-Boundaries.
- SQL: Parameterized Queries Pflicht, kein String-Interpolation in Queries.
- Unsafe Deserialization (z.B. `yaml.load` ohne SafeLoader, beliebige Code-`eval`, andere Code-loadende Formate) auf User-Input: BLOCK. Nur sichere, dokumentierte Formate (JSON, msgpack, geprüfter YAML-SafeLoader).
- Logging: PII-Filter, keine Tokens, keine Bodies ungefiltert.

## 7. Build & Verification

- `uv sync` oder `poetry install --sync` reproducible.
- `ruff check`: clean.
- `ruff format --check`: clean.
- `mypy` / `pyright`: clean.
- `pytest`: alle grün.
- Optional: `bandit`, `pip-audit` in CI.

## 8. Domain (project-specific)

- Zweck des Repos in einem Satz.
- Domain-Vokabular.
- Compliance-Anforderungen.
- Stakeholder-Reviewer.
