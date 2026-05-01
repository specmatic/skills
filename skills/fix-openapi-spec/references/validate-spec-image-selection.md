# Validate Spec Docker Setup

Source of truth for Specmatic Docker image and license setup in:

- `scripts/validate_spec.sh`
- `scripts/validate_spec.ps1`

Keep both script implementations in sync with this reference and with each other.

## Required Flow

1. Confirm the `docker` command is available before resolving the image.
2. If `SPECMATIC_DOCKER_IMAGE` is set, treat it as the only candidate.
3. For a user-provided candidate, require the image to exist locally through `docker image inspect`.
4. If no image was provided, look for the first local Docker image whose repository or tag contains `specmatic`, excluding `<none>:<none>`.
5. If a local image is found, tell the user which image is being used and use that exact image for validation.
6. Do not pre-validate the image with `--version` and do not infer image validity from Specmatic command output.
7. If no local `specmatic` image exists, tell the user the workflow is trying to pull `specmatic/enterprise:latest`.
8. If the pull succeeds, use `specmatic/enterprise:latest` for validation.
9. If the pull fails, tell the user:
   **Action Required:** I could not find a usable local Specmatic Enterprise image and pulling `specmatic/enterprise:latest` failed. Please pull the image yourself, then tell me the image name so I can continue validation.

## License Setup

1. After resolving the Docker image, look for a license file under the user home `.specmatic` directory.
2. Only two license file names are considered: `specmatic-license.txt` and `license.json`.
3. If a license is found, copy it into `<spec-dir>/.specmatic/<license-file-name>`.
4. If a license is found, generate validation config with `specmatic.license.path: /usr/src/app/.specmatic/<license-file-name>`.
5. If a license is found, mount `<spec-dir>/.specmatic` into Docker at `/usr/src/app/.specmatic`.
6. If no license is found, omit `specmatic.license` and continue validation without failing up front.

## Validation Command

Run validation through a generated config piped into Docker:

`cat > /tmp/specmatic.yaml && specmatic validate --config /tmp/specmatic.yaml`
