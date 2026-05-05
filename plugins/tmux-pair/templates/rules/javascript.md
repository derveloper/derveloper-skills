# JavaScript Rules Skeleton

Vorlage für plain-JS-Projekte (Node-Scripts, Browser-Code ohne TypeScript). Wenn TypeScript verfügbar ist, lieber `typescript.md` als Basis.

## 1. Style & Format

- `prettier` als Formatter mit eingecheckter Config.
- `eslint` mit eingechecktem Regelset; CI: `--max-warnings 0`.
- ECMAScript-Modules (`import`/`export`), CommonJS nur wenn Legacy.
- Keine `// eslint-disable-...` ohne Begründung.

## 2. Tests

- Test-Runner: vitest / jest / node:test, eingecheckt.
- Tests neben File (`foo.test.js`) oder in `__tests__/`.
- Coverage-Threshold im CI-Gate.

## 3. Architecture & Boundaries

- Feature-Folder-Layout statt querliegender Util-Müllhalden.
- ESM-Imports stabil, keine zyklischen Importe (`import/no-cycles`).
- Public-API per Barrel-File (`index.js`).
- Externe Dependencies PR-begründet, Bundle-Size beobachten.

## 4. Anti-Patterns

- `var`: BLOCK. `let`/`const` Pflicht.
- `==`: BLOCK. `===` immer (außer `null`-Check `== null`).
- Implicit Globals: BLOCK. `'use strict'` oder ESM-Module.
- `eval` / `Function(...)`-Compile: BLOCK.
- `console.log` in committed Code (nur Scripts).
- Sync-IO im Hot-Path (`fs.readFileSync`, etc.) ohne Begründung.

## 5. Naming

- Variablen + Funktionen: `camelCase`.
- Klassen: `PascalCase`.
- Konstanten: `SCREAMING_SNAKE_CASE` für echte Konstanten.
- Files: `kebab-case.js`.
- Booleans mit `is`/`has`/`should`-Prefix.

## 6. Security & Privacy

- Inputs an HTTP-/Form-Boundaries validieren (Zod/Joi/Hand-Validator).
- Secrets via `process.env`, nicht im Repo, nicht im Client-Bundle.
- Raw-HTML-Injection nur via Sanitizer (DOMPurify) oder Markdown-Renderer mit Safe-Mode.
- Logging: keine PII / Tokens / Bodies ungefiltert.
- CSP-Header in Production gesetzt.

## 7. Build & Verification

- `npm install` / `pnpm install --frozen-lockfile`.
- `eslint .`: clean.
- `prettier --check`: clean.
- `npm test`: alle grün.
- Optional: `npm audit`, `osv-scanner` in CI.

## 8. Domain (project-specific)

- Zweck des Repos in einem Satz.
- Domain-Vokabular.
- Compliance-Anforderungen.
- Stakeholder-Reviewer.
