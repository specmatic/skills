## Installation

Run the following command to install any skill from this repository in codex:
```bash
npx skills add git@github.com:specmatic/specmatic-skills.git -a codex
```

Note: Use the `https` based github link if `ssh` is not set up in your machine.

## Uninstallation

```bash
npx skills remove specmatic-openapi-spec-extractor -g
```

Replace the skill name with the one you want to uninstall.
Use `-g` flag if you want to uninstall the skill installed at global level. Do not use it if it is installed at project level.
