# TypeScript Rules Skeleton

Vorlage für TypeScript-Projekte (Node, Next/Astro/Vite, React, Svelte, etc.). Bootstrap-Agent passt Tooling + Framework projektspezifisch an.

## 1. Style & Format

- `prettier` mit eingecheckter Config (`.prettierrc`). CI bricht bei Diff.
- `eslint` mit eingechecktem Regelset. Pflicht: `--max-warnings 0`.
- `tsconfig.json`: `strict: true`, `noImplicitAny: true`, `noUncheckedIndexedAccess: true`.
- Keine `// eslint-disable-next-line` ohne kurze Begründung.

## 2. Tests

- Test-Runner: vitest oder jest, eingecheckt in package.json.
- Unit-Tests neben dem File (`foo.test.ts` neben `foo.ts`) oder in `__tests__/`.
- Integration/E2E in eigener Suite (`tests/integration`, `e2e/`).
- React/UI: testing-library + Vitest/Jest. Keine Snapshots ohne Begründung (rotten leicht).
- Coverage-Threshold per CI-Gate, nicht nur als Report.

## 3. Architecture & Boundaries

- Module-Struktur: feature-folders bevorzugt. Keine querliegenden util-Müllhalden.
- `import/no-cycles` via eslint aktiv.
- Server-/Client-Split eindeutig (Next: `"use server"`/`"use client"`-Boundaries beachten).
- Public-API eines Packages nur via `index.ts` Barrel; interne Module nicht direkt importieren lassen.
- Externe Dependencies: jede neue Dependency PR-begründet, Bundle-Size beobachten.

## 4. Anti-Patterns

- `any`: BLOCK außer bei dokumentierten unknown-Boundaries (dann `unknown` + Narrowing).
- `as any` Cast: BLOCK.
- `// @ts-ignore` ohne Issue-Link: BLOCK. `@ts-expect-error` ist die ehrlichere Form.
- `JSON.parse(JSON.stringify(...))` Deep-Copies: nur als Workaround mit Comment.
- `useEffect` für Datenfluss der besser via Derived-State ginge.
- `process.env` direkt im Hot-Path lesen statt einmal validieren.
- `console.log` in committed Code (nur in scripts/ erlaubt).

## 5. Naming

- Variablen + Funktionen: `camelCase`.
- Typen + Interfaces + Klassen: `PascalCase`.
- Konstanten: `SCREAMING_SNAKE_CASE` für echte Konstanten, sonst `camelCase`.
- Files: `kebab-case.ts` für Module, `PascalCase.tsx` für React-Komponenten.
- Booleans mit `is`/`has`/`should`-Prefix.

## 6. Security & Privacy

- Inputs an HTTP-/Form-Boundaries via Zod/Valibot validieren.
- Secrets nur via `process.env`, keine im Repo, keine in Client-Bundles (Next: `NEXT_PUBLIC_`-Disziplin).
- Raw-HTML-Injection in React-Komponenten nur via Sanitizer (DOMPurify) oder geprüften Markdown-Renderer.
- Logging: keine PII, keine Tokens, keine Request-Bodies ungefiltert.
- CSP-Header in Production gesetzt.

## 7. Build & Verification

- `pnpm install --frozen-lockfile` (oder npm/yarn-Äquivalent) in CI.
- `pnpm typecheck` (`tsc --noEmit`): clean.
- `pnpm lint`: clean.
- `pnpm test`: alle grün.
- `pnpm build`: erfolgreich.
- E2E nur wenn vom Projekt vorgesehen, klar als eigenes Job.

## 8. Domain (project-specific)

- Zweck des Repos in einem Satz.
- Domain-Vokabular, das ein Reviewer kennen muss.
- Compliance-Anforderungen (DSGVO, Cookies, Tracking).
- Stakeholder-Reviewer für Frontend/Backend/Infra.
