param(
    [switch]$IncludeMockLiveHarness
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = "C:\Users\MATEO\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Bundled Python not found: $Python"
}

$env:PYTHONPATH = Join-Path $RepoRoot "src"
$env:SYBERRUNTIME_PYTHON = $Python

Push-Location $RepoRoot
try {
    & $Python -m unittest discover -s tests
    & $Python -m compileall -q src tests examples
    & $Python -m syberruntime.cli acceptance-check

    if ($IncludeMockLiveHarness) {
        $runId = "verify-mock-live-" + [System.Guid]::NewGuid().ToString("N")
        $runtimeRoot = Join-Path $env:TEMP ("syber-verify-live-" + [System.Guid]::NewGuid().ToString("N"))
        $reportPath = Join-Path $env:TEMP ($runId + ".json")
        & $Python -m syberruntime.cli --root $runtimeRoot agent-harness run --mode live --config examples\mock_mcp_adapter_config.example.json --run-id $runId --output $reportPath
    }
}
finally {
    Pop-Location
}
