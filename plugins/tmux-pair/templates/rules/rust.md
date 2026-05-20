# Rust Rules Skeleton

Template for Rust projects. The bootstrap agent adapts it per project (crate structure, MSRV, async runtime, and so on).

## 1. Style & Format

- `rustfmt` with a checked-in `rustfmt.toml` is mandatory. CI fails on any diff.
- `cargo clippy --all-targets --all-features -- -D warnings`. No `#[allow(...)]` without a short justification in the code.
- MSRV pinned in `rust-toolchain.toml`. Do not bump without a plan.
- Imports: `use foo::bar` at the top of the file; no inline paths inside functions except for disambiguation.

## 2. Tests

- Unit tests in the same file under `#[cfg(test)] mod tests`.
- Integration tests in `tests/`.
- `cargo nextest run` as the standard runner if available in the project.
- `#[ignore]` only with an issue link or justification comment.
- Property and fuzz tests for crypto, parsing, and data-structure invariants.

## 3. Architecture & Boundaries

- Workspace layout: one crate per clearly bounded responsibility. The `Cargo.toml` workspace member list is the source of truth.
- Public API is only what is deliberately exported (`pub` at module roots, `pub(crate)` otherwise).
- Breaking changes only with a semver bump in the affected crate.
- Feature flags in `Cargo.toml` carry a doc comment explaining what they switch on or off.
- External dependencies: every new dependency requires a justification in the PR description.

## 4. Anti-Patterns

- `unwrap()` / `expect("infallible")` in library code: BLOCK. Only allowed in tests and `main.rs`.
- `panic!()` in library paths without a documented invariant: BLOCK.
- Global mutable state (`static mut`, `lazy_static!` with mutability): only with explicit consensus.
- `Box<dyn Error>` as the error type in public APIs is lazy; prefer a concrete `enum Error` via `thiserror`.
- `clone()` in the hot path when not needed.
- `#[allow(dead_code)]` as a workaround instead of deleting the code.

## 5. Naming

- Functions and variables: `snake_case`.
- Types, traits, enums: `UpperCamelCase`.
- Constants and statics: `SCREAMING_SNAKE_CASE`.
- Module names: short, snake_case, no plural when singular fits.
- Trait methods avoid verbs like `get_` except when looking up map-like structures.

## 6. Security & Privacy

- `unsafe` requires a `// SAFETY:` comment stating the invariant.
- Secrets via env/Vault, never in the repo, never in logs.
- Input validation at FFI and network boundaries (for example Axum handlers, Tonic services).
- Filter `tracing` fields: no PII, no tokens, no full request bodies.
- `serde` deserialization with `deny_unknown_fields` where sensitive structures come in.

## 7. Build & Verification

- `cargo build --all-targets`: clean.
- `cargo test --all-features` or `cargo nextest run`: all green.
- `cargo clippy --all-targets --all-features -- -D warnings`: no warnings.
- `cargo fmt --check`: no diff.
- Optional: `cargo deny`, `cargo audit` in CI.

## 8. Domain (project-specific)

- Fill in during bootstrap: repo purpose, domain vocabulary, compliance requirements, stakeholders.
- Examples a reviewer must be able to look up: data models, trait hierarchies, crate responsibilities.
