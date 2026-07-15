# Acceptance Criteria

A generated sample is "done" when ALL of the following are true.

All checks apply inside the generated sample folder at `<provided-location>/<sample-id>/`.

## Must Pass

- [ ] `npm test` (or equivalent) exits with code 0
- [ ] All Specmatic contract tests pass (0 failures)
- [ ] Generated behavior matches the executable contract used by Specmatic
- [ ] No manual intervention needed after generation
- [ ] Any mismatch between local guides/test data and the executable contract is resolved in favor of the executable contract
- [ ] The sample does not require real downstream dependency processes unless
  the user explicitly selected real dependency integration
- [ ] No generated files are written at the provided location root except the sample folder itself, unless updating an existing root `.github/workflows/samples-ci.yml`
- [ ] The sample folder is self-contained and does not require shared generated assets outside the folder
- [ ] If the destination root has `.github/workflows/samples-ci.yml`, it includes a job for this sample
- [ ] Ports, dependency base URLs, service endpoints, broker URLs, and
  protocol-specific test settings can be overridden from environment variables
  consumed by the checked-in `specmatic.yaml`
- [ ] The checked-in root `specmatic.yaml` is the only Specmatic config source;
  tests do not generate, copy, overwrite, or mutate another Specmatic YAML file,
  and the config is not relocated into build directories (e.g.
  `build/specmatic-runner/specmatic.yaml`)
- [ ] The delivered `specmatic.yaml` ships with `schemaResiliencyTests: all`
  (schema resiliency ON), unless documented unresolvable contract-gap failures
  force a lower level recorded in the manifest learnings
- [ ] Specmatic is configured to generate HTML and CTRF reports. The verified
  runtime report location is recorded in the manifest and used by the README;
  generated files may capture/upload, ignore, or link to that output, but must
  not create custom report HTML, templates, pages, or renderers.
- [ ] For OpenAPI Backend and BFF samples, endpoint discovery uses a
  runtime-supported, framework-applicable Specmatic integration and Specmatic
  output confirms that real application endpoints were discovered. Placeholder
  endpoints, empty discovery responses, and emulated endpoints from another
  framework do not satisfy this criterion. Non-contract infrastructure or
  discovery endpoints are excluded from API coverage using the runtime-accepted
  OpenAPI `filter` run option, and governance coverage is enforced (`enforce:
  true`) at the measured final threshold and missed-operation allowance after
  filtering is applied. If verified runtime/framework support is unavailable,
  the manifest learnings record the discovery limitation while governance
  remains enforced from the measured final report.
- [ ] Non-OpenAPI and mock-only samples retain HTML/CTRF reports without
  unsupported API-coverage success criteria.
- [ ] In `cli` mode, Specmatic is invoked directly, not through a native
  JUnit/`ContractTest`/pytest adapter; Specmatic resolves and caches contracts
  itself; the sample does not clone the contract repo or generate its own
  test/coverage report
- [ ] Consumer samples document and implement the contract-derived mapping between SUT/consumer operations and dependency mock operations
- [ ] Every configured dependency is either observed during verification or
  recorded as unobserved in the manifest learnings and final response.
- [ ] The generated test command, script, or adapter uses the selected and
  verified Specmatic integration mode: `cli`, `docker-cli`, `test-container`,
  or `native`
- [ ] The generated test command/script/adapter and CI use only official
  Specmatic Enterprise artifacts: `io.specmatic.enterprise:*`,
  `specmatic/enterprise:*`, or a documented Enterprise-native language
  artifact/API. Generated files must not reference `npm exec specmatic`, `npx
  specmatic`, `specmatic@`, `node_modules/specmatic/specmatic.jar`, or
  `specmatic/specmatic`.
- [ ] `.specmatic-sample-manifest.json` records the exact Enterprise runtime
  artifact/version/source. A license initialization message alone is not
  accepted as proof of Enterprise runtime usage.
- [ ] Generated Dockerfiles build from source and do not depend on local build
  outputs that are excluded by `.dockerignore`, such as `target/`, `dist/`, or
  `build/`
- [ ] `README.md` complies with `guides/readme-generation.md`: required
  sections are present and in order, contract links point to the resolved
  executable specs, role-appropriate architecture assets are included when
  available, run commands cover Unix/macOS, Windows PowerShell, and Windows
  Command Prompt, test modes are documented, and project structure matches the
  generated files
- [ ] README-required assets, such as architecture GIFs copied from `assets/`,
  are included inside the sample folder and listed in
  `.specmatic-sample-manifest.json`
- [ ] Local verification artifacts are ignored and are not left as source files in the generated sample folder

## Required Files

| File | Purpose |
|------|---------|
| `specmatic.yaml` | Points to the resolved user-provided contract source, defines test config, and contains environment-template runtime values |
| Build file (`package.json` / `pom.xml` / `build.gradle` / `requirements.txt`) | Dependencies including Specmatic |
| Lockfile when produced by the package manager | Enables reproducible installs and CI locked installs |
| Source code (controllers/routes/services/resolvers/handlers) | Implements all operations from the contract |
| Data layer (db/store) | In-memory store with seed data when the role needs local state |
| Contract test file or script | Test command, script, or adapter for the selected integration mode |
| `Dockerfile` | Production container image that builds from source; use a multi-stage build for compiled stacks instead of copying local build outputs from ignored folders |
| `.dockerignore` when `Dockerfile` is generated | Keeps dependencies, virtualenvs, reports, caches, Specmatic repos, and local files out of image build context |
| `.github/workflows/ci.yml` | CI pipeline: test + Docker build |
| `README.md` | Generated per `guides/readme-generation.md` — includes value prop, run instructions, and architecture |
| `.gitignore` | Ignore dependency folders, virtualenvs, build output, reports, caches, and `.specmatic` |
| `.specmatic-sample-manifest.json` | Records generated files, test coverage, and learnings |

## Manifest Required Fields

The `.specmatic-sample-manifest.json` must include:

```json
{
  "id": "<sample-id>",
  "application_type": "<backend|bff|frontend>",
  "protocol": "<rest|kafka|grpc|graphql|soap>",
  "language": "<language>",
  "framework": "<framework>",
  "data_layer": "<data-layer>",
  "integration_mode": "<native|cli|docker-cli|test-container>",
  "specmaticRuntime": {
    "artifact": "<io.specmatic.enterprise:executable-all|specmatic/enterprise|enterprise-native-artifact>",
    "version": "<version-or-tag>",
    "source": "<maven-central|docker-hub|official-enterprise-docs>",
    "invocation": "<java -jar|docker run|testcontainers|native-api>"
  },
  "contract_version": "<version>",
  "port": 8080,
  "test_command": "<command>",
  "install_command": "<command>",
  "generated_files": ["<list of generated file paths>"],
  "testCoverage": {
    "level1_none": { "tests": 0, "passed": 0, "failed": 0 },
    "level2_positiveOnly": { "tests": 0, "passed": 0, "failed": 0 },
    "level3_all": { "tests": 0, "passed": 0, "failed": 0 },
    "shipped_level": "all"
  },
  "reports": {
    "formats": ["html", "ctrf"],
    "outputDirectory": "<verified-runtime-report-directory>",
    "coverageGovernance": null
  },
  "infraEndpoints": ["<non-contract infra endpoints generated by the app>"],
  "coverageExclusionMode": "<filter|null>",
  "learnings": [
    "Brief description of any issue encountered and how it was resolved"
  ]
}
```

- `testCoverage`: records test counts at each progressive verification level.
  `shipped_level` indicates which `schemaResiliencyTests` value the delivered
  `specmatic.yaml` uses.
- `specmaticRuntime`: records the official Enterprise runtime artifact used by
  the generated sample. It must never identify the public npm `specmatic`
  package, the bundled npm `specmatic.jar`, or the `specmatic/specmatic` Docker
  image.
- `learnings`: array of strings documenting issues encountered during
  generation — dependency conflicts, contract gaps, framework quirks, or
  workarounds applied. Empty array if generation was clean.
- `reports`: records the Specmatic report formats and location. For applicable
  OpenAPI provider samples, replace `coverageGovernance: null` with the final
  measured `minCoveragePercentage`, `maxMissedOperationsInSpec`, and
  `enforce: true` values.
- `coverageExclusionMode`: records how generated non-contract infrastructure
  or discovery endpoints were excluded from API coverage. Use `filter` for
  OpenAPI Backend/BFF samples with generated endpoints that are not contract
  operations.

## CI Workflow Must Include

1. Multi-OS matrix strategy based on integration mode:
   - `native` or `cli` modes: `[ubuntu-latest, macos-latest, windows-latest]`
     (only requires Java/language runtime, available on all OSes)
   - `docker-cli` or `test-container` modes: `ubuntu-latest` only
     (Docker requires a Linux kernel; macOS/Windows CI runners do not have
     Docker pre-installed, and installing it adds fragile VM setup + minutes
     of startup time)
2. Setup JRE 17 when the selected integration mode or language runtime requires it
3. Setup language runtime (Node 20 / JDK 17 / Python 3.x)
4. Install dependencies, including CLI/JAR, Docker image access, Testcontainers, or native Specmatic test support for the selected integration mode
5. Run tests
6. Upload test report artifact
7. (On main branch) Build and push Docker image

All generated samples must use Specmatic Enterprise (`specmatic/enterprise`
Docker image, `io.specmatic.enterprise` Maven artifacts, or documented
Enterprise-native language artifacts). CI must document the required
`SPECMATIC_LICENSE_KEY` environment variable in the generated README. Do not
rely on accidental local license files, preinstalled CLIs, private caches,
checked-out contract repo state, the public npm `specmatic` package, or
open-source Docker images.

For `docker-cli`, CI must make Docker available and run Specmatic through a
direct `docker run` command or wrapper script using the official Docker image.

For `test-container`, CI must make Docker available to the test process and run
Specmatic through the official Docker image from the generated test suite
instead of requiring a local Java installation for Specmatic itself.

For `cli`, CI must install or download the verified Enterprise executable JAR
from an `io.specmatic.enterprise:*` Maven artifact and run it from the
generated test command or script.

For `native`, CI must install the official Enterprise-native Specmatic test
dependency for the selected language and run the generated native test class or
module. If no Enterprise-native artifact is verified, `native` is invalid for
that stack.

## Root Samples CI

When the destination root already has `.github/workflows/samples-ci.yml`, add or update one job for the generated sample:

- Use the sample id as the job name.
- Run commands with `working-directory: <sample-id>`.
- Use the install and test commands generated for the selected language and framework.
- Set up JRE 17 before running Specmatic tests when required by the selected
  language or integration mode.
- Set up the language runtime required by the selected language.
- Set up Docker when the selected integration mode is `docker-cli` or
  `test-container`.
- Include the documented Enterprise runtime/license setup for every generated
  sample.
- Upload the generated Specmatic/JUnit report artifact when the test command
  produces one.

## Local Run Must Work With

```bash
# Node.js
npm install && npm test

# Java
./mvnw test

# Python
pip install -r requirements.txt && pytest test -v -s
```

Single command, green output.

The single test command must use the selected Specmatic integration mode:

- `cli`: starts the app and runs the verified Enterprise executable JAR from an
  `io.specmatic.enterprise:*` artifact.
- `docker-cli`: starts the app and runs the official Specmatic Docker image
  through a direct Docker command.
- `test-container`: starts the app and runs the official Specmatic Docker image
  from the generated test suite.
- `native`: runs the generated native Specmatic test class/module.

If the default service port or broker port is occupied, the test command may use
documented environment overrides such as `SUT_PORT`, `SUT_BASE_URL`,
`BROKER_PORT`, `BROKER_URL`, or stack-equivalent names. Normal service startup
should still use the documented default endpoint unless the user overrides it.

## What "Green" Means

Specmatic output shows:
```text
Tests run: N, Successes: N, Failures: 0, Errors: 0
```

Or in Jest format:
```text
Test Suites: 1 passed, 1 total
Tests:       N passed, N total
```

Any failures = not done. Fix and re-run.

When tests fail, use the generated Specmatic/JUnit/report files to identify the
exact contract mismatch. Fix status codes, content types, request/response
shape, RPC/message shape, GraphQL selection/variables, SOAP XML, examples,
stubs, or startup configuration until the report has zero failures.
