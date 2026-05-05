# Rust Rules Skeleton

Vorlage für Rust-Projekte. Bootstrap-Agent passt projektspezifisch an (Crate-Struktur, MSRV, async-Runtime, etc.).

## 1. Style & Format

- `rustfmt` mit eingecheckter `rustfmt.toml` ist verbindlich. CI bricht bei Diff.
- `cargo clippy --all-targets --all-features -- -D warnings`. Keine `#[allow(...)]` ohne kurze Begründung im Code.
- MSRV in `rust-toolchain.toml` festgenagelt. Nicht ohne Plan hochziehen.
- Imports: `use foo::bar` Top-of-File, keine Inline-Pfade in Funktionen außer für Disambiguation.

## 2. Tests

- Unit-Tests im selben File unter `#[cfg(test)] mod tests`.
- Integration-Tests in `tests/`.
- `cargo nextest run` als Standard-Runner wenn im Projekt vorhanden.
- Nur `#[ignore]` mit Issue-Link oder Begründungs-Comment.
- Property-/Fuzz-Tests bei Crypto, Parsing, Datenstrukturen-Invarianten.

## 3. Architecture & Boundaries

- Workspace-Layout: ein Crate je klar abgegrenzte Verantwortung. `Cargo.toml` Workspace-Member-Liste ist die Wahrheit.
- Public-API nur was bewusst exportiert wird (`pub` an Modul-Wurzeln, sonst `pub(crate)`).
- Breaking-Changes nur mit semver-bump im jeweiligen Crate.
- Feature-Flags in `Cargo.toml` haben Doku-Kommentar was sie ein-/ausschalten.
- Externe Dependencies: jede neue Dependency ist begründungspflichtig (PR-Beschreibung).

## 4. Anti-Patterns

- `unwrap()` / `expect("infallible")` in Library-Code: BLOCK. Nur in Tests + main.rs erlaubt.
- `panic!()` in Lib-Pfaden ohne dokumentierte Invariante: BLOCK.
- Globaler Mutable State (`static mut`, `lazy_static!` mit Mutability): nur mit explizitem Konsens.
- `Box<dyn Error>` als Error-Typ in Public-APIs ist faul, lieber konkretes `enum Error` per `thiserror`.
- `clone()` im Hot-Path ohne Notwendigkeit.
- `#[allow(dead_code)]` als Workaround statt Code zu löschen.

## 5. Naming

- Funktionen + Variablen: `snake_case`.
- Typen, Traits, Enums: `UpperCamelCase`.
- Konstanten + statische: `SCREAMING_SNAKE_CASE`.
- Modulnamen: kurz, snake_case, kein Plural wenn Singular trifft.
- Trait-Methoden vermeiden Verben wie `get_` außer beim Lookup von Map-ähnlichen Strukturen.

## 6. Security & Privacy

- `unsafe` braucht `// SAFETY:` Kommentar mit Invariante.
- Secrets via env/Vault, nie im Repo, nie in Logs.
- Input-Validation an FFI- und Network-Boundaries (z.B. Axum-Handler, Tonic-Service).
- `tracing`-Felder filtern: keine PII, keine Tokens, keine vollen Bodies.
- `serde`-Deserialization mit `deny_unknown_fields` wo vertrauliche Strukturen reinkommen.

## 7. Build & Verification

- `cargo build --all-targets`: clean.
- `cargo test --all-features` oder `cargo nextest run`: alle grün.
- `cargo clippy --all-targets --all-features -- -D warnings`: keine Warnings.
- `cargo fmt --check`: kein Diff.
- Optional: `cargo deny`, `cargo audit` in CI.

## 8. Domain (project-specific)

- Beim Bootstrap füllen: Repo-Zweck, Domain-Vokabular, Compliance-Anforderungen, Stakeholder.
- Beispiele die der Reviewer nachschlagen können muss: Datenmodelle, Trait-Hierarchien, Crate-Verantwortlichkeiten.
