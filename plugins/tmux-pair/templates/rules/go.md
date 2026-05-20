# Go Rules Skeleton

Template for Go projects. The bootstrap agent adapts toolchain version, module layout, and framework.

## 1. Style & Format

- `gofmt`/`goimports` is mandatory, CI fails on any diff.
- `golangci-lint run` with a checked-in `.golangci.yml` as the linter gate.
- Minimum linters: `errcheck`, `govet`, `staticcheck`, `gosimple`, `unused`, `gosec`.
- Go toolchain version pinned in `go.mod`; do not bump without a plan.

## 2. Tests

- Standard test tooling: `go test ./...`.
- Tests live next to the file (`foo_test.go` next to `foo.go`).
- Prefer table-driven tests with clear sub-tests via `t.Run`.
- Coverage via `go test -coverprofile=...`, threshold enforced by the CI gate.
- Use `t.Parallel()` where possible; race detector in CI (`go test -race`).

## 3. Architecture & Boundaries

- Module layout: one module per repo. `cmd/<binary>/main.go` for binaries, `internal/` for non-API packages.
- Public API is only what lives under `pkg/` or the top level; everything else goes into `internal/`.
- No circular imports (the compiler prevents it, but keep the architecture clean).
- External dependencies: every new one requires a PR-level justification, `go.mod` with explicit versions, no `replace` directives outside of local worktrees.

## 4. Anti-Patterns

- `panic` outside of init or genuinely impossible states: BLOCK.
- `interface{}`/`any` as a band-aid instead of a proper type: BLOCK without justification.
- `init()` for magic side effects: BLOCK. Make initialization explicit.
- `time.Now()` / `os.Getenv()` called directly in the hot path instead of through an injected clock/config.
- Global mutable state (package-level vars): only with justification.
- Losing wrapped errors: always use `fmt.Errorf("...: %w", err)`.

## 5. Naming

- Exported identifiers: `UpperCamelCase`.
- Unexported: `lowerCamelCase`.
- Acronyms uppercase (`HTTP`, `URL`, `ID`).
- Receiver names short (1-2 letters), consistent per type.
- Files: `snake_case.go`, tests `<file>_test.go`.

## 6. Security & Privacy

- Secrets via env / Vault, never in the repo.
- Input validation at HTTP boundaries (for example via `validator` or a hand-written parser, no blind JSON decode into a DB struct).
- SQL: `database/sql` with parameters, or `sqlc`/`sqlx`. No string concatenation in queries.
- `crypto/*` is mandatory; never use `math/rand` for crypto.
- Logging: no PII, no tokens.

## 7. Build & Verification

- `go build ./...`: clean.
- `go vet ./...`: clean.
- `golangci-lint run`: clean.
- `go test ./... -race`: all green.
- Optional: `govulncheck`, `gosec` in CI.

## 8. Domain (project-specific)

- Purpose of the repo in one sentence.
- Domain vocabulary.
- Compliance requirements.
- Stakeholder reviewers.
