# Failure Classification

The refinement loop should classify failures before making any change.

## Categories

- `generated-contract-mismatch`
  - wrong channel mapping
  - wrong operation type
  - missing reply, retry, or DLQ metadata
  - wrong message names or refs

- `generated-example-mismatch`
  - payload shape mismatch
  - header mismatch
  - missing correlation header
  - wrong key shape

- `generated-config-mismatch`
  - broken generated `specmatic.yaml`
  - wrong example directory wiring
  - missing async servers in generated run options
  - unnecessary schema registry config

- `implementation-mismatch`
  - app behavior conflicts with a contract that is otherwise evidence-backed
  - runtime emits data that contradicts the visible code model
  - app uses channels or payloads not represented in the confirmed operation inventory

- `environment-issue`
  - broker unavailable
  - schema registry unavailable
  - app not running or not reachable
  - Docker unavailable for the generated `specmatic/enterprise` runner
  - Gradle or harness failures unrelated to contract semantics

## Refinement Rule

Only the first three classes are eligible for automatic generated-artifact changes.

If a failure is `implementation-mismatch` or `environment-issue`, report it and stop changing artifacts for that failure.

## Supported Automatic Fixes

- `generated-config-mismatch`
  - rewrite generated Kafka server host to match inferred bootstrap server from app config

- `generated-example-mismatch`
  - add HTTP `before` fixture when a send-only operation has trigger hints
  - remove standalone send-only operation when it is already covered by a listener-driven receive scenario
