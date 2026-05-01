[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = (Resolve-Path -LiteralPath $ScriptDir).Path
$SpecmaticDir = Join-Path $RepoRoot "specmatic"
$SpecmaticConfig = Join-Path $RepoRoot "specmatic.yaml"
$ReportsDir = Join-Path $RepoRoot "build/reports"
$UserSpecifiedSpecmaticImage = if ($env:SPECMATIC_DOCKER_IMAGE) { $env:SPECMATIC_DOCKER_IMAGE } else { $null }
$SpecmaticDockerImage = $null
$SutPort = if ($env:SUT_PORT) { $env:SUT_PORT } else { "<SUT_PORT>" }
$PreTestSetupCommand = if ($env:PRE_TEST_SETUP_CMD) { $env:PRE_TEST_SETUP_CMD } else { $null }
$HomeDir = if ($env:HOME) { $env:HOME } elseif ($env:USERPROFILE) { $env:USERPROFILE } else { [Environment]::GetFolderPath("UserProfile") }
$HomeLicenseDir = Join-Path $HomeDir ".specmatic"
$PullSourceImage = "specmatic/enterprise:latest"
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

try {
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

    if (Test-Path -LiteralPath $HomeLicenseDir -PathType Container) {
        $ValidateArgs += @("-v", "${HomeLicenseDir}:/root/.specmatic:ro")
        $TestArgs += @("-v", "${HomeLicenseDir}:/root/.specmatic:ro")
    }

    Invoke-SpecmaticDockerCommand -DockerArgs $ValidateArgs -SpecmaticArgs @("validate")

    Invoke-SpecmaticDockerCommand -DockerArgs $TestArgs -SpecmaticArgs @(
        "test",
        "--host=host.docker.internal",
        "--port=$SutPort"
    )

    Write-Host "Done. HTML report: $ReportsDir/specmatic/html/index.html"
} catch {
    if ($_.Exception.Message.StartsWith("**Action Required:**")) {
        throw $_.Exception.Message
    }

    throw $_.Exception.Message
}
