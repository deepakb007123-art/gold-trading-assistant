from typing import Dict, List

from ..models.signal import WebhookPayload


class LiquidityMap:
    """Build directional liquidity targets from signal/context levels."""

    def detect_liquidity(self, payload: WebhookPayload) -> Dict:
        price = payload.price
        is_buy = payload.action == "BUY"

        extra = payload.extra or {}
        pdh = payload.pdh or extra.get("pdh")
        pdl = payload.pdl or extra.get("pdl")
        eqh = payload.eqh or extra.get("eqh")
        eql = payload.eql or extra.get("eql")
        sweep = payload.sweep_level or extra.get("sweep")

        targets: List[Dict] = []
        reasons: List[str] = []
        confidence = 40

        if is_buy:
            if pdh and pdh > price:
                targets.append({"price": pdh, "type": "PDH", "priority": "HIGH"})
                reasons.append("Previous Day High above price")
            if eqh and eqh > price:
                targets.append({"price": eqh, "type": "EQH", "priority": "HIGH"})
                reasons.append("Equal High liquidity above price")
        else:
            if pdl and pdl < price:
                targets.append({"price": pdl, "type": "PDL", "priority": "HIGH"})
                reasons.append("Previous Day Low below price")
            if eql and eql < price:
                targets.append({"price": eql, "type": "EQL", "priority": "HIGH"})
                reasons.append("Equal Low liquidity below price")

        # A small internal target is used only as a fallback context level.
        internal = price + 3 if is_buy else price - 3
        targets.append({"price": internal, "type": "INTERNAL", "priority": "MEDIUM"})

        if sweep is not None:
            confidence += 20
            reasons.append("Liquidity sweep level supplied")

        if targets:
            confidence += 15

        confidence = min(confidence, 100)
        directional = [t for t in targets if (t["price"] > price if is_buy else t["price"] < price)]
        directional.sort(key=lambda x: abs(x["price"] - price))
        best_target = directional[0] if directional else None

        entry_zone = {
            "low": price - 2 if is_buy else price + 0.5,
            "high": price - 0.5 if is_buy else price + 2,
        }

        return {
            "targets": targets,
            "best_target": best_target,
            "sweep_level": sweep,
            "equal_high": eqh,
            "equal_low": eql,
            "entry_zone": entry_zone,
            "confidence": confidence,
            "liquidity_reasons": reasons,
        }


liquidity_map = LiquidityMap()
