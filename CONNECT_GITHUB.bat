@echo off
chcp 65001 >nul
echo ============================================================
echo   AI GOLD SIGNAL - ONE-CLICK GITHUB CONNECT
echo ============================================================
echo.
echo ১. এখন আপনার ব্রাউজারে GitHub লগইন পেজ খুলবে এবং একটি কোড দেখাবে।
echo ২. শুধু কোডটি কনফার্ম করুন (Authorize চাপুন)।
echo ৩. বাকি সব কাজ (Repository তৈরি ও কোড আপলোড) স্বয়ংক্রিয়ভাবে হয়ে যাবে!
echo.
pause

echo.
echo [1/2] Logging into GitHub...
gh_bin\bin\gh.exe auth login --hostname github.com -p https -w

if errorlevel 1 (
    echo.
    echo ❌ লগইন সফল হয়নি। আবার চেষ্টা করুন।
    pause
    exit /b 1
)

echo.
echo [2/2] Creating GitHub Repository and Uploading Code...
git remote remove origin >nul 2>&1
gh_bin\bin\gh.exe repo create gold-ai-signals --public --source=. --remote=origin --push

if errorlevel 1 (
    echo.
    echo [Info] Repo might already exist, pushing changes...
    git push -u origin main --force
)

echo.
echo ============================================================
echo   ✅ সফলভাবে GitHub-এ কোড আপলোড হয়ে গেছে!
echo ============================================================
echo.
echo আপনার রিপোজিটরি লিংক দেখতে:
gh_bin\bin\gh.exe repo view --web
echo.
pause
