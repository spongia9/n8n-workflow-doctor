param([int]$Port = 8080, [switch]$Prepare, [string]$PythonPath)
& "$PSScriptRoot/scripts/native.ps1" -Action start -Port $Port -Prepare:$Prepare -PythonPath $PythonPath
exit $LASTEXITCODE
