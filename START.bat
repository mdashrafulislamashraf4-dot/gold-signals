@echo off
echo ============================================================
echo   AI GOLD SIGNAL SYSTEM - Starting...
echo ============================================================
echo.

set PYTHON="C:\Users\Ashraful Islam\AppData\Local\Programs\Python\Python312\python.exe"

if not exist .env (
    echo ERROR: .env file not found!
    echo Please configure your API keys in the .env file first.
    pause
    exit /b 1
)

echo Starting AI Gold Signal System...
echo Press Ctrl+C to stop.
echo.
%PYTHON% main.py

pause
