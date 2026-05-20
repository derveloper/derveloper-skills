# Java Rules Skeleton

Template for Java projects (Maven/Gradle, Spring/Quarkus/Micronaut/plain). The bootstrap agent adapts JDK version, build tool, and framework.

## 1. Style & Format

- `spotless` (Maven/Gradle plugin) as the formatter, config checked in.
- `checkstyle` or `google-java-format` as the style gate; CI fails on any diff.
- `errorprone`/`spotbugs`/`pmd` as the linter set, config checked in.
- JDK version pinned in `pom.xml`/`build.gradle`; do not bump without a plan.

## 2. Tests

- JUnit 5 is the standard.
- Tests in `src/test/java`, naming `*Test.java`.
- AssertJ for readable assertions, Mockito where mocks are unavoidable.
- Coverage via JaCoCo, threshold enforced as a CI gate.
- Property tests via jqwik for data-structure invariants.

## 3. Architecture & Boundaries

- Module structure: `mvn` multi-module or `gradle` sub-projects for clear boundaries.
- Public API via `module-info.java` (JPMS) or clearly defined packages.
- No cross-module reach-throughs into internal packages.
- External dependencies: every new one requires PR-level justification, BOM file for versions.

## 4. Anti-Patterns

- Checked exceptions as a lifestyle: BLOCK. Concrete justification per usage.
- `null` as a return value: BLOCK. Use `Optional<T>` or a NotNull annotation.
- `Object` as a parameter type without generics: BLOCK.
- Static mutable state (singletons with mutable members): BLOCK without justification.
- `System.out.println` in committed code (except in main): BLOCK. Use a logger.
- `printStackTrace()`: BLOCK. Use a logger.
- Reflection outside of documented frameworks: BLOCK.

## 5. Naming

- Classes and interfaces: `PascalCase`.
- Methods and variables: `camelCase`.
- Constants: `SCREAMING_SNAKE_CASE`.
- Packages: `lowercase.dots.separated`.
- Test classes: `<Sut>Test`.

## 6. Security & Privacy

- Secrets via Vault / env, never in the repo.
- Input validation via Bean Validation (`@Valid`) at HTTP boundaries.
- SQL via JPA/JDBC with parameter binding, no string concatenation.
- Unsafe deserialization (Java-native `ObjectInputStream` on user input, etc.): BLOCK.
- Logging: no PII, no tokens, no unfiltered stack traces in production logs.

## 7. Build & Verification

- `mvn verify` or `gradle check`: clean.
- Spotless: clean.
- Checkstyle/errorprone/spotbugs: clean.
- JUnit suite: all green.
- Optional: `dependency-check`, `owasp-dependency-check` in CI.

## 8. Domain (project-specific)

- Purpose of the repo in one sentence.
- Domain vocabulary.
- Compliance requirements.
- Stakeholder reviewers.
