from typing import Dict

from ..models.signal import WebhookPayload
from ..core.logger import logger


class MarketStructureEngine:
    """Read market-structure flags supplied by the upstream signal."""

    def analyze_structure(self, payload: WebhookPayload) -> Dict:
        logger.info("Analyzing market structure for %s at %.2f", payload.symbol, payload.price)

        is_buy = payload.action == "BUY"
        trend = "BULLISH" if is_buy else "BEARISH"
        htf_alignment = payload.htf_alignment
        if htf_alignment is None:
            htf_alignment = payload.htf_bias in ("NEUTRAL", trend)

        has_bos = payload.bos
        has_choch = payload.choch
        is_consolidation = not has_bos and not has_choch

        confidence = 0
        reasoning = []

        if has_choch:
            confidence += 30
            reasoning.append(f"{'Bullish' if is_buy else 'Bearish'} CHoCH detected")
        if has_bos:
            confidence += 20
            reasoning.append("Pro-trend BOS observed")
        if is_consolidation:
            confidence += 10
            reasoning.append("No explicit BOS/CHoCH supplied; consolidation state")

        if htf_alignment:
            confidence += 15
            reasoning.append("HTF/LTF structural alignment confirmed")
        else:
            reasoning.append("HTF/LTF structural disagreement")

        opposite_bos = has_bos and not htf_alignment

        return {
            "trend": trend,
            "htf_alignment": bool(htf_alignment),
            "has_bos": has_bos,
            "has_choch": has_choch,
            "is_consolidation": is_consolidation,
            "opposite_bos": opposite_bos,
            "confidence": confidence,
            "confidence_contribution": confidence,
            "structure_reasoning": reasoning,
        }


market_structure = MarketStructureEngine()
