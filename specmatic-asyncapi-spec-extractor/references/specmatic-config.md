# Specmatic Config

Use this reference when generating or repairing `specmatic.yaml` for async contract tests.

The generated config should follow the async shapes used in the sample projects and keep environment-specific connection details in `specmatic.yaml`, not in the AsyncAPI contract.

Schema reference:

- SchemaStore entry for `specmatic.yaml`: [https://www.schemastore.org/specmatic.json](https://www.schemastore.org/specmatic.json)

When useful, add a schema directive at the top of generated config files:

```yaml
# yaml-language-server: $schema=https://www.schemastore.org/specmatic.json
```

## Minimum Async Test Shape

```yaml
version: 3
systemUnderTest:
  service:
    $ref: "#/components/services/orderAsyncService"
    runOptions:
      $ref: "#/components/runOptions/orderAsyncServiceTest"
    data:
      examples:
        - directories:
            - examples/async-order-service
components:
  sources:
    generatedContracts:
      filesystem:
        directory: .
  services:
    orderAsyncService:
      definitions:
        - definition:
            source:
              $ref: "#/components/sources/generatedContracts"
            specs:
              - specs/asyncapi-extracted.yaml
  runOptions:
    orderAsyncServiceTest:
      asyncapi:
        type: test
        servers:
          - host: "${KAFKA_BROKER_HOST:localhost:9092}"
            protocol: kafka
```

## Sections the Skill Must Know

Top level:

- `version`
- `systemUnderTest`
- optional `dependencies`
- `components`
- optional `specmatic.governance`
- generated feedback-loop metadata such as `x-specmatic-feedback-loop`

Under `systemUnderTest.service`:

- service reference
- runOptions reference
- examples directories

Under `components.services`:

- one or more `definitions`
- each definition references a source and one or more spec paths

Under `components.runOptions.<name>.asyncapi`:

- `type: test`
- `servers`
- optional `schemaRegistry`

## Server Shape

Each async server entry should use this shape:

```yaml
- host: "${KAFKA_BROKER_HOST:localhost:9092}"
  protocol: kafka
  adminCredentials:
    security.protocol: SASL_PLAINTEXT
    sasl.mechanism: PLAIN
  client:
    producer:
      basic.auth.credentials.source: USER_INFO
      basic.auth.user.info: admin:admin-secret
    consumer:
      group.id: order-service
```

Common protocols already supported by the extractor:

- `kafka`
- `sqs`
- `jms`
- `mqtt`
- `amqp`

Use `adminCredentials` for broker-level credentials and admin settings.

Use `client.producer` and `client.consumer` for producer and consumer client properties when the repo makes them discoverable.

## Avro Schema Registry Shape

When the repo uses registry-backed Avro, place schema registry settings in `specmatic.yaml`:

```yaml
schemaRegistry:
  url: "${SCHEMA_REGISTRY_BASE_URL:http://localhost:8085}"
  kind: CONFLUENT
  username: admin
  password: admin-secret
```

Rules:

- Keep schema registry config in `specmatic.yaml`, not the AsyncAPI `servers` section.
- Prefer an env-backed URL in generated config.
- If a concrete local URL is discovered, use it only as the default part of the env expression.
- The generated AsyncAPI spec should still use placeholder registry `$ref` values such as `<SCHEMA_REGISTRY_URL>/subjects/<subject>/versions/<version>/schema`.

## Dependencies Shape

Use `dependencies` when the test suite also needs mocks or external specs:

```yaml
dependencies:
  services:
    - service:
        $ref: "#/components/services/taxService"
        runOptions:
          $ref: "#/components/runOptions/taxServiceMock"
        data:
          examples:
            - directories:
                - examples/tax-service
```

This is especially relevant when the async flow under test triggers downstream HTTP or async dependencies that should be mocked by Specmatic.

For the generated async suite, the extractor currently auto-wires the proven case:

- downstream checked-in OpenAPI specs discovered in the repo
- synthesized minimal downstream OpenAPI specs generated from direct HTTP client calls when no checked-in spec is available

It copies those specs into:

- `specs/dependencies/`

and, when matching example directories exist, copies dependency examples into:

- `examples/dependencies/<dependency-name>/`

## Feedback-Loop Metadata

The async extractor currently stores loop-tunable settings in generated config:

```yaml
x-specmatic-feedback-loop:
  replyTimeoutInMilliseconds: 10000
  subscriberReadinessWaitTimeInMilliseconds: 2000
  maxAttempts: 5
  batchSize: 25
```

These values belong only in the generated suite. The feedback loop may tune them when failures are timeout-related.

`batchSize` controls example-based batching for large generated async suites. When the generated example count exceeds this threshold, the feedback loop creates batch-specific suite copies and runs those batches separately.

## Generated Runner

The generated suite should also contain:

- `scripts/prepare_async_test_data.sh`
- `run_async_contract_tests.sh`

Purpose:

- `scripts/prepare_async_test_data.sh` is the deterministic setup hook that can seed data, reset queues, or rewrite example values before a run.
- `run_async_contract_tests.sh` is the single-command entrypoint for rerunning the generated async contract suite with either the local `specmatic` CLI or the Docker image.

## Sample References

Use these files as concrete references:

- `../sample-projects/specmatic-kafka-sample-asyncapi3/specmatic.yaml`
- `../sample-projects/specmatic-async-sample/specmatic.yaml`
- `../sample-projects/specmatic-kafka-avro-sample/specmatic.yaml`

## Generation Rules

- Put broker connectivity and auth in `components.runOptions.*.asyncapi`.
- Put spec file locations under `components.services.*.definitions`.
- Put examples directories under `systemUnderTest.service.data.examples` and dependency service data when needed.
- Generate `schemaRegistry` only when Avro registry usage is discoverable.
- Do not move broker client config into the AsyncAPI spec.
- Do not write implementation config files; generate only `specmatic.yaml` in the suite.
