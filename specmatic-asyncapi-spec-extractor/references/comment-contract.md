# Comment Contract

The extractor reads JSON payloads from comment blocks delimited by:

- `@specmatic-asyncapi`
- `@end-specmatic-asyncapi`

Any common line comment prefix is allowed as long as every JSON line stays commented:

- `#`
- `//`
- `/* ... */`
- `*`
- `--`

## Operation Block

Place operation blocks near:

- consumer/listener/subscriber methods
- standalone publisher/send code

The skill may synthesize these blocks into `specmatic-asyncapi.generated.annotations.txt` when they do not already exist in source comments. That synthesized annotation layer is maintained by the extractor and may be refined across feedback-loop retries.

Schema:

```json
{
  "kind": "operation",
  "role": "consumer",
  "operationId": "placeOrder",
  "channel": {
    "name": "NewOrderPlaced",
    "address": "new-orders"
  },
  "message": "OrderRequest",
  "example": {
    "name": "NEW_ORDER",
    "id": "new-order",
    "payload": {
      "id": 10
    },
    "headers": {
      "orderCorrelationId": "12345"
    },
    "key": 10
  },
  "replies": [
    {
      "operationId": "placeOrderWip",
      "channel": {
        "name": "OrderInitiated",
        "address": "wip-orders"
      },
      "message": "Order",
      "example": {
        "payload": {
          "id": 10,
          "status": "INITIATED"
        },
        "headers": {
          "orderCorrelationId": "12345"
        },
        "key": 10
      }
    }
  ]
}
```

Required fields:

- `kind`: must be `operation`
- `role`: `consumer` or `publisher`
- `operationId`
- `channel.name`
- `channel.address`
- `message`: message component name
- `example.payload`

Additional rules:

- `consumer` may omit `replies` to become `receive-only`
- `consumer.replies` emits one `receive-reply` operation per reply entry
- `publisher` must not define `replies`; it becomes `send-only`
- `example.headers` and `example.key` are optional
- `example.before` and `example.after` are optional fixture arrays copied into generated externalised examples
- `reply.operationId` is optional; when omitted the extractor derives one from the base operation and reply channel

### Fixture-capable example blocks

Use `before` and `after` when contract tests need setup or side-effect verification:

```json
{
  "payload": { "id": 123 },
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
        "path": "/orders/123",
        "method": "GET"
      },
      "http-response": {
        "status": 200
      }
    }
  ]
}
```

The extractor copies these fixtures only into generated examples. The feedback loop may refine the generated copies later, but it must never write fixture changes back into checked-in app config or checked-in Avro schemas.

## Message Block

Place message blocks near DTO/message classes or schema-owning code.

The skill may also synthesize message blocks into `specmatic-asyncapi.generated.annotations.txt` when it can infer them from code, Avro files, broker config, or prior loop feedback.

```json
{
  "kind": "message",
  "name": "OrderRequest",
  "title": "An order request",
  "contentType": "application/json",
  "payloadSchema": {
    "type": "object",
    "required": ["id"],
    "properties": {
      "id": {
        "type": "integer"
      }
    }
  },
  "headersSchema": {
    "type": "object",
    "properties": {
      "orderCorrelationId": {
        "type": "string"
      }
    }
  },
  "correlationId": {
    "id": "orderCorrelationId",
    "location": "$message.header#/orderCorrelationId"
  },
  "bindings": {
    "kafka": {
      "key": {
        "type": "integer"
      }
    }
  }
}
```

Required fields:

- `kind`: must be `message`
- `name`
- payload definition, using either `payloadSchema` for JSON-style schemas or `avro` for Avro-backed schemas

Optional fields:

- `title`
- `contentType`
- `headersSchema`
- `correlationId.id`
- `correlationId.location`
- `bindings`

### JSON / inline-schema messages

Use:

- `contentType`
- `payloadSchema`

Example:

```json
{
  "kind": "message",
  "name": "OrderRequest",
  "contentType": "application/json",
  "payloadSchema": {
    "type": "object",
    "properties": {
      "id": {
        "type": "integer"
      }
    }
  }
}
```

### Avro-backed messages

Use an `avro` block instead of `payloadSchema`.

```json
{
  "kind": "message",
  "name": "OrderRequest",
  "title": "An order request",
  "avro": {
    "source": "auto",
    "file": "src/main/avro/NewOrders.avsc",
    "subject": "new-orders-value",
    "version": "1"
  }
}
```

Supported `avro.source` values:

- `auto`: let the extractor choose between local `.avsc` and schema-registry style based on repo evidence plus any provided hints
- `file`: emit a local file `$ref`
- `registry`: emit a placeholder registry `$ref`

Rules:

- Avro messages must not inline the Avro schema into AsyncAPI
- the extractor sets `schemaFormat` to `application/vnd.apache.avro+json;version=1.9.0`
- when using file refs, the extractor prefers a checked-in `.avsc`
- when using registry refs, the extractor emits:

```yaml
payload:
  schemaFormat: application/vnd.apache.avro+json;version=1.9.0
  schema:
    $ref: '<SCHEMA_REGISTRY_URL>/subjects/<subject>/versions/<version>/schema'
```

- any discovered concrete registry base URL is treated only as evidence that a registry is in use; the generated spec still uses the placeholder base unless the user explicitly asks otherwise
- if `file`, `subject`, or `version` are omitted, the extractor may infer them from `.avsc` files, schema registration scripts, serializer/deserializer config, or schema-registry URL patterns in the repo

Additional optional Avro fields:

- `title`
- `avro.file`
- `avro.subject`
- `avro.version`
- `avro.ref`

## Overlay Boundary

Use the annotation layer for source-derived facts:

- operations
- channels
- messages
- payload examples
- `before` and `after` fixture seeds

Use the generated overlay file for loop-local or spec-only fixes that should not be pushed back into annotations:

- timeout-related spec adjustments
- loop-only contract corrections
- extensions such as `x-specmatic-*` metadata that do not represent source truth

## Overlay Boundary

Use annotations for source-derived facts:

- operations
- channels
- messages
- examples
- fixture seeds

Use the generated overlay file for spec-only or loop-only corrections that do not belong in the annotation layer.

## Validation Rules

- Every discovered consumer candidate must have a nearby `role: consumer` block.
- Every standalone publisher candidate must have a nearby `role: publisher` block.
- Every referenced message must have a corresponding message block.
- Every emitted operation must be able to generate a valid externalised example.
- Missing or conflicting metadata is fatal.
