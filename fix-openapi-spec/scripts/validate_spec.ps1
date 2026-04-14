[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$SpecFile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$SPECMATIC_ENTERPRISE_DOCKER_IMAGE = if ($env:SPECMATIC_ENTERPRISE_DOCKER_IMAGE) { $env:SPECMATIC_ENTERPRISE_DOCKER_IMAGE } else { "specmatic/enterprise:latest" }

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

Write-Host "Running enterprise validate for $SpecFile"
$validateArgs = @(
    "run", "--rm",
    "-v", "${specDir}:/usr/src/app",
    "-w", "/usr/src/app",
    $SPECMATIC_ENTERPRISE_DOCKER_IMAGE,
    "validate", "--spec-file", $specBasename
)

docker @validateArgs
exit $LASTEXITCODE
