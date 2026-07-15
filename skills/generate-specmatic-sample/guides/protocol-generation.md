# Protocol Generation Guide

Use this guide after resolving the executable contract source from the
user-provided repo/spec path or the checked-in `specmatic.yaml`. The executable
contract and Specmatic output remain the final source of truth for every
protocol.

## Contract Format Detection

Detect the contract format from parsed content first, using file extension only
as fallback evidence:

- OpenAPI: top-level `openapi`, implemented as HTTP routes/controllers.
- AsyncAPI: top-level `asyncapi`, implemented as broker/message handlers unless
  the resolved contract declares another transport.
- Protobuf/gRPC: `.proto` syntax, package, service, and rpc declarations.
- GraphQL SDL: schema, type, query, mutation, or subscription SDL.
- WSDL/SOAP: XML WSDL definitions, bindings, services, and SOAP metadata.

Reject only combinations that are incoherent for the detected format. For
example, a browser-only frontend can consume GraphQL or HTTP APIs directly, but
should not be generated as a native gRPC server unless the stack includes a
gRPC-web or gateway layer.

## Required Contract Facts

OpenAPI and WSDL:

- operations/actions, transport endpoint, request body, headers, query/path
  parameters, response status, response body, content type, and security.
- imported schemas, external examples, and dependency mock expectations.

AsyncAPI:

- channel/topic names, operation direction, message key, headers, payload
  schema, examples, correlation IDs, reply channels, server/broker settings,
  and whether the flow is fire-and-forget or request-reply.
- producer and consumer responsibilities for the selected application type.
- in-memory broker or external broker settings needed by Specmatic.

Protobuf/gRPC:

- package, service, full method names, unary/server-stream/client-stream/bidi
  call type, request/response messages, status/error examples, metadata, import
  paths, protoc version, and request timeout.
- generated server interface and client stub requirements for the chosen
  language/framework.

GraphQL SDL:

- schema entrypoints, query/mutation/subscription fields, arguments, required
  fields, scalar/enums/input/object types, response selection sets, variables,
  example directories, and HTTP headers declared through examples.
- generated resolver behavior and dependency client calls for each workflow.

SOAP/WSDL:

- service, port, binding, SOAP action, operation input/output messages, XML
  namespaces, headers, fault messages, imported XSDs, and endpoint URL.
- generated SOAP server/client bindings and XML serialization settings.

## Generation Rules

- Generate protocol-native app code: routes for OpenAPI, message handlers for
  AsyncAPI, gRPC services for Protobuf, resolvers for GraphQL, and SOAP
  handlers for WSDL.
- For BFF and Frontend samples, compare consumer-facing and dependency
  contracts before coding. Record the required mapping between operations,
  message shapes, metadata/headers, topics/endpoints, status/errors, and
  security.
- For every protocol, use the documented Specmatic Enterprise Docker image or
  language artifact in generated tests and CI, and document the license/setup
  requirement in the generated README.
- Keep all protocol endpoints, base URLs, broker URLs, ports, import paths, and
  example directories configurable through environment variables or generated
  config.
