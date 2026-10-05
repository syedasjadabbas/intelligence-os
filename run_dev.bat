@echo off
echo ==========================================================
echo   Starting Intelligence OS (FastAPI Backend + Next.js UI)
echo ==========================================================

start "Intelligence OS Backend" cmd /k "cd /d %~dp0backend && .venv\Scripts\activate && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

timeout /t 2 /nobreak >nul

echo Starting Next.js frontend on http://localhost:3000...
cd /d %~dp0frontend
npm run dev
