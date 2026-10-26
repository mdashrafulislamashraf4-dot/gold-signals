"""
============================================================
  modules/engines/base_engine.py
  Base Abstract Setup Engine for XAUUSD Scalping Strategies
  Strict Completed-Candle Analysis & Technical Calculations
============================================================
"""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd

from config import (
    MIN_RR_RATIO,
    MAX_SPREAD_ALLOWED,
    COMMISSION_PER_LOT,
    ESTIMATED_SLIPPAGE_POINTS,
    LOT_SIZE,
)

logger = logging.getLogger(__name__)


class BaseSetupEngine(ABC):
    """Abstract Base Class for all independent scalping engines"""

    def __init__(self, name: str, enabled: bool = True):
        self.name = name
        self.enabled = enabled

    @abstractmethod
    def analyze(
        self,
        df_15m: pd.DataFrame,
        df_5m: pd.DataFrame,
        df_1m: Optional[pd.DataFrame],
        current_price: float,
        current_spread: float,
    ) -> Dict[str, Any]:
        """Runs the deterministic strategy and returns validated trade setup or NO_TRADE"""
        pass

    # ─────────────────────────────────────────────────────────
    # Technical Indicators (Completed Bars Only)
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
        """Calculates EMA 20, 50, 200, ATR 14, and RSI 14"""
        if df is None or len(df) < 14:
            return df

        df = df.copy()
        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        # EMAs
        df["EMA_20"] = close.ewm(span=20, adjust=False).mean()
        df["EMA_50"] = close.ewm(span=min(len(df), 50), adjust=False).mean()
        df["EMA_200"] = close.ewm(span=min(len(df), 200), adjust=False).mean()

        # ATR 14
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        df["ATR"] = tr.rolling(14).mean().bfill().fillna(2.50)

        # RSI 14
        delta = close.diff()
        gain = delta.clip(lower=0)
        loss = -delta.clip(upper=0)
        avg_gain = gain.ewm(com=13, adjust=False).mean()
        avg_loss = loss.ewm(com=13, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, 1e-9)
        df["RSI"] = 100 - (100 / (1 + rs))

        return df

    # ─────────────────────────────────────────────────────────
    # Swing & Structure Identification
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def find_swings(df: pd.DataFrame, left: int = 2, right: int = 2) -> Dict[str, List[Dict[str, Any]]]:
        """Identifies fractal swing highs and lows on completed candles"""
        highs = []
        lows = []
        if df is None or len(df) < (left + right + 2):
            return {"highs": highs, "lows": lows}

        high_vals = df["High"].values
        low_vals  = df["Low"].values

        for i in range(left, len(df) - right):
            val_h = high_vals[i]
            if all(val_h >= high_vals[i - l] for l in range(1, left + 1)) and \
               all(val_h >= high_vals[i + r] for r in range(1, right + 1)):
                highs.append({"index": i, "price": round(float(val_h), 2)})

            val_l = low_vals[i]
            if all(val_l <= low_vals[i - l] for l in range(1, left + 1)) and \
               all(val_l <= low_vals[i + r] for r in range(1, right + 1)):
                lows.append({"index": i, "price": round(float(val_l), 2)})

        return {"highs": highs, "lows": lows}

    @staticmethod
    def detect_fair_value_gaps(df: pd.DataFrame, lookback: int = 25) -> List[Dict[str, Any]]:
        """Detects 3-bar Fair Value Gaps (FVG) on completed candles"""
        fvgs = []
        if df is None or len(df) < 5:
            return fvgs

        sub = df.tail(lookback).copy().reset_index(drop=True)
        highs = sub["High"].values
        lows  = sub["Low"].values

        for i in range(1, len(sub) - 2):
            if highs[i - 1] < lows[i + 1]:
                gap = round(float(lows[i + 1] - highs[i - 1]), 2)
                if gap >= 0.40:
                    fvgs.append({
                        "type": "BULLISH",
                        "bottom": round(float(highs[i - 1]), 2),
                        "top": round(float(lows[i + 1]), 2),
                        "size": gap,
                    })
            elif lows[i - 1] > highs[i + 1]:
                gap = round(float(lows[i - 1] - highs[i + 1]), 2)
                if gap >= 0.40:
                    fvgs.append({
                        "type": "BEARISH",
                        "top": round(float(lows[i - 1]), 2),
                        "bottom": round(float(highs[i + 1]), 2),
                        "size": gap,
                    })
        return fvgs

    # ─────────────────────────────────────────────────────────
    # Adaptive Target Calculation
    # ─────────────────────────────────────────────────────────
    @staticmethod
    def calculate_adaptive_targets(
        direction: str,
        entry: float,
        sl: float,
        swings_m5: Dict[str, list],
        swings_m15: Dict[str, list],
        fvgs: list,
        atr: float,
        spread: float,
        min_move: float = 2.00,
        target_multiplier: float = 0.75,
    ) -> Dict[str, Any]:
        """Calculates single high-probability realistic target covering trading costs"""
        risk_dist = abs(entry - sl)
        if risk_dist <= 0.20:
            return {"valid": False, "reason": "SL too tight / invalid"}

        cost_per_oz = spread + (COMMISSION_PER_LOT / LOT_SIZE) + (ESTIMATED_SLIPPAGE_POINTS * 2)

        if direction == "BUY":
            all_highs = [h["price"] for h in swings_m5.get("highs", []) if h["price"] > entry + cost_per_oz]
            all_highs += [h["price"] for h in swings_m15.get("highs", []) if h["price"] > entry + cost_per_oz]
            all_highs = sorted(list(set(all_highs)))

            for f in fvgs:
                if f["type"] == "BEARISH" and f["bottom"] > entry + cost_per_oz:
                    all_highs.append(f["bottom"])

            all_highs = sorted(list(set(all_highs)))

            valid_targets = [h for h in all_highs if (h - entry) >= max(cost_per_oz * 2.5, min_move)]
            if valid_targets:
                tp = valid_targets[0]
                target_basis = f"M5/M15 Structural Resistance at ${tp:.2f}"
            else:
                tp = round(entry + max(min_move, min(risk_dist * 1.1, atr * target_multiplier)), 2)
                target_basis = f"Dynamic High-Probability Scalp Target (${tp - entry:.2f})"

            gross_move = round(tp - entry, 2)
            net_reward = round(gross_move - cost_per_oz, 2)
            rr = round(gross_move / risk_dist, 2)

        else:  # SELL
            all_lows = [l["price"] for l in swings_m5.get("lows", []) if l["price"] < entry - cost_per_oz]
            all_lows += [l["price"] for l in swings_m15.get("lows", []) if l["price"] < entry - cost_per_oz]
            all_lows = sorted(list(set(all_lows)), reverse=True)

            for f in fvgs:
                if f["type"] == "BULLISH" and f["top"] < entry - cost_per_oz:
                    all_lows.append(f["top"])

            all_lows = sorted(list(set(all_lows)), reverse=True)

            valid_targets = [l for l in all_lows if (entry - l) >= max(cost_per_oz * 2.5, min_move)]
            if valid_targets:
                tp = valid_targets[0]
                target_basis = f"M5/M15 Structural Support at ${tp:.2f}"
            else:
                tp = round(entry - max(min_move, min(risk_dist * 1.1, atr * target_multiplier)), 2)
                target_basis = f"Dynamic High-Probability Scalp Target (${entry - tp:.2f})"

            gross_move = round(entry - tp, 2)
            net_reward = round(gross_move - cost_per_oz, 2)
            rr = round(gross_move / risk_dist, 2)

        if net_reward <= 0 or rr < 0.65:
            return {
                "valid": False,
                "reason": f"Target reward (${net_reward:.2f}) or R:R (1:{rr}) insufficient after trading costs (${cost_per_oz:.2f})",
                "tp": tp,
                "tp1": tp,
                "tp2": tp,
                "rr_tp1": rr,
                "rr_tp2": rr,
            }

        return {
            "valid": True,
            "tp": tp,
            "tp1": tp,
            "tp2": tp,
            "gross_move": gross_move,
            "net_reward": net_reward,
            "cost_per_oz": round(cost_per_oz, 2),
            "rr_tp1": rr,
            "rr_tp2": rr,
            "target_basis": target_basis,
        }
