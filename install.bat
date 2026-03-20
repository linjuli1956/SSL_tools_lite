@echo off
echo ========================================
echo    SSL Certificate Manager - Install
echo ========================================
echo.
echo Installing dependencies...
echo.

pip install flask cryptography paramiko

echo.
echo Installation complete!
echo.
echo Run start.bat to start the service
echo.

pause
