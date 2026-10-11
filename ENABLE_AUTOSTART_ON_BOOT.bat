@echo off
chcp 65001 >nul
echo ============================================================
echo   AI GOLD SIGNAL - WINDOWS AUTO-START ENABLER
echo ============================================================
echo.
echo এই স্ক্রিপ্টটি চালু করলে:
echo আপনার কম্পিউটার অন করার সাথে সাথে বটটি কোনো কমান্ড প্রম্পট বা উইন্ডো
echo ছাড়াই সম্পূর্ণ ব্যাকগ্রাউন্ডে নিরবে চালু হয়ে যাবে!
echo.
pause

set "STARTUP_FOLDER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup"
set "TARGET_VBS=%~dp0RUN_BACKGROUND.vbs"
set "SHORTCUT=%STARTUP_FOLDER%\GoldSignalBot.lnk"

powershell -Command "$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('%SHORTCUT%'); $s.TargetPath = 'wscript.exe'; $s.Arguments = '\"%TARGET_VBS%\"'; $s.WorkingDirectory = '%~dp0'; $s.Save()"

if exist "%SHORTCUT%" (
    echo.
    echo ✅ সফলভাবে অটো-স্টার্ট চালু করা হয়েছে!
    echo এখন থেকে কম্পিউটার অন করলেই বট একা একা ব্যাকগ্রাউন্ডে চলবে।
) else (
    echo.
    echo ❌ অটো-স্টার্ট সেট করতে সমস্যা হয়েছে।
)

echo.
pause
