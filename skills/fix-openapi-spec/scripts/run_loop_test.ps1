[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$InputArgs = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Show-Usage {
    @"
Usage: ./run_loop_test.ps1 [--port <port>] <spec-file.[yaml|yml|json]>

Starts a Specmatic mock for the given spec, waits for the health endpoint,
and then runs a loop test against it.

Options:
  --port <port>  Run both mock and test against this port
  --help         Show this help message and exit
"@
}

$SpecFile = $null
$Port = $null
$AutoPort = $true

for ($index = 0; $index -lt $InputArgs.Count; $index++) {
    $argument = $InputArgs[$index]

    switch ($argument) {
        "--help" {
            Show-Usage
            exit 0
        }
        "--port" {
            if (($index + 1) -ge $InputArgs.Count -or $InputArgs[$index + 1].StartsWith("--")) {
                [Console]::Error.WriteLine("--port requires a value.")
                [Console]::Error.WriteLine((Show-Usage))
                exit 2
            }

            $Port = $InputArgs[$index + 1]
            $AutoPort = $false
            $index++
        }
        { $_.StartsWith("--") } {
            [Console]::Error.WriteLine("Unknown option: $argument")
            [Console]::Error.WriteLine((Show-Usage))
            exit 2
        }
        default {
            if ($SpecFile) {
                [Console]::Error.WriteLine("Only one spec file can be provided.")
                [Console]::Error.WriteLine((Show-Usage))
                exit 2
            }

            $SpecFile = $argument
        }
    }
}

if (-not $SpecFile) {
    [Console]::Error.WriteLine((Show-Usage))
    exit 2
}

$SPECMATIC_DOCKER_IMAGE = if ($env:SPECMATIC_DOCKER_IMAGE) { $env:SPECMATIC_DOCKER_IMAGE } else { "specmatic/specmatic:latest" }
$HEALTH_URL_OVERRIDE = if ($env:HEALTH_URL) { $env:HEALTH_URL } else { $null }
$TEST_BASE_URL_HOST = if ($env:TEST_BASE_URL_HOST) { $env:TEST_BASE_URL_HOST } else { "host.docker.internal" }
$STARTUP_TIMEOUT_SECONDS = 25
$MAX_AUTO_PORT_ATTEMPTS = 10
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

function Get-RandomPort {
    Get-Random -Minimum 49152 -Maximum 65536
}

function Test-PortLooksAvailable {
    param([Parameter(Mandatory = $true)][int]$CandidatePort)

    $client = $null
    try {
        $client = [System.Net.Sockets.TcpClient]::new()
        $connection = $client.BeginConnect("127.0.0.1", $CandidatePort, $null, $null)
        $connected = $connection.AsyncWaitHandle.WaitOne(200, $false)
        return -not $connected
    } catch {
        return $true
    } finally {
        if ($client) {
            $client.Close()
        }
    }
}

function Select-Port {
    if (-not $script:AutoPort) {
        return
    }

    for ($attempt = 1; $attempt -le 20; $attempt++) {
        $candidate = Get-RandomPort
        if (Test-PortLooksAvailable -CandidatePort $candidate) {
            $script:Port = [string]$candidate
            return
        }
    }

    $script:Port = [string](Get-RandomPort)
}

function Get-HealthUrl {
    if ($script:HEALTH_URL_OVERRIDE) {
        return $script:HEALTH_URL_OVERRIDE
    }

    return "http://127.0.0.1:{0}/_specmatic/health" -f $script:Port
}

function Test-MockLogHasPortConflict {
    $patterns = @(
        "Address already in use",
        "BindException",
        "EADDRINUSE",
        "port is already allocated",
        "Ports are not available",
        "bind: address already in use"
    )

    foreach ($logPath in @($script:mockLog, $script:mockErrLog)) {
        if (-not (Test-Path -LiteralPath $logPath)) {
            continue
        }

        $content = Get-Content -LiteralPath $logPath -Raw
        foreach ($pattern in $patterns) {
            if ($content -match [Regex]::Escape($pattern)) {
                return $true
            }
        }
    }

    return $false
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

    $healthy = $false
    :mockStartAttempts for ($attempt = 1; $attempt -le $MAX_AUTO_PORT_ATTEMPTS; $attempt++) {
        Select-Port
        Write-Host "Using Specmatic port: $Port"
        Write-Host "Starting mock for $SpecFile"

        $mockSpecmaticArgs = @("mock", "--port", $Port, $specBasename, "--lenient")
        foreach ($logPath in @($mockLog, $mockErrLog)) {
            if (Test-Path -LiteralPath $logPath) {
                Remove-Item -LiteralPath $logPath -Force
            }
        }

        $mockArgs = @(
            "run", "--rm",
            "-p", "${Port}:${Port}",
            "--name", $mockContainerName,
            "-v", "${specDir}:/usr/src/app",
            "-w", "/usr/src/app",
            $SPECMATIC_DOCKER_IMAGE
        ) + $mockSpecmaticArgs
        $mockProcess = Start-Process -FilePath "docker" -ArgumentList $mockArgs -RedirectStandardOutput $mockLog -RedirectStandardError $mockErrLog -NoNewWindow -PassThru

        $deadline = (Get-Date).AddSeconds($STARTUP_TIMEOUT_SECONDS)
        while ((Get-Date) -lt $deadline) {
            if ($mockProcess.HasExited) {
                if ($AutoPort -and $attempt -lt $MAX_AUTO_PORT_ATTEMPTS -and (Test-MockLogHasPortConflict)) {
                    [Console]::Error.WriteLine("Mock could not bind port $Port; retrying with another port.")
                    Stop-MockContainer
                    continue mockStartAttempts
                }

                [Console]::Error.WriteLine("Mock exited before becoming healthy.")
                Print-LogTail -Label "mock" -FilePath $mockLog
                Print-LogTail -Label "mock-stderr" -FilePath $mockErrLog
                exit 1
            }

            if ((Get-HttpStatusCode -Url (Get-HealthUrl)) -eq 200) {
                $healthy = $true
                break
            }

            Start-Sleep -Seconds 1
        }

        if ($healthy) {
            break
        }

        if ($AutoPort -and $attempt -lt $MAX_AUTO_PORT_ATTEMPTS -and (Test-MockLogHasPortConflict)) {
            [Console]::Error.WriteLine("Mock did not become healthy on port $Port; retrying with another port.")
            Stop-MockContainer
            continue
        }

        [Console]::Error.WriteLine("Mock did not become healthy within $STARTUP_TIMEOUT_SECONDS seconds.")
        Print-LogTail -Label "mock" -FilePath $mockLog
        Print-LogTail -Label "mock-stderr" -FilePath $mockErrLog
        exit 1
    }

    if (-not $healthy) {
        [Console]::Error.WriteLine("Mock did not become healthy within $STARTUP_TIMEOUT_SECONDS seconds.")
        Print-LogTail -Label "mock" -FilePath $mockLog
        Print-LogTail -Label "mock-stderr" -FilePath $mockErrLog
        exit 1
    }

    Write-Host "Mock is healthy."
    Write-Host "Running loop test for $SpecFile"

    $testSpecmaticArgs = @("test", "--port", $Port, $specBasename, "--lenient", "--testBaseURL", "http://${TEST_BASE_URL_HOST}:$Port")

    $testArgs = @(
        "run", "--rm",
        "--add-host", "${TEST_BASE_URL_HOST}:host-gateway",
        "-e", "MAX_TEST_REQUEST_COMBINATIONS=$MAX_TEST_REQUEST_COMBINATIONS",
        "-v", "${specDir}:/usr/src/app",
        "-w", "/usr/src/app",
        $SPECMATIC_DOCKER_IMAGE
    ) + $testSpecmaticArgs
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
