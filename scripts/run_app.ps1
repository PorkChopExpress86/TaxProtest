Param()
$ErrorActionPreference = 'Stop'
$venvActivate = Join-Path $PSScriptRoot '..' | Join-Path -ChildPath '.venv/Scripts/Activate.ps1'
if (-not (Test-Path $venvActivate)) {
  Write-Error "Virtual environment not found. Create it first: py -3.13 -m venv .venv"
  exit 1
}
. $venvActivate
Write-Host 'Activated virtual environment.' -ForegroundColor Green
python app.py
