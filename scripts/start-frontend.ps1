Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location "$PSScriptRoot\.."

if (-not (Test-Path ".\frontend\.env")) {
  Copy-Item .\frontend\.env.example .\frontend\.env
}

corepack pnpm install --dir .\frontend
corepack pnpm --dir .\frontend dev
