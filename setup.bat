@echo off
echo ============================================================
echo   AI GOLD SIGNAL SYSTEM - Setup Script
echo ============================================================
echo.

:: Try to find Python in common locations
set PYTHON_CMD=
for %%p in (
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python310\python.exe"
) do (
    if exist %%p (
        set PYTHON_CMD=%%p
        goto :found_python
    )
)

:: Check AppData
for %%v in (Python312 Python311 Python310 Python39) do (
    if exist "%USERPROFILE%\AppData\Local\Programs\Python\%%v\python.exe" (
        set PYTHON_CMD="%USERPROFILE%\AppData\Local\Programs\Python\%%v\python.exe"
        goto :found_python
    )
)

:: Check PATH
where python.exe >nul 2>&1
if not errorlevel 1 (
    set PYTHON_CMD=python
    goto :found_python
)

echo ERROR: Python is not installed or not found!
echo.
echo Please install Python 3.10+ from: https://www.python.org/downloads/
echo Make sure to check "Add Python to PATH" during installation!
echo.
echo After installing Python, run this setup.bat again.
pause
exit /b 1

:found_python
echo [OK] Python found: %PYTHON_CMD%
%PYTHON_CMD% --version
echo.

echo [1/4] Installing dependencies...
%PYTHON_CMD% -m pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Failed to install dependencies!
    pause
    exit /b 1
)

echo.
echo [2/4] Creating .env file from template...
if not exist .env (
    copy .env.example .env
    echo .env file created! Please edit it with your API keys.
) else (
    echo .env already exists. Skipping...
)

echo.
echo [3/4] Creating required directories...
if not exist database mkdir database
if not exist logs mkdir logs
echo Directories created.

echo.
echo [4/4] Setup complete!
echo.
echo ============================================================
echo   NEXT STEPS:
echo ============================================================
echo.
echo 1. Edit the .env file with your API keys:
echo    - TELEGRAM_BOT_TOKEN (from @BotFather on Telegram)
echo    - TELEGRAM_CHAT_ID   (your Telegram chat ID)
echo    - GEMINI_API_KEY     (FREE from aistudio.google.com)
echo    - NEWS_API_KEY       (FREE from newsapi.org)
echo.
echo 2. Run the system by double-clicking START.bat
echo    OR run: python main.py
echo.
echo ============================================================
echo.
pause
