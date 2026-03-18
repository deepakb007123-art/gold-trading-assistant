from typing import Dict, List, Tuple
from models.signal import WebhookPayload
from core.logger import logger
import random

class LiquidityMapEngine:
    """
    Detects target liquidity zones (Stop clusters, Equal Highs/Lows, 
    Previous Day High/Low, Session Highs/Lows). 
    Used for TP targeting and trap identification.
    """

    def detect_liquidity(self, payload: WebhookPayload) -> Dict:
        """
        Maps liquidity targets relative to the current price.
        """
        logger.info(f"Mapping Liquidity Zones for {payload.symbol} near {payload.price}")
        
        price = payload.price
        is_buy = payload.action == "BUY"
        
        # Simulate local liquidity nodes (in production, populated via price feed/DB)
        # Gold average ATR is ~20-30 pips standard, so points are spread by a few dollars
        
        spread = random.uniform(2.0, 5.0)
        
        # If BUY, targets are above (EQH, PDH)
        # If SELL, targets are below (EQL, PDL)
        
        targets = []
        confidence = 0
        liquidity_reasons = []
        
        has_eqh_eql = random.choice([True, False])
        has_pdh_pdl = random.choice([True, False])
        
        if is_buy:
            if has_eqh_eql:
                target_price = price + (spread * 2)
                targets.append({"type": "Equal Highs (EQH)", "price": target_price, "weight": 50, "priority": "MEDIUM"})
                liquidity_reasons.append("Targeting Equal Highs (EQH) liquidity resting above")
            if has_pdh_pdl:
                target_price = price + (spread * 3.5)
                targets.append({"type": "Previous Day High (PDH)", "price": target_price, "weight": 80, "priority": "HIGH"})
                liquidity_reasons.append("PDH acts as a major high-priority liquidity draw")
        else: # SELL
            if has_eqh_eql:
                target_price = price - (spread * 2)
                targets.append({"type": "Equal Lows (EQL)", "price": target_price, "weight": 50, "priority": "MEDIUM"})
                liquidity_reasons.append("Targeting Equal Lows (EQL) liquidity resting below")
            if has_pdh_pdl:
                target_price = price - (spread * 3.5)
                targets.append({"type": "Previous Day Low (PDL)", "price": target_price, "weight": 80, "priority": "HIGH"})
                liquidity_reasons.append("PDL acts as a major high-priority liquidity draw")
        
        # General Retail/Session Stop Clusters (always present, lower priority)
        cluster_price = price + spread if is_buy else price - spread
        targets.append({"type": "Session/Retail Stop Cluster", "price": cluster_price, "weight": 30, "priority": "LOW"})
        
        # Calculate target confidence based on highest priority targets available
        confidence = sum(t["weight"] for t in targets) // len(targets)
        
        # Sort targets by probability/weight
        targets.sort(key=lambda x: x["weight"], reverse=True)
        
        best_target = targets[0] if targets else None

        return {
            "targets": targets,
            "best_target": best_target,
            "target_confidence": confidence,
            "liquidity_reasons": liquidity_reasons,
            "has_eqh_eql": has_eqh_eql
        }

liquidity_map = LiquidityMapEngine()
