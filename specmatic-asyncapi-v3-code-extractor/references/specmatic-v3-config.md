# Specmatic Config V3 Guidance

This skill should generate Specmatic config version 3 by default.

## Required Direction

The generated config should align with the SchemaStore-backed Specmatic schema at `https://json.schemastore.org/specmatic.json`.

For config-shape errors:
- use SchemaStore as the source of truth
- make fixes from the schema validation error and the schema definition itself
- do not inspect local Specmatic implementation files to guess missing fields or structure

Local Specmatic runtime behavior is still relevant for execution, but not for deciding the valid schema shape of `specmatic.yaml`.

## Expected Shape

The generated config should include:

- `version: 3`
- `systemUnderTest.service.definitions`
- `systemUnderTest.service.runOptions.asyncapi.type: test`
- `systemUnderTest.service.data.examples.directories`
- `components.sources`
- `components.services`
- `components.runOptions`
- `dependencies.services` only when downstream mocks or support services are needed
- `schemaRegistry` only when Avro evidence exists
- `servers` under async `runOptions`

## Design Intent

- keep generated config self-contained
- point all definitions to generated specs
- point example directories to generated examples
- avoid mutating app-owned config
- prefer one generated system-under-test service unless there is strong evidence for multiple distinct async services

## Avro

Emit `schemaRegistry` only when the codebase shows real Avro or schema registry evidence:
- schema registry URLs or config
- references to `schema.registry.url`
- explicit Avro payload annotations or serializers
- `.avsc` or registry-backed schema refs used by the app
