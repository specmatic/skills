# BFF Generation Guide

The BFF sits between the Frontend and the Backend. It provides the Product and
Order BFF contract without a local database, and it consumes the Backend
Products and Orders contract through a configurable endpoint or broker. Exact
protocol behavior, schemas, examples, content types, statuses/errors, messages,
and metadata must be verified against the executable contracts referenced by
`specmatic.yaml`.

During tests, the Frontend/client calls the BFF, and the BFF calls a Backend
mock/stub started by Specmatic.

## Role-Specific Requirements

- A Specmatic dependency mock/stub for the Backend contract.
- Source code with no local database.
- Backend base URL, service endpoint, or broker settings from configuration
  such as `STUB_URL`.

## Specmatic Requirements

- Use `guides/specmatic-runtime.md` for Specmatic runtime assembly and contract test adapter behavior.
- Configure the BFF contract as the system under test.
- Configure every discovered dependency contract as a Specmatic mock/stub
  dependency. BFF dependencies may include REST backend mocks and broker/message
  mocks such as AsyncAPI/Kafka.
- Start all dependency mocks before running BFF contract tests and always stop
  them afterward.
- Keep mock host, mock port, BFF host, BFF port, Backend base URL, service
  endpoint, broker URL, and protocol-specific settings configurable for tests.

## Implementation Notes

- Forward every request header, query parameter, metadata field, message header,
  or SOAP header declared by both the BFF system-under-test contract and the
  matching Backend dependency contract (for example idempotency, auth,
  pagination). Do not hardcode names that the executable contracts do not
  declare.
- BFF samples have no seed data.
- Implement every endpoint the executable BFF contract declares, including
  monitor or polling endpoints such as `/monitor/{id}`. Do not filter a
  contract-declared path. For endpoint discovery and path-filter syntax, follow
  `guides/specmatic-runtime.md`.

### Dependency boundary integrity

The BFF calls the Backend dependency mock during tests, so it must preserve the
Backend dependency contract. Follow the dependency boundary integrity rules in
`guides/specmatic-runtime.md`: derive the BFF response body from the actual
dependency response, never swallow the dependency call or fabricate payloads, and
make dependency failures visible. The only data a BFF may synthesize is behavior
its own contract defines, such as a monitor or aggregation endpoint. Return only
the status codes the BFF contract declares for an operation; do not add a 4xx/5xx
the contract does not define.

## Endpoint Mapping
- Implement BFF endpoints from the BFF system-under-test contract, then map
  those calls to Backend dependency endpoints from the Backend mock contract.
- Before coding the BFF adapter, build a blocking comparison table across all
  executable dependency contracts. Do not write adapter code until every BFF
  workflow row records its dependency operation/message, path/topic/method/action
  mapping, SUT response statuses, dependency response statuses, status
  translation, request body/message transformation, response body/message
  transformation, query/header/metadata forwarding, security transformation,
  and async publish/send failure handling.
- Use the dependency spec paths the user provided during input collection to
  wire each dependency in `specmatic.yaml`.
- Satisfy Backend dependency security schemes in outbound calls even when the
  BFF contract does not declare the same incoming credential. Use a sample
  credential value only to satisfy the mock contract shape.
- Do not assume BFF requests and Backend requests have identical paths, topics,
  RPC methods, GraphQL fields, SOAP actions, required fields, status codes,
  headers, metadata, content types, or response schemas.
- When the contracts differ, implement the smallest adapter transformation
  required by the executable contracts and verify it with Specmatic.
- Preserve request headers, query parameters, metadata, and message headers
  needed by either contract.
- Do not re-create schema definitions from markdown; read exact request,
  response, message, and error fields from the executable contracts or
  Specmatic report output.
