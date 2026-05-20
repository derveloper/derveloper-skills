# Generic Rules Skeleton

Language-agnostic template. During bootstrap the `rules-bootstrap` agent fills in each section per project, based on repo recon plus user answers.

The eight sections are the mandatory topics every reviewer-readiness check requires. The order is fixed because the checklist iterates through them in this order.

## 1. Style & Format

- Which formatter is mandatory? (tool + version + config file)
- Which linter blocks merges? (tool + rule set)
- Which style conventions are required (indentation, line length, quotes)?
- Pre-commit hooks or CI gate?

## 2. Tests

- Which test framework and runner?
- What is the coverage expectation (required threshold, excluded paths)?
- Which test types are in scope (unit, integration, E2E)?
- Naming convention for tests (file, function)?
- When may a test be ignored/skipped, and what justification is required?

## 3. Architecture & Boundaries

- Which modules/crates/packages are the structural units?
- Which layers exist and which imports are allowed/forbidden?
- Which external dependencies require approval?
- Where do public-API boundaries lie, and where are breaking changes forbidden?

## 4. Anti-Patterns

- Concrete patterns rejected in this repo, with justification.
- Examples from past incidents or PR reviews if available.
- No double standard with "sometimes ok": anti-patterns are absolute.

## 5. Naming

- Convention for functions, types, files, variables.
- Domain-specific terms and their spelling (for example, tool name always lowercase).
- Abbreviations that are acceptable and which are off-limits.

## 6. Security & Privacy

- How are secrets handled (env, vault, NEVER in the repo)?
- Required input validation at system boundaries.
- PII and logging discipline.
- Known sensitive paths that must never leak outside.

## 7. Build & Verification

- Which build command is canonical?
- Which test suite runs pre-merge?
- Which lints/checks are blockers and which are advisory?
- CI pipeline stages and their gates.

## 8. Domain (project-specific)

- What is the purpose of this repo in one sentence?
- Which domain terms must a new reviewer know?
- Which compliance or regulation applies to the code (for example GDPR, NIS2, industry-specific)?
- Which stakeholders review which areas?
