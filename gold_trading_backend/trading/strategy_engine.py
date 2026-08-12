from typing import Dict

from ..models.signal import WebhookPayload, SMCConditions
from ..core.logger import logger


class StrategyEngine:
    """Evaluate SMC conditions explicitly supplied by the upstream signal."""

    def analyze_smc_conditions(self, payload: WebhookPayload, structure: Dict, liquidity: Dict) -> Dict:
        logger.info("Evaluating SMC conditions for %s", payload.symbol)

        is_buy = payload.action == "BUY"
        conditions = SMCConditions(
            liquidity_sweep=payload.liquidity_sweep,
            order_block=payload.order_block,
            fvg_imbalance=payload.fvg_imbalance,
            bos=structure.get("has_bos", False),
            choch=structure.get("has_choch", False),
            inducements=payload.inducements,
            displacement=payload.displacement,
            sweep_confirmed=payload.sweep_confirmed,
            liquidity_approaching=payload.liquidity_approaching,
        )

        # If an upstream sweep is marked but confirmation was omitted, derive a conservative confirmation
        # from displacement or an order block instead of inventing a random condition.
        if conditions.liquidity_sweep and not conditions.sweep_confirmed:
            conditions.sweep_confirmed = conditions.displacement or conditions.order_block

        best_target = liquidity.get("best_target")
        if best_target and best_target.get("price") is not None:
            distance = abs(payload.price - best_target["price"])
            conditions.liquidity_approaching = conditions.liquidity_approaching or (1.0 < distance < 8.0)

        confidence = 0
        reasoning = []
        strategies_used = []

        if conditions.liquidity_sweep:
            confidence += 25
            reasoning.append(
                "Sell-side liquidity swept prior to entry" if is_buy else "Buy-side liquidity swept prior to entry"
            )
            strategies_used.append("Liquidity Sweep")
            if conditions.sweep_confirmed:
                confidence += 10
                reasoning.append("Sweep confirmed by reaction/displacement")
            else:
                reasoning.append("Sweep not confirmed")

        if conditions.order_block:
            confidence += 20
            reasoning.append(
                "Price mitigating Bullish Order Block" if is_buy else "Price mitigating Bearish Order Block"
            )
            strategies_used.append("Order Block (OB)")

        if conditions.fvg_imbalance:
            confidence += 15
            reasoning.append(
                "Bullish FVG alignment" if is_buy else "Bearish FVG alignment"
            )
            strategies_used.append("Fair Value Gap (FVG)")

        if conditions.displacement:
            confidence += 10
            reasoning.append("Strong displacement/momentum present")

        if conditions.inducements:
            confidence += 15
            reasoning.append("Inducement condition supplied by upstream signal")
            strategies_used.append("Inducement")

        return {
            "smc_conditions": conditions,
            "confidence_contribution": min(confidence, 100),
            "smc_reasoning": reasoning,
            "strategies_used": strategies_used,
        }


strategy_engine = StrategyEngine()
