@echo off
set PORT=8000
title PBIP Sentinel - Studio Launcher

echo ============================================================
echo   PBIP Sentinel - Power BI Diagnostic Workbench
echo ============================================================
echo.

echo [*] Checking and freeing port %PORT% if in use...
powershell -NoProfile -Command "$conns = Get-NetTCPConnection -LocalPort %PORT% -ErrorAction SilentlyContinue; if ($conns) { foreach ($c in $conns) { try { Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue } catch {} } }"

echo [*] Starting PBIP Sentinel Studio on http://127.0.0.1:%PORT%...
echo.
python -m pbiscan studio --port %PORT%

if %ERRORLEVEL% neq 0 (
    echo.
    echo [!] Server exited with code %ERRORLEVEL%
    pause
)
