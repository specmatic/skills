## Specmatic Skills

This repository packages reusable AI assistant skills for working with Specmatic and OpenAPI.

It is intended for cases where you want an assistant to follow a structured workflow for:
- extracting an OpenAPI specification from an existing API codebase
- fixing OpenAPI specifications that break Specmatic validation, mocking, or contract tests
- debugging Specmatic failures and separating concrete spec or app defects from likely Specmatic issues

## What Problems These Skills Solve

These skills are useful when:
- your application already exists, but its OpenAPI or Swagger specification is missing, incomplete, or stale
- your OpenAPI file looks valid, but Specmatic cannot mock it, validate it, or execute tests against it
- a Specmatic workflow is failing, and it is unclear whether the root cause is the spec, the provider app, configuration, Docker/runtime setup, or Specmatic itself

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

Use this when a Specmatic workflow is failing, and you need to diagnosis the issue.

This skill is best for:
- identifying the exact failing command, spec path, mode, and version
- determining whether the problem is a concrete spec defect, provider bug, config issue, or Specmatic bug
- stopping early once the failure is clearly a Specmatic limitation or contradiction

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
