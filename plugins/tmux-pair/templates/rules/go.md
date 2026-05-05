# Go Rules Skeleton

Vorlage für Go-Projekte. Bootstrap-Agent passt Toolchain-Version, Module-Layout und Framework an.

## 1. Style & Format

- `gofmt`/`goimports` ist verbindlich, CI bricht bei Diff.
- `golangci-lint run` mit eingecheckter `.golangci.yml` als Linter-Gate.
- Mindest-Linters: `errcheck`, `govet`, `staticcheck`, `gosimple`, `unused`, `gosec`.
- Go-Toolchain-Version in `go.mod` festgenagelt; nicht ohne Plan hochziehen.

## 2. Tests

- Standard-Test-Tooling: `go test ./...`.
- Tests neben dem File (`foo_test.go` neben `foo.go`).
- Table-driven Tests bevorzugt, klare Sub-Tests via `t.Run`.
- Coverage via `go test -coverprofile=...`, Threshold im CI-Gate.
- `t.Parallel()` wo möglich; Race-Detector im CI (`go test -race`).

## 3. Architecture & Boundaries

- Module-Layout: ein Modul pro Repo. `cmd/<binary>/main.go` für Binaries, `internal/` für nicht-API-Pakete.
- Public-API nur was unter `pkg/` oder Top-Level liegt; alles andere `internal/`.
- Keine zirkulären Importe (Compiler verhindert, aber Architektur sauber halten).
- Externe Dependencies: jede neue PR-begründet, `go.mod` mit klaren Versionen, kein `replace` außer für lokale Worktrees.

## 4. Anti-Patterns

- `panic` außerhalb von init / wirklich-impossible-states: BLOCK.
- `interface{}`/`any` als Pflasterlösung statt richtigem Typ: BLOCK ohne Begründung.
- `init()` für Magic-Side-Effects: BLOCK. Init explicit machen.
- `time.Now()` / `os.Getenv()` direkt im Hot-Path statt über injizierte Clock/Config.
- Globale Mutable State (Package-Level-Vars): nur mit Begründung.
- Error wrappen verlieren: immer `fmt.Errorf("...: %w", err)`.

## 5. Naming

- Exportierte Identifier: `UpperCamelCase`.
- Unexportierte: `lowerCamelCase`.
- Acronyme groß (`HTTP`, `URL`, `ID`).
- Receiver-Namen kurz (1-2 Buchstaben), konsistent pro Typ.
- Files: `snake_case.go`, Tests `<file>_test.go`.

## 6. Security & Privacy

- Secrets via env / Vault, nie im Repo.
- Input-Validation an HTTP-Boundaries (z.B. via `validator` oder Hand-Parser, kein blindes JSON-Decode in DB-Struct).
- SQL: `database/sql` mit Parametern oder `sqlc`/`sqlx`. Kein String-Concat in Queries.
- `crypto/*` Pflicht, niemals `math/rand` für Crypto.
- Logging: keine PII, keine Tokens.

## 7. Build & Verification

- `go build ./...`: clean.
- `go vet ./...`: clean.
- `golangci-lint run`: clean.
- `go test ./... -race`: alle grün.
- Optional: `govulncheck`, `gosec` in CI.

## 8. Domain (project-specific)

- Zweck des Repos in einem Satz.
- Domain-Vokabular.
- Compliance-Anforderungen.
- Stakeholder-Reviewer.
