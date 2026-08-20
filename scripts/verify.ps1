param(
    [switch]$IncludeMockLiveHarness
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot

function Resolve-PythonExecutable {
    param(
        [string]$Candidate
    )
    if (-not $Candidate) {
        return $null
    }
    try {
        $resolved = (& $Candidate -c "import sys; print(sys.executable)" 2>$null)
        if ($LASTEXITCODE -ne 0 -or -not $resolved) {
            return $null
        }
        return ($resolved | Select-Object -Last 1).Trim()
    }
    catch {
        return $null
    }
}

# Resolve Python: explicit override, then PATH, then the py launcher.
$Python = Resolve-PythonExecutable $env:SYBERRUNTIME_PYTHON
if ($env:SYBERRUNTIME_PYTHON -and -not $Python) {
    throw "SYBERRUNTIME_PYTHON does not point to a runnable Python interpreter."
}
if (-not $Python) {
    $candidate = Get-Command python -ErrorAction SilentlyContinue
    if ($candidate) { $Python = Resolve-PythonExecutable $candidate.Source }
}
if (-not $Python) {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        try {
            $resolved = (& $launcher.Source -3 -c "import sys; print(sys.executable)" 2>$null)
            if ($LASTEXITCODE -eq 0 -and $resolved) {
                $Python = ($resolved | Select-Object -Last 1).Trim()
            }
        }
        catch {
            $Python = $null
        }
    }
}
if (-not $Python -or -not (Test-Path -LiteralPath $Python)) {
    throw "No Python interpreter found. Set SYBERRUNTIME_PYTHON or put python on PATH."
}

$env:PYTHONPATH = Join-Path $RepoRoot "src"
$env:SYBERRUNTIME_PYTHON = $Python

Push-Location $RepoRoot
try {
    & $Python -m unittest discover -s tests
    if ($LASTEXITCODE -ne 0) { throw "Unit tests failed with exit code $LASTEXITCODE." }
    & $Python -m compileall -q src tests examples
    if ($LASTEXITCODE -ne 0) { throw "Compile check failed with exit code $LASTEXITCODE." }
    & $Python -m syberruntime.cli acceptance-check
    if ($LASTEXITCODE -ne 0) { throw "Acceptance check failed with exit code $LASTEXITCODE." }

    if ($IncludeMockLiveHarness) {
        $runId = "verify-mock-live-" + [System.Guid]::NewGuid().ToString("N")
        $runtimeRoot = Join-Path $env:TEMP ("syber-verify-live-" + [System.Guid]::NewGuid().ToString("N"))
        $reportPath = Join-Path $env:TEMP ($runId + ".json")
        & $Python -m syberruntime.cli --root $runtimeRoot agent-harness run --mode live --config examples\mock_mcp_adapter_config.example.json --run-id $runId --output $reportPath
        if ($LASTEXITCODE -ne 0) { throw "Mock live harness failed with exit code $LASTEXITCODE." }
    }
}
finally {
    Pop-Location
}
