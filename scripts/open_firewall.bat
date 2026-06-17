@echo off
echo ========================================================
echo Screen Monitoring System Pro - Open Firewall Ports
echo ========================================================

REM Check for Administrator privileges
NET SESSION >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo [ERROR] You must run this script as Administrator!
    echo Please right-click on this script and select "Run as administrator".
    pause
    exit /B
)

echo [1/2] Opening port 8765 for WebSocket Server...
netsh advfirewall firewall add rule name="Screen Monitor Server WS" dir=in action=allow protocol=TCP localport=8765

echo [2/2] Opening port 8080 for API Server...
netsh advfirewall firewall add rule name="Screen Monitor Server API" dir=in action=allow protocol=TCP localport=8080

echo.
echo Firewall ports have been successfully opened!
echo Client machines should now be able to connect to the server.
pause
