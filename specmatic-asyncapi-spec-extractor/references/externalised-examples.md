# Externalised Examples

Use this reference when generating or repairing Specmatic externalised example files.

Schema reference:

- [references/externalised-example.schema.json](externalised-example.schema.json)

When generating or repairing examples, treat that schema as the machine-readable source of truth for supported top-level keys and payload-envelope keys.

## Required Top-Level Shape

Each example file is one JSON object.

Required field:

- `name`

At least one of these must be present:

- `receive`
- `send`

Optional top-level fields:

- `id`
- `retry`
- `dlq`
- `before`
- `after`

The async extractor currently generates:

- `receive` for receive-only and receive-reply operations
- `send` for send-only and receive-reply operations
- optional `before` and `after` fixture arrays
- optional `id`

## Payload Block Shape

Each of `receive`, `send`, `retry`, and `dlq` uses the same payload structure:

```json
{
  "topic": "new-orders",
  "payload": {
    "id": 10
  },
  "headers": {
    "orderCorrelationId": "12345"
  },
  "key": 10
}
```

Required field:

- `topic`
- `payload`

Optional fields:

- `headers`
- `key`

## Canonical Example Patterns

Receive-only:

```json
{
  "name": "NEW_ORDER",
  "id": "new-order",
  "receive": {
    "topic": "new-orders",
    "payload": {
      "id": 10
    },
    "headers": {
      "orderCorrelationId": "12345"
    }
  }
}
```

Send-only:

```json
{
  "name": "ORDER_INITIATED",
  "send": {
    "topic": "wip-orders",
    "payload": {
      "id": 10,
      "status": "INITIATED"
    }
  }
}
```

Receive-reply:

```json
{
  "name": "NEW_ORDER",
  "id": "new-order",
  "receive": {
    "topic": "new-orders",
    "payload": {
      "id": 10
    }
  },
  "send": {
    "topic": "wip-orders",
    "payload": {
      "id": 10,
      "status": "INITIATED"
    }
  }
}
```

## Fixtures

`before` and `after` are top-level arrays, not nested inside `receive` or `send`.

Use them when:

- a message flow requires HTTP or DB setup before publishing or consuming
- a side effect must be verified after a message exchange
- the feedback loop needs extra setup or assertion steps to make the contract test meaningful

Pattern:

```json
{
  "name": "NEW_ORDER",
  "receive": {
    "topic": "new-orders",
    "payload": {
      "id": 10
    }
  },
  "before": [
    {
      "type": "http",
      "wait": "PT1S",
      "http-request": {
        "baseUrl": "http://localhost:8080",
        "path": "/orders",
        "method": "PUT"
      },
      "http-response": {
        "status": 200
      }
    }
  ],
  "after": [
    {
      "type": "http",
      "http-request": {
        "baseUrl": "http://localhost:8080",
        "path": "/orders/10",
        "method": "GET"
      },
      "http-response": {
        "status": 200
      }
    }
  ]
}
```

## Generation Rules

- Every generated file must contain `name`.
- Every generated file must contain at least one of `receive` or `send`.
- Use the channel address in `topic`.
- Put message bodies in `payload`.
- Copy headers only when present or required by the contract.
- Copy keys only when meaningful and discoverable.
- Keep `before` and `after` at the top level.
- Do not invent `retry` or `dlq` unless the codebase or annotations actually support them.

## Sample References

Use these sample files as concrete shape references:

- `../sample-projects/specmatic-kafka-sample-asyncapi3/examples/async-order-service/newOrder.json`
- `../sample-projects/specmatic-async-sample/examples/newOrder.json`

## Validation Reminder

An example is invalid if it contains neither `receive` nor `send`. The extractor and feedback loop should treat that as a contract artifact error, not an implementation bug.

Use the schema file to remember the exact supported keys and the minimal required structure:

- top level requires `name`
- top level requires at least one of `receive` or `send`
- each message envelope requires `topic` and `payload`
