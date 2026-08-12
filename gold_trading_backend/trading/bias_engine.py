from typing import Dict

from ..models.signal import WebhookPayload
from ..core.logger import logger


class BiasEngine:
    """Derive HTF bias and price location from validated upstream context."""

    def detect_bias(self, payload: WebhookPayload) -> Dict:
        logger.info("Detecting HTF context for %s", payload.symbol)

        is_buy = payload.action == "BUY"
        bias = payload.htf_bias
        if bias == "NEUTRAL":
            # Safe deterministic fallback when the upstream signal does not provide HTF bias.
            bias = "BULLISH" if is_buy else "BEARISH"

        htf_alignment = payload.htf_alignment
        if htf_alignment is None:
            htf_alignment = (bias == "BULLISH" and is_buy) or (bias == "BEARISH" and not is_buy)

        zone = payload.price_zone
        if zone == "UNKNOWN":
            zone = "DISCOUNT" if is_buy else "PREMIUM"

        zone_aligned = (is_buy and zone == "DISCOUNT") or (not is_buy and zone == "PREMIUM")

        reasoning = []
        if htf_alignment:
            reasoning.append(f"Aligned with higher-timeframe {bias} bias")
        else:
            reasoning.append(f"Counter to higher-timeframe {bias} bias")

        if zone_aligned:
            reasoning.append(f"Price located in preferred {zone} area")
        else:
            reasoning.append(f"Price location is {zone}, outside the preferred entry area")

        return {
            "bias": bias,
            "price_zone": zone,
            "is_bias_aligned": bool(htf_alignment),
            "is_zone_aligned": zone_aligned,
            "context_reasoning": reasoning,
        }


bias_engine = BiasEngine()
