[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$SpecFile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$SPECMATIC_DOCKER_IMAGE = if ($env:SPECMATIC_DOCKER_IMAGE) { $env:SPECMATIC_DOCKER_IMAGE } else { "specmatic/specmatic:latest" }
$HEALTH_URL = if ($env:HEALTH_URL) { $env:HEALTH_URL } else { "http://127.0.0.1:9000/_specmatic/health" }
$STARTUP_TIMEOUT_SECONDS = 25
$MAX_TEST_REQUEST_COMBINATIONS = if ($env:MAX_TEST_REQUEST_COMBINATIONS) { $env:MAX_TEST_REQUEST_COMBINATIONS } else { "1" }

if (-not (Test-Path -LiteralPath $SpecFile -PathType Leaf)) {
    Write-Error "Spec file not found: $SpecFile"
}

$specPath = (Resolve-Path -LiteralPath $SpecFile).Path
$specDir = Split-Path -Parent $specPath
$specBasename = Split-Path -Leaf $specPath

$mockLog = Join-Path ([System.IO.Path]::GetTempPath()) ("specmatic-mock-{0}.log" -f ([System.Guid]::NewGuid().ToString("N")))
$mockErrLog = Join-Path ([System.IO.Path]::GetTempPath()) ("specmatic-mock-{0}.err.log" -f ([System.Guid]::NewGuid().ToString("N")))
$testLog = Join-Path ([System.IO.Path]::GetTempPath()) ("specmatic-test-{0}.log" -f ([System.Guid]::NewGuid().ToString("N")))
$mockContainerName = "specmatic-loop-mock-{0}" -f ([System.Guid]::NewGuid().ToString("N").Substring(0, 12))

function Get-HttpStatusCode {
    param([Parameter(Mandatory = $true)][string]$Url)
    try {
        return (Invoke-WebRequest -UseBasicParsing -Uri $Url -Method Get -TimeoutSec 2).StatusCode
    } catch {
        return 0
    }
}

function Print-LogTail {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][string]$FilePath
    )
    [Console]::Error.WriteLine("Last lines from $Label log ($FilePath):")
    if (Test-Path -LiteralPath $FilePath) {
        Get-Content -LiteralPath $FilePath -Tail 40 | ForEach-Object { [Console]::Error.WriteLine($_) }
    }
}

function Stop-MockContainer {
    if ($script:mockContainerName) {
        docker stop $script:mockContainerName *> $null
    }
}

function Test-DockerPreflight {
    $dockerCmd = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $dockerCmd) {
        Write-Error "Docker is not installed or not on PATH."
    }

    try {
        docker info *> $null
    } catch {
        Write-Error "Docker daemon is not available. Start Docker Desktop (Windows/macOS) or Docker daemon (Linux) and retry."
    }
}

try {
    Test-DockerPreflight

    $buildDir = Join-Path $specDir "build"
    if (Test-Path -LiteralPath $buildDir) {
        Remove-Item -LiteralPath $buildDir -Recurse -Force
    }

    Write-Host "Starting mock for $SpecFile"
    $mockArgs = @(
        "run", "--rm",
        "--network", "host",
        "--name", $mockContainerName,
        "-v", "${specDir}:/usr/src/app",
        "-w", "/usr/src/app",
        $SPECMATIC_DOCKER_IMAGE,
        "mock", $specBasename, "--lenient"
    )
    $mockProcess = Start-Process -FilePath "docker" -ArgumentList $mockArgs -RedirectStandardOutput $mockLog -RedirectStandardError $mockErrLog -NoNewWindow -PassThru

    $deadline = (Get-Date).AddSeconds($STARTUP_TIMEOUT_SECONDS)
    $healthy = $false
    while ((Get-Date) -lt $deadline) {
        if ($mockProcess.HasExited) {
            [Console]::Error.WriteLine("Mock exited before becoming healthy.")
            Print-LogTail -Label "mock" -FilePath $mockLog
            Print-LogTail -Label "mock-stderr" -FilePath $mockErrLog
            exit 1
        }

        if ((Get-HttpStatusCode -Url $HEALTH_URL) -eq 200) {
            $healthy = $true
            break
        }

        Start-Sleep -Seconds 1
    }

    if (-not $healthy) {
        [Console]::Error.WriteLine("Mock did not become healthy within $STARTUP_TIMEOUT_SECONDS seconds.")
        Print-LogTail -Label "mock" -FilePath $mockLog
        Print-LogTail -Label "mock-stderr" -FilePath $mockErrLog
        exit 1
    }

    Write-Host "Mock is healthy."
    Write-Host "Running loop test for $SpecFile"

    $testArgs = @(
        "run", "--rm",
        "--network", "host",
        "-e", "MAX_TEST_REQUEST_COMBINATIONS=$MAX_TEST_REQUEST_COMBINATIONS",
        "-v", "${specDir}:/usr/src/app",
        "-w", "/usr/src/app",
        $SPECMATIC_DOCKER_IMAGE,
        "test", $specBasename, "--lenient"
    )
    $testExitCode = 0
    docker @testArgs *> $testLog
    $testExitCode = $LASTEXITCODE

    if ($testExitCode -ne 0) {
        Stop-MockContainer
        [Console]::Error.WriteLine("Loop test failed.")
        Print-LogTail -Label "test" -FilePath $testLog
        exit 1
    }

    Stop-MockContainer
    Write-Host "Loop test passed."
    Write-Host "Mock log: $mockLog"
    Write-Host "Mock stderr log: $mockErrLog"
    Write-Host "Test log: $testLog"
    exit 0
}
finally {
    Stop-MockContainer
}
