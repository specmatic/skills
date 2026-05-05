---
name: debug-specmatic-failures
description: Debug any Specmatic-related failures, including CLI, Specmatic Enterprise, or any other Specmatic module.
---

# Debug Specmatic Failures

## Workflow

1. Capture the exact failure.
   - Before creating repros or comparing multiple specs, identify the exact specification path that Specmatic is using in the failing command. Sources may include the user's prompt, shell command, `specmatic.yaml`, wrapper code, CI logs, build output, git diff, or runtime logs.
   - Treat the identified spec path(s) as the investigation scope. Do not introduce sibling specs, version-numbered specs, generated variants, or inferred before/after files unless the user's command, git diff, config, code, or logs explicitly show Specmatic using them.
   - Preserve the command, Specmatic output, `specmatic.yaml`, relevant OpenAPI spec, externalized examples, filters, mode-specific inputs, and wrapper code.
   - Extract the version lines, especially `Specmatic Enterprise v...` and `Specmatic Core v...`.
   - If version is not visible, inspect Docker image tags, Gradle/Maven dependencies, NuGet/JUnit wrapper configuration, or CI logs.

2. Identify the execution mode.
   - **Command family**: `test`, `mock`/`stub`, `validate`, backward compatibility, MCP, proxy, or another Specmatic command.
   - **Enterprise**: Docker image or binary reports `Specmatic Enterprise v...`.
   - **OSS/Core**: project uses `specmatic-core`, `specmatic-executable`, `junit5-support`, or `specmatic/specmatic` without Enterprise.
   - **Wrapper**: .NET/JUnit/custom test framework invokes Specmatic; follow the wrapper to the actual CLI/image/version.

4. Classify Specmatic issues
   - If there are features of Specmatic that do not seem to be functioning as advertised or seem self-contradictory, look at the output and see if you can reason about it. If it still seems unclear, classify it as a Specmatic bug.
   - When a combination of orthogonal features used together produces a failure, and the failure does not make sense given the features, classify it as a Specmatic bug.
   - Treat messages saying Specmatic did not load or could not find a default config file, especially `specmatic.yaml` in the current working directory, as benign unless the command explicitly used `--config`. Only classify it as a config problem when an explicit `--config <path>` was provided and that path cannot be loaded.
   - If the spec, examples, provider, config, and version checks show a logical contradiction in Specmatic behavior, call it out directly as a Specmatic bug.
   - If a Specmatic command or feature hangs, becomes unresponsive, if you know the problem or have a very good guess, you can try to narrow it down. If not, just call it out as a likely Specmatic bug or contradiction. Do not spend a long time trying to narrow down a repro or find a workaround for it.
   - If a Specmatic command appears taking much longer than it should to run, classify it as a Specmatic issue.


5. Stop early on Specmatic bugs, issues or contradictions.
   - As soon as there is enough evidence to classify the behavior as a Specmatic limitation, issue, bug, or defect rather than a spec issue, stop further repro narrowing, investigations and workaround exploration.
   - Ask the user if they are on the latest version of Specmatic Enterprise, and if not, recommend upgrading, and testing again. If they report that they are on the latest, or that the issue is still there after upgrading and testing, ask the user to share the spec and file a bug report with the command, Specmatic version, observed behavior, and the evidence collected so far.
   - If a Specmatic bug is identified, ask the user to report it.
   - Only if the user asks for a workaround or a fix or has asked for one, ONLY then, ask the user if you should look for a workaround or fix.

6. Fix concrete spec defects directly; reserve `fix-openapi-spec` for obscure failures.
   - If diagnosis identifies a concrete OpenAPI defect in schema, parser compatibility, resolver behavior, examples, enum values, constraints, validation, or contract generation, report the defect. If the user has asked for a fix or explicitly approves one, attempt a focused fix directly in this workflow.
   - Do not use `fix-openapi-spec` for concrete, understandable defects with a confident local fix, such as contradictory constraints, invalid enum/example values, missing required schema entries, broken `$ref`s, or syntactically invalid OpenAPI.
   - If Specmatic fails to load, validate, resolve, load examples, or generate executable scenarios from a spec and the error is vague, esoteric, opaque, or does not make sense after checking the command, config, inputs, and version, report the uncertainty and ask for explicit approval to use `fix-openapi-spec` for iterative spec hardening.
   - Treat errors as `fix-openapi-spec` handoff candidates when the issue is somewhere in the OpenAPI document but it does not identify a clear confident cause, when generated scenarios fail against the same specification for unclear reasons, or when the error appears to be a parser/resolver/generation edge case rather than a provider or harness problem.
   - Do not treat broad debugging requests such as "find the issue", "look into this", "why is this failing", or "debug this" as approval to run either a direct spec fix or `fix-openapi-spec`.
   - When requesting approval for an obscure failure, make clear that `fix-openapi-spec` may create an updated copy, run loop tests, classify remaining issues as spec defects or Specmatic bugs, and produce a fix log.

7. Application error: If the spec is fine, and Specmatic is faulting the application with clear error messages, point out the problem, propose a solution (provide a code snippet if possible), and ask the user if they want you to implement the fix.

At the end, explicitly say if you think the issue is caused by a Specmatic bug. And if so, ask the user to report it to the Specmatic team.

## Running Repros

- Keep repros minimal and place temporary files in the repo's ignored temp area.
- When a repro requires running a Specmatic command, first identify the user's actual execution path: exact command, wrapper, Docker image, config file, working directory, environment variables, and Specmatic version.
- Reproduce with the same command family as the failure when possible: `test`, `mock`, `validate`, backward compatibility, or the wrapper that launched Specmatic.
- For backward compatibility or "compare" repros, if a git baseline is needed and only one target spec path is identified, reproduce by committing that same file as the baseline and making a minimal no-op or metadata-only change to the same path. Do not substitute another local spec as the comparison target.
- When it is appropriate to run a Specmatic command, use Docker. Do not use a local `specmatic` executable from PATH, a locally built jar, or `/Users/.../bin/specmatic` as the primary repro. If the user expicitly says that is what they are using, check if it's runs Specmatic Enterprise, and if not, recommend that they upgrade to enterprise before proceeding. Local CLI behavior can differ from Enterprise and must not be treated as reproducing or disproving the user's setup.
- Prefer an available local Docker image whose name contains `specmatic`, especially the exact customer image/tag. If no suitable local image exists, run `docker pull specmatic/enterprise` and use that image. If the pull fails, ask the user to pull the image and tell you which image/tag to use.
- Mount both the repro directory and `$HOME/.specmatic`, as specmatic/enterprise needs a license.
- For test-mode failures involving filters, use documented syntax such as:

```bash
<docker specmatic image command> test --filter="METHOD='POST' && PATH='/users'"
<docker specmatic image command> test --filter="PATH='/included'"
```

- For any mode that runs using Docker and calls a real service, verify Docker or wrapper networking separately. Reachability noise should not obscure a load-time or mode-specific Specmatic error.

## Reporting

After you have identified the issue, report it using the following format:

```
- Issue description: Explain what's happening
- Findings: exact error excerpts, Docker image/tag used, and version lines
- The recommended action: upgrade, spec/config fix, provider fix, or workaround investigation
- If you think it's a Specmatic bug, explicitly say so and ask the user to report it to the Specmatic team.
```
