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
$LocalLicenseDir = $null
$LicenseFileName = $null

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

function Find-LicenseFile {
    if (-not (Test-Path -LiteralPath $HomeLicenseDir -PathType Container)) {
        return $null
    }

    $preferredNames = @(
        "specmatic-license.txt",
        "license.json"
    )

    foreach ($name in $preferredNames) {
        $candidate = Join-Path $HomeLicenseDir $name
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return $candidate
        }
    }

    return $null
}

function Prepare-License {
    $sourceLicense = Find-LicenseFile
    if (-not $sourceLicense) {
        return
    }

    $script:LocalLicenseDir = Join-Path $script:specDir ".specmatic"
    New-Item -ItemType Directory -Path $script:LocalLicenseDir -Force | Out-Null
    $script:LicenseFileName = Split-Path -Leaf $sourceLicense
    Copy-Item -LiteralPath $sourceLicense -Destination (Join-Path $script:LocalLicenseDir $script:LicenseFileName) -Force
}

function Get-ValidateConfig {
    $lines = @(
        "version: 3",
        "systemUnderTest:",
        "  service:",
        "    definitions:",
        "      - definition:",
        "          source:",
        "            filesystem:",
        "              directory: .",
        "          specs:",
        "            - $script:specBasename"
    )

    if ($script:LicenseFileName) {
        $lines += @(
            "specmatic:",
            "  license:",
            "    path: /usr/src/app/.specmatic/$($script:LicenseFileName)"
        )
    }

    return ($lines -join "`n") + "`n"
}

function New-ValidateDockerArgs {
    $dockerArgs = @(
        "run", "--rm",
        "-i",
        "--entrypoint", "sh",
        "-v", "${script:specDir}:/usr/src/app",
        "-w", "/usr/src/app"
    )

    if ($script:LicenseFileName) {
        $dockerArgs += @("-v", "${script:LocalLicenseDir}:/usr/src/app/.specmatic")
    }

    return $dockerArgs + @(
        $script:SPECMATIC_DOCKER_IMAGE,
        "-c", "cat > /tmp/specmatic.yaml && specmatic validate --config /tmp/specmatic.yaml"
    )
}

Resolve-SpecmaticImage
Prepare-License

Write-Host "Running validate for $SpecFile"
$validateConfig = Get-ValidateConfig
$validateArgs = New-ValidateDockerArgs
$validateConfig | docker @validateArgs
exit $LASTEXITCODE
