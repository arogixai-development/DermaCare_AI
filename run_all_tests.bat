@echo off
REM DermaCare AI - Run All Tests (Windows)
REM ========================================
echo ================================================================
echo DermaCare AI - Test Suite
echo ================================================================
echo.

cd /d "%~dp0"

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

REM Start Ollama if not running
echo Checking Ollama...
ollama list >nul 2>&1
if errorlevel 1 (
    echo Starting Ollama...
    start ollama serve
    timeout /t 5
)

REM Start Backend if not running
echo Checking Backend...
curl -s http://127.0.0.1:8000/health >nul 2>&1
if errorlevel 1 (
    echo Starting Backend...
    start "DermaCare Backend" cmd /c python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000
    timeout /t 5
)

REM Run comprehensive tests
echo.
echo Running Comprehensive Tests...
echo ================================================================
python test_comprehensive.py

REM Run security tests
echo.
echo Running Security Tests...
echo ================================================================
python quick_security_test.py

echo.
echo ================================================================
echo All Tests Complete
echo ================================================================
pause
