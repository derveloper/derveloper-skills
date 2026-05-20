# TypeScript Rules Skeleton

Template for TypeScript projects (Node, Next/Astro/Vite, React, Svelte, and so on). The bootstrap agent adapts tooling and framework per project.

## 1. Style & Format

- `prettier` with a checked-in config (`.prettierrc`). CI fails on any diff.
- `eslint` with a checked-in rule set. Required: `--max-warnings 0`.
- `tsconfig.json`: `strict: true`, `noImplicitAny: true`, `noUncheckedIndexedAccess: true`.
- No `// eslint-disable-next-line` without a short justification.

## 2. Tests

- Test runner: vitest or jest, checked in via package.json.
- Unit tests next to the file (`foo.test.ts` next to `foo.ts`) or in `__tests__/`.
- Integration/E2E in a separate suite (`tests/integration`, `e2e/`).
- React/UI: testing-library plus Vitest/Jest. No snapshots without justification (they rot easily).
- Coverage threshold enforced as a CI gate, not just produced as a report.

## 3. Architecture & Boundaries

- Module structure: feature folders preferred. No sprawling util dumping grounds.
- `import/no-cycles` active in eslint.
- Server/client split unambiguous (Next: respect `"use server"`/`"use client"` boundaries).
- A package's public API only via an `index.ts` barrel; internal modules should not be imported directly.
- External dependencies: every new dependency requires PR-level justification; watch bundle size.

## 4. Anti-Patterns

- `any`: BLOCK except at documented unknown boundaries (then use `unknown` plus narrowing).
- `as any` cast: BLOCK.
- `// @ts-ignore` without an issue link: BLOCK. `@ts-expect-error` is the more honest form.
- `JSON.parse(JSON.stringify(...))` deep copies: only as a workaround with a comment.
- `useEffect` for data flow that would be cleaner via derived state.
- Reading `process.env` directly in the hot path instead of validating it once.
- `console.log` in committed code (only allowed in scripts/).

## 5. Naming

- Variables and functions: `camelCase`.
- Types, interfaces, classes: `PascalCase`.
- Constants: `SCREAMING_SNAKE_CASE` for true constants, otherwise `camelCase`.
- Files: `kebab-case.ts` for modules, `PascalCase.tsx` for React components.
- Booleans with `is`/`has`/`should` prefix.

## 6. Security & Privacy

- Validate inputs at HTTP/form boundaries via Zod/Valibot.
- Secrets only via `process.env`, none in the repo, none in client bundles (Next: respect `NEXT_PUBLIC_` discipline).
- Raw-HTML injection in React components only via a sanitizer (DOMPurify) or a vetted Markdown renderer.
- Logging: no PII, no tokens, no unfiltered request bodies.
- CSP header set in production.

## 7. Build & Verification

- `pnpm install --frozen-lockfile` (or the npm/yarn equivalent) in CI.
- `pnpm typecheck` (`tsc --noEmit`): clean.
- `pnpm lint`: clean.
- `pnpm test`: all green.
- `pnpm build`: succeeds.
- E2E only if the project includes it, run as a separate job.

## 8. Domain (project-specific)

- Purpose of the repo in one sentence.
- Domain vocabulary a reviewer must know.
- Compliance requirements (GDPR, cookies, tracking).
- Stakeholder reviewers for frontend/backend/infra.
