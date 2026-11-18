$ErrorActionPreference = 'Stop'
python (Join-Path $PSScriptRoot 'init_project.py') --root (Get-Location).Path @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
