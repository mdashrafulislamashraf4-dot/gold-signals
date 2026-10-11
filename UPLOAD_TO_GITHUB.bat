@echo off
chcp 65001 >nul
echo ============================================================
echo   AI GOLD SIGNAL - UPLOADING TO GITHUB...
echo ============================================================
echo.
echo আপনার রিপোজিটরি: https://github.com/mdashrafulislamashraf4-dot/gold-signals.git
echo.
echo [1/3] Adding files to git...
git add .
git commit -m "Upload AI Gold Signal System" >nul 2>&1

echo [2/3] Setting remote...
git remote remove origin >nul 2>&1
git remote add origin https://github.com/mdashrafulislamashraf4-dot/gold-signals.git
git branch -M main

echo [3/3] Uploading files to GitHub...
echo (যদি কোনো ব্রাউজার উইন্ডো আসে, শুধু "Sign in" ক্লিক করুন)
git push -u origin main

if errorlevel 1 (
    echo.
    echo ❌ সমস্যা হয়েছে। দয়া করে আবার চেষ্টা করুন।
) else (
    echo.
    echo ============================================================
    echo   ✅ অভিনন্দন! কোড সফলভাবে GitHub-এ আপলোড হয়ে গেছে!
    echo ============================================================
)

echo.
pause
