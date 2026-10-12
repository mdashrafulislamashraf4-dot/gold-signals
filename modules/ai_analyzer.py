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

    def __init__(self, api_key: str):
        if api_key:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(
                "gemini-3.8-flash",
                system_instruction=self.SYSTEM_PROMPT,
            )
            self.available = True
            logger.info("Gemini AI initialized successfully")
        else:
            self.available = False
            logger.warning("No Gemini API key — AI analysis disabled")

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
            response  = self.model.generate_content(prompt)
            ai_text   = response.text
            parsed    = self._parse_ai_response(ai_text, current_price, technical_data)
            logger.info(f"AI Analysis complete: {parsed.get('direction')} | Confidence: {parsed.get('confidence')}%")
            return parsed
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

## Technical Indicators
- RSI(14): {details.get('RSI', 'N/A')}
- MACD: {details.get('MACD', 'N/A')}
- EMA20: {details.get('EMA_20', 'N/A')}
- EMA50: {details.get('EMA_50', 'N/A')}
- EMA200: {details.get('EMA_200', 'N/A')}
- ATR(14): {details.get('ATR', 'N/A')}
- ADX: {details.get('ADX', 'N/A')}
- Stochastic K: {details.get('Stochastic_K', 'N/A')}
- Williams %R: {details.get('Williams_R', 'N/A')}
- BB Upper: {details.get('BB_Upper', 'N/A')}
- BB Lower: {details.get('BB_Lower', 'N/A')}

## Technical Score
- Bullish Signals: {len(tech.get('buy_signals', []))}
  - {buy_sigs}
- Bearish Signals: {len(tech.get('sell_signals', []))}
  - {sell_sigs}
- Overall Technical Score: {tech.get('score', 50)}/100
- Candlestick Patterns: {patterns}

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
            response = self.model.generate_content(prompt)
            return response.text.strip()
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
            response = self.model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            logger.error(f"Weekly summary error: {e}")
            return "সাপ্তাহিক রিপোর্ট তৈরি করা সম্ভব হয়নি।"
