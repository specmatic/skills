[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path -LiteralPath $ScriptDir).Path
$SpecmaticDir = Join-Path $RepoRoot "specmatic"
$SpecmaticConfig = Join-Path $RepoRoot "specmatic.yaml"
$ReportsDir = Join-Path $RepoRoot "build/reports"
$LocalLicenseDir = Join-Path $RepoRoot ".specmatic"
$SpecmaticDockerImage = if ($env:SPECMATIC_DOCKER_IMAGE) { $env:SPECMATIC_DOCKER_IMAGE } else { "specmatic/enterprise:latest" }
$SutPort = if ($env:SUT_PORT) { $env:SUT_PORT } else { "<SUT_PORT>" }
$PreTestSetupCommand = if ($env:PRE_TEST_SETUP_CMD) { $env:PRE_TEST_SETUP_CMD } else { $null }
$HomeDir = if ($env:HOME) { $env:HOME } elseif ($env:USERPROFILE) { $env:USERPROFILE } else { [Environment]::GetFolderPath("UserProfile") }
$HomeLicenseDir = Join-Path $HomeDir ".specmatic"
$LicenseFileName = $null

function Find-LicenseFile {
    if (-not (Test-Path -LiteralPath $HomeLicenseDir -PathType Container)) {
        return $null
    }

    $preferredNames = @(
        "license.txt",
        "license.lic",
        "specmatic-license.txt",
        "specmatic-license.lic"
    )

    foreach ($name in $preferredNames) {
        $candidate = Join-Path $HomeLicenseDir $name
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return $candidate
        }
    }

    $fallback = Get-ChildItem -LiteralPath $HomeLicenseDir -File |
        Where-Object { $_.Name -match "license" -or $_.Extension -ieq ".lic" } |
        Select-Object -First 1

    if ($fallback) {
        return $fallback.FullName
    }

    return $null
}

function Prepare-License {
    $sourceLicense = Find-LicenseFile
    if (-not $sourceLicense) {
        return
    }

    New-Item -ItemType Directory -Path $LocalLicenseDir -Force | Out-Null
    $script:LicenseFileName = Split-Path -Leaf $sourceLicense
    Copy-Item -LiteralPath $sourceLicense -Destination (Join-Path $LocalLicenseDir $script:LicenseFileName) -Force
}

$IsLinuxHost = [System.Runtime.InteropServices.RuntimeInformation]::IsOSPlatform(
    [System.Runtime.InteropServices.OSPlatform]::Linux
)

$DockerArgs = @("run", "--rm")
if ($IsLinuxHost) {
    $DockerArgs += @("--add-host", "host.docker.internal:host-gateway")
}

New-Item -ItemType Directory -Path $ReportsDir -Force | Out-Null
Prepare-License

docker pull $SpecmaticDockerImage

# Optional runtime throttle for slow or overly large suites.
# Add this only after you observe too many generated test combinations:
# yq -i '.specmatic.settings.test.maxTestRequestCombinations = 1' $SpecmaticConfig

if ($PreTestSetupCommand) {
    Write-Host "Running pre-test setup: $PreTestSetupCommand"
    Push-Location $RepoRoot
    try {
        Invoke-Expression $PreTestSetupCommand
    } finally {
        Pop-Location
    }
}

$ValidateArgs = $DockerArgs + @(
    "-v", "${RepoRoot}:/usr/src/app",
    "-w", "/usr/src/app"
)

$TestArgs = $DockerArgs + @(
    "-v", "${SpecmaticDir}:/usr/src/app/specmatic",
    "-v", "${SpecmaticConfig}:/usr/src/app/specmatic.yaml",
    "-v", "${ReportsDir}:/usr/src/app/build/reports",
    "-w", "/usr/src/app"
)

if ($LicenseFileName) {
    $ValidateArgs += @("-v", "${LocalLicenseDir}:/usr/src/app/.specmatic")
    $TestArgs += @("-v", "${LocalLicenseDir}:/usr/src/app/.specmatic")
}

$ValidateArgs += @(
    $SpecmaticDockerImage,
    "validate"
)
& docker @ValidateArgs

$TestArgs += @(
    $SpecmaticDockerImage,
    "test",
    "--host=host.docker.internal",
    "--port=$SutPort"
)
& docker @TestArgs

Write-Host "Done. HTML report: $ReportsDir/specmatic/html/index.html"
