from typing import Dict, List
from models.signal import WebhookPayload
from core.logger import logger


class LiquidityMap:

    def detect_liquidity(self, payload: WebhookPayload) -> Dict:

        price = payload.price
        is_buy = payload.action == "BUY"

        # -------------------------
        # 🔥 MOCK STRUCTURE INPUT (FROM PAYLOAD / EXTRA)
        # -------------------------
        extra = payload.extra or {}

        pdh = extra.get("pdh")      # Previous Day High
        pdl = extra.get("pdl")      # Previous Day Low
        eqh = extra.get("eqh")      # Equal Highs
        eql = extra.get("eql")      # Equal Lows
        sweep = extra.get("sweep")  # Liquidity sweep level

        targets: List[Dict] = []
        confidence = 50
        reasons = []

        # -------------------------
        # 🎯 1. EXTERNAL LIQUIDITY (STRONG TARGETS)
        # -------------------------
        if is_buy:
            if pdh:
                targets.append({"price": pdh, "type": "PDH", "priority": "HIGH"})
                reasons.append("Targeting Previous Day High liquidity")

            if eqh:
                targets.append({"price": eqh, "type": "EQH", "priority": "HIGH"})
                reasons.append("Targeting Equal High liquidity")

        else:
            if pdl:
                targets.append({"price": pdl, "type": "PDL", "priority": "HIGH"})
                reasons.append("Targeting Previous Day Low liquidity")

            if eql:
                targets.append({"price": eql, "type": "EQL", "priority": "HIGH"})
                reasons.append("Targeting Equal Low liquidity")

        # -------------------------
        # ⚡ 2. INTERNAL LIQUIDITY (NEAR TARGETS)
        # -------------------------
        if is_buy:
            internal = price + 3
            targets.append({"price": internal, "type": "INTERNAL", "priority": "MEDIUM"})
        else:
            internal = price - 3
            targets.append({"price": internal, "type": "INTERNAL", "priority": "MEDIUM"})

        # -------------------------
        # 🧨 3. SWEEP DETECTION
        # -------------------------
        if sweep:
            confidence += 20
            reasons.append("Liquidity sweep detected")

        # -------------------------
        # 🎯 4. ENTRY ZONE (SNIPER LOGIC)
        # -------------------------
        entry_zone = None

        if is_buy:
            entry_zone = {
                "low": price - 2,
                "high": price - 0.5
            }
        else:
            entry_zone = {
                "low": price + 0.5,
                "high": price + 2
            }

        # -------------------------
        # 🧠 5. CONFIDENCE BOOST
        # -------------------------
        if targets:
            confidence += 15

        confidence = min(confidence, 100)

        return {
            "targets": targets,
            "sweep_level": sweep,
            "equal_high": eqh,
            "equal_low": eql,
            "entry_zone": entry_zone,
            "confidence": confidence,
            "liquidity_reasons": reasons,
        }


liquidity_map = LiquidityMap()
