Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location "$PSScriptRoot\.."

if (-not (Test-Path ".\.venv")) {
  py -3 -m venv .venv
}

$pythonExe = Join-Path (Resolve-Path ".\.venv").Path "Scripts\python.exe"

if (-not (Test-Path $pythonExe)) {
  throw "Could not find virtual environment Python at $pythonExe"
}

& $pythonExe -m pip install -r .\backend\requirements.txt

if (-not $env:ALLOWED_ORIGINS) {
  $env:ALLOWED_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
}

if ($env:DEV_RELOAD -eq "1") {
  & $pythonExe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
} else {
  & $pythonExe -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
}
