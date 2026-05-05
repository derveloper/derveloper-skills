# Java Rules Skeleton

Vorlage für Java-Projekte (Maven/Gradle, Spring/Quarkus/Micronaut/plain). Bootstrap-Agent passt JDK-Version, Build-Tool und Framework an.

## 1. Style & Format

- `spotless` (Maven/Gradle Plugin) als Formatter, Config eingecheckt.
- `checkstyle` oder `google-java-format` als Style-Gate; CI bricht bei Diff.
- `errorprone`/`spotbugs`/`pmd` als Linter-Set, Konfig eingecheckt.
- JDK-Version in `pom.xml`/`build.gradle` festgenagelt; nicht ohne Plan hochziehen.

## 2. Tests

- JUnit 5 als Standard.
- Tests in `src/test/java`, Naming `*Test.java`.
- AssertJ für lesbare Assertions, Mockito wo Mocks unvermeidbar.
- Coverage via JaCoCo, Threshold im CI-Gate.
- Property-Tests via jqwik bei Datenstrukturen-Invarianten.

## 3. Architecture & Boundaries

- Module-Struktur: `mvn` Multi-Module oder `gradle` Sub-Projekte für klare Boundaries.
- Public-API über `module-info.java` (JPMS) oder klar definierte Packages.
- Keine Cross-Module-Reachthroughs in interne Pakete.
- Externe Dependencies: jede neue PR-begründet, BOM-Datei für Versionen.

## 4. Anti-Patterns

- Checked Exceptions als Lifestyle: BLOCK. Konkrete Begründung pro Stelle.
- `null` als Rückgabewert: BLOCK. `Optional<T>` oder NotNull-Annotation.
- `Object` als Parameter-Typ ohne Generics: BLOCK.
- Statische Mutable State (Singletons mit Mutable-Members): BLOCK ohne Begründung.
- `System.out.println` in committed Code (außer main): BLOCK. Logger nutzen.
- `printStackTrace()`: BLOCK. Logger nutzen.
- Reflection außer in dokumentierten Frameworks: BLOCK.

## 5. Naming

- Klassen + Interfaces: `PascalCase`.
- Methoden + Variablen: `camelCase`.
- Konstanten: `SCREAMING_SNAKE_CASE`.
- Pakete: `lowercase.dots.separated`.
- Test-Klassen: `<Sut>Test`.

## 6. Security & Privacy

- Secrets via Vault / env, nie im Repo.
- Input-Validation via Bean Validation (`@Valid`) an HTTP-Boundaries.
- SQL via JPA/JDBC mit Parameter-Binding, kein String-Concat.
- Unsafe Deserialization (Java-Native-`ObjectInputStream` auf User-Input, etc.): BLOCK.
- Logging: keine PII, keine Tokens, keine Stacktraces in Production-Logs ungefiltert.

## 7. Build & Verification

- `mvn verify` oder `gradle check`: clean.
- Spotless: clean.
- Checkstyle/errorprone/spotbugs: clean.
- JUnit-Suite: alle grün.
- Optional: `dependency-check`, `owasp-dependency-check` im CI.

## 8. Domain (project-specific)

- Zweck des Repos in einem Satz.
- Domain-Vokabular.
- Compliance-Anforderungen.
- Stakeholder-Reviewer.
