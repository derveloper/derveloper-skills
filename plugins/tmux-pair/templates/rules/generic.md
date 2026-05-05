# Generic Rules Skeleton

Sprachunabhängige Vorlage. Beim Bootstrap füllt der `rules-bootstrap`-Agent jeden Abschnitt projektspezifisch aus, basierend auf Repo-Recon + User-Antworten.

Die acht Abschnitte sind die Pflicht-Topics, die jeder Reviewer-Readiness-Check fordert. Reihenfolge fest, weil die Checkliste sie in dieser Reihenfolge prüft.

## 1. Style & Format

- Welcher Formatter ist verbindlich? (Tool + Version + Konfig-Datei)
- Welcher Linter blockiert Merges? (Tool + Regelset)
- Welche Stilkonventionen sind Pflicht (Indentation, Zeilenlänge, Quotes)?
- Pre-commit Hooks oder CI-Gate?

## 2. Tests

- Welches Test-Framework und welcher Runner?
- Welcher Coverage-Anspruch (Pflicht-Schwelle, exkludierte Pfade)?
- Welche Test-Typen sind vorgesehen (Unit, Integration, E2E)?
- Naming-Konvention für Tests (Datei, Funktion)?
- Wann darf ein Test ignoriert/skipped werden, mit welcher Begründungspflicht?

## 3. Architecture & Boundaries

- Welche Module/Crates/Packages sind die strukturellen Einheiten?
- Welche Layer existieren und welche Imports sind erlaubt/verboten?
- Welche externen Abhängigkeiten brauchen Approval?
- Wo liegen Public-API-Grenzen, wo sind Breaking Changes verboten?

## 4. Anti-Patterns

- Konkrete Patterns die in diesem Repo abgelehnt werden, mit Begründung.
- Beispiele aus früheren Incidents oder PR-Reviews wenn vorhanden.
- Kein Doppel-Standard mit "manchmal ok": Anti-Patterns sind absolut.

## 5. Naming

- Konvention für Funktionen, Typen, Files, Variablen.
- Domain-spezifische Begriffe und ihre Schreibweise (z.B. tool-Name immer klein).
- Abkürzungen die ok sind und welche tabu.

## 6. Security & Privacy

- Wie werden Secrets gehandhabt (env, vault, NIE im Repo)?
- Input-Validation-Pflichten an System-Boundaries.
- PII/Logging-Disziplin.
- Bekannte sensitive Pfade die nie nach außen dürfen.

## 7. Build & Verification

- Welcher Build-Befehl ist kanonisch?
- Welche Test-Suite läuft pre-merge?
- Welche Lints/Checks sind blocker, welche advisory?
- CI-Pipeline-Stages und ihre Gates.

## 8. Domain (project-specific)

- Was ist der Zweck dieses Repos in einem Satz?
- Welche Domain-Begriffe muss ein neuer Reviewer kennen?
- Welche Compliance/Regulierung trifft den Code (z.B. DSGVO, NIS2, branchenspezifisch)?
- Welche Stakeholder reviewen welche Bereiche?
