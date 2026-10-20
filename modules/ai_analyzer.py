"""
============================================================
  modules/ai_analyzer.py
  Google Gemini AI দিয়ে গভীর মার্কেট এনালাইসিস
============================================================
"""

import logging
from typing import Optional

try:
    from google import genai
    from google.genai import types as genai_types
    _NEW_SDK = True
except ImportError:
    import google.generativeai as genai  # type: ignore
    _NEW_SDK = False

logger = logging.getLogger(__name__)


class AIAnalyzer:
    """Gemini AI দিয়ে সম্পূর্ণ গোল্ড মার্কেট এনালাইসিস করে"""

    SYSTEM_PROMPT = """You are an elite Institutional XAUUSD (Gold) intraday trader specializing in Smart Money Concepts (SMC), Market Structure (BOS/CHoCH), Liquidity Sweeps (PDH/PDL, Asian Session High/Low, Equal Highs/Lows), Fair Value Gaps (FVG), and Disciplined Risk Management.
Your core philosophy: "No Setup = No Trade". You NEVER force a trade.
You strictly require:
1. Higher timeframe context: 4H Trend and 1H Intraday Bias.
2. Clear Liquidity Sweep of key levels (PDL/PDH, Asian High/Low, Swing High/Low) followed by institutional displacement.
3. FVG or Order Block retest with 5m confirmation.
4. Risk-to-Reward ratio minimum 1:2.
5. Strict caution around high-impact US economic news (CPI, NFP, FOMC).
Always output structured trading signals or explicitly state NO_TRADE / WAIT when conditions are not fully met."""

    # নতুন google.genai SDK-তে সক্রিয় ও আপডেটেড মডেল তালিকা
    MODELS = [
        "gemini-3.5-flash-lite",
        "gemini-3.8-flash",
        "gemini-3.5-flash",
        "gemini-flash-latest",
        "gemini-flash-lite-latest",
    ]

    def __init__(self, api_key: str):
        self._api_key = api_key
        if api_key:
            if _NEW_SDK:
                self._client = genai.Client(api_key=api_key)
            else:
                genai.configure(api_key=api_key)  # type: ignore
                self._client = None
            self.available = True
            logger.info(f"Gemini AI initialized (SDK: {'google.genai (new)' if _NEW_SDK else 'google.generativeai (legacy)'})")
        else:
            self.available = False
            self._client = None
            logger.warning("No Gemini API key — AI analysis disabled")

    def _generate(self, prompt: str, system_prompt: str = None) -> Optional[str]:
        """একাধিক মডেল ট্রাই করে যাতে কোটা শেষ না হয়"""
        if not self.available:
            return None
        sys_inst = system_prompt or self.SYSTEM_PROMPT

        for model_name in self.MODELS:
            try:
                if _NEW_SDK and self._client:
                    # নতুন google.genai SDK
                    response = self._client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=genai_types.GenerateContentConfig(
                            system_instruction=sys_inst,
                            temperature=0.3,
                        ),
                    )
                    if response and response.text:
                        return response.text.strip()
                else:
                    # পুরোনো google.generativeai ফলব্যাক
                    m = genai.GenerativeModel(model_name, system_instruction=sys_inst)  # type: ignore
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
        """AI-এর জন্য বিস্তারিত প্রম্পট তৈরি করে (ইনস্টিটিউশনাল মাস্টার স্ট্র্যাটেজি ও SMC ফোকাস্ড)"""

        # ── 1. MASTER STRATEGY PROMPT ──────────────────────────────
        if "checklist_score" in tech:
            liquidity = tech.get("liquidity", {})
            sweep = tech.get("sweep", {})
            disp = tech.get("displacement", {})
            conf_5m = tech.get("confirmation_5m", {})
            checklist = tech.get("checklist", [])

            checklist_str = "\n".join([
                f"  [{'PASS' if c['passed'] else 'FAIL'}] {c['num']}. {c.get('name', c.get('task', ''))}"
                for c in checklist
            ])

            key_news = "\n  - ".join(news.get("key_events", [])[:4]) or "কোনো বড় ব্রেকিং ইভেন্ট নেই"
            sweep_info = sweep.get("sweep_details") or "কোনো সক্রিয় লিকুইডিটি সুইপ নেই"

            prompt = f"""
You are an expert XAUUSD (Gold) institutional trader executing a strict Multi-Timeframe Intraday Master Strategy.
CORE PHILOSOPHY: "No Setup = No Trade". DO NOT force a trade if conditions are not clean.

## Live Market Context
- Current Spot Price: ${price}
- Current Session: {liquidity.get('current_session', 'N/A')}
- Timeframe Hierarchy: 4H (Direction) -> 1H (Intraday Bias) -> 15m (Setup / SMC) -> 5m (Precision Trigger)

## Multi-Timeframe Structural Analysis
1. 4H Trend: {tech.get('trend_4h', 'RANGE')} (4H EMA 200: ${tech.get('ema200_4h', 'N/A')})
2. 1H Intraday Bias: {tech.get('bias_1h', 'RANGE')} (1H EMA 50: ${tech.get('ema50_1h', 'N/A')})
3. Liquidity Map:
   - Previous Day High (PDH): ${liquidity.get('pdh', 'N/A')} | Low (PDL): ${liquidity.get('pdl', 'N/A')}
   - Asian Session High: ${liquidity.get('asian_high', 'N/A')} | Low: ${liquidity.get('asian_low', 'N/A')}
4. 15m SMC Setup:
   - Liquidity Sweep: {sweep_info}
   - Displacement: Bullish={disp.get('bullish')} / Bearish={disp.get('bearish')} (Body size: ${disp.get('size')} USD)
   - Active FVGs: {len(tech.get('active_fvgs', []))} found
5. 5m Confirmation Trigger: {conf_5m.get('reason', 'N/A')}
6. Volatility (ATR 14): ${tech.get('atr', 15.0)}

## 9-Step Daily Checklist Evaluation (Technical: {tech.get('checklist_score')})
{checklist_str}

## Macro & News Sentiment
- Direction: {news.get('direction', 'NEUTRAL')} | Score: {news.get('score', 50)}/100 | Impact: {news.get('impact', 'LOW')}
- Upcoming Events:
  - {key_news}

## Trading Rules & Logic:
- A valid Long Setup requires: Liquidity Sweep of low (SSL / Asian Low / PDL) -> Bullish Displacement + BOS -> FVG Retest -> 5m Bullish Confirmation.
- A valid Short Setup requires: Liquidity Sweep of high (BSL / Asian High / PDH) -> Bearish Displacement + BOS -> FVG Retest -> 5m Bearish Confirmation.
- If high-impact news is imminent or setup is incomplete, set SIGNAL to NO_TRADE or WAIT.
- Keep R:R minimum 1:2.

Format your response EXACTLY like this:
SIGNAL: [BUY / SELL / NO_TRADE / WAIT]
CONFIDENCE: [number]%
ENTRY: [price]
TP1: [price]
TP2: [price]
TP3: [price]
SL: [price]
R_R: [ratio like 1:2.5]
RISK: [কম / মাঝারি]
VALIDITY: [৪-৬ ঘণ্টা]
REASONING:
- [বাংলায় প্রাতিষ্ঠানিক যুক্তি ১ - যেমন: Asian Low সুইপের পর বুলিশ ডিসপ্লেসমেন্ট এসেছে]
- [বাংলায় প্রাতিষ্ঠানিক যুক্তি ২ - যেমন: 4H ও 1H বুলিশ ট্রেন্ডের সাথে অ্যালাইনমেন্ট আছে]
- [বাংলায় প্রাতিষ্ঠানিক যুক্তি ৩ - যেমন: 5m ক্যান্ডেলে স্পষ্ট রিজেকশন কনফার্মেশন পাওয়া গেছে]
WARNINGS:
- [বাংলায় সতর্কতা ১ - যেমন: আসন্ন মার্কিন ইকোনমিক নিউজের সময় সতর্ক থাকুন]
- [বাংলায় সতর্কতা ২ - যেমন: সর্বোচ্চ ০.৫% রিস্কের বেশি লট নিবেন না]
"""
            return prompt

        # ── 2. STANDARD FALLBACK PROMPT ────────────────────────────
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
- Momentum & Oscillators:
  - RSI(14): {details.get('RSI', 'N/A')}
  - MACD: {details.get('MACD', 'N/A')} (Signal: {details.get('MACD_Signal', 'N/A')})
  - Stochastic K: {details.get('Stochastic_K', 'N/A')} | D: {details.get('Stochastic_D', 'N/A')}
  - ATR (14): ${details.get('ATR', 'N/A')}
- Smart Money & Volume:
  - Institutional VWAP: ${details.get('VWAP', 'N/A')}

## Technical Confluence Summary
- Bullish Indicator Signals ({len(tech.get('buy_signals', []))} count):
  - {buy_sigs}
- Bearish Indicator Signals ({len(tech.get('sell_signals', []))} count):
  - {sell_sigs}
- Overall Technical Score: {tech.get('score', 50)}/100
- Candlestick Patterns: {patterns}

## News Sentiment
- Sentiment Score: {news.get('score', 50)}/100
- Direction: {news.get('direction', 'NEUTRAL')}
- Impact Level: {news.get('impact', 'LOW')}
- Key Events:
  - {key_news}

Format your response EXACTLY like this:
SIGNAL: [BUY/SELL/NEUTRAL/NO_TRADE/WAIT]
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
- [বাংলায় কারণ ১]
- [বাংলায় কারণ ২]
WARNINGS:
- [বাংলায় সতর্কতা ১]
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
        current_section = None  # Bug fix: initialize before loop to prevent NameError

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith("SIGNAL:"):
                val = line.replace("SIGNAL:", "").strip().upper()
                if "BUY" in val:
                    result["direction"] = "BUY"
                elif "SELL" in val:
                    result["direction"] = "SELL"
                elif "WAIT" in val:
                    result["direction"] = "WAIT"
                elif "NO_TRADE" in val or "NO TRADE" in val:
                    result["direction"] = "NO_TRADE"
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

Your task: Determine if this is a GENUINE MARKET-MOVING EVENT or catalyst that will tangibly impact Gold (XAUUSD) prices (either bullish or bearish), such as:
1. Significant geopolitical escalation or military actions (war, strikes, missile attacks, major escalations involving Middle East, Russia/Ukraine, US, China, etc.).
2. Central bank & interest rate decisions/statements (Fed rate cuts/hikes, FOMC decisions, Jerome Powell speeches/statements).
3. Major economic data releases & macro indicators (US CPI/inflation, NFP jobs report, GDP, unemployment rate, PCE).
4. Major currency, tariff, trade war, banking or debt events (sharp US dollar movements, banking crisis, debt default, emergency sanctions).

STRICT EXCLUSIONS - MUST BE REJECTED (RESPOND SKIP):
- Routine daily market recaps or price tick updates ("Gold rises as dollar softens", "Gold holds steady", "Gold drops 0.2%")
- Routine analyst forecasts, predictions, technical chart analyses ("Gold Price Forecast: ...", "Gold looks to plunge/surge towards...")
- Routine opinion pieces, newsletters, or daily blogs
- Local city gold rates, bullion dealer promotions, or jewelry store prices

INSTRUCTIONS:
If this news is ROUTINE, MINOR, AN OPINION, LOCAL JEWELRY, OR A GENERIC FORECAST:
Respond strictly with single word:
SKIP

If this news has a REAL IMPACT on the Gold market (will cause price to rise or fall):
Start with "APPROVED:" and provide a professional, concise assessment strictly in natural BENGALI (বাংলা ভাষায়):
• 📌 <b>সংক্ষিপ্ত খবর:</b> [বাংলায় ১ লাইনে কি ঘটেছে]
• 📈 <b>মার্কেট অভিমুখ:</b> [বুলিশ (দাম বাড়ার সম্ভাবনা 🟢) / বেয়ারিশ (দাম কমার সম্ভাবনা 🔴) / তীব্র ওঠানামা ⚠️]
• 🔍 <b>কেন দাম কমতে বা বাড়তে পারে:</b> [১-২ লাইনে সুস্পষ্ট কারণ — যেমন নিরাপদ আশ্রয়ের চাহিদা বৃদ্ধি, ডলার দুর্বল হওয়া, বা ফেডের সুদের হারের প্রভাব ইত্যাদির কারণে গোল্ডের দাম কেন বাড়ছে বা কমছে তা স্পষ্ট করে বলুন]
• 📊 <b>প্রত্যাশিত মুভমেন্ট:</b> [আনুমানিক কত ডলার বা পিপস ওঠানামা হতে পারে, যেমন $১০-$২৫+]
• 💡 <b>ট্রেডারদের করণীয়:</b> [১ লাইনে তাৎক্ষণিক ট্রেডিং পরামর্শ ও সতর্কতা]
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
