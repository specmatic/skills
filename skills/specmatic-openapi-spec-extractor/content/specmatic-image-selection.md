# Specmatic Enterprise Image Selection

Use this flow whenever the skill needs a Docker image for Specmatic Enterprise.

## Required Flow

1. Look for the first local Docker image whose repository or tag contains `specmatic`.
2. If one exists, tell the user that this local image is being used and use that exact image directly for the workflow.
3. Do not pre-validate the image with `--version` and do not infer validity from Specmatic command output.
4. If no local `specmatic` image exists, tell the user that the workflow is trying to pull `specmatic/enterprise:latest` from Docker Hub.
5. If the pull succeeds, use `specmatic/enterprise:latest` directly for the workflow.
6. If the pull fails, tell the user exactly:
   `**Action Required:** I could not find a usable local Specmatic Enterprise image and pulling \`specmatic/enterprise:latest\` failed. Please pull the image yourself, then tell me the image name so I can continue the feedback loop.`

## Notes

- Do not use temporary retagging such as `specmatic/enterprise:agent-temp` if deterministic behavior can be achieved by resolving a concrete image name directly.
- If the user explicitly provides an image name, treat that as the first candidate.
- Once a concrete enterprise image name is resolved, use that exact image name consistently for `validate`, `stub`, and `test` commands in the current workflow.
