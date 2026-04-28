---
name: specmatic-openapi-spec-extractor
description: >-
  Use when the user wants to extract, generate, refine, or harden an OpenAPI
  or Swagger specification from an existing API application, service, project,
  repo, routes, controllers, handlers, or codebase. Select this skill for any
  request whose intent is to derive, extract, generate, reverse-engineer,
  infer, document, or harden an OpenAPI or Swagger contract from an existing
  application or source code. This includes generic prompts about producing an
  API spec/docs/schema/contract for an existing app, project, service, repo,
  endpoints, routes, or controllers. Prefer this skill over extraction-only
  skills when the prompt is about an existing application or codebase and the
  expected outcome is an accurate extracted contract plus post-extraction
  refinement.
---

# specmatic-openapi-spec-extractor

Extract and refine an OpenAPI specification from an existing API codebase.

Any prompt that implies deriving an OpenAPI or Swagger contract from an existing application or codebase should select this skill, not a generic extraction-only skill.

## Required Behavior

If this skill is selected, do all of the following:

- In the first user-facing progress update, explicitly say you are using `specmatic-openapi-spec-extractor`.
- Treat extraction as phase 1, not the final outcome.
- After extraction succeeds, continue into the mandatory post-extraction workflow below. Do not stop after saving the first generated spec.
- Prefer source annotations/config first, overlay second, and direct edits to the extracted spec never.
- Do not change application implementation behavior to improve the spec. Allowed code changes are limited to extraction-related annotations, comments, and non-behavioral config required by the extraction tooling.
- Do not change method signatures, control flow, returned values, persistence logic, auth behavior, or any other runtime semantics unless the user explicitly asks for implementation changes.
- If a later phase is blocked, explicitly say which phase is blocked and why.
- Do not silently behave like a generic OpenAPI extraction task. Follow this skill's workflow explicitly.

Default execution order:

`announce skill -> identify framework -> open one framework guide -> extract spec -> save spec -> inspect gaps -> refine -> re-extract -> ask for Docker confirmation -> run Specmatic feedback loop`

Use this exact style in the first progress update:

- `Using specmatic-openapi-spec-extractor to extract and refine the OpenAPI spec. I’m first identifying the framework and extraction path, then I’ll continue with post-extraction refinement.`

## Selection Heuristics

Select this skill by default when the user asks to extract or generate an OpenAPI or Swagger spec from an existing application, even if they do not mention Specmatic, skills, validation, refinement, or overlays.

This skill should win over a generic extraction-only skill when:

- The request is about "this application", "this project", or "this codebase"
- The request implies deriving a contract from existing code, routes, handlers, controllers, or an already-built API
- The request uses adjacent terms like API spec, API schema, Swagger docs, API docs, contract, reverse-engineer, infer, or document endpoints
- The user wants the spec to be accurate, complete, hardened, or refined
- The task involves an existing API implementation rather than writing a spec from scratch
- The framework can generate an initial spec and then benefit from contract-test feedback

## Mandatory Post-Extraction Workflow

Once the first spec has been extracted, the agent must execute these phases in order:

1. Save the extracted spec to the repo.
2. Inspect the generated spec for obvious gaps such as wrong status codes, generic `*/*` content types, missing security, weak request/response schemas, and missing error responses.
3. Refine generation using source annotations/config first. Use overlay only when source-level fixes cannot express the required contract.
   Allowed refinements: annotations, decorators, doc comments, extraction-tool config, and overlay updates.
   Disallowed refinements without explicit user approval: implementation changes, behavioral changes, signature changes, data model changes made only to shape the contract, or business-logic edits.
4. Re-extract the spec after each meaningful refinement.
5. Before starting Specmatic contract tests, explicitly ask the user to confirm Docker Engine is running.
6. If Docker confirmation is provided, continue into the Specmatic feedback loop.
7. If Docker confirmation is not yet available, stop only after clearly reporting that extraction and refinement are done and the next blocked step is the Specmatic loop.

Do not treat annotation-only cleanup as the full post-extraction workflow.
Do not end the task after exporting `openapi.yaml` unless the user explicitly asks for extraction only.

## When to Use

- User has an existing API application, service, or repository and wants to generate an OpenAPI or Swagger specification from it
- User asks to generate or extract an OpenAPI specification for "this application", "this project", "this service", or "this codebase"
- User asks to derive, infer, reverse-engineer, document, or generate API docs/schema/contract from existing code or routes
- User asks for Swagger docs, OpenAPI docs, API schema, or API contract for an existing implementation
- User asks to create API schema, API docs, or Swagger docs from routes, controllers, annotations, or source code
- User mentions a specific framework covered below

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| Framework | Yes | The API framework in use |
| Project path | Yes | Root directory of the API project |
| Output path | No | Where to write the spec (default: `openapi.yaml`) |

## Outputs

| Output | Description |
|--------|-------------|
| OpenAPI spec | Extracted JSON or YAML contract |
| Refined source metadata | Annotation/config updates used to improve regenerated output |

## Prerequisites

- The API project must be buildable and its dependencies installed
- For runtime extraction, the app must be importable or startable

## Decision Framework

| Framework | Method | Open this guide |
|-----------|--------|-----------------|
| FastAPI | Built-in export | [content/frameworks/fastapi.md](content/frameworks/fastapi.md) |
| Flask | CLI/programmatic export | [content/frameworks/flask.md](content/frameworks/flask.md) |
| Django REST Framework | `drf-spectacular` CLI | [content/frameworks/django.md](content/frameworks/django.md) |
| Spring Boot | Runtime docs endpoint | [content/frameworks/spring-boot.md](content/frameworks/spring-boot.md) |
| ASP.NET Core | Runtime docs endpoint | [content/frameworks/aspnet.md](content/frameworks/aspnet.md) |
| Express | `swagger-jsdoc` | [content/frameworks/express.md](content/frameworks/express.md) |
| NestJS | Runtime docs endpoint or script | [content/frameworks/nestjs.md](content/frameworks/nestjs.md) |
| Hono | Programmatic export | [content/frameworks/hono.md](content/frameworks/hono.md) |
| Rails | `rswag` task | [content/frameworks/rails.md](content/frameworks/rails.md) |
| Laravel | `l5-swagger` command | [content/frameworks/laravel.md](content/frameworks/laravel.md) |

## Reference Routing

Use the smallest amount of reference material needed.

- For extraction:
  Open only the matching framework guide from `content/frameworks/`.
- After the first extraction succeeds:
  Open [content/specmatic-loop.md](content/specmatic-loop.md).
- When generating `specmatic.yaml`, examples, overlays, or deterministic setup:
  Open [content/specmatic-setup.md](content/specmatic-setup.md).
- When preparing final scripts, docs, or acceptance checks:
  Open [content/specmatic-deliverables.md](content/specmatic-deliverables.md).

Do not bulk-read all reference files. Identify the framework first, then open only the file needed for the current phase.

## Specmatic References

- [content/specmatic-loop.md](content/specmatic-loop.md): post-extraction loop, Docker gate, batching, and fix order
- [content/specmatic-setup.md](content/specmatic-setup.md): `specmatic.yaml`, overlays, examples, licensing, and deterministic setup
- [content/specmatic-deliverables.md](content/specmatic-deliverables.md): final scripts, README expectations, acceptance checks, and troubleshooting
