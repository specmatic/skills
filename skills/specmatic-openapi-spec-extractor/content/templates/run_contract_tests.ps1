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
$SutStartCommand = if ($env:SUT_START_CMD) { $env:SUT_START_CMD } else { $null }
$SutHealthcheckUrl = if ($env:SUT_HEALTHCHECK_URL) { $env:SUT_HEALTHCHECK_URL } else { $null }
$SutStartupWaitSeconds = if ($env:SUT_STARTUP_WAIT_SECONDS) { [int]$env:SUT_STARTUP_WAIT_SECONDS } else { 60 }
$HomeDir = if ($env:HOME) { $env:HOME } elseif ($env:USERPROFILE) { $env:USERPROFILE } else { [Environment]::GetFolderPath("UserProfile") }
$HomeLicenseDir = Join-Path $HomeDir ".specmatic"
$PullSourceImage = "specmatic/enterprise:latest"
$StartedSutProcess = $null
$HostAliasFallbackAdded = $false
function Test-ImageExistsLocally {
    param([Parameter(Mandatory = $true)][string]$Image)

    docker image inspect $Image *> $null
    return $LASTEXITCODE -eq 0
}

function Find-LatestLocalSpecmaticImage {
    $candidates = foreach ($line in (docker image ls --no-trunc --format '{{.Repository}}	{{.Tag}}	{{.ID}}')) {
        if (-not $line) {
            continue
        }

        $parts = $line -split "`t"
        if ($parts.Count -lt 3) {
            continue
        }

        $repo = $parts[0]
        $tag = $parts[1]
        $id = $parts[2]

        if ("$repo`:$tag" -eq "<none>:<none>") {
            continue
        }

        if ($repo -notmatch "specmatic" -and $tag -notmatch "specmatic") {
            continue
        }

        $created = docker image inspect --format '{{.Created}}' $id 2>$null
        if (-not $created) {
            continue
        }

        [pscustomobject]@{
            Created = [string]$created
            Ref = "{0}:{1}" -f $repo, $tag
        }
    }

    return $candidates |
        Sort-Object @{ Expression = "Created"; Descending = $true }, @{ Expression = "Ref"; Descending = $false } |
        Select-Object -First 1 -ExpandProperty Ref
}

function Resolve-EnterpriseImage {
    $candidate = $null

    if ($script:UserSpecifiedSpecmaticImage) {
        $candidate = $script:UserSpecifiedSpecmaticImage
    } else {
        $candidate = Find-LatestLocalSpecmaticImage
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

function Add-HostAliasFallback {
    if ($script:HostAliasFallbackAdded) {
        return
    }

    $script:DockerArgs += @("--add-host", "host.docker.internal:host-gateway")
    $script:HostAliasFallbackAdded = $true
}

function Rebuild-DockerArgs {
    $script:ValidateArgs = $script:DockerArgs + @(
        "-v", "${SpecmaticDir}:/usr/src/app/specmatic",
        "-v", "${SpecmaticConfig}:/usr/src/app/specmatic.yaml",
        "-w", "/usr/src/app"
    )

    $script:TestArgs = $script:DockerArgs + @(
        "-v", "${SpecmaticDir}:/usr/src/app/specmatic",
        "-v", "${SpecmaticConfig}:/usr/src/app/specmatic.yaml",
        "-v", "${ReportsDir}:/usr/src/app/build/reports",
        "-w", "/usr/src/app"
    )

    if (Test-Path -LiteralPath $HomeLicenseDir -PathType Container) {
        $script:ValidateArgs += @("-v", "${HomeLicenseDir}:/root/.specmatic:ro")
        $script:TestArgs += @("-v", "${HomeLicenseDir}:/root/.specmatic:ro")
    }
}

function Invoke-SpecmaticTestWithFallback {
    try {
        Invoke-SpecmaticDockerCommand -DockerArgs $script:TestArgs -SpecmaticArgs @(
            "test",
            "--host=host.docker.internal",
            "--port=$SutPort"
        )
    } catch {
        $message = $_.Exception.Message
        if (-not $IsLinuxHost -and $message -like "*host.docker.internal*") {
            Write-Host "Retrying with explicit host.docker.internal mapping because Docker DNS did not resolve the host alias."
            Add-HostAliasFallback
            Rebuild-DockerArgs
            Invoke-SpecmaticDockerCommand -DockerArgs $script:TestArgs -SpecmaticArgs @(
                "test",
                "--host=host.docker.internal",
                "--port=$SutPort"
            )
            return
        }

        throw $message
    }
}

function Wait-ForSut {
    $deadline = (Get-Date).AddSeconds($script:SutStartupWaitSeconds)

    while ((Get-Date) -lt $deadline) {
        if ($script:SutHealthcheckUrl) {
            try {
                Invoke-WebRequest -Uri $script:SutHealthcheckUrl -UseBasicParsing | Out-Null
                return
            } catch {
            }
        } else {
            try {
                Invoke-WebRequest -Uri "http://127.0.0.1:$($script:SutPort)/" -UseBasicParsing | Out-Null
                return
            } catch {
                if ($_.Exception.Response) {
                    return
                }
            }
        }

        Start-Sleep -Seconds 2
    }

    throw "**Action Required:** The SUT is not reachable on localhost:$($script:SutPort). Start it on the host or provide the correct reachable host port from Docker."
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
    if ($SutStartCommand) {
        Write-Host "Starting SUT: $SutStartCommand"
        $sutLogPath = Join-Path $ReportsDir "sut.log"
        $StartedSutProcess = Start-Process -FilePath "powershell" -ArgumentList "-NoProfile", "-Command", $SutStartCommand -WorkingDirectory $RepoRoot -RedirectStandardOutput $sutLogPath -RedirectStandardError $sutLogPath -PassThru
    }

    Wait-ForSut

    Rebuild-DockerArgs

    Invoke-SpecmaticDockerCommand -DockerArgs $script:ValidateArgs -SpecmaticArgs @("validate")

    Invoke-SpecmaticTestWithFallback

    Write-Host "Done. HTML report: $ReportsDir/specmatic/html/index.html"
} catch {
    if ($_.Exception.Message.StartsWith("**Action Required:**")) {
        throw $_.Exception.Message
    }

    throw $_.Exception.Message
} finally {
    if ($StartedSutProcess -and -not $StartedSutProcess.HasExited) {
        Stop-Process -Id $StartedSutProcess.Id -Force -ErrorAction SilentlyContinue
    }
}
