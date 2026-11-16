param([string]$PythonPath)
& "$PSScriptRoot/scripts/native.ps1" -Action status -PythonPath $PythonPath
exit $LASTEXITCODE
