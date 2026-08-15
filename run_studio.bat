@echo off
setlocal enabledelayedexpansion
title PBIP Sentinel - Studio Launcher

echo ============================================================
echo   PBIP Sentinel - Power BI Diagnostic Workbench
echo ============================================================
echo.

set PORT=8000

echo [*] Checking for existing processes on port %PORT%...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr ":%PORT%" ^| findstr "LISTENING"') do (
    echo [*] Terminating existing process on port %PORT% (PID: %%a)...
    taskkill /F /PID %%a >nul 2>&1
)

echo [*] Starting PBIP Sentinel Studio on http://127.0.0.1:%PORT%...
echo.
python -m pbiscan studio --port %PORT%

if %ERRORLEVEL% neq 0 (
    echo.
    echo [!] Server exited with code %ERRORLEVEL%
    pause
)
