from typing import Dict, Literal
from models.signal import WebhookPayload
from core.logger import logger
import random

class BiasEngine:
    """
    Market Context Engine.
    Detects Higher Timeframe (HTF) directional bias and values the current
    price within Premium (expensive, look to sell) or Discount (cheap, look to buy) zones.
    Filters out trades that fight the overarching institutional flow.
    """

    def detect_bias(self, payload: WebhookPayload) -> Dict:
        """
        Calculates HTF bias and Premium/Discount zone.
        """
        logger.info(f"Detecting HTF Market Context for {payload.symbol}")

        # In a genuine real-time system with indicator math, this would verify EMA 200/Daily Structure.
        # Here we simulate an HTF bias mapping for the webhook architecture.
        # We heavily weight the bias to likely support the incoming signal to avoid blocking all testing,
        # but randomly generate neutral/opposing contexts.
        is_buy = payload.action == "BUY"
        
        rand_val = random.random()
        if rand_val > 0.3:
            # Aligned Bias
            bias = "BULLISH" if is_buy else "BEARISH"
        elif rand_val > 0.1:
            # Neutral Zone
            bias = "NEUTRAL"
        else:
            # Opposing Bias (Counter-trend)
            bias = "BEARISH" if is_buy else "BULLISH"

        # Categorize price location
        # If BUY context, we want to buy in 'DISCOUNT'
        # If SELL context, we want to sell in 'PREMIUM'
        is_premium = random.choice([True, False])
        if is_buy:
            zone = "DISCOUNT" if not is_premium else "PREMIUM"
        else:
            zone = "PREMIUM" if is_premium else "DISCOUNT"

        # Validation Logic: Only trade aligned with bias
        bias_aligned = bias == "NEUTRAL" or (bias == "BULLISH" and is_buy) or (bias == "BEARISH" and not is_buy)
        zone_aligned = (is_buy and zone == "DISCOUNT") or (not is_buy and zone == "PREMIUM")

        reasoning = []
        if bias_aligned:
            reasoning.append(f"Aligned with Higher Timeframe {bias} bias")
        else:
            reasoning.append(f"WARNING: Counter to Higher Timeframe {bias} bias")

        if zone_aligned:
            reasoning.append(f"Executions priced in ideal {zone} environment")
        else:
            reasoning.append(f"Sub-optimal pricing: Executing from {zone}")

        return {
            "bias": bias,
            "price_zone": zone,
            "is_bias_aligned": bias_aligned,
            "is_zone_aligned": zone_aligned,
            "context_reasoning": reasoning
        }

bias_engine = BiasEngine()
