# Specmatic Enterprise Async: Expert Note

## Architecture Overview

`../enterprise/async` is the async engine for Specmatic Enterprise. It sits on top of `:core`, exposes CLI/programmatic entrypoints, parses AsyncAPI contracts into Specmatic-native runtime structures, executes async contract tests or mocks over multiple transports, and emits reports.

The highest-level entrypoints are:

- `io.specmatic.async.internal.application.AsyncTestCommand`
- `io.specmatic.async.internal.application.AsyncMockCommand`
- `io.specmatic.async.api.AsyncSpecificationAPI`
- `io.specmatic.async.test.SpecmaticAsyncContractTest`
- `io.specmatic.async.mock.AsyncMock`

The module is wired into the enterprise build through [`settings.gradle.kts`](/Users/yogeshanandanikam/project/enterprise/settings.gradle.kts) and [`async/build.gradle.kts`](/Users/yogeshanandanikam/project/enterprise/async/build.gradle.kts). It depends on `:core` and pulls in protocol clients for Kafka, SQS, SNS, EventBridge, Google Pub/Sub, AMQP, JMS, IBM MQ, MQTT, WebSocket, plus Avro/XSD dependencies.

The internal architecture has five layers:

1. Spec ingestion: `AsyncApiSpecification` + v2/v3 implementations
2. Runtime model: `AsyncFeatureMetadata`, `OperationExchange`, `Operation`, `MessagePattern`
3. Execution orchestration: `AsyncScenario` + strategy classes
4. Transport adapters: `AsyncClient` / `AsyncAdminClient` implementations
5. Reporting and mock control: report classes, `AsyncMockImplementation`, `AsyncMockAPIServer`

## Core Execution Flow

### 1. Spec loading

The test path starts by loading a spec into `AsyncApiSpecification`:

- [`AsyncApiSpecification.kt`](/Users/yogeshanandanikam/project/enterprise/async/src/main/kotlin/io/specmatic/async/internal/spec/AsyncApiSpecification.kt)
- [`AsyncApiSpecificationV3.kt`](/Users/yogeshanandanikam/project/enterprise/async/src/main/kotlin/io/specmatic/async/internal/spec/v3/AsyncApiSpecificationV3.kt)
- [`AsyncApiSpecificationV2.kt`](/Users/yogeshanandanikam/project/enterprise/async/src/main/kotlin/io/specmatic/async/internal/spec/v2/AsyncApiSpecificationV2.kt)

Version detection is simple:

- `3.0.0` -> V3 parser
- `2.x` -> V2 parser

V3 is the richer path. It supports:

- channels with address and optional server references
- operations with `action`
- reply operations
- inline examples
- external examples
- retry and DLQ via `x-specmatic-retry` and `x-specmatic-dlq`
- schema registry-backed Avro payloads

### 2. Feature metadata creation

Each parsed spec becomes `AsyncFeatureMetadata`, which bundles:

- the spec file
- a `Resolver`
- the parsed `AsyncApiSpecification`
- the final `OperationExchange` list

This is the point where the raw AsyncAPI document becomes Specmatic’s runtime test/mock model.

### 3. Operation modeling

The central runtime unit is `OperationExchange`:

- request side: `operation`
- optional reply side: `replyOperation`
- optional retry side: `retryOperation`
- optional DLQ side: `dlqOperation`
- optional `before` fixtures
- optional `after` fixtures
- optional `exampleId`

Files:

- [`OperationExchange.kt`](/Users/yogeshanandanikam/project/enterprise/async/src/main/kotlin/io/specmatic/async/internal/scenario/operation/OperationExchange.kt)
- [`Operation.kt`](/Users/yogeshanandanikam/project/enterprise/async/src/main/kotlin/io/specmatic/async/internal/scenario/operation/Operation.kt)
- [`Action.kt`](/Users/yogeshanandanikam/project/enterprise/async/src/main/kotlin/io/specmatic/async/internal/scenario/operation/Action.kt)

This matters because Specmatic does not execute directly from AsyncAPI objects. It executes from `OperationExchange`.

For V2 specifically, the runtime model is much flatter:

- publish/subscribe channel items are converted into simpler `Operation` shapes
- inline examples are grouped back into request/reply-like exchanges only when the model allows it
- server resolution is much less expressive than the V3 path

So the practical expert mental model should be: V3 is the full async engine, V2 is the compatibility layer.

### 4. Action reversal semantics

`Action` is intentionally reversed in test mode:

- AsyncAPI `receive` means “the application receives”
- In a contract test, Specmatic must therefore `send`
- AsyncAPI `send` means “the application sends”
- In a contract test, Specmatic must therefore `receive`

That reversal is implemented in `Action.valueFromPerspectiveOf(executionMode)`.

Behavior by mode:

- `ExecutionMode.TEST` -> reverse action
- `ExecutionMode.MOCK` -> keep original action

This reversal is the reason strategy selection works correctly without redefining contracts for tests.

### 5. Scenario construction and execution

`SpecmaticAsyncContractTestInternal` turns operation exchanges into `AsyncScenario` instances, checks that brokers are reachable using admin clients, and executes scenarios dynamically as JUnit tests.

Key files:

- [`SpecmaticAsyncContractTestInternal.kt`](/Users/yogeshanandanikam/project/enterprise/async/src/main/kotlin/io/specmatic/async/internal/test/SpecmaticAsyncContractTestInternal.kt)
- [`AsyncScenario.kt`](/Users/yogeshanandanikam/project/enterprise/async/src/main/kotlin/io/specmatic/async/internal/scenario/AsyncScenario.kt)
- [`ScenarioExecutionStrategyFactory.kt`](/Users/yogeshanandanikam/project/enterprise/async/src/main/kotlin/io/specmatic/async/internal/scenario/strategy/factory/ScenarioExecutionStrategyFactory.kt)

`AsyncScenario` owns:

- client resolution per operation
- subscription setup
- correlation extraction
- wait/send behavior
- fixture execution
- timeout handling

### 6. Reporting

The test path emits:

- async test result records
- message count reports
- coverage reports
- CTRF/JUnit-style outputs

Representative files:

- [`MessageCountReport.kt`](/Users/yogeshanandanikam/project/enterprise/async/src/main/kotlin/io/specmatic/async/internal/report/MessageCountReport.kt)
- [`CoverageReport.kt`](/Users/yogeshanandanikam/project/enterprise/async/src/main/kotlin/io/specmatic/async/internal/report/test/CoverageReport.kt)
- [`AsyncTestResultRecord.kt`](/Users/yogeshanandanikam/project/enterprise/async/src/main/kotlin/io/specmatic/async/internal/test/AsyncTestResultRecord.kt)

## Spec Model Deep Dive

### V3 vs V2 support

V3 is operation-first and richer. The code reflects that:

- V3 builds exchanges from `operations`, channels, replies, examples, retry, and DLQ
- V2 support is narrower and mostly focused on channels/messages without the same rich runtime features
- V2 parses correctly and is still testable, but it does not carry the same execution richness as the V3 path

Practically, the current sample ecosystem is v3-oriented:

- request-reply
- send-only flows
- mixed transport servers
- schema registry references
- retry/DLQ metadata

### Schema to pattern translation

`SchemaToPattern` is the bridge from AsyncAPI schema objects to Specmatic patterns.

File:

- [`SchemaToPattern.kt`](/Users/yogeshanandanikam/project/enterprise/async/src/main/kotlin/io/specmatic/async/internal/spec/SchemaToPattern.kt)

It supports:

- primitive JSON schema-ish types
- object/array schemas
- `oneOf`
- `allOf`
- enums
- nullable unions
- internal references to component schemas
- references to component messages
- Avro multiformat schemas
- XSD/XML multiformat schemas

Special cases:

- Avro -> `AvroPattern`
- XSD -> `XSDMatcherPattern`
- validate mode Avro can degrade to looser behavior in some paths

### Message pattern and message value

`MessagePattern` represents the contract for one message shape:

- headers pattern
- payload pattern
- examples
- optional correlation pattern
- optional Kafka key pattern

File:

- [`MessagePattern.kt`](/Users/yogeshanandanikam/project/enterprise/async/src/main/kotlin/io/specmatic/async/internal/pattern/MessagePattern.kt)

`MessageValue` represents an actual or generated runtime message:

- headers
- payload
- topic
- report metadata
- optional key

File:

- [`MessageValue.kt`](/Users/yogeshanandanikam/project/enterprise/async/src/main/kotlin/io/specmatic/async/internal/pattern/MessageValue.kt)

Matching works in layers:

1. parse headers and payload
2. validate headers pattern
3. validate payload pattern
4. validate Kafka key if present
5. if example-backed, optionally validate example-specific values and matcher expressions

### Correlation handling

Correlation is modeled explicitly in `CorrelationIdPattern`.

File:

- [`CorrelationIdPattern.kt`](/Users/yogeshanandanikam/project/enterprise/async/src/main/kotlin/io/specmatic/async/internal/pattern/CorrelationIdPattern.kt)

Supported locations:

- header: `$message.header#...`
- payload: `$message.payload#...`

Capabilities:

- extract correlation from received messages
- inject correlation into generated messages
- compare expected and actual correlation values
- respect optionality in the underlying schema/pattern

### Kafka key handling

Kafka message keys are resolved by `BindingKeyResolver`.

File:

- [`BindingKeyResolver.kt`](/Users/yogeshanandanikam/project/enterprise/async/src/main/kotlin/io/specmatic/async/internal/spec/BindingKeyResolver.kt)

Important limitation:

- only a single protocol binding block is supported at resolution time
- message-level Kafka binding key is the main supported key source
- if multiple protocol binding blocks exist together, key resolution throws

## Scenario Execution Behaviors

### Receive-only

Class:

- [`ReceiveOnlyScenarioStrategy.kt`](/Users/yogeshanandanikam/project/enterprise/async/src/main/kotlin/io/specmatic/async/internal/scenario/strategy/ReceiveOnlyScenarioStrategy.kt)

Meaning:

- the app is expected to send a message
- Specmatic subscribes and validates the received message

Behavior:

- runs `before` fixtures first
- subscribes to the target channel
- waits for one matching message
- validates shape and correlation if applicable
- runs `after` fixtures after success

### Send-only

Class:

- [`SendOnlyScenarioStrategy.kt`](/Users/yogeshanandanikam/project/enterprise/async/src/main/kotlin/io/specmatic/async/internal/scenario/strategy/SendOnlyScenarioStrategy.kt)

Meaning:

- the app is expected to receive a message
- Specmatic sends the message, with no reply channel required

Behavior:

- runs `before` fixtures
- sends request message
- success is basically “message sent without contract-side failure”
- side effects are usually asserted through `after` fixtures

### Request-reply

Class:

- [`RequestReplyScenarioStrategy.kt`](/Users/yogeshanandanikam/project/enterprise/async/src/main/kotlin/io/specmatic/async/internal/scenario/strategy/RequestReplyScenarioStrategy.kt)

Meaning:

- Specmatic sends the request
- Specmatic waits for reply

Behavior:

- runs `before` fixtures
- sends request
- extracts correlation from request
- waits for reply matching the same correlation
- validates reply shape

### Request-retry

Class:

- [`RequestRetryScenarioStrategy.kt`](/Users/yogeshanandanikam/project/enterprise/async/src/main/kotlin/io/specmatic/async/internal/scenario/strategy/RequestRetryScenarioStrategy.kt)

Meaning:

- request should lead to retry messages rather than a normal reply

Behavior:

- pre-subscribes to the retry topic before sending
- sends request
- waits up to strategy-derived total retry time
- validates retry message shape and correlation

### Request-DLQ

Class:

- [`RequestDlqScenarioStrategy.kt`](/Users/yogeshanandanikam/project/enterprise/async/src/main/kotlin/io/specmatic/async/internal/scenario/strategy/RequestDlqScenarioStrategy.kt)

Meaning:

- request should end up on DLQ

Behavior:

- pre-subscribes to the DLQ topic before sending
- sends request
- waits for DLQ message
- validates DLQ message shape

### Request-retry-reply

Class:

- [`RequestRetryReplyScenarioStrategy.kt`](/Users/yogeshanandanikam/project/enterprise/async/src/main/kotlin/io/specmatic/async/internal/scenario/strategy/RequestRetryReplyScenarioStrategy.kt)

Meaning:

- request causes retry messages and eventually a successful reply

Behavior:

- pre-subscribes to retry topic
- sends request
- extracts correlation
- processes retry messages in a background coroutine
- waits for final reply concurrently
- succeeds when valid reply arrives in allowed time

Current caveat:

- the code that re-sends retry messages back onto the retry topic is commented out
- this means the strategy currently observes retry messages but does not actively simulate a full retry loop by replaying them
- that is an important sharp edge when interpreting retry support

### Request-retry-DLQ

Class:

- [`RequestRetryDlqScenarioStrategy.kt`](/Users/yogeshanandanikam/project/enterprise/async/src/main/kotlin/io/specmatic/async/internal/scenario/strategy/RequestRetryDlqScenarioStrategy.kt)

Meaning:

- request causes retries and, only after retries are exhausted, a DLQ message

Behavior:

- pre-subscribes to both retry and DLQ channels
- sends request
- runs retry observation and DLQ wait concurrently
- marks early DLQ as failure
- marks DLQ after completed retry phase as success

### Fixture timing

Fixture timing is owned by `OperationExchange` + `AsyncScenario`:

- `before` fixtures run before send/wait begins
- `after` fixtures run after the strategy succeeds
- failed `after` fixtures can still fail the scenario even if messaging passed

This is why Specmatic async is really behavior-driven, not just schema-driven.

## Mock Flow

The mock path is implemented by:

- [`AsyncMockImplementation.kt`](/Users/yogeshanandanikam/project/enterprise/async/src/main/kotlin/io/specmatic/async/internal/mock/AsyncMockImplementation.kt)
- [`AsyncMockAPIServer.kt`](/Users/yogeshanandanikam/project/enterprise/async/src/main/kotlin/io/specmatic/async/mock/server/AsyncMockAPIServer.kt)

Mock startup flow:

1. load specs into feature metadata
2. derive all known topics/channels from exchanges
3. create missing topics/queues via `AsyncAdminClient`
4. subscribe to request topics
5. match incoming messages against `OperationExchange`
6. emit responses when the contract implies a send/reply behavior
7. track messages and usage for reporting
8. expose control endpoints

API endpoints:

- `POST /_specmatic/snapshot`
- `GET /_specmatic/verify?exampleIds=...`
- `GET /_specmatic/verify?channels=...`
- `POST /_specmatic/stop`

The important design point is that async mock verification is intentionally snapshot/count-oriented:

- channel verification is count-based
- example verification is aggregate-count-based
- removed legacy expectation-verification endpoints are intentionally gone

So the mock is primarily a contract-driven responder plus usage tracker, not a rich semantic assertion engine by itself.

Operationally:

- snapshot captures message-count baseline
- verify compares later counts to expectations
- stop dumps reports and shuts down subscribers/admin clients

This is the basis for side-effect verification in async behavior flows.

## Examples And Fixtures

External examples are modeled by `ExternalisedExample`.

File:

- [`ExternalisedExample.kt`](/Users/yogeshanandanikam/project/enterprise/async/src/main/kotlin/io/specmatic/async/example/ExternalisedExample.kt)

Supported blocks:

- `receive`
- `send`
- `retry`
- `dlq`
- `before`
- `after`
- `id`

Example loading behavior:

- implicit examples directory: spec name + `_examples`
- explicit example directories from config are also supported
- valid JSON files in nested subdirectories are loaded
- strict mode can fail hard on invalid examples
- non-strict mode logs warnings and continues

How an example becomes executable:

1. load JSON into `ExternalisedExample`
2. convert each message block into `MessageValue`
3. find matching spec-side message patterns and channels
4. create example-backed `Operation` objects
5. assemble `OperationExchange`
6. attach fixtures and example id

The tests in `ExternalisedExampleTest` confirm that examples are first-class test scenarios, not just sample payloads.

## Transport Support Matrix

| Protocol | Client | Admin client | Notes |
| --- | --- | --- | --- |
| Kafka | `KafkaClient` | `KafkaAdminClient` | richest path; supports key schema, Avro/schema registry |
| SQS | `SQSClient` | `SQSAdminClient` | header codec needed; queue-oriented |
| SNS | `SNSClient` | `SNSAdminClient` | publish/subscribe AWS path |
| EventBridge | `EventBridgeClient` | `EventBridgeAdminClient` | AWS event bus style |
| Google Pub/Sub | `GooglePubSubClient` | `GooglePubSubAdminClient` | GCP transport |
| AMQP | `AMQPClient` | `AMQPAdminClient` | exchange/routing semantics |
| JMS | `JMSClient` | `JMSAdminClient` | queue/topic via JMS destination type |
| IBM MQ | `IBMMQClient` | `IBMMQAdminClient` | JMS-like enterprise broker path |
| MQTT | `MQTTClient` | `MQTTAdminClient` | topic pub/sub with broker session options |
| WebSocket | `WebSocketClient` | `WebSocketAdminClient` | lower-usage path in this repo |

Common abstraction points:

- `AsyncClient.createClient(...)`
- `AsyncClient.createAdminClient(...)`
- `ServerResolver.resolveServerForOperation(...)`

Common cross-protocol behavior:

- server resolution from specmatic config + spec servers
- send one generated or example-backed message
- subscribe and push received messages into scenario channels
- protocol-specific shutdown
- broker/server readiness checks before test execution

Protocol-specific differences:

- Kafka supports key schema and Avro payload serialization/deserialization
- SQS needs header encoding/decoding because queue metadata differs from Kafka headers
- AMQP/JMS distinguish queue/topic or exchange/routing semantics
- MQTT exposes QoS and retained-message concerns
- AWS/GCP protocols depend on richer endpoint/admin credentials

## Sample-To-Capability Mapping

### `../labs/quick-start-async-contract-testing`

SUT:

- a Kafka-backed provider that consumes `new-orders` and produces `wip-orders`

Specmatic drives:

- request-reply contract testing against the real provider

Artifacts:

- AsyncAPI contract fetched from `labs-contracts`
- `specmatic.yaml`

Examples:

- mostly contract-driven, minimal fixture complexity

Capability demonstrated:

- baseline request-reply validation and contract drift detection

### `../labs/async-event-flow`

SUT:

- Spring Boot order service with Kafka + downstream HTTP side effects

Specmatic drives:

- request-reply
- send-only validation
- `before` HTTP triggers
- `after` side-effect assertions

Artifacts:

- AsyncAPI contract for order service
- OpenAPI contract for tax service
- externalized examples under `examples`

Capability demonstrated:

- full event-flow behavior testing with fixtures

### `../specmatic-kafka-sample-asyncapi3`

SUT:

- Spring Boot Kafka application

Specmatic drives:

- same functional model as the lab, but as a reference sample

Artifacts:

- local `specs/async-order-service.yaml`
- local `specs/tax-service.yaml`
- `specmatic.yaml`
- examples directory

Capability demonstrated:

- canonical AsyncAPI 3 request-reply, send-only flows, and side-effect verification

### `../labs/kafka-avro`

SUT:

- Kafka provider + schema registry-backed Avro contracts

Specmatic drives:

- request-reply async testing using Avro schemas resolved through schema registry

Artifacts:

- AsyncAPI contract from `labs-contracts`
- Avro schemas
- external example JSON
- strict-mode config

Capability demonstrated:

- Avro payload validation, schema constraints, and schema-registry integration

### `../specmatic-kafka-avro-sample`

SUT:

- Spring Boot Kafka app using generated Avro classes

Specmatic drives:

- programmatic async contract tests through `SpecmaticAsyncContractTest`

Artifacts:

- `specmatic.yaml`
- registry-backed AsyncAPI spec
- Avro schemas

Capability demonstrated:

- app-side programmatic usage of Specmatic async with schema registry

### `../labs/kafka-sqs-retry-dlq`

SUT:

- provider bridging Kafka and SQS/LocalStack behavior

Specmatic drives:

- success path
- retry path
- retry-to-DLQ path
- direct-DLQ path

Artifacts:

- AsyncAPI contract from `labs-contracts`
- external examples
- `specmatic.yaml`

Capability demonstrated:

- retry and DLQ modeling through `x-specmatic-retry` and `x-specmatic-dlq`

### `../specmatic-async-sample`

SUT:

- transport-agnostic order app with configurable receive/send protocols

Specmatic drives:

- the same logical scenarios across different receive/send protocol combinations

Artifacts:

- mixed-server AsyncAPI spec
- `specmatic.yaml`
- programmatic test wrappers

Capability demonstrated:

- protocol abstraction and server routing independence from business logic

## Behavior Confirmed From Tests

Focused verification run:

```bash
cd /Users/yogeshanandanikam/project/enterprise
./gradlew --stop
./gradlew :async:test --no-daemon \
  --tests 'io.specmatic.async.internal.spec.v3.AsyncApiSpecificationV3Test' \
  --tests 'io.specmatic.async.example.ExternalisedExampleTest' \
  --tests 'io.specmatic.async.internal.scenario.operation.OperationExchangeTest' \
  --tests 'io.specmatic.async.internal.spec.BindingKeyResolverTest'
```

Observed result:

- build succeeded
- 77 targeted tests passed
- 3 tests were skipped

Confirmed behaviors from those tests:

- v3 operation exchange generation works for plain specs, inline examples, external examples, and mixed inline/external example cases
- external examples support strict and non-strict loading behavior
- correlation consistency between request and response examples is validated
- operation exchange naming covers reply, retry, and DLQ shapes
- Kafka binding key resolution works from message bindings and rejects mixed binding protocols
- V3 remains the primary rich execution path; V2 parses and builds features successfully as a simpler compatibility model

Additional focused verification run:

```bash
cd /Users/yogeshanandanikam/project/enterprise
./gradlew :async:test --no-daemon \
  --tests 'io.specmatic.async.mock.server.AsyncMockAPIServerTest' \
  --tests 'io.specmatic.async.internal.scenario.strategy.RequestSubscriptionPreparationTest' \
  --tests 'io.specmatic.async.internal.spec.v2.AsyncApiSpecificationV2Test'
```

Observed result:

- build succeeded
- async mock API behavior passed
- request retry/DLQ strategies were confirmed to subscribe before sending
- V2 parsing/feature creation passed

Another focused verification run:

```bash
cd /Users/yogeshanandanikam/project/enterprise
./gradlew :async:test --no-daemon \
  --tests 'io.specmatic.async.internal.pattern.MessagePatternTest' \
  --tests 'io.specmatic.async.internal.pattern.MessageValueTest'
```

Observed result:

- all test assertions passed
- the Gradle task still failed afterward because XML result files could not be written under `async/build/test-results/test`

That last case appears to be a test-report artifact-writing issue rather than a functional async logic failure.

## Known Gaps And Surprising Behavior

1. `Action` reversal is essential and easy to misunderstand.
   Test mode semantics are from Specmatic’s point of view, not AsyncAPI’s original application point of view.

2. Retry support is only partially “active simulation.”
   `RequestRetryReplyScenarioStrategy` currently observes retry messages but has commented-out code for replaying them back to the retry topic.

3. V2 is best treated as a compatibility path.
   It parses and executes simpler channel-based interactions, but the richer operational model clearly lives in V3.

4. Fan-out is explicitly not handled well yet.
   There are TODOs in `ExternalisedExample` and `OperationExchange` noting lack of fan-out support.

5. Binding-key resolution assumes a single protocol binding block.
   Mixed bindings are not gracefully merged.

6. There are Kotlin 2.5-forward-compat warnings in several client implementations.
   Multiple clients use returns inside expression-bodied functions that will become errors in future language versions.

7. The async module’s verification is sensitive to Gradle/Kotlin daemon state.
   A prior run hit a missing `dirty-sources.txt` in Kotlin incremental compilation under `core/build`; `--stop` plus `--no-daemon` avoided it.

8. Some test runs can fail after assertions pass because Gradle cannot write XML result files.
   This happened in the `MessagePatternTest` / `MessageValueTest` run and looks like a reporting/filesystem issue, not a contract-engine failure.

9. Mock verification relies on message counts and active expectations, not a richer semantic assertion layer.
   That is sufficient for current examples but worth remembering when designing complex flows.

10. Some correlation-heavy integration coverage exists but is not fully in the stable always-on test path.
   `CorrelationIdIntegrationTests` is currently disabled, so the correlation model is present and used elsewhere, but that integration suite is not presently part of the stable verification baseline.

## Glossary

- **Action**: contract-side `send` or `receive`, reversed in test mode from Specmatic’s perspective.
- **Operation**: one side of an interaction on one channel, with one message pattern.
- **OperationExchange**: a grouped interaction containing request plus optional reply, retry, and DLQ operations.
- **Scenario**: runtime executable wrapper around an `OperationExchange`.
- **Example**: inline AsyncAPI example or externalized JSON scenario data.
- **Reply**: the normal successful response message after a request.
- **Retry**: an intermediate retry message or retry phase after a failed attempt.
- **DLQ**: dead-letter message expected after retry exhaustion or non-retryable failure.
- **Fixture**: pre/post action attached to an example, usually HTTP-based, executed in `before` or `after`.
- **Correlation**: identifier carried in header or payload to match request and follow-up messages.

## Bottom Line

Specmatic Enterprise async is best understood as an operation-exchange engine rather than a simple AsyncAPI validator. The contract is parsed into executable exchanges, examples enrich those exchanges into behavioral tests, strategies determine runtime sequencing, and transport clients make the same model work across Kafka, queues, brokers, and cloud messaging backends.

The strongest parts today are:

- AsyncAPI 3 parsing
- external examples
- fixtures
- request-reply flows
- retry/DLQ sequencing
- Avro/schema-registry support
- protocol abstraction
- async mock snapshot/count verification

The main sharp edges are:

- retry-loop realism in retry-reply flows
- fan-out limitations
- mixed binding complexity
- thinner V2 semantics
- some disabled correlation-heavy integration coverage
- build-tool and test-report stability during verification
