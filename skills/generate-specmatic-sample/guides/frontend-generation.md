# Frontend Generation Guide

Frontend samples do not provide a provider contract. They implement client
workflows that consume the Product and Order BFF contract through a configurable
base URL, service endpoint, or broker. Exact consumed protocol behavior,
schemas, examples, content types, statuses/errors, messages, and metadata must
be verified against the executable contract referenced by `specmatic.yaml`.

## Role-Specific Requirements

- Client application with create product, find available products, and create
  order workflows.
- Configurable BFF base URL, service endpoint, or broker settings.
- Client module for BFF calls, GraphQL operations, RPC calls, SOAP calls, or
  messages.
- Contract consumption tests using a Specmatic mock/stub of the BFF contract.

## Implementation Notes

- Send every request header, query parameter, metadata field, message header,
  or SOAP header declared by the BFF executable contract for each call (for
  example idempotency, auth, pagination). Do not hardcode names the contract
  does not declare.
- Keep BFF endpoint/broker configuration environment-specific.
- Before coding the client module, build a consumed-operation summary from
  the BFF executable contract that records each workflow's method/path/topic/RPC
  method/GraphQL field/SOAP action, parameters, request body/message, response
  shape, content type, metadata, and security needs.
- Create product calls the BFF product creation operation.
- Find available products calls the BFF product search operation with the
  parameters the contract declares for that operation.
- Create order calls the BFF order creation operation.
- Do not re-create schema definitions from markdown; read exact request,
  response, message, and error fields from the executable contract or Specmatic
  report output.
