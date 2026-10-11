# 🏆 AI GOLD SIGNAL SYSTEM — সেটআপ গাইড

## ধাপ ১: Telegram Bot তৈরি করুন

1. Telegram খুলুন, `@BotFather` সার্চ করুন
2. `/newbot` টাইপ করুন
3. Bot-এর নাম দিন (যেমন: `Gold Signal Bot`)
4. Username দিন (যেমন: `my_gold_signal_bot`)
5. **Bot Token** কপি করুন (এরকম দেখাবে: `1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ`)

## ধাপ ২: আপনার Chat ID বের করুন

1. `@userinfobot` বা `@getmyid_bot`-এ `/start` পাঠান
2. আপনার **Chat ID** কপি করুন (সংখ্যা)

## ধাপ ৩: Gemini API Key নিন (বিনামূল্যে)

1. https://aistudio.google.com যান
2. Google account দিয়ে লগইন করুন
3. "Get API Key" → "Create API Key" ক্লিক করুন
4. **API Key** কপি করুন

## ধাপ ৪: NewsAPI Key নিন (বিনামূল্যে)

1. https://newsapi.org/register যান
2. ফ্রি একাউন্ট তৈরি করুন
3. **API Key** কপি করুন (100 requests/day ফ্রি)

## ধাপ ৫: `.env` ফাইল এডিট করুন

`.env` ফাইলটি Notepad দিয়ে খুলুন এবং আপনার key গুলো দিন:

```
TELEGRAM_BOT_TOKEN=আপনার_বট_টোকেন
TELEGRAM_CHAT_ID=আপনার_চ্যাট_আইডি
GEMINI_API_KEY=আপনার_জেমিনি_কী
NEWS_API_KEY=আপনার_নিউজ_কী
```

## ধাপ ৬: সিস্টেম চালু করুন

```
setup.bat চালান (প্রথমবার)
তারপর START.bat চালান
```

অথবা:
```bash
pip install -r requirements.txt
python main.py
```

---

## Cloud Hosting (Render.com — বিনামূল্যে)

1. https://render.com যান, GitHub দিয়ে লগইন করুন
2. GitHub-এ এই প্রজেক্টটি আপলোড করুন
3. Render-এ "New Web Service" → GitHub repo সিলেক্ট করুন
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `python main.py`
6. Environment Variables-এ `.env`-এর সব key দিন
7. Deploy করুন — ২৪/৭ চলবে!

---

## সিস্টেম কীভাবে কাজ করে

```
প্রতি ১৫ মিনিটে:
  ✅ Gold price ফেচ
  ✅ Technical indicators calculate
  ✅ News sentiment analyze
  ✅ AI (Gemini) analysis
  ✅ Signal generate → Telegram-এ পাঠায়

প্রতি ৩ মিনিটে:
  ✅ Active signals monitor
  ✅ TP/SL hit হলে alert পাঠায়

প্রতি ৩০ মিনিটে:
  ✅ High-impact news monitor
  ✅ News alert পাঠায়

রাত ১২টায়:
  ✅ Daily performance report

শুক্রবার বিকেলে:
  ✅ Weekly performance report
```

---

## Telegram Commands

| Command | কাজ |
|---|---|
| `/signal` | লেটেস্ট BUY/SELL সিগনাল |
| `/price` | বর্তমান Gold প্রাইস |
| `/news` | লেটেস্ট Gold নিউজ |
| `/analysis` | সম্পূর্ণ টেকনিক্যাল এনালাইসিস |
| `/calendar` | আজকের economic events |
| `/report` | আজকের performance |
| `/weekly` | সাপ্তাহিক performance |
| `/status` | সিস্টেম status |
| `/help` | সব command দেখুন |

---

> ⚠️ **ঝুঁকির সতর্কতা**: ট্রেডিং সবসময় ঝুঁকিপূর্ণ। AI সিগনাল যতই নির্ভুল হোক, বাজারে অনিশ্চয়তা থাকেই। সর্বদা ২% এর বেশি রিস্ক নেবেন না এবং SL মেনে চলুন।
