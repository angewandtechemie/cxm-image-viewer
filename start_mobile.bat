@echo off
rem CxM Mobile launcher: serves this folder on the LAN so a phone can open cxm-mobile.html.
rem Run from any git clone: double-click, then open the printed URL on the phone.
setlocal
set PORT=8642
if not exist "%~dp0cxm-mobile.html" (
  echo Error: cxm-mobile.html not found next to this bat.
  pause
  exit /b 1
)
netstat -ano | findstr "LISTENING" | findstr ":%PORT% " >nul
if not errorlevel 1 (
  echo Port %PORT% already in use. Close the old server window first.
  pause
  exit /b 1
)
rem Prefer python (binds all interfaces, no admin needed). Fallback: serve.ps1 -lan.
where py >nul 2>nul
if not errorlevel 1 (
  start "CxM Mobile server" /min py -m http.server %PORT% --bind 0.0.0.0 --directory "%~dp0."
) else (
  start "CxM Mobile server" /min powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0serve.ps1" -lan -port %PORT%
)
timeout /t 2 /nobatch >nul
rem Show the LAN URL for the phone.
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "(Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' -and $_.PrefixOrigin -ne 'WellKnown' } | Sort-Object InterfaceMetric | Select-Object -First 1 -ExpandProperty IPAddress)"`) do set LANIP=%%I
if defined LANIP (
  echo.
  echo   Open this on your phone ^(same Wi-Fi^):
  echo     http://%LANIP%:%PORT%/cxm-mobile.html
  echo.
) else (
  echo Could not detect LAN IP. Try http://THIS-PC-IP:%PORT%/cxm-mobile.html
)
start "" "http://127.0.0.1:%PORT%/cxm-mobile.html"
echo Server keeps running in the minimized window. Close it to stop.
