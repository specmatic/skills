# Specmatic Enterprise Image Selection

Use this flow whenever the skill needs a Docker image for Specmatic Enterprise.

## Required Flow

1. Look for the latest local Docker image whose repository or tag contains `specmatic`, excluding `<none>:<none>`.
2. Determine "latest" by Docker image creation time descending. If multiple matching references point at images with the same creation timestamp, pick the lexicographically smallest `<repository>:<tag>` as the stable tie-breaker.
3. If one exists, tell the user that this local image is being used and use that exact image directly for the workflow.
4. Do not pre-validate the image with `--version` and do not infer validity from Specmatic command output.
5. If no local `specmatic` image exists, tell the user that the workflow is trying to pull `specmatic/enterprise:latest` from Docker Hub.
6. If the pull succeeds, use `specmatic/enterprise:latest` directly for the workflow.
7. If the pull fails, tell the user exactly:
   `**Action Required:** I could not find a usable local Specmatic Enterprise image and pulling \`specmatic/enterprise:latest\` failed. Please pull the image yourself, then tell me the image name so I can continue the feedback loop.`

## Notes

- Do not use temporary retagging such as `specmatic/enterprise:agent-temp` if deterministic behavior can be achieved by resolving a concrete image name directly.
- If the user explicitly provides an image name, treat that as the first candidate.
- Once a concrete enterprise image name is resolved, use that exact image name consistently for `validate`, `stub`, and `test` commands in the current workflow.
