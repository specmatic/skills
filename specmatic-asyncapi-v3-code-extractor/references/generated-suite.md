# Generated Suite

The generated suite is intentionally isolated so the refinement loop can change only generated artifacts.

## Layout

- `specmatic/specs/asyncapi-extracted.yaml`
- `specmatic/specs/asyncapi-overlay.yaml`
- `specmatic/specmatic.yaml`
- `specmatic/examples/<service>/*.json`
- `specmatic/reports/`
- `specmatic/run_async_contract_tests.sh`
- `specmatic/docker-compose.yml`
- `specmatic/extraction-report.json`

## Base Spec vs Overlay

- `asyncapi-extracted.yaml` is the evidence-backed base extraction.
- `asyncapi-overlay.yaml` is for refinement-time contract-side corrections that should remain clearly separate from the original extraction.
- If the refinement loop changes semantics beyond evidence-backed extraction, prefer placing the change in the overlay.

## Payload Schemas

Payload schemas should be generated from the strongest available evidence, in this order:

- explicit schema files such as Avro, JSON Schema, or XSD
- DTO or data-class definitions referenced by listener and publish flows
- serialized examples or test fixtures
- broad fallback object schemas only when no stronger evidence exists

## Externalized Examples

Examples should follow the real `enterprise/async` shape:

```json
{
  "name": "PLACE_ORDER",
  "receive": {
    "topic": "place-order",
    "headers": {
      "requestId": "123"
    },
    "payload": {
      "id": 1
    }
  },
  "send": {
    "topic": "process-order",
    "payload": {
      "status": "PROCESSED"
    }
  }
}
```

Optional blocks:
- `retry`
- `dlq`
- `before`
- `after`
- `key`

## Mutation Boundary

Only files inside the generated `specmatic/` folder are eligible for automated refinement.

## Diagnostic Sources

When async tests fail, inspect these generated artifacts together:

- `specmatic.yaml` for broker and runtime wiring
- `extraction-report.json` for inferred broker hosts, trigger hints, and listener coverage
- `reports/specmatic-test.log` for transport and timeout failures
- generated examples to see whether a send-only operation is actually drivable

## Runtime Execution

The generated `run_async_contract_tests.sh` script is Docker-only by design.

- It should run Specmatic through the `specmatic/enterprise` image by default.
- It should not fall back to a local `specmatic` CLI.
- `SPECMATIC_DOCKER_IMAGE` is only an override, not a prerequisite for Docker execution.
- The generated `docker-compose.yml` should be runnable by the user to start the app, required dependencies, and the Specmatic test container together.
