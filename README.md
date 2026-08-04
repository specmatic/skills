## Specmatic Skills

This repository packages reusable AI assistant skills for working with Specmatic and API specifications.

It is intended for cases where you want an assistant to follow a structured workflow for:
- extracting an OpenAPI specification from an existing API codebase
- fixing OpenAPI specifications that break Specmatic validation, mocking, or contract tests
- debugging Specmatic failures and separating concrete spec or app defects from likely Specmatic issues
- generating runnable Backend, BFF, and Frontend sample projects that demonstrate Specmatic contract testing

## What Problems These Skills Solve

These skills are useful when:
- your application already exists, but its OpenAPI or Swagger specification is missing, incomplete, or stale
- your OpenAPI file looks valid, but Specmatic cannot mock it, validate it, or execute tests against it
- a Specmatic workflow is failing, and it is unclear whether the root cause is the spec, the provider app, configuration, Docker/runtime setup, or Specmatic itself
- you need a working sample for a particular language, framework, protocol, and Specmatic integration mode
- an existing Specmatic sample needs contract, dependency, runtime, or configuration updates

They are not meant for:
- writing a brand-new API design from scratch
- general application development unrelated to API contracts
- non-Specmatic testing workflows

## Skills

### `specmatic-openapi-spec-extractor`

Use this when you have an existing API application or repository and want to derive an OpenAPI or Swagger specification from the implementation.

This skill is best for:
- generating a first-pass contract from routes, controllers, handlers, or framework metadata
- refining the generated contract through framework-native extraction paths
- preparing Specmatic validation and contract-test assets after extraction

### `fix-openapi-spec`

Use this when you already have an OpenAPI file, but it fails in Specmatic.

This skill is best for:
- diagnosing obscure spec issues that prevent mocking or contract testing
- iteratively fixing schema, example, enum, `$ref`, and constraint problems
- producing an audit trail of observed issues, applied fixes, and likely Specmatic bugs

### `debug-specmatic-failures`

Use this when a Specmatic workflow is failing, and you need to diagnose the issue.

This skill is best for:
- identifying the exact failing command, spec path, mode, and version
- determining whether the problem is a concrete spec defect, provider bug, config issue, or Specmatic bug
- stopping early once the failure is clearly a Specmatic limitation or contradiction

### `generate-specmatic-sample`

Generate or maintain self-contained Backend, BFF, and Frontend samples from an executable contract. The skill supports REST/OpenAPI, AsyncAPI, gRPC, GraphQL, and SOAP; mocks external dependencies by default; and integrates Specmatic through CLI, Docker, Testcontainers, or native test libraries. A sample is complete only after its build and Specmatic contract tests pass.

Provide the contract repository and spec path, application type, language, framework, integration mode, and destination path. The protocol is inferred from the contract.

## Installation

To install the skills in Codex, run the following command:

```bash
npx skills add specmatic/skills -a codex
```

To install the skills in Claude Code, run the following command:

```bash
npx skills add specmatic/skills -a claude-code
```

## Uninstallation

```bash
npx skills remove specmatic-openapi-spec-extractor -g
```

Replace the skill name with the one you want to uninstall.
Use `-g` flag if you want to uninstall the skill installed at global level. Do not use it if it is installed at project level.

## Examples

Sample prompts for each skill:

### `specmatic-openapi-spec-extractor`

- "Extract an OpenAPI spec from this Spring Boot service."
- "Generate OpenAPI spec for this FastAPI app."
- "Derive an OpenAPI spec from this Express project and harden it for contract testing."

### `fix-openapi-spec`

- "This OpenAPI spec fails in Specmatic mock mode. Fix it."
- "When I run Specmatic validate command it is reporting issues in the spec. Diagnose and repair the spec."
- "Create an updated copy of this OpenAPI spec and fix the issues preventing Specmatic from using it."

### `debug-specmatic-failures`

- "Why is this Specmatic test failing?"
- "Debug this Specmatic run and tell me whether the issue is in the spec, app, or Specmatic."
- "Investigate this Specmatic error and tell me if it looks like a product bug."

### `generate-specmatic-sample`

- "Generate a Specmatic sample project from this OpenAPI contract."
- "Create a Java Spring Boot backend sample using native Specmatic contract tests."
- "Create a TypeScript BFF sample whose backend dependencies are mocked by Specmatic."
- "Create a gRPC backend sample from this Protobuf contract and verify it with Specmatic."
- "Update this existing sample for the latest contract and Specmatic runtime, preserving its customizations."

For a non-interactive generation request, include all inputs in the prompt:

```text
Use generate-specmatic-sample in generate mode.

Contract repo: https://github.com/specmatic/specmatic-order-contracts.git
Spec path: io/specmatic/examples/store/openapi/api_order_v5.yaml
Application type: backend
Language: java
Framework: spring-boot
Specmatic integration mode: native
Destination path: /tmp/my-sample

Skip interactive questions because all inputs are provided, and report the test counts at each verification level.
```
