param([string]$PythonPath)
& "$PSScriptRoot/scripts/native.ps1" -Action stop -PythonPath $PythonPath
exit $LASTEXITCODE
