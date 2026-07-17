# Backend Generation Guide

Backend samples provide the Products and Orders capability for the selected
protocol and consume an Inventory boundary when creating products, reading
products, and creating orders. Exact protocol behavior, schemas, examples,
content types, statuses/errors, messages, and metadata must be verified against
the executable contract referenced by `specmatic.yaml`.

## Role-Specific Requirements

- Source code implementing Products and Orders endpoints, services, resolvers,
  SOAP handlers, or message handlers for the selected protocol.
- In-memory product/order store seeded from `test-data/backend-seed-data.md`.
- Inventory client boundary with an in-memory implementation for local tests unless the stack selection says otherwise.

## Implementation Notes

- Keep product persistence separate from inventory count lookup.
- Create product calls Inventory `addInventory`.
- Read product calls Inventory `getInventory`.
- Create order calls Inventory `reduceInventory`.
- Accept every request header, metadata field, SOAP header, GraphQL example
  header, or message header the executable contract declares for an operation
  (for example idempotency, auth, pagination). Headers not declared by the
  contract should not be required.
- Authenticated operations should accept the declared credential shape without
  requiring local credential setup.
- Unknown resource reads should return the executable contract's error response
  or protocol-native error.
- Use a multipart parser for product image uploads when an OpenAPI contract
  includes that endpoint.
- Do not re-create schema definitions from markdown; read exact request,
  response, message, and error fields from the executable contract or Specmatic
  report output.
