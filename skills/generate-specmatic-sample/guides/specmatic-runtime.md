# Specmatic Runtime & Contract Test Patterns

This guide contains generator policy, integration wiring, and documentation/runtime gaps.
The current official Specmatic documentation defines the `specmatic.yaml`
schema and field syntax. Do not maintain or copy a local schema template here.

## Pinned runtime versions

```
enterprise_cli_version: 1.19.1
enterprise_docker_tag: 1.19.1
```

Use these versions for all generated samples. Do not resolve "latest" dynamically.

## Documentation-driven configuration

Before creating or refreshing `specmatic.yaml`, read the official v3 pages that
apply to the sample. The URLs in this list are a closed allowlist:

- [Getting Started with Configuration](https://docs.specmatic.io/references/configuration/getting-started)
  for the v3 component model and top-level wiring.
- [Contract Management](https://docs.specmatic.io/references/configuration/contract-management)
  for the selected source type and service definitions.
- [Test Configuration](https://docs.specmatic.io/references/configuration/test-configuration)
  for test-mode settings.
- [Mock Configuration](https://docs.specmatic.io/references/configuration/mock-configuration)
  when the SUT or a dependency is mocked.
- [Template Values](https://docs.specmatic.io/references/configuration/template-values)
  when runtime values are environment-configurable.
- [Reports](https://docs.specmatic.io/references/configuration/reports) for
  reports and OpenAPI coverage governance.
- [CLI Quick Start](https://docs.specmatic.io/getting_started/cli_quick_start)
  for `Specmatic-Response-Code` provider behavior with multiple response
  status codes.

Do not follow links from these pages. This includes sidebar links,
previous/next links, edit links, GitHub links, related documentation links,
embedded cross-references, and example/sample-project links. Same-page content
loaded from an allowlisted URL may be read, but navigation to another URL or
fragment must not be used during generation. If another documentation page is
needed, stop and ask for it to be added to this allowlist before using it.

Populate documented fields directly. For configuration version 3, define
sources, services, and protocol run options under `components`, then wire the
system under test and each dependency by `$ref` using the layout accepted by the
selected Enterprise runtime. Use the resolved contract source, spec paths,
service IDs, run-option key, and protocol values from user input and the
executable contract; those are generator inputs, not a replacement schema.

For dependency services, derive Specmatic mock `runOptions` from the applicable
allowlisted official documentation before writing the file. Do not fall back to
starting real dependency infrastructure unless the user explicitly selected real
dependency integration.

Place the generated `specmatic.yaml` at the sample root. It is the only
Specmatic configuration source: adapters must not create, copy, relocate, or
mutate another config file.

### Runtime values

Keep endpoints, ports, broker settings, import paths, examples directories, and
timeouts configurable through the documented template syntax. The generated app
and the configuration must use the same environment-variable names. Use the
root workflow defaults unless the resolved contract requires another value:

- SUT HTTP base URL: `SUT_BASE_URL`, defaulting to `http://localhost:8080`.
- Dependency HTTP mock URL: `STUB_BASE_URL`, defaulting to
  `http://localhost:8090`.
- gRPC and Kafka host, port, broker, import-path, `protoc`, and timeout values:
  derive their exact fields from the allowlisted protocol documentation and the
  resolved contract.

### Reports and governance

Every sample configures Specmatic-owned reports with `html` and `ctrf` formats.
Do not hard-code an `outputDirectory`: use the selected runtime's documented
default or a sample-specific configured location, verify the produced location,
record it in the manifest, and use that exact location in the generated README.
Do not create a sample-owned report renderer.

For OpenAPI Backend and BFF samples, configure runtime-supported endpoint
discovery before the final Specmatic verification run when the selected
Enterprise runtime and generated framework can support it. Use only the
selected framework's real OpenAPI, route metadata, or equivalent capability; do
not emulate discovery endpoints from another framework. If official
configuration pages are incomplete but the selected Enterprise runtime accepts
the required discovery fields, use the verified runtime behavior and record the
documentation/runtime gap in the manifest learnings.

When the generated app exposes non-contract infrastructure or discovery
endpoints, exclude only those endpoints from API coverage with the
runtime-accepted OpenAPI `filter` run option. After the final run confirms that
Specmatic discovered real application endpoints, write `successCriteria` using
the measured, filtered report: `enforce: true`, `minCoveragePercentage`, and
`maxMissedOperationsInSpec`. If endpoint discovery cannot be configured for
the selected runtime/framework, record that in the manifest learnings and still
write OpenAPI coverage governance from the measured, filtered final report.
After the final successful OpenAPI run, replace placeholder governance values:
`minCoveragePercentage` is the measured API coverage percentage, and
`maxMissedOperationsInSpec` is the measured missed-operation count after
documented WIP or unresolvable contract gaps are accounted for. Do not ship
`minCoveragePercentage: 0` unless measured API coverage is actually 0.
API coverage governance is not emitted for non-OpenAPI or mock-only samples
because the official reports documentation supports API coverage configuration
for OpenAPI.

### Resiliency verification policy

Use the documentation-supported `schemaResiliencyTests` setting during the
existing `none` → `positiveOnly` → `all` verification workflow. Ship `all`
unless an unresolvable contract gap is recorded in the manifest. Test counts
must increase at each level; otherwise stop and diagnose the generated config
and runtime combination.

## Documentation/runtime discrepancy policy

When official v3 pages conflict, use the shape accepted by the selected
Enterprise runtime and record version-scoped workarounds in the manifest.
Treat rejected config fields as config/runtime issues before changing app code.

Verified Enterprise `1.19.0` config behavior:

| Area | Symptom | Runtime-accepted generation rule |
|---|---|---|
| `runOptions` placement | Rejects sibling `systemUnderTest.runOptions` with known property `service` only. | Nest `runOptions` under the `service` object for the system under test and each dependency, for example `systemUnderTest.service.runOptions` and `dependencies.services[].service.runOptions`. |
| Report configuration | Rejects `specmatic.reports`; top-level known properties include `governance`, `license`, and `settings`. | Configure Specmatic-owned reports under `specmatic.governance.report` with `formats` and the verified `outputDirectory`. |
| Test settings | Some examples place settings under `components`. | Keep global test settings under top-level `specmatic.settings.test`, including `schemaResiliencyTests`. |

## Runtime and integration policy

All generated samples must use an official Specmatic Enterprise runtime. Allowed
artifacts are `io.specmatic.enterprise:*` Maven artifacts,
`specmatic/enterprise:*` Docker images, and documented Enterprise-native
language artifacts. Never use the public npm `specmatic` package, its bundled
JAR, or the `specmatic/specmatic` image.

After installing dependencies, verify the selected runtime can parse the
generated configuration version before changing application behavior. A license
initialization message is not proof of Enterprise usage: verify the artifact,
image, package, or JAR path.

Generated wrappers must not fail solely because `SPECMATIC_LICENSE_KEY` is
unset. Pass it through when present, but let the Specmatic Enterprise runtime
handle license discovery and license errors.

| Mode | When | Runtime artifact | Local/CI prereqs | Key constraint |
|---|---|---|---|---|
| `cli` | Run Specmatic as an external executable | `io.specmatic.enterprise:executable-all` (pinned version above) | Java 17+ | Invoke `java -jar <jar> run-suite --config specmatic.yaml` directly. Do NOT route through a JUnit/`ContractTest`/pytest adapter — that is `native`. |
| `docker-cli` | Run Specmatic as a direct `docker run` | `specmatic/enterprise` (pinned tag above) | Docker, no local Java for Specmatic | Mount root `specmatic.yaml` + contracts/reports; reach the app via host networking / shared network / host alias. |
| `test-container` | Run Specmatic from Docker inside the test suite | `specmatic/enterprise` (pinned tag above) | Docker, no local Java outside the container | Use the language's Testcontainers dep; stream container logs; fail on non-zero exit. |
| `native` | Language has an official Enterprise-native test integration | `io.specmatic.enterprise:*` (JVM) or documented Enterprise-native package | Per package (JVM normally JDK/JRE 17+) | Use the official Enterprise API. Reject `native` if only the open-source/public package exists — ask the user for another mode. |

For `cli` mode, generate a direct executable entrypoint such as a build-tool
exec target or `scripts/test.sh` that starts the app, runs
`java -jar <enterprise-jar> run-suite --config specmatic.yaml`, streams
Specmatic output, propagates the exit code, and tears down started processes.
Let Specmatic fetch and cache contracts from the root config; do not clone or
copy the contract repository. Do not generate a JUnit, pytest, Jest, or
framework test class whose purpose is to call the CLI.

### Docker CLI and test-container

Use only the official `specmatic/enterprise` image. Mount the root config,
needed support files, and report directory; make the config read-only when
possible. Pass endpoint overrides through the documented template values and
use host access or network aliases rather than container-local `localhost`.
Stream logs, fail on a non-zero exit, and require Docker but not local Java for
Specmatic.

### Native

Use native mode only after verifying an official Enterprise-native language API
for the selected protocol. Keep the root config as the single source; start the
app and dependencies, run the native contract tests, surface failures, and tear
down every process. If no official native artifact exists, require `cli`,
`docker-cli`, or `test-container` instead.

## Contract test adapter requirements

- Read host, port, base URL, broker, imports, examples, and timeout values from
  the generated app configuration or environment, then expose the same values
  to Specmatic through the root config.
- Start dependency mocks before the app; fail fast on bind/startup errors.
- Run Specmatic against the configured endpoint and require zero failures.
- Always stop the app and mocks in teardown.
- Stage only protocol support files, such as imported protos, in ignored runtime
  directories; never stage another Specmatic configuration file.
- Read Specmatic reports before changing generated behavior. Classify failures
  as SUT mismatch, dependency mismatch, runtime mismatch, startup/config
  mismatch, or duplicated configuration before applying the smallest fix.

### Provider responses with multiple status codes

For a test-mode operation with multiple responses for one request (for example
`201` and `202`), Specmatic sends the target status per test in the
`Specmatic-Response-Code` request header; the provider must branch on it. Applies
to Backend and BFF providers.

### Dependency boundary integrity

For samples whose SUT calls a Specmatic-mocked dependency (BFF, Frontend): the
test must fail when the boundary breaks, not pass on fabricated data.

- Derive the app response (status, headers, and body) from the actual dependency
  response; do not return canned values.
- Do not swallow the dependency call (no blanket `catch (Exception)` or discarded
  response); catch only to rethrow or map a real dependency error to a
  contract-declared response.
- Make dependency failures visible; verify the mock's response reaches the app
  response.
- Synthesize data only for behavior the app's own contract defines (for example a
  BFF monitor/aggregation endpoint).

- Do not silently swallow configured dependency interaction errors. Verify the
  interaction against the Specmatic mock/stub; if it cannot be verified, record
  a manifest learning and final-response warning instead of treating the
  dependency as verified.

Enterprise `1.19.0` caveat: consuming a dependency mock body can stall on some
default HTTP clients (seen with the Spring Boot 4.1.0 JDK client); use one that
consumes the body, such as Apache HttpClient 5, rather than fabricating it.
