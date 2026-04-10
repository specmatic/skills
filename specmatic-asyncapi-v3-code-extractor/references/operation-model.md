# Operation Model

This skill models operations before it emits AsyncAPI. The operation inventory is the reviewable truth source.

## Required Fields

- `operationId`: stable generated identifier
- `type`: `request-reply`, `send-only`, `receive-only`
- `applicationPerspective`: how the application under contract experiences the flow
- `requestChannel`
- `replyChannel`
- `retryChannel`
- `dlqChannel`
- `requestMessage`
- `replyMessage`
- `requestSchemaHints`
- `replySchemaHints`
- `correlationStrategy`: `explicit`, `inferred`, `unknown`
- `confidence`: `high`, `medium`, `low`
- `evidence`: file and line anchors plus extracted snippets when possible
- `unresolvedConcerns`: list of ambiguities that need user attention

## Interpretation Rules

- `request-reply` means the application consumes one message and, as part of the same business flow, emits a corresponding reply or result message.
- `send-only` means the application is primarily a producer for that flow.
- `receive-only` means the application is primarily a consumer for that flow and no paired response is visible.
- `retryChannel` and `dlqChannel` are modeled as operation metadata because Specmatic async strategies consume them as part of the same `OperationExchange`.

## Review Gate Expectations

The review table should let the user quickly verify:
- which operations are real
- which channels are requests versus replies
- which flows should be split
- which retry and DLQ channels belong to an operation
- where correlation is explicit versus guessed

## Confidence Guidelines

- `high`: direct listener and producer evidence in the same flow, with clear channels and payload types
- `medium`: strong listener or producer evidence, but pairing or payload shape required heuristics
- `low`: indirect evidence from config or naming only; user confirmation is mandatory
