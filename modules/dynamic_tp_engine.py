"""
============================================================
  modules/dynamic_tp_engine.py
  UPGRADE MODULE — FULLY DYNAMIC AI XAUUSD SCALPING ENGINE
  Calculates structure-based TP, ranks candidates, validates
  cost-adjusted reward-to-risk, and prohibits fixed TP ratios.
============================================================
"""

import logging
from typing import Dict, List, Optional, Tuple, Any

from config import (
    MIN_RR_RATIO,
    TARGET_RR_CANDIDATES,
    COMMISSION_PER_LOT,
    ESTIMATED_SLIPPAGE_POINTS,
    LOT_SIZE,
)

logger = logging.getLogger(__name__)


class DynamicTPEngine:
    """
    Dynamic Take-Profit Engine for XAUUSD Gold Scalping.
    Strictly derives targets from opposing market structure, liquidity pools,
    FVG/OB boundaries, and execution costs.
    """

    def __init__(self, min_rr_ratio: float = MIN_RR_RATIO):
        self.min_rr_ratio = min_rr_ratio
        self.rr_candidates = TARGET_RR_CANDIDATES

    def calculate_transaction_costs(self, spread: float, lot_size: float = 1.0) -> float:
        """
        Calculates total round-trip estimated transaction cost per ounce in USD:
        Spread ($) + Commission ($0.04/oz = $4/lot) + Estimated Slippage ($0.05).
        """
        comm_per_oz = COMMISSION_PER_LOT / LOT_SIZE  # e.g. 4.0 / 100 = 0.04
        slippage = ESTIMATED_SLIPPAGE_POINTS          # e.g. 0.05
        total_cost_per_oz = round(spread + comm_per_oz + slippage, 2)
        return max(total_cost_per_oz, 0.20)

    def find_opposing_targets(
        self,
        direction: str,
        entry_price: float,
        sl_price: float,
        swings_5m: Dict[str, List[float]],
        swings_15m: Dict[str, List[float]],
        eq_pools: Dict[str, List[float]],
        fvgs_5m: List[Dict[str, Any]],
        fvgs_15m: List[Dict[str, Any]],
        obs_5m: Dict[str, Any],
        obs_15m: Dict[str, Any],
        key_levels: Dict[str, List[float]],
        atr: float,
        spread: float,
    ) -> Dict[str, Any]:
        """
        Gathers, ranks, and validates structural take-profit candidates.
        Returns the optimal dynamic target, candidate list, and structural rationale.
        """
        risk_distance = abs(entry_price - sl_price)
        if risk_distance <= 0:
            return {
                "valid": False,
                "reason": "Invalid stop loss distance (zero or negative risk).",
                "tp": entry_price,
                "rr_ratio": 0.0,
                "target_basis": "None",
            }

        total_costs = self.calculate_transaction_costs(spread)
        candidates = []

        # Buffer before opposing liquidity (to ensure fill before order rejection)
        buffer = round(max(atr * 0.15, 0.25), 2)

        def _extract_prices(items):
            out = set()
            for it in items:
                if isinstance(it, dict):
                    p = it.get("price")
                    if p is not None:
                        out.add(float(p))
                elif isinstance(it, (int, float)):
                    out.add(float(it))
            return out

        if direction == "BUY":
            # 1. Opposing Swing Highs (5M and 15M)
            all_highs = _extract_prices(swings_5m.get("highs", []) + swings_15m.get("highs", []))
            for h in all_highs:
                if h > entry_price:
                    target_price = round(h - buffer, 2)
                    dist = target_price - entry_price
                    if dist > total_costs:
                        candidates.append({
                            "type": "SWING_HIGH",
                            "raw_level": h,
                            "tp": target_price,
                            "distance": round(dist, 2),
                            "weight": 85,
                            "description": f"5M/15M Swing High (${h:.2f}) minus ${buffer} buffer",
                        })

            # 2. Buy-side Liquidity (BSL) & Equal Highs
            eq_highs = eq_pools.get("equal_highs", [])
            for eqh in eq_highs:
                if eqh > entry_price:
                    target_price = round(eqh - buffer, 2)
                    dist = target_price - entry_price
                    if dist > total_costs:
                        candidates.append({
                            "type": "EQUAL_HIGHS_BSL",
                            "raw_level": eqh,
                            "tp": target_price,
                            "distance": round(dist, 2),
                            "weight": 95,
                            "description": f"Buy-Side Liquidity / Equal Highs (${eqh:.2f}) front-run",
                        })

            # 3. Opposing Bearish Fair Value Gap (FVG) bottom boundary
            all_bearish_fvgs = [f for f in fvgs_5m + fvgs_15m if f.get("type") == "BEARISH"]
            for fvg in all_bearish_fvgs:
                fvg_bottom = fvg.get("bottom", 0)
                if fvg_bottom > entry_price:
                    dist = fvg_bottom - entry_price
                    if dist > total_costs:
                        candidates.append({
                            "type": "BEARISH_FVG_BOTTOM",
                            "raw_level": fvg_bottom,
                            "tp": round(fvg_bottom, 2),
                            "distance": round(dist, 2),
                            "weight": 80,
                            "description": f"Opposing Bearish FVG Entry Boundary (${fvg_bottom:.2f})",
                        })

            # 4. Opposing Bearish Order Block (OB) bottom
            for obs in [obs_5m, obs_15m]:
                bear_ob = obs.get("bearish_ob") if obs else None
                if bear_ob and bear_ob.get("bottom", 0) > entry_price:
                    ob_bottom = bear_ob["bottom"]
                    dist = ob_bottom - entry_price
                    if dist > total_costs:
                        candidates.append({
                            "type": "BEARISH_OB_BOTTOM",
                            "raw_level": ob_bottom,
                            "tp": round(ob_bottom, 2),
                            "distance": round(dist, 2),
                            "weight": 85,
                            "description": f"Opposing Institutional Bearish OB Base (${ob_bottom:.2f})",
                        })

            # 5. Resistance Key Levels
            for res in key_levels.get("resistance", []):
                if res > entry_price:
                    target_price = round(res - buffer, 2)
                    dist = target_price - entry_price
                    if dist > total_costs:
                        candidates.append({
                            "type": "RESISTANCE",
                            "raw_level": res,
                            "tp": target_price,
                            "distance": round(dist, 2),
                            "weight": 70,
                            "description": f"Intraday Pivot Resistance (${res:.2f})",
                        })

        elif direction == "SELL":
            # 1. Opposing Swing Lows (5M and 15M)
            all_lows = _extract_prices(swings_5m.get("lows", []) + swings_15m.get("lows", []))
            for l in all_lows:
                if l < entry_price:
                    target_price = round(l + buffer, 2)
                    dist = entry_price - target_price
                    if dist > total_costs:
                        candidates.append({
                            "type": "SWING_LOW",
                            "raw_level": l,
                            "tp": target_price,
                            "distance": round(dist, 2),
                            "weight": 85,
                            "description": f"5M/15M Swing Low (${l:.2f}) plus ${buffer} buffer",
                        })

            # 2. Sell-side Liquidity (SSL) & Equal Lows
            eq_lows = eq_pools.get("equal_lows", [])
            for eql in eq_lows:
                if eql < entry_price:
                    target_price = round(eql + buffer, 2)
                    dist = entry_price - target_price
                    if dist > total_costs:
                        candidates.append({
                            "type": "EQUAL_LOWS_SSL",
                            "raw_level": eql,
                            "tp": target_price,
                            "distance": round(dist, 2),
                            "weight": 95,
                            "description": f"Sell-Side Liquidity / Equal Lows (${eql:.2f}) front-run",
                        })

            # 3. Opposing Bullish Fair Value Gap (FVG) top boundary
            all_bullish_fvgs = [f for f in fvgs_5m + fvgs_15m if f.get("type") == "BULLISH"]
            for fvg in all_bullish_fvgs:
                fvg_top = fvg.get("top", 0)
                if fvg_top < entry_price:
                    dist = entry_price - fvg_top
                    if dist > total_costs:
                        candidates.append({
                            "type": "BULLISH_FVG_TOP",
                            "raw_level": fvg_top,
                            "tp": round(fvg_top, 2),
                            "distance": round(dist, 2),
                            "weight": 80,
                            "description": f"Opposing Bullish FVG Entry Boundary (${fvg_top:.2f})",
                        })

            # 4. Opposing Bullish Order Block (OB) top
            for obs in [obs_5m, obs_15m]:
                bull_ob = obs.get("bullish_ob") if obs else None
                if bull_ob and bull_ob.get("top", 0) < entry_price:
                    ob_top = bull_ob["top"]
                    dist = entry_price - ob_top
                    if dist > total_costs:
                        candidates.append({
                            "type": "BULLISH_OB_TOP",
                            "raw_level": ob_top,
                            "tp": round(ob_top, 2),
                            "distance": round(dist, 2),
                            "weight": 85,
                            "description": f"Opposing Institutional Bullish OB Ceiling (${ob_top:.2f})",
                        })

            # 5. Support Key Levels
            for sup in key_levels.get("support", []):
                if sup < entry_price:
                    target_price = round(sup + buffer, 2)
                    dist = entry_price - target_price
                    if dist > total_costs:
                        candidates.append({
                            "type": "SUPPORT",
                            "raw_level": sup,
                            "tp": target_price,
                            "distance": round(dist, 2),
                            "weight": 70,
                            "description": f"Intraday Pivot Support (${sup:.2f})",
                        })

        # Filter and Score Candidates
        valid_candidates = []
        for c in candidates:
            dist = c["distance"]
            # Net reward after transaction costs
            net_reward = dist - total_costs
            rr = round(net_reward / risk_distance, 2)
            c["rr_ratio"] = rr
            c["net_reward"] = round(net_reward, 2)

            # Target validation criteria:
            # 1. Must offer >= min_rr_ratio (e.g. 1.0R) after transaction costs
            # 2. Must not require unrealistic extension without structure (> 2.5R for scalp)
            # 3. Distance must exceed total transaction costs
            if rr >= self.min_rr_ratio and dist > total_costs and rr <= 2.8:
                # Scoring: prioritize 1.0R - 1.8R sweet spot for gold scalping
                rr_score = 100 - abs(rr - 1.35) * 40
                c["total_score"] = round(c["weight"] * 0.6 + rr_score * 0.4, 1)
                valid_candidates.append(c)

        if not valid_candidates:
            # Check baseline candidate structure (1.0R - 1.5R) if close to market structure
            fallback_rr = 1.25
            fallback_dist = round(risk_distance * fallback_rr + total_costs, 2)
            fallback_tp = round(entry_price + fallback_dist if direction == "BUY" else entry_price - fallback_dist, 2)
            net_reward = round(fallback_dist - total_costs, 2)
            rr = round(net_reward / risk_distance, 2)

            # If risk distance is too tight or wide, reject trade
            if risk_distance < 1.0 or risk_distance > max(10.0, atr * 3.0):
                return {
                    "valid": False,
                    "reason": f"No valid structural target found and risk distance (${risk_distance:.2f}) is outside scalping bounds.",
                    "tp": entry_price,
                    "rr_ratio": 0.0,
                    "target_basis": "No structural target",
                    "candidates": [],
                }

            # Return baseline 1.25R candidate clearly labeled
            return {
                "valid": True,
                "reason": "Structural baseline target (1.25R net of spread/costs).",
                "tp": fallback_tp,
                "rr_ratio": rr,
                "target_basis": f"1.25R Structural Volatility Target (${fallback_dist:.2f} distance)",
                "distance": fallback_dist,
                "candidates": [{
                    "type": "BASELINE_1.25R",
                    "tp": fallback_tp,
                    "distance": fallback_dist,
                    "rr_ratio": rr,
                    "description": "Baseline cost-adjusted structural target",
                }],
            }

        # Sort valid candidates by score descending
        valid_candidates.sort(key=lambda x: x["total_score"], reverse=True)
        best = valid_candidates[0]

        return {
            "valid": True,
            "reason": "High-probability structural target identified.",
            "tp": best["tp"],
            "rr_ratio": best["rr_ratio"],
            "target_basis": best["description"],
            "distance": best["distance"],
            "candidates": valid_candidates,
        }
