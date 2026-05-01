[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$SpecFile,

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Show-Usage {
    @"
Usage: ./validate_spec.ps1 <spec-file.[yaml|yml|json]>

Runs Specmatic validation for the given OpenAPI spec.

Options:
  --help    Show this help message and exit
"@
}

if ($SpecFile -eq "--help" -or $RemainingArgs -contains "--help") {
    Show-Usage
    exit 0
}

if (-not $SpecFile -or $RemainingArgs.Count -gt 0) {
    [Console]::Error.WriteLine((Show-Usage))
    exit 2
}

$UserSpecifiedSpecmaticImage = if ($env:SPECMATIC_DOCKER_IMAGE) { $env:SPECMATIC_DOCKER_IMAGE } else { $null }
$SPECMATIC_DOCKER_IMAGE = $null
$PullSourceImage = "specmatic/enterprise:latest"
$HomeDir = if ($env:HOME) { $env:HOME } elseif ($env:USERPROFILE) { $env:USERPROFILE } else { [Environment]::GetFolderPath("UserProfile") }
$HomeLicenseDir = Join-Path $HomeDir ".specmatic"

if (-not (Test-Path -LiteralPath $SpecFile -PathType Leaf)) {
    Write-Error "Spec file not found: $SpecFile"
}

$specPath = (Resolve-Path -LiteralPath $SpecFile).Path
$specDir = Split-Path -Parent $specPath
$specBasename = Split-Path -Leaf $specPath

$dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
if (-not $dockerCmd) {
    Write-Error "Docker is not installed or not on PATH."
}

# Source of truth: ../references/validate-spec-image-selection.md
# Keep this implementation in sync with that reference and validate_spec.sh.
function Test-ImageExistsLocally {
    param([Parameter(Mandatory = $true)][string]$Image)

    docker image inspect $Image *> $null
    return $LASTEXITCODE -eq 0
}

function Resolve-SpecmaticImage {
    $candidate = $null

    if ($script:UserSpecifiedSpecmaticImage) {
        $candidate = $script:UserSpecifiedSpecmaticImage
    } else {
        $candidate = docker image ls --format '{{.Repository}}:{{.Tag}}' |
            Where-Object { $_ -and $_ -ne "<none>:<none>" -and $_ -match "specmatic" } |
            Select-Object -First 1
    }

    if ($candidate) {
        if (Test-ImageExistsLocally -Image $candidate) {
            $script:SPECMATIC_DOCKER_IMAGE = $candidate
            Write-Host "Using local Specmatic image: $($script:SPECMATIC_DOCKER_IMAGE)"
            return
        }

        if ($script:UserSpecifiedSpecmaticImage) {
            Write-Error "**Action Required:** The provided Docker image does not exist locally: $candidate. Please provide a valid local image name."
        }
    } else {
        Write-Host "No local Docker image with 'specmatic' in its name was found. Trying to pull: $($script:PullSourceImage)"
    }

    docker pull $script:PullSourceImage
    if ($LASTEXITCODE -eq 0) {
        $script:SPECMATIC_DOCKER_IMAGE = $script:PullSourceImage
        Write-Host "Using Specmatic Enterprise image: $($script:SPECMATIC_DOCKER_IMAGE)"
        return
    }

    Write-Error "**Action Required:** I could not find a usable local Specmatic Enterprise image and pulling `specmatic/enterprise:latest` failed. Please pull the image yourself, then tell me the image name so I can continue validation."
}

function New-ValidateDockerArgs {
    $dockerArgs = @(
        "run", "--rm",
        "--entrypoint", "sh",
        "-v", "${script:specDir}:/usr/src/app",
        "-w", "/usr/src/app"
    )

    if (Test-Path -LiteralPath $script:HomeLicenseDir -PathType Container) {
        $dockerArgs += @("-v", "${script:HomeLicenseDir}:/root/.specmatic")
    }

    return $dockerArgs + @(
        $script:SPECMATIC_DOCKER_IMAGE,
        "-c", "specmatic validate `"$($script:specBasename)`""
    )
}

Resolve-SpecmaticImage

Write-Host "Running validate for $SpecFile"
$validateArgs = New-ValidateDockerArgs
docker @validateArgs
exit $LASTEXITCODE
