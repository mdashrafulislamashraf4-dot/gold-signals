@echo off
cls
echo ============================================================
echo   AI GOLD SIGNAL - UPLOADING TO GITHUB
echo ============================================================
echo.
echo Target Repo: https://github.com/mdashrafulislamashraf4-dot/gold-signals.git
echo.
echo [1/2] Preparing files...
git branch -M main

echo.
echo [2/2] Uploading to GitHub...
echo If a window pops up, click "Sign in with your browser"...
echo.
git push -u origin main

if %ERRORLEVEL% EQU 0 (
    echo.
    echo ============================================================
    echo   SUCCESS! Upload to GitHub is complete!
    echo ============================================================
) else (
    echo.
    echo Upload failed. Please check your internet or GitHub login.
)

echo.
pause
