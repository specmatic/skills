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
        "specmatic-license.lic",
        "specmatic.txt"
    )

    foreach ($name in $preferredNames) {
        $candidate = Join-Path $HomeLicenseDir $name
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return $candidate
        }
    }

    $fallback = Get-ChildItem -LiteralPath $HomeLicenseDir -File |
        Where-Object { $_.Name -match "license" -or $_.Extension -ieq ".lic" -or $_.Name -like "specmatic*.txt" } |
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

function Sync-SpecmaticLicenseConfig {
    if (-not $script:LicenseFileName) {
        return
    }

    if (-not (Test-Path -LiteralPath $SpecmaticConfig -PathType Leaf)) {
        return
    }

    $desiredPath = "/usr/src/app/.specmatic/$($script:LicenseFileName)"
    $content = Get-Content -LiteralPath $SpecmaticConfig -Raw

    if ($content.Contains($desiredPath)) {
        return
    }

    if ($content -match '(?m)^(\s*path:\s*/usr/src/app/\.specmatic/).+$') {
        $updated = [regex]::Replace(
            $content,
            '(?m)^(\s*path:\s*/usr/src/app/\.specmatic/).+$',
            "`$1$($script:LicenseFileName)",
            1
        )
        Set-Content -LiteralPath $SpecmaticConfig -Value $updated
        return
    }

    $updated = [regex]::Replace(
        $content,
        '(?m)^specmatic:$',
        "specmatic:`n  license:`n    path: $desiredPath",
        1
    )
    Set-Content -LiteralPath $SpecmaticConfig -Value $updated
}

function Test-ImageExistsLocally {
    param([Parameter(Mandatory = $true)][string]$Image)

    docker image inspect $Image *> $null
    return $LASTEXITCODE -eq 0
}

function Resolve-EnterpriseImage {
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
            $script:SpecmaticDockerImage = $candidate
            Write-Host "Using local Specmatic image: $($script:SpecmaticDockerImage)"
            return
        }

        if ($script:UserSpecifiedSpecmaticImage) {
            throw "The provided Docker image does not exist locally: $candidate. Please provide a valid local image name."
        }
    } else {
        Write-Host "No local Docker image with 'specmatic' in its name was found. Trying to pull: $($script:PullSourceImage)"
    }

    docker pull $script:PullSourceImage
    if ($LASTEXITCODE -eq 0) {
        $script:SpecmaticDockerImage = $script:PullSourceImage
        Write-Host "Using Specmatic Enterprise image: $($script:SpecmaticDockerImage)"
        return
    }

    throw "I could not find a usable local Specmatic Enterprise image and pulling `specmatic/enterprise:latest` failed. Please pull the image yourself, then tell me the image name so I can continue the feedback loop."
}

function Invoke-SpecmaticDockerCommand {
    param(
        [Parameter(Mandatory = $true)][string[]]$DockerArgs,
        [Parameter(Mandatory = $true)][string[]]$SpecmaticArgs
    )

    $allArgs = $DockerArgs + @($script:SpecmaticDockerImage) + $SpecmaticArgs
    $output = & docker @allArgs 2>&1
    $status = $LASTEXITCODE

    if ($output) {
        $output | Out-Host
    }

    if ($status -eq 0) {
        return
    }

    throw ($output | Out-String).Trim()
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
Sync-SpecmaticLicenseConfig
Resolve-EnterpriseImage

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
