# Validate Spec Docker Setup

Source of truth for Specmatic Docker image and license setup in:

- `scripts/validate_spec.sh`
- `scripts/validate_spec.ps1`

Keep both script implementations in sync with this reference and with each other.

## Required Flow

1. Confirm the `docker` command is available before resolving the image.
2. If `SPECMATIC_DOCKER_IMAGE` is set, treat it as the only candidate.
3. For a user-provided candidate, require the image to exist locally through `docker image inspect`.
4. If no image was provided, look for the latest local Docker image whose repository or tag contains `specmatic`, excluding `<none>:<none>`.
5. Determine "latest" by Docker image creation time descending. If multiple matching references point at images with the same creation timestamp, pick the lexicographically smallest `<repository>:<tag>` as the stable tie-breaker.
6. If a local image is found, tell the user which image is being used and use that exact image for validation.
7. Do not pre-validate the image with `--version` and do not infer image validity from Specmatic command output.
8. If no local `specmatic` image exists, tell the user the workflow is trying to pull `specmatic/enterprise:latest`.
9. If the pull succeeds, use `specmatic/enterprise:latest` for validation.
10. If the pull fails, tell the user:
   **Action Required:** I could not find a usable local Specmatic Enterprise image and pulling `specmatic/enterprise:latest` failed. Please pull the image yourself, then tell me the image name so I can continue validation.

## License Setup

1. After resolving the Docker image, check whether the user home `.specmatic` directory exists.
2. If the directory exists, mount it into Docker at `/root/.specmatic`.
3. Do not copy license files into the spec directory.
4. Do not generate `specmatic.license.path`; let Specmatic discover the license from `/root/.specmatic`.
5. If the directory does not exist, continue validation without failing up front.

## Validation Command

Run validation through a generated config piped into Docker:

`cat > /tmp/specmatic.yaml && specmatic validate --config /tmp/specmatic.yaml`
