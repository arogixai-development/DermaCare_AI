@echo off
REM DermaCare AI - Windows Launcher Script
REM ========================================
REM This script starts Ollama, Backend, and Frontend servers

echo ========================================
echo DermaCare AI - Starting Services
echo ========================================

REM Set working directory
cd /d "%~dp0"

REM Check if virtual environment exists
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

REM Install dependencies if needed
echo Checking dependencies...
pip install -q -r requirements.txt 2>nul

REM Step 1: Start Ollama (if not running)
echo.
echo [1/3] Checking Ollama...
netstat -an | findstr "11434" >nul
if %errorlevel% neq 0 (
    echo Starting Ollama service...
    start /min cmd /c "ollama serve"
    timeout /t 5 /nobreak >nul
) else (
    echo Ollama already running on port 11434
)

REM Step 2: Start Backend
echo.
echo [2/3] Starting Backend (FastAPI on port 8000)...
start /min cmd /c "python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --reload"

REM Wait for backend to be ready
timeout /t 3 /nobreak >nul

REM Step 3: Start Frontend
echo.
echo [3/3] Starting Frontend (Static server on port 3000)...
start /min cmd /c "python -m http.server 3000"

echo.
echo ========================================
echo DermaCare AI Services Started
echo ========================================
echo.
echo Backend API:  http://127.0.0.1:8000
echo Frontend:     http://localhost:3000
echo Health:       http://127.0.0.1:8000/health
echo.
echo Default admin credentials:
echo   Username: admin
echo   Password: (check terminal output on first run)
echo.
echo Press any key to open browser...
pause >nul

REM Open browser
start http://localhost:3000

echo.
echo Services are running. Keep this window open.
echo Press Ctrl+C to stop all services.
pause
