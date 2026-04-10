---
name: specmatic-asyncapi-spec-extractor
description: Extract an AsyncAPI 3.0.0 contract from an existing async or event-driven codebase using a bundled automated extractor. Use when Codex needs to derive operations, channels, message formats, and mandatory Specmatic externalised examples from consumers, listeners, subscribers, publishers, or messaging code. Triggers on requests like "extract AsyncAPI", "generate AsyncAPI from code", "derive async contract", "code first asyncapi", "extract async operations", or "generate Specmatic async examples from code".
---

# Specmatic AsyncAPI Spec Extractor

Generate an AsyncAPI 3.0.0 draft, a generated `specmatic.yaml`, mandatory externalised Specmatic examples, and a generated annotation layer from a codebase. The skill also includes a feedback loop runner that tests only generated artifacts and iterates until no more contract-side gains are possible. The extractor is framework-agnostic and synthesizes missing annotations itself instead of requiring the user to add them first.

## Reference Guides

Read these references when working on the corresponding output:

- [references/comment-contract.md](references/comment-contract.md) for synthesized and handwritten `@specmatic-asyncapi` blocks
- [references/externalised-examples.md](references/externalised-examples.md) for the Specmatic externalised example JSON structure, including `receive`, `send`, `retry`, `dlq`, `before`, and `after`
- [references/externalised-example.schema.json](references/externalised-example.schema.json) for the machine-readable schema of externalised examples
- [references/specmatic-config.md](references/specmatic-config.md) for generated `specmatic.yaml`, including `components.services`, async `runOptions`, broker `servers`, `adminCredentials`, client props, and Avro `schemaRegistry`

## Quick Start

1. Run the bundled extractor:

```bash
python3 /absolute/path/to/specmatic-asyncapi-spec-extractor/scripts/extract_asyncapi.py /path/to/project
```

2. Review:
   - `asyncapi-extracted.yaml`
   - `asyncapi-extraction-report.json`
   - `specmatic-asyncapi.generated.annotations.txt`
   - `.specmatic-async-generated/specs/asyncapi-extracted.yaml`
   - `.specmatic-async-generated/specs/asyncapi-overlay.yaml`
   - `.specmatic-async-generated/specmatic.yaml`
   - `.specmatic-async-generated/scripts/prepare_async_test_data.sh`
   - `.specmatic-async-generated/run_async_contract_tests.sh`
   - `.specmatic-async-generated/examples/<service-name>/*.json`

The extractor synthesizes missing annotations into `specmatic-asyncapi.generated.annotations.txt`, then extracts from that annotation layer plus any existing handwritten annotations. That synthesized layer is part of the repo-local working state for this skill.

## Feedback Loop

After extraction, start the application and broker, then run the feedback loop:

```bash
python3 /absolute/path/to/specmatic-asyncapi-spec-extractor/scripts/run_async_feedback_loop.py /path/to/project
```

The loop:

1. uses only the generated suite under `.specmatic-async-generated/`
2. pulls `specmatic/enterprise:latest` first when using the Docker execution path
3. validates generated `specmatic.yaml` structure and, when tooling is available, validates it against the SchemaStore Specmatic schema
4. validates generated externalised examples locally before the first test run
5. runs the generated deterministic setup hook at `scripts/prepare_async_test_data.sh` before each loop attempt
6. runs Specmatic tests using a CLI-first path
7. classifies failures as timeout/harness, contract-side, or implementation-side
8. applies fixes in this order: synthesized annotations, overlay, timeout tuning
9. re-extracts after updating the synthesized annotation layer when source-derived facts need refinement
10. uses `specs/asyncapi-overlay.yaml` for spec-only fixes that should not live in annotations
11. copies discovered downstream OpenAPI dependency specs into the generated suite and wires them into `specmatic.yaml` as mock dependencies
12. synthesizes minimal downstream OpenAPI dependency specs from direct HTTP client calls when no checked-in dependency spec exists
13. batches large suites by generated example files so async tests can run in smaller working sets
14. updates only generated contract artifacts during test execution
15. writes a structured summary that separates fixable, non-fixable, and deferred failures
16. stops when further improvements would require changing implementation, app config, or checked-in schemas

Do not use this skill to modify:

- application config
- checked-in Avro schemas

## Workflow

1. Scan the repo for likely consumers and publishers.
2. Synthesize missing `@specmatic-asyncapi` blocks into `specmatic-asyncapi.generated.annotations.txt`.
3. Parse synthesized and handwritten `@specmatic-asyncapi` blocks and match them to nearby code.
4. Build a normalized model of:
   - inbound operations
   - outbound reply operations
   - send-only operations
   - channels
   - servers
   - messages
   - example payloads, headers, keys, and optional fixtures
   - Specmatic test runtime settings
5. Emit AsyncAPI 3.0.0.
6. Emit one externalised example per extracted operation variant.
7. Emit generated `specmatic.yaml`.
8. Emit a generated deterministic setup hook at `scripts/prepare_async_test_data.sh`.
9. Copy discovered downstream OpenAPI dependency specs and examples into the generated suite when available.
10. Emit `run_async_contract_tests.sh` so the full generated suite can be rerun in one command.
11. Emit generated overlay scaffolding for spec-side loop fixes.
12. Optionally run the feedback loop against the generated suite.

## Operation Rules

- Consumer with no replies becomes `receive-only`.
- Consumer with one reply becomes `receive-reply`.
- Consumer with multiple replies becomes multiple `receive-reply` operations.
- Publisher outside a consumer flow becomes `send-only`.

For receive-reply fan-out, the extractor emits one operation and one example file per reply channel.

## Comment Contract

Use JSON blocks inside comments:

```java
// @specmatic-asyncapi
// {
//   "kind": "operation",
//   "role": "consumer",
//   "operationId": "placeOrder",
//   "channel": { "name": "NewOrderPlaced", "address": "new-orders" },
//   "message": "OrderRequest",
//   "example": {
//     "name": "NEW_ORDER",
//     "payload": { "id": 10 }
//   },
//   "replies": [
//     {
//       "channel": { "name": "OrderInitiated", "address": "wip-orders" },
//       "message": "Order",
//       "example": {
//         "payload": { "id": 10, "status": "INITIATED" }
//       }
//     }
//   ]
// }
// @end-specmatic-asyncapi
@KafkaListener(topics = "${channel.new-orders}")
public void handleNewOrder(String payload) {}
```

Read [references/comment-contract.md](references/comment-contract.md) for the full block schema. The skill may create and update this annotation format on its own during extraction and feedback-loop retries.

Read [references/externalised-examples.md](references/externalised-examples.md) and [references/externalised-example.schema.json](references/externalised-example.schema.json) before changing generated examples, and read [references/specmatic-config.md](references/specmatic-config.md) before changing generated `specmatic.yaml`.

## Avro Payloads

For Avro-backed messages, use an `avro` block in the message annotation instead of `payloadSchema`.

The extractor supports both Specmatic-compatible reference styles:

- local `.avsc` file references
- schema-registry references using the placeholder base URL

The extractor inspects repository evidence such as:

- checked-in `*.avsc` files
- serializer and deserializer configuration
- schema registry URLs
- subject naming patterns in registration scripts or config

It then chooses one of these outputs:

```yaml
payload:
  schemaFormat: 'application/vnd.apache.avro+json;version=1.9.0'
  schema:
    $ref: './order-request.avsc'
```

or

```yaml
payload:
  schemaFormat: 'application/vnd.apache.avro+json;version=1.9.0'
  schema:
    $ref: '<SCHEMA_REGISTRY_URL>/subjects/new-orders-value/versions/1/schema'
```

For schema-registry-backed Avro, tell the user to set `SCHEMA_REGISTRY_BASE_URL` before running Specmatic against the generated spec.

## Notes

- The extractor supports only `asyncapi: 3.0.0`.
- Generated examples may include `before` and `after` fixtures when the annotations provide them.
- Missing annotations are synthesized into `specmatic-asyncapi.generated.annotations.txt` and may be regenerated or refined on later passes.
- `specs/asyncapi-overlay.yaml` is reserved for fixes that should stay spec-side rather than being pushed back into annotations.
- The generated suite contains the only editable artifacts for the feedback loop.
- `scripts/prepare_async_test_data.sh` is the generated place for deterministic setup that should run before each async test attempt.
- `run_async_contract_tests.sh` is the generated single-command entrypoint for rerunning the full async contract suite.
- Downstream OpenAPI dependency specs discovered in the repo are copied into the generated suite under `specs/dependencies/` and wired as mock dependencies in `specmatic.yaml`.
- When no checked-in downstream dependency spec exists, the extractor can synthesize a minimal OpenAPI dependency spec from direct HTTP client calls such as `requests.post(...)`, `axios.get(...)`, `fetch(...)`, or `RestTemplate.postForEntity(...)`.
- Large suites are batched by generated example files using `x-specmatic-feedback-loop.batchSize` so the feedback loop can run smaller async working sets.
- Specmatic-specific output structure lives in [references/externalised-examples.md](references/externalised-examples.md) and [references/specmatic-config.md](references/specmatic-config.md).
- Prefer putting example seed values in the operation block and reusable schemas in message blocks.
