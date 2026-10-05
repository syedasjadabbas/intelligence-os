# PowerShell script to launch both Intelligence OS Backend and Frontend concurrently

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  Starting Intelligence OS (FastAPI Backend + Next.js UI) " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Start FastAPI Backend in a separate background job or window
$backendDir = Join-Path $PSScriptRoot "backend"
$frontendDir = Join-Path $PSScriptRoot "frontend"

Write-Host "`n[1/2] Starting FastAPI backend on http://localhost:8000..." -ForegroundColor Yellow
$backendJob = Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$backendDir'; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload" -PassThru

# 2. Start Next.js Frontend in current terminal
Write-Host "[2/2] Starting Next.js frontend on http://localhost:3000..." -ForegroundColor Yellow
cd $frontendDir
npm run dev
