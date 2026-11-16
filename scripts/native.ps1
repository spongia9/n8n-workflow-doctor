param([ValidateSet('start','stop','status')][string]$Action, [int]$Port = 8080,
      [switch]$Prepare, [string]$PythonPath)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path $PSScriptRoot -Parent
try {
    if ($Prepare -and $Action -ne 'start') { throw 'Prepare is supported only for start.' }
    if (-not $PythonPath) {
        foreach ($relative in @('.venv/Scripts/python.exe', '.venv-312/Scripts/python.exe')) {
            $candidate = Join-Path $projectRoot $relative
            if (Test-Path -LiteralPath $candidate) { $PythonPath = $candidate; break }
        }
    }
    if (-not $PythonPath -and $Prepare) {
        & py -3.12 -m venv (Join-Path $projectRoot '.venv')
        if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12 with the py launcher, or provide -PythonPath.' }
        $PythonPath = Join-Path $projectRoot '.venv/Scripts/python.exe'
    }
    if (-not $PythonPath) { throw 'Python environment missing. Run start.ps1 -Prepare or provide -PythonPath.' }
    $PythonPath = (Resolve-Path -LiteralPath $PythonPath).Path
    & $PythonPath -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3,12) and sys.prefix != sys.base_prefix else 1)'
    if ($LASTEXITCODE -ne 0) { throw 'Use a Python 3.12 virtual environment.' }
    Push-Location $projectRoot
    try {
        if ($Prepare) {
            if (Test-Path -LiteralPath (Join-Path $projectRoot '.runtime/instance.json')) {
                throw 'Run stop.ps1 before preparing a new build (check stale runtime record if already stopped).'
            }
            & $PythonPath -m pip install --require-hashes -r deploy/backend/requirements.lock -r deploy/backend/build.lock
            if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
            & $PythonPath -m pip install --no-build-isolation --no-deps -e .
            if ($LASTEXITCODE -ne 0) { throw 'Project installation failed.' }
            & node -e 'process.exit(Number(process.versions.node.split(String.fromCharCode(46))[0]) === 24 ? 0 : 1)'
            if ($LASTEXITCODE -ne 0) { throw 'Install supported Node.js 24 before preparing the frontend.' }
            Push-Location frontend
            $oldApiBase = $env:VITE_API_BASE_URL
            try {
                & npm.cmd ci
                if ($LASTEXITCODE -ne 0) { throw 'npm ci failed.' }
                $env:VITE_API_BASE_URL = 'same-origin'
                & npm.cmd run build
                if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
            } finally {
                $env:VITE_API_BASE_URL = $oldApiBase
                Pop-Location
            }
        }
        & $PythonPath -c 'import workflow_doctor.api.native_runtime'
        if ($LASTEXITCODE -ne 0) { throw 'Install the project API dependencies first: start.ps1 -Prepare.' }
        & $PythonPath -m workflow_doctor.api.native_runtime $Action --root $projectRoot --port $Port
        exit $LASTEXITCODE
    } finally { Pop-Location }
} catch {
    Write-Host ('NATIVE_ERROR: ' + $_.Exception.Message)
    exit 1
}
