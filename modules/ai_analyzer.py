"""
============================================================
  modules/ai_analyzer.py
  Google Gemini AI দিয়ে গভীর মার্কেট এনালাইসিস
============================================================
"""

import logging
from typing import Optional

import google.generativeai as genai

logger = logging.getLogger(__name__)


class AIAnalyzer:
    """Gemini AI দিয়ে সম্পূর্ণ গোল্ড মার্কেট এনালাইসিস করে"""

    SYSTEM_PROMPT = """You are an expert XAUUSD (Gold) forex and commodities trader with 20+ years of experience.
You analyze gold markets using technical analysis, fundamental analysis, news sentiment, and geopolitical factors.
Always provide precise, actionable trading signals with clear entry, TP, and SL levels.
Be concise, accurate, and professional. Always consider risk management.
Respond in a structured JSON-compatible format."""

    MODELS = [
        "gemini-3.1-flash-lite",
        "gemini-3.5-flash-lite",
        "gemini-flash-lite-latest",
        "gemini-3.8-flash",
    ]

    def __init__(self, api_key: str):
        if api_key:
            genai.configure(api_key=api_key)
            self.available = True
            logger.info("Gemini AI initialized with multi-model fallback")
        else:
            self.available = False
            logger.warning("No Gemini API key — AI analysis disabled")

    def _generate(self, prompt: str, system_prompt: str = None) -> Optional[str]:
        """একাধিক মডেল ট্রাই করে যাতে কোটা শেষ না হয়"""
        if not self.available:
            return None
        sys_inst = system_prompt or self.SYSTEM_PROMPT
        for model_name in self.MODELS:
            try:
                m = genai.GenerativeModel(model_name, system_instruction=sys_inst)
                res = m.generate_content(prompt)
                if res and res.text:
                    return res.text.strip()
            except Exception as e:
                logger.warning(f"Model {model_name} quota/error: {e}")
        return None

    # ─────────────────────────────────────────────────────────
    # Full Market Analysis
    # ─────────────────────────────────────────────────────────
    def analyze_market(
        self,
        current_price: float,
        technical_data: dict,
        news_sentiment: dict,
        correlated_assets: dict,
        timeframe: str = "H1",
    ) -> dict:
        """
        সব ডেটা কম্বাইন করে Gemini AI দিয়ে গভীর এনালাইসিস করে
        """
        if not self.available:
            return self._fallback_analysis(current_price, technical_data, news_sentiment)

        try:
            prompt = self._build_prompt(
                current_price, technical_data, news_sentiment,
                correlated_assets, timeframe
            )
            ai_text = self._generate(prompt)
            if ai_text:
                parsed = self._parse_ai_response(ai_text, current_price, technical_data)
                logger.info(f"AI Analysis complete: {parsed.get('direction')} | Confidence: {parsed.get('confidence')}%")
                return parsed
            else:
                return self._fallback_analysis(current_price, technical_data, news_sentiment)
        except Exception as e:
            logger.error(f"Gemini AI error: {e}")
            return self._fallback_analysis(current_price, technical_data, news_sentiment)

    def _build_prompt(self, price, tech, news, corr, tf) -> str:
        """AI-এর জন্য বিস্তারিত প্রম্পট তৈরি করে"""

        buy_sigs  = "\n  - ".join(tech.get("buy_signals", [])[:5])
        sell_sigs = "\n  - ".join(tech.get("sell_signals", [])[:5])
        patterns  = ", ".join([p[0] for p in tech.get("patterns", [])]) or "None"
        key_news  = "\n  - ".join(news.get("key_events", [])[:4]) or "No major news"

        details = tech.get("details", {})
        fib     = tech.get("fibonacci", {})

        corr_str = ""
        for name, val in corr.items():
            corr_str += f"  {name}: {val.get('price','N/A')} ({val.get('change_pct','N/A')}%)\n"

        fib_str = ""
        for level, price_val in fib.items():
            fib_str += f"  Fib {level}%: {price_val}\n"

        prompt = f"""
Analyze XAUUSD (Gold) market and provide a trading signal.

## Current Market Data
- Current Price: ${price}
- Timeframe: {tf}
- Market Status: Active

## Technical Indicators & Multi-Oscillator Metrics
- Trend:
  - SuperTrend (10,3): {details.get('SuperTrend', 'N/A')} (${details.get('SuperTrend_Val', 'N/A')})
  - Parabolic SAR: ${details.get('PSAR', 'N/A')}
  - Hull MA (HMA 16): ${details.get('HMA_16', 'N/A')}
  - EMA 20: ${details.get('EMA_20', 'N/A')} | EMA 50: ${details.get('EMA_50', 'N/A')} | EMA 200: ${details.get('EMA_200', 'N/A')}
  - Ichimoku: Tenkan=${details.get('Ichimoku_Tenkan', 'N/A')}, Kijun=${details.get('Ichimoku_Kijun', 'N/A')}
- Momentum & Oscillators:
  - RSI(14): {details.get('RSI', 'N/A')}
  - MACD: {details.get('MACD', 'N/A')} (Signal: {details.get('MACD_Signal', 'N/A')})
  - Stochastic K: {details.get('Stochastic_K', 'N/A')} | D: {details.get('Stochastic_D', 'N/A')}
  - Stochastic RSI (Fast): {details.get('StochRSI_K', 'N/A')}
  - CCI (Commodity Channel Index 20): {details.get('CCI', 'N/A')}
  - Williams %R: {details.get('Williams_R', 'N/A')}
  - Awesome Oscillator (AO): {details.get('Awesome_Osc', 'N/A')}
  - ADX (Trend Strength): {details.get('ADX', 'N/A')}
- Volatility & Squeeze:
  - ATR (14): ${details.get('ATR', 'N/A')}
  - Bollinger Bands: Upper=${details.get('BB_Upper', 'N/A')}, Lower=${details.get('BB_Lower', 'N/A')}
  - TTM Bollinger/Keltner Squeeze: {details.get('Squeeze', 'RELEASED')}
- Smart Money & Volume:
  - Institutional VWAP: ${details.get('VWAP', 'N/A')}
  - Money Flow Index (MFI 14): {details.get('MFI', 'N/A')}
  - Chaikin Money Flow (CMF 20): {details.get('CMF', 'N/A')}

## Technical Confluence Summary
- Bullish Indicator Signals ({len(tech.get('buy_signals', []))} count):
  - {buy_sigs}
- Bearish Indicator Signals ({len(tech.get('sell_signals', []))} count):
  - {sell_sigs}
- Overall Technical Score: {tech.get('score', 50)}/100
- Candlestick Patterns: {patterns}
- Divergences: {", ".join([d[0] for d in tech.get('divergences', [])]) or "None"}
- Daily Pivot: ${details.get('Pivot_Point', 'N/A')} (Camarilla Breakout H4: ${details.get('Cam_H4', 'N/A')}, L4: ${details.get('Cam_L4', 'N/A')})

## Fibonacci Levels
{fib_str}

## Correlated Markets
{corr_str}

## News Sentiment
- Sentiment Score: {news.get('score', 50)}/100
- Direction: {news.get('direction', 'NEUTRAL')}
- Impact Level: {news.get('impact', 'LOW')}
- Key Events:
  - {key_news}

## Your Task
Provide a complete trading analysis.
IMPORTANT LANGUAGE REQUIREMENT:
- Keep SIGNAL strictly as [BUY/SELL/NEUTRAL].
- Keep numeric numbers (ENTRY, TP1, TP2, TP3, SL, R_R) as numbers.
- Provide all REASONING (কারণ ও যুক্তি) and WARNINGS (সতর্কতা) strictly in natural, professional BENGALI (বাংলা ভাষায়).

Format your response EXACTLY like this:
SIGNAL: [BUY/SELL/NEUTRAL]
CONFIDENCE: [number]%
ENTRY: [price]
TP1: [price]
TP2: [price]
TP3: [price]
SL: [price]
R_R: [ratio like 1:2.5]
RISK: [কম/মাঝারি/উচ্চ]
VALIDITY: [মেয়াদ যেমন ৪-৮ ঘণ্টা]
REASONING:
- [বাংলায় কারণ ১ - যেমন: আরএসআই ওভারসোল্ড জোন থেকে বাউন্স করেছে]
- [বাংলায় কারণ ২ - যেমন: ভূরাজনৈতিক উত্তেজনায় ডলার দুর্বল হচ্ছে]
- [বাংলায় কারণ ৩ - যেমন: প্রাইস গুরুত্বপূর্ণ ২০০-ইএমএ সাপোর্টের উপরে আছে]
WARNINGS:
- [বাংলায় সতর্কতা ১ - যেমন: আসন্ন মার্কিন সিপিআই নিউজের দিকে নজর রাখুন]
- [বাংলায় সতর্কতা ২ - যেমন: প্রতি ট্রেডে ২% এর বেশি ঝুঁকি নেবেন না]
"""
        return prompt

    def _parse_ai_response(self, text: str, current_price: float, tech: dict) -> dict:
        """AI response parse করে structured dict বানায়"""
        result = {
            "direction":   "NEUTRAL",
            "confidence":  60,
            "entry":       current_price,
            "tp1":         0,
            "tp2":         0,
            "tp3":         0,
            "sl":          0,
            "rr_ratio":    "1:2",
            "risk_level":  "MEDIUM",
            "validity":    "4-8 hours",
            "reasoning":   [],
            "warnings":    [],
            "raw_response": text,
        }

        lines = text.strip().split("\n")
        current_section = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith("SIGNAL:"):
                val = line.replace("SIGNAL:", "").strip()
                if "BUY" in val.upper():
                    result["direction"] = "BUY"
                elif "SELL" in val.upper():
                    result["direction"] = "SELL"
                else:
                    result["direction"] = "NEUTRAL"

            elif line.startswith("CONFIDENCE:"):
                try:
                    val = line.replace("CONFIDENCE:", "").replace("%", "").strip()
                    result["confidence"] = int(float(val))
                except Exception:
                    pass

            elif line.startswith("ENTRY:"):
                try:
                    val = line.replace("ENTRY:", "").replace("$", "").replace(",", "").strip()
                    result["entry"] = float(val)
                except Exception:
                    result["entry"] = current_price

            elif line.startswith("TP1:"):
                try:
                    val = line.replace("TP1:", "").replace("$", "").replace(",", "").strip()
                    result["tp1"] = float(val)
                except Exception:
                    pass

            elif line.startswith("TP2:"):
                try:
                    val = line.replace("TP2:", "").replace("$", "").replace(",", "").strip()
                    result["tp2"] = float(val)
                except Exception:
                    pass

            elif line.startswith("TP3:"):
                try:
                    val = line.replace("TP3:", "").replace("$", "").replace(",", "").strip()
                    result["tp3"] = float(val)
                except Exception:
                    pass

            elif line.startswith("SL:"):
                try:
                    val = line.replace("SL:", "").replace("$", "").replace(",", "").strip()
                    result["sl"] = float(val)
                except Exception:
                    pass

            elif line.startswith("R_R:"):
                result["rr_ratio"] = line.replace("R_R:", "").strip()

            elif line.startswith("RISK:"):
                result["risk_level"] = line.replace("RISK:", "").strip()

            elif line.startswith("VALIDITY:"):
                result["validity"] = line.replace("VALIDITY:", "").strip()

            elif line.startswith("REASONING:"):
                current_section = "reasoning"

            elif line.startswith("WARNINGS:"):
                current_section = "warnings"

            elif line.startswith("-") and current_section:
                content = line[1:].strip()
                if content:
                    result[current_section].append(content)

        # Fallback TP/SL using ATR if AI didn't provide
        atr = tech.get("details", {}).get("ATR", 15)
        if result["tp1"] == 0 or result["tp1"] == current_price:
            if result["direction"] == "BUY":
                result["tp1"] = round(current_price + atr * 1.5, 2)
                result["tp2"] = round(current_price + atr * 3.0, 2)
                result["tp3"] = round(current_price + atr * 5.0, 2)
                result["sl"]  = round(current_price - atr * 1.0, 2)
            elif result["direction"] == "SELL":
                result["tp1"] = round(current_price - atr * 1.5, 2)
                result["tp2"] = round(current_price - atr * 3.0, 2)
                result["tp3"] = round(current_price - atr * 5.0, 2)
                result["sl"]  = round(current_price + atr * 1.0, 2)

        return result

    # ─────────────────────────────────────────────────────────
    # Fallback (no AI)
    # ─────────────────────────────────────────────────────────
    def _fallback_analysis(self, price: float, tech: dict, news: dict) -> dict:
        """Gemini ছাড়াও basic analysis করে"""
        tech_score  = tech.get("score", 50)
        news_score  = news.get("score", 50)
        combo_score = (tech_score * 0.6) + (news_score * 0.4)

        if combo_score >= 65:
            direction = "BUY"
        elif combo_score <= 35:
            direction = "SELL"
        else:
            direction = "NEUTRAL"

        atr = tech.get("details", {}).get("ATR", 15)
        confidence = int(abs(combo_score - 50) * 2)

        result = {
            "direction":  direction,
            "confidence": min(confidence + 40, 85),
            "entry":      price,
            "rr_ratio":   "1:2",
            "risk_level": "MEDIUM",
            "validity":   "4-8 hours",
            "reasoning":  tech.get("buy_signals", [])[:3] or tech.get("sell_signals", [])[:3],
            "warnings":   ["Using fallback analysis (no AI key configured)"],
            "raw_response": "Fallback mode",
        }

        if direction == "BUY":
            result["tp1"] = round(price + atr * 1.5, 2)
            result["tp2"] = round(price + atr * 3.0, 2)
            result["tp3"] = round(price + atr * 5.0, 2)
            result["sl"]  = round(price - atr * 1.0, 2)
        elif direction == "SELL":
            result["tp1"] = round(price - atr * 1.5, 2)
            result["tp2"] = round(price - atr * 3.0, 2)
            result["tp3"] = round(price - atr * 5.0, 2)
            result["sl"]  = round(price + atr * 1.0, 2)
        else:
            result["tp1"] = result["tp2"] = result["tp3"] = price
            result["sl"]  = price

        return result

    # ─────────────────────────────────────────────────────────
    # News Impact Analysis (AI-powered)
    # ─────────────────────────────────────────────────────────
    # Evaluate & Filter Major Breaking News (বড় খবর যাচাই)
    # ─────────────────────────────────────────────────────────
    def evaluate_breaking_news(self, news_title: str, news_summary: str, current_price: float) -> Optional[str]:
        """
        যাচাই করে এটি কি আসলেই গোল্ড মার্কেটে বড় প্রভাব ফেলার মতো ব্রেকিং নিউজ কি না।
        ছোটখাটো খবর, সাধারণ কমেন্ট্রি, বা দৈনিক পূর্বাভাস হলে None রিটার্ন করে এলার্ট বাতিল করবে।
        """
        if not self.available:
            return None

        prompt = f"""
You are a senior Gold (XAUUSD) market analyst and macroeconomic risk specialist.
Critically evaluate the following news item:
Title: "{news_title}"
Summary: "{news_summary}"
Current Gold Price: ${current_price}

Your task: Determine if this is a GENUINE MAJOR BREAKING EVENT that will cause SUBSTANTIAL market volatility (at least $15 - $30+ sudden move in Gold price), such as:
1. Significant geopolitical escalation (direct war strikes, missile attacks, major conflict escalation involving major powers like Middle East, Russia/Ukraine, US/China, nuclear tensions).
2. Major central bank policy surprises or emergency statements (Fed rate decision, emergency rate cut/hike, surprise Powell announcement).
3. Major economic shocks (surprise CPI/NFP release deviating heavily from estimates, sovereign debt crisis, banking collapse).

STRICT EXCLUSIONS - MUST BE REJECTED:
- Routine daily market commentary or price recaps ("Gold rises as dollar softens", "Gold holds steady")
- Analyst forecasts, technical analysis, price targets ("Gold Price Forecast: XAUUSD looks to plunge...", "Gold price targets $4200")
- Routine opinions, newsletters, opinion pieces, or daily summaries
- Local city gold rates or jewelry store prices
- Routine geopolitical commentary without new breaking attacks/events

INSTRUCTIONS:
If this news is ROUTINE, MINOR, AN OPINION, OR A FORECAST:
Respond strictly with single word:
SKIP

If this news is truly a MAJOR BREAKING MARKET-MOVING EVENT:
Start with "APPROVED:" and provide a professional, concise impact assessment strictly in natural BENGALI (বাংলা ভাষায়):
• <b>সংক্ষিপ্ত খবর:</b> [বাংলায় ১ লাইনে কি ঘটেছে]
• <b>মার্কেট অভিমুখ:</b> [বুলিশ (দাম বাড়ার তীব্র সম্ভাবনা 🟢) / বেয়ারিশ (দাম কমার তীব্র সম্ভাবনা 🔴) / চরম অস্থিরতা ⚠️]
• <b>প্রত্যাশিত মুভমেন্ট:</b> [আনুমানিক কত ডলার ওঠানামা হতে পারে, যেমন $১৫-$৩০]
• <b>কেন বড় প্রভাব পড়বে:</b> [১-২ লাইনে মূল অর্থনৈতিক/ভূরাজনৈতিক কারণ]
• <b>ট্রেডারদের করণীয়:</b> [১ লাইনে তাৎক্ষণিক পরামর্শ]
"""
        try:
            ai_text = self._generate(prompt)
            if not ai_text:
                return None
            ai_text = ai_text.strip()
            if "SKIP" in ai_text.upper() and "APPROVED:" not in ai_text:
                return None
            if "APPROVED:" in ai_text:
                clean_text = ai_text.split("APPROVED:", 1)[1].strip()
                return clean_text
            return None
        except Exception as e:
            logger.error(f"Breaking news evaluation error: {e}")
            return None

    def analyze_news_impact(self, news_title: str, current_price: float) -> str:
        """একটি নির্দিষ্ট নিউজের গোল্ড মার্কেটে প্রভাব বাংলায় বিশ্লেষণ করে"""
        if not self.available:
            return "এআই বিশ্লেষণ এই মুহূর্তে প্রস্তুত নয়।"

        try:
            prompt = f"""
You are an expert XAUUSD (Gold) commodities trader and market analyst.
Analyze the impact of this breaking news on XAUUSD (Gold) price.
Provide your response strictly in natural, professional BENGALI (বাংলা ভাষায়):

News: "{news_title}"
Current Gold Price: ${current_price}

Provide a concise analysis in Bengali using this exact layout:
• <b>অভিমুখ (Impact Direction):</b> [বুলিশ (দাম বাড়ার সম্ভাবনা 🟢) / বেয়ারিশ (দাম কমার সম্ভাবনা 🔴) / নিরপেক্ষ ⚪]
• <b>প্রত্যাশিত প্রভাব:</b> [আনুমানিক ৫-২০ ডলার বা কত মুভমেন্ট হতে পারে]
• <b>জরুরি মাত্রা:</b> [উচ্চ ঝুঁকি / মাঝারি / সাধারণ]
• <b>ট্রেডারদের প্রতি পরামর্শ:</b> [বাংলায় ১-২ লাইনে ট্রেডারদের কি করণীয় তা বলুন]
"""
            ai_text = self._generate(prompt)
            return ai_text if ai_text else "নিউজ প্রভাব বিশ্লেষণ করা সম্ভব হয়নি।"
        except Exception as e:
            logger.error(f"News impact analysis error: {e}")
            return "নিউজ প্রভাব বিশ্লেষণ করা সম্ভব হয়নি।"

    # ─────────────────────────────────────────────────────────
    # Generate Weekly Summary (AI-powered in Bengali)
    # ─────────────────────────────────────────────────────────
    def generate_weekly_summary(self, signals_data: list, win_rate: float) -> str:
        """সাপ্তাহিক সিগনাল পারফরম্যান্স সারাংশ বাংলায় তৈরি করে"""
        if not self.available or not signals_data:
            return "সাপ্তাহিক এআই পর্যালোচনা এই মুহূর্তে প্রস্তুত নয়।"

        try:
            prompt = f"""
As a gold trading system AI, generate a professional weekly performance summary in BENGALI (বাংলা ভাষায়):

Performance Data:
- Total Signals: {len(signals_data)}
- Win Rate: {win_rate:.1f}%
- Signals data: {signals_data[:10]}

Create a concise weekly summary in BENGALI covering:
১. পুরো সপ্তাহের পারফরম্যান্স মূল্যায়ন
২. এই সপ্তাহে গোল্ড মার্কেট কোন কোন ফ্যাক্টরে (যুদ্ধ, ডলার, ফেড) চালিত হয়েছে
৩. আগামী সপ্তাহের গোল্ডের সম্ভাবনাময় গতিপথ ও গুরুত্বপূর্ণ লেভেল

Keep it professional, encouraging, and under 250 words in natural Bengali with appropriate emojis.
"""
            ai_text = self._generate(prompt)
            return ai_text if ai_text else "সাপ্তাহিক রিপোর্ট তৈরি করা সম্ভব হয়নি।"
        except Exception as e:
            logger.error(f"Weekly summary error: {e}")
            return "সাপ্তাহিক রিপোর্ট তৈরি করা সম্ভব হয়নি।"
