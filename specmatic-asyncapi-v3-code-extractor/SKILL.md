---
name: specmatic-asyncapi-v3-code-extractor
description: Use when extracting an AsyncAPI 3.0.0 contract from an existing async or event-driven codebase, reviewing inferred operations, generating a Specmatic async test suite, and refining only generated artifacts with real Specmatic async contract tests. Triggers on "extract AsyncAPI", "derive async contract", "code first asyncapi", "extract async operations", "generate Specmatic async examples from code", or "extract AsyncAPI from messaging code"
---

# specmatic-asyncapi-v3-code-extractor

Extract an AsyncAPI 3.0.0 contract from an application by treating operations as the primary unit of discovery, then generate a runnable Specmatic async suite and refine only the generated artifacts with Specmatic async contract tests.

This skill is grounded in the real Specmatic async runtime:
- async contract tests are driven through `SpecmaticAsyncContractTest` and `TestCommand` in `../enterprise/async`
- generated runtime config should follow the SchemaStore Specmatic config schema version 3 at `https://json.schemastore.org/specmatic.json`
- externalized examples must match the `ExternalisedExample` shape used by `enterprise/async`
- payload schemas should be inferred from explicit schema files, DTO/data-class evidence, and examples when available, then refined by Specmatic feedback rather than guessed blindly

## Use This When

- The user wants to extract AsyncAPI from existing code
- The user wants to infer async operations from an event-driven application
- The user wants a Specmatic-ready async suite generated from code
- The user wants contract-test-driven refinement of generated async artifacts only

## Files

- Extractor and generator: `scripts/extract_asyncapi_suite.py`
- Async test runner template: `scripts/run_specmatic_async_tests.sh`
- Failure classifier: `scripts/classify_async_failures.py`
- Refinement loop: `scripts/run_async_refinement_loop.py`
- Operation model reference: `references/operation-model.md`
- Generated suite reference: `references/generated-suite.md`
- Specmatic config v3 reference: `references/specmatic-v3-config.md`
- Failure policy reference: `references/failure-classification.md`

## Workflow

1. Identify the target application root.
2. Run the extractor in `inspect` mode to build an evidence-backed async inventory.
3. Review the inferred operation table before generating any suite artifacts.
4. Stop and ask the user to confirm, correct, or prune the inferred operations.
5. After confirmation, save the approved operations to `approved-operations.json`.
6. Run the extractor in `generate` mode to create `specmatic/` under the target application, or `specmatic-1/`, `specmatic-2/`, and so on if `specmatic/` already exists.
7. Validate the generated `specmatic.yaml` shape against the SchemaStore Specmatic schema before making config fixes.
8. Validate generated examples locally.
9. Run Specmatic async contract tests using the generated suite only, always through the `specmatic/enterprise` Docker image unless the user explicitly asks for a different image.
10. Classify failures using generated logs plus generated artifacts, especially:
    - generated broker host versus app bootstrap server
    - send-only operations that require HTTP trigger fixtures
    - standalone send-only operations already covered by listener-driven flows
11. Separate contract-side, example-side, config-side, implementation-side, or environment-side issues.
12. Automatically refine supported generated-artifact issues and rerun until no contract-side gain remains.
13. Report extracted operations, generated artifacts, refinements made, unresolved ambiguities, and implementation-side failures separately.

## Hard Rules

- Operations are the primary extraction unit. Do not jump straight from channels to AsyncAPI without an explicit operation inventory.
- Always stop for an operation review gate after `inspect`.
- Never generate the final suite before user confirmation.
- Generate AsyncAPI `3.0.0` only unless the user explicitly asks for legacy output.
- Generate Specmatic config `version: 3` by default.
- Always execute generated async contract tests through Docker with `specmatic/enterprise` by default. Do not fall back to a local `specmatic` CLI.
- When `specmatic.yaml` validation fails, use the SchemaStore schema as the source of truth for shape fixes.
- Do not inspect local Specmatic implementation artifacts to guess config-shape corrections.
- Use externalized examples in the shape expected by `enterprise/async`.
- Infer payload structure from evidence-backed models and schema files where possible. If structure is unclear, keep the schema broad instead of inventing fields.
- Allow refinement only inside the generated `specmatic/` folder chosen for that run.
- Never modify application code, checked-in contracts, checked-in schemas, or app config as part of refinement.

## Operation Inference Model

Every inferred operation should capture:
- `operationId`
- `type`: `request-reply`, `send-only`, or `receive-only`
- direction from the application-under-contract perspective
- inbound channel
- outbound reply channel if any
- retry channel if any
- DLQ channel if any
- request message
- reply message if any
- evidence anchors in code
- confidence
- correlation strategy: `explicit`, `inferred`, or `unknown`

Inference defaults:
- consume plus immediate derived publish in the same flow -> propose `request-reply`
- standalone publisher path -> propose `send-only`
- standalone consumer path with no visible paired response -> propose `receive-only`
- retry and DLQ infrastructure belong to the operation, not as unrelated extra channels
- low-confidence flows must be surfaced as unresolved in the review gate

## Commands

Inspect a codebase:

```bash
python3 scripts/extract_asyncapi_suite.py inspect /path/to/app
```

Generate a suite after review:

```bash
python3 scripts/extract_asyncapi_suite.py generate /path/to/app \
  --report /path/to/app/specmatic/extraction-report.json \
  --approved /path/to/app/specmatic/approved-operations.json
```

Run the generated async suite:

```bash
bash /path/to/app/specmatic/run_async_contract_tests.sh
```

Override the Docker image only if the user explicitly asks for it:

```bash
SPECMATIC_DOCKER_IMAGE=specmatic/enterprise bash /path/to/app/specmatic/run_async_contract_tests.sh
```

Run the refinement loop:

```bash
python3 scripts/run_async_refinement_loop.py /path/to/app
```

## Review Gate Output

The review step must present, per operation:
- operation name
- type
- request channel
- reply channel
- retry channel
- DLQ channel
- evidence sources
- confidence
- unresolved concerns

If operations are ambiguous, state that explicitly and ask the user to confirm or correct them before generation.

## Generated Suite Layout

The generated folder inside the target application must contain:

- `specmatic/specs/asyncapi-extracted.yaml`
- `specmatic/specs/asyncapi-overlay.yaml`
- `specmatic/specmatic.yaml`
- `specmatic/examples/<service>/*.json`
- `specmatic/reports/`
- `specmatic/run_async_contract_tests.sh`
- `specmatic/docker-compose.yml`
- `specmatic/extraction-report.json`

If `specmatic/` already exists, use `specmatic-1/`, `specmatic-2/`, and so on.

## Refinement Policy

Allowed edits during refinement:
- generated AsyncAPI
- generated examples
- generated overlay
- generated `specmatic.yaml`
- generated `docker-compose.yml`
- generated runner scripts

Disallowed edits:
- application source code
- checked-in source specs
- checked-in schemas
- application configuration
- runtime code

Refinement priorities:
1. generated contract mismatches
2. generated example mismatches
3. generated config-shape mismatches resolved from `https://json.schemastore.org/specmatic.json`
4. generated runtime wiring mismatches
5. spec-only overlay corrections
6. generated timeout or harness tuning

Supported automatic refinements:
- update generated async broker host from inferred app bootstrap server
- add HTTP `before` fixtures for send-only operations when trigger hints are available
- remove standalone send-only operations that are already covered by a listener-driven flow

## Final Response

In the final response:
- separate extracted operations from generated artifacts
- list refinements made during contract-test-driven iteration
- call out unresolved ambiguities explicitly
- separate implementation-side failures from contract-side issues
- mention assumptions and confidence level where inference was weak
