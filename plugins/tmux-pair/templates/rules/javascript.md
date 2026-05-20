# JavaScript Rules Skeleton

Template for plain-JS projects (Node scripts, browser code without TypeScript). If TypeScript is available, prefer `typescript.md` as the base.

## 1. Style & Format

- `prettier` as the formatter with a checked-in config.
- `eslint` with a checked-in rule set; CI: `--max-warnings 0`.
- ECMAScript modules (`import`/`export`); CommonJS only for legacy code.
- No `// eslint-disable-...` without justification.

## 2. Tests

- Test runner: vitest / jest / node:test, checked in.
- Tests next to the file (`foo.test.js`) or under `__tests__/`.
- Coverage threshold enforced as a CI gate.

## 3. Architecture & Boundaries

- Feature-folder layout instead of a sprawling util dumping ground.
- Stable ESM imports, no cyclic imports (`import/no-cycles`).
- Public API via a barrel file (`index.js`).
- External dependencies require PR-level justification; watch bundle size.

## 4. Anti-Patterns

- `var`: BLOCK. `let`/`const` only.
- `==`: BLOCK. Always use `===` (except `== null` for null checks).
- Implicit globals: BLOCK. Use `'use strict'` or ESM modules.
- `eval` / `Function(...)` compile: BLOCK.
- `console.log` in committed code (scripts only).
- Sync IO in the hot path (`fs.readFileSync`, etc.) without justification.

## 5. Naming

- Variables and functions: `camelCase`.
- Classes: `PascalCase`.
- Constants: `SCREAMING_SNAKE_CASE` for true constants.
- Files: `kebab-case.js`.
- Booleans with `is`/`has`/`should` prefix.

## 6. Security & Privacy

- Validate inputs at HTTP/form boundaries (Zod/Joi/hand-written validator).
- Secrets via `process.env`, never in the repo, never in the client bundle.
- Raw-HTML injection only via a sanitizer (DOMPurify) or a Markdown renderer in safe mode.
- Logging: no PII, no tokens, no unfiltered request bodies.
- CSP header set in production.

## 7. Build & Verification

- `npm install` / `pnpm install --frozen-lockfile`.
- `eslint .`: clean.
- `prettier --check`: clean.
- `npm test`: all green.
- Optional: `npm audit`, `osv-scanner` in CI.

## 8. Domain (project-specific)

- Purpose of the repo in one sentence.
- Domain vocabulary.
- Compliance requirements.
- Stakeholder reviewers.
