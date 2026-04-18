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

Runs Specmatic Enterprise validation for the given OpenAPI spec.

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
