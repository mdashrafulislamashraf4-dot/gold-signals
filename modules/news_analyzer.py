"""
============================================================
  modules/news_analyzer.py
  গোল্ড-সংক্রান্ত নিউজ ফেচ ও সেন্টিমেন্ট এনালাইসিস
  Sources: NewsAPI (free), Google News RSS, Economic Calendar
============================================================
"""

import logging
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import Optional
import re

import feedparser
import pytz
import requests

from config import DB_PATH, TIMEZONE

logger = logging.getLogger(__name__)


class NewsAnalyzer:
    """গোল্ড মার্কেট-সংক্রান্ত নিউজ এনালাইসিস করে"""

    EXCLUDE_KEYWORDS = [
        "forecast", "prediction", "technical analysis", "outlook", "weekly forecast",
        "price analysis", "price target", "chart analysis", "live blog", "today's price",
        "gold rate today", "opinion", "commentary", "daily chart", "price steady",
        "edges higher", "edges lower", "slips", "inches up", "holds firm", "trades flat",
        "market wrap", "morning brief", "where is gold heading", "recommendation",
        "bullion rate", "jewelry", "jewellery", "gold rate in", "why gold",
        "what's next for gold", "chart setup", "setups",
    ]

    BREAKING_SHOCK_KEYWORDS = [
        "breaking", "declares war", "air strike", "airstrike", "missile attack", "missile strike",
        "ballistic missile", "drone attack", "nuclear threat", "emergency meeting",
        "invasion begins", "state of emergency", "military retaliation", "assassination",
        "fed cuts rate", "fed raises rate", "interest rate decision", "fomc decision",
        "emergency rate", "powell speech", "bank failure", "bank collapse",
        "debt default", "emergency sanctions", "ceasefire broken", "escalation",
        "cpi rises", "cpi falls", "inflation surges", "inflation cools",
        "nfp surges", "nfp falls", "jobs surge", "unemployment rises", "unemployment falls",
        "tariff announced", "trade war escalation", "dollar surge", "dollar plunge",
    ]

    HIGH_IMPACT_KEYWORDS = [
        "war", "attack", "military", "nuclear", "missile", "bomb", "strike",
        "sanctions", "invasion", "conflict", "crisis", "explosion", "ceasefire",
        "Middle East", "Israel", "Iran", "Gaza", "Lebanon", "Russia", "Ukraine",
        "Taiwan", "China", "US China", "trade war", "tariff",
        "Federal Reserve", "Fed rate", "rate hike", "rate cut", "FOMC", "Powell",
        "CPI", "inflation", "NFP", "non-farm", "GDP", "recession",
        "dollar collapse", "debt ceiling", "default", "Treasury yield",
        "China gold", "central bank gold", "gold reserves", "safe haven",
    ]

    def __init__(self):
        self._evaluated_cache = {}
        self._cached_articles = []
        self._last_fetch_time = 0
        self._init_evaluated_db()

    def _init_evaluated_db(self):
        """মূল্যায়িত সংবাদের ডাটাবেস টেবিল ইনিশিয়ালাইজ করে"""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS evaluated_news (
                        id        INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        title     TEXT UNIQUE,
                        status    TEXT
                    )
                """)
                conn.commit()
        except Exception as e:
            logger.error(f"Init evaluated_news DB error: {e}")

    def is_news_already_evaluated(self, title: str) -> bool:
        """যাচাই করে এই নিউজটি ইতিমধ্যে যাচাই বা ফিল্টার করা হয়েছে কি না"""
        if not title:
            return True
        short_title = title[:60].strip().lower()
        if short_title in self._evaluated_cache:
            return True
        try:
            with sqlite3.connect(DB_PATH) as conn:
                row = conn.execute(
                    "SELECT id FROM evaluated_news WHERE title LIKE ? LIMIT 1",
                    (f"%{short_title[:45]}%",)
                ).fetchone()
                if row:
                    self._evaluated_cache[short_title] = "EXISTING"
                    return True
                row2 = conn.execute(
                    "SELECT id FROM news_alerts WHERE title LIKE ? LIMIT 1",
                    (f"%{short_title[:45]}%",)
                ).fetchone()
                if row2:
                    self._evaluated_cache[short_title] = "SENT"
                    return True
        except Exception as e:
            logger.error(f"DB check news evaluated error: {e}")
        return False

    def record_evaluated_news(self, title: str, status: str = "SKIPPED"):
        """যাচাইকৃত নিউজ রেকর্ড করে যাতে পরবর্তী রাউন্ডে বারবার এআই কল না হয়"""
        if not title:
            return
        short_title = title[:60].strip().lower()
        self._evaluated_cache[short_title] = status
        try:
            with sqlite3.connect(DB_PATH) as conn:
                tz = pytz.timezone(TIMEZONE)
                now = datetime.now(tz).isoformat()
                conn.execute(
                    "INSERT OR IGNORE INTO evaluated_news (timestamp, title, status) VALUES (?, ?, ?)",
                    (now, short_title, status)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"DB record evaluated news error: {e}")

    def is_candidate_breaking_news(self, article: dict) -> bool:
        """
        যাচাই করে কোনো নিউজ কি বড় মার্কেট মুভার হওয়ার মতো সম্ভাব্য ব্রেকিং নিউজ কি না।
        রুটিন পূর্বাভাস, মতামত, চার্ট এনালাইসিস সরাসরি বাদ দেয়।
        """
        title = article.get("title", "").lower()
        summary = article.get("summary", "").lower()
        full_text = f"{title} {summary}"

        # 1. Blacklist check - Exclude routine commentary, forecast, opinion
        for kw in self.EXCLUDE_KEYWORDS:
            if kw.lower() in title:
                return False

        # 2. Whitelist check - Must match a major shock keyword
        for kw in self.BREAKING_SHOCK_KEYWORDS:
            if kw.lower() in full_text:
                return True

        # 3. Check combinations of high-impact geopolitics + attack/strike/war
        geo_keywords = ["middle east", "iran", "israel", "gaza", "lebanon", "russia", "ukraine", "taiwan", "china", "red sea", "houthis"]
        action_keywords = ["strike", "attack", "bomb", "missile", "war", "invade", "military", "nuclear", "retaliation", "sanction", "ceasefire"]
        has_geo = any(g in full_text for g in geo_keywords)
        has_action = any(a in full_text for a in action_keywords)
        if has_geo and has_action:
            return True

        # 4. Check combinations of central bank / Fed + rate decisions
        fed_keywords = ["federal reserve", "fed", "fomc", "powell", "central bank"]
        fed_action = ["rate", "interest", "cut", "hike", "decision", "policy", "surprise", "shock", "emergency", "urgent", "speech"]
        has_fed = any(f in full_text for f in fed_keywords)
        has_fed_action = any(fa in full_text for fa in fed_action)
        if has_fed and has_fed_action:
            return True

        # 5. Major economic releases: CPI, Inflation, NFP, Jobs report, Unemployment
        econ_keywords = ["cpi", "inflation", "nfp", "non-farm payroll", "payrolls", "unemployment rate", "jobs report", "pce"]
        if any(ek in full_text for ek in econ_keywords):
            return True

        # 6. Tariffs, Trade War & Banking Crisis
        trade_keywords = ["tariff", "tariffs", "trade war", "bank collapse", "bank failure", "debt default"]
        if any(tk in full_text for tk in trade_keywords):
            return True

        return False

    def is_news_already_sent(self, title: str) -> bool:
        """যাচাই করে এই নিউজটি ইতিমধ্যে টেলিগ্রামে পাঠানো হয়েছে কি না"""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                short_title = title[:45].strip()
                row = conn.execute(
                    "SELECT id FROM news_alerts WHERE title LIKE ? LIMIT 1",
                    (f"%{short_title}%",)
                ).fetchone()
                return row is not None
        except Exception as e:
            logger.error(f"DB check news sent error: {e}")
            return False

    def record_sent_news(self, title: str, source: str = "", impact: str = "HIGH"):
        """পাঠানো নিউজটি ডেটাবেসে রেকর্ড করে যাতে পুনরাবৃত্তি না হয়"""
        try:
            with sqlite3.connect(DB_PATH) as conn:
                tz = pytz.timezone(TIMEZONE)
                now = datetime.now(tz).isoformat()
                conn.execute(
                    "INSERT INTO news_alerts (timestamp, title, source, impact, sent) VALUES (?, ?, ?, ?, 1)",
                    (now, title, source, impact)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"DB record sent news error: {e}")

    BULLISH_KEYWORDS = [
        "gold rises", "gold surges", "gold rally", "gold up",
        "dollar falls", "dollar weakens", "DXY down",
        "inflation high", "recession fears", "safe haven demand",
        "war escalation", "conflict worsens", "geopolitical tension",
        "rate cut", "dovish", "Fed pauses",
        "gold demand", "central bank buying",
    ]

    BEARISH_KEYWORDS = [
        "gold falls", "gold drops", "gold declines", "gold down",
        "dollar strengthens", "dollar rises", "DXY up",
        "rate hike", "hawkish", "inflation cools",
        "risk on", "stocks rally", "peace deal",
        "gold sell-off", "gold pressure",
    ]

    # ─────────────────────────────────────────────────────────
    # Google News RSS Feed
    # ─────────────────────────────────────────────────────────
    def fetch_google_news(self, query: str = "gold price XAUUSD") -> list:
        """Google News RSS থেকে নিউজ ফেচ করে (সম্পূর্ণ ফ্রি)"""
        try:
            encoded  = requests.utils.quote(query)
            url      = f"https://news.google.com/rss/search?q={encoded}&hl=en-US&gl=US&ceid=US:en"
            headers  = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            }
            resp     = requests.get(url, headers=headers, timeout=10)
            if not resp.ok:
                logger.warning(f"Google News RSS returned status {resp.status_code}")
                return []
            feed     = feedparser.parse(resp.content)
            articles = []
            for entry in feed.entries[:20]:
                articles.append({
                    "title":     entry.get("title", ""),
                    "summary":   entry.get("summary", ""),
                    "link":      entry.get("link", ""),
                    "published": entry.get("published", ""),
                    "source":    entry.get("source", {}).get("title", "Google News"),
                })
            return articles
        except Exception as e:
            logger.error(f"Google News RSS error for '{query}': {e}")
            return []

    # ─────────────────────────────────────────────────────────
    # NewsAPI.org
    # ─────────────────────────────────────────────────────────
    def fetch_newsapi(self, api_key: str, query: str = "gold price") -> list:
        """NewsAPI.org থেকে নিউজ ফেচ করে"""
        if not api_key:
            return []
        try:
            from_date = (datetime.now(timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%S")
            url = "https://newsapi.org/v2/everything"
            params = {
                "q":          query,
                "from":       from_date,
                "sortBy":     "publishedAt",
                "language":   "en",
                "pageSize":   20,
                "apiKey":     api_key,
            }
            resp = requests.get(url, params=params, timeout=15)
            if resp.ok:
                data = resp.json()
                articles = []
                for a in data.get("articles", []):
                    articles.append({
                        "title":     a.get("title", ""),
                        "summary":   a.get("description", ""),
                        "link":      a.get("url", ""),
                        "published": a.get("publishedAt", ""),
                        "source":    a.get("source", {}).get("name", "NewsAPI"),
                    })
                logger.info(f"NewsAPI: {len(articles)} articles")
                return articles
        except Exception as e:
            logger.error(f"NewsAPI error: {e}")
        return []

    # ─────────────────────────────────────────────────────────
    # Combine all sources
    # ─────────────────────────────────────────────────────────
    def fetch_all_news(self, api_key: str = "") -> list:
        """সব সোর্স থেকে নিউজ কম্বাইন করে (১৫ সেকেন্ড ক্যাশিং সহ)"""
        now = time.time()
        if self._cached_articles and (now - self._last_fetch_time) < 15:
            return self._cached_articles

        all_news = []

        # Gold & Macro Market News
        all_news += self.fetch_google_news("gold price breaking news OR XAUUSD")
        time.sleep(0.2)
        all_news += self.fetch_google_news("gold market war geopolitical conflict Middle East")
        time.sleep(0.2)
        all_news += self.fetch_google_news("Federal Reserve interest rate FOMC Powell")
        time.sleep(0.2)
        all_news += self.fetch_google_news("US inflation CPI NFP payrolls US dollar")

        if api_key:
            all_news += self.fetch_newsapi(api_key, "gold XAU price")

        # Deduplicate by title
        seen   = set()
        unique = []
        for n in all_news:
            title = n.get("title", "")
            if title and title not in seen:
                seen.add(title)
                unique.append(n)

        self._cached_articles = unique
        self._last_fetch_time = now
        logger.info(f"Total unique news: {len(unique)}")
        return unique

    # ─────────────────────────────────────────────────────────
    # Sentiment Analysis (keyword-based, no API needed)
    # ─────────────────────────────────────────────────────────
    def analyze_sentiment(self, articles: list) -> dict:
        """
        নিউজ সেন্টিমেন্ট এনালাইসিস করে
        Returns: {score, direction, impact, key_events, high_impact_news}
        """
        if not articles:
            return {
                "score":           50,
                "direction":       "NEUTRAL",
                "impact":          "LOW",
                "key_events":      [],
                "high_impact_news": [],
                "summary":         "No news available",
            }

        bullish_count  = 0
        bearish_count  = 0
        neutral_count  = 0
        key_events     = []
        high_impact    = []

        for article in articles:
            text  = (article.get("title", "") + " " + article.get("summary", "")).lower()
            score = 0

            for kw in self.BULLISH_KEYWORDS:
                if kw.lower() in text:
                    score += 1

            for kw in self.BEARISH_KEYWORDS:
                if kw.lower() in text:
                    score -= 1

            if score > 0:
                bullish_count += 1
            elif score < 0:
                bearish_count += 1
            else:
                neutral_count += 1

            # Check high impact
            is_high_impact = False
            for kw in self.HIGH_IMPACT_KEYWORDS:
                if kw.lower() in text:
                    is_high_impact = True
                    break

            if is_high_impact:
                high_impact.append({
                    "title":  article.get("title", ""),
                    "source": article.get("source", ""),
                    "link":   article.get("link", ""),
                })
                key_events.append(article.get("title", "")[:100])

        total = bullish_count + bearish_count + neutral_count
        directional_count = bullish_count + bearish_count

        if directional_count == 0:
            sentiment_score = 50
            direction = "NEUTRAL"
        else:
            # Scale sentiment score from 15 to 85 centered at 50
            diff = bullish_count - bearish_count
            sentiment_score = int(50 + (diff / directional_count) * 35)
            sentiment_score = max(5, min(95, sentiment_score))

            if sentiment_score >= 58:
                direction = "BULLISH"
            elif sentiment_score <= 42:
                direction = "BEARISH"
            else:
                direction = "NEUTRAL"

        impact = "HIGH" if len(high_impact) >= 3 else ("MEDIUM" if len(high_impact) >= 1 else "LOW")

        return {
            "score":            sentiment_score,
            "direction":        direction,
            "impact":           impact,
            "bullish_count":    bullish_count,
            "bearish_count":    bearish_count,
            "key_events":       key_events[:5],
            "high_impact_news": high_impact[:5],
            "total_analyzed":   total,
        }

    # ─────────────────────────────────────────────────────────
    # Economic Calendar (Investing.com public RSS)
    # ─────────────────────────────────────────────────────────
    def get_economic_calendar(self) -> list:
        """আজকের ইকোনমিক ইভেন্ট ফেচ করে"""
        events = []

        # Key economic events that affect gold
        high_impact_events = [
            "Non-Farm Payrolls", "NFP", "CPI", "Consumer Price Index",
            "FOMC", "Federal Reserve", "GDP", "Interest Rate",
            "Unemployment", "PPI", "PCE", "Retail Sales",
        ]

        try:
            # Use forexfactory RSS (free)
            url  = "https://nfs.faireconomy.media/ff_calendar_thisweek.xml"
            resp = requests.get(url, timeout=15)
            if resp.ok:
                feed = feedparser.parse(resp.content)
                for entry in feed.entries:
                    title   = entry.get("title", "")
                    is_high = any(kw.lower() in title.lower() for kw in high_impact_events)
                    events.append({
                        "event":   title,
                        "time":    entry.get("published", ""),
                        "impact":  "HIGH" if is_high else "MEDIUM",
                        "summary": entry.get("summary", ""),
                    })
            logger.info(f"Economic calendar: {len(events)} events")
        except Exception as e:
            logger.warning(f"Economic calendar error: {e}")

        # Add known upcoming high-impact events from Google News
        try:
            news = self.fetch_google_news("economic calendar today FOMC CPI NFP")
            for n in news[:5]:
                events.append({
                    "event":   n.get("title", ""),
                    "time":    n.get("published", ""),
                    "impact":  "HIGH",
                    "source":  n.get("source", ""),
                })
        except Exception:
            pass

        return events[:20]

    # ─────────────────────────────────────────────────────────
    # Format news for Telegram
    # ─────────────────────────────────────────────────────────
    def format_news_alert(self, article: dict, impact: str = "HIGH") -> str:
        """টেলিগ্রামে পাঠানোর জন্য নিউজ ফরম্যাট করে"""
        emoji = "🚨" if impact == "HIGH" else "📰"
        title  = article.get("title", "")[:150]
        source = article.get("source", "")
        link   = article.get("link", "")

        msg = (
            f"{emoji} <b>GOLD NEWS ALERT</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📌 {title}\n"
            f"📎 Source: {source}\n"
            f"⚠️ Impact: {impact}\n"
        )
        if link:
            msg += f"🔗 <a href='{link}'>Read More</a>\n"
        return msg
