@echo off
rem CxM Image viewer launcher (no Python needed; uses Windows PowerShell)
if not exist "%~dp0index.html" (
  echo Error: index.html not found next to this bat.
  echo Extract the whole zip first, then run start_viewer.bat inside the folder.
  pause
  exit /b 1
)
netstat -ano | findstr "LISTENING" | findstr ":8642 " >nul
if not errorlevel 1 (
  echo Port 8642 already in use. Close the old server window first.
  pause
  exit /b 1
)
start "" /min powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0serve.ps1"
timeout /t 1 /nobatch >nul
start "" "http://127.0.0.1:8642/"
