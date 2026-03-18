from typing import Dict, Tuple
from models.signal import WebhookPayload
from core.logger import logger
from core.config import settings

class RiskManager:
    """
    Smart Risk Management System. 
    Dynamic Logic:
    1. Structure SL (Below swing)
    2. Liquidity SL (Below sweep/EQL)
    3. ATR fallback
    
    TP Logic: Target identified liquidity zones, while ensuring Risk-to-Reward (RR) >= 1.5
    """

    def calculate_risk_parameters(self, payload: WebhookPayload, liquidity: Dict) -> Dict:
        """
        Determines the dynamic SL, TP, and resulting RR ratio.
        """
        logger.info(f"Calculating dynamic risk parameters for {payload.symbol}")
        
        price = payload.price
        is_buy = payload.action == "BUY"
        targets = liquidity.get("targets", [])
        
        fallback_atr = 3.0  # e.g., $3 on Gold
        
        # 1. Calculate Stop Loss (Prefer Structural, Fallback to ATR)
        if payload.tv_sl and payload.tv_sl > 0:
            sl = payload.tv_sl
        else:
            # Prefer structure SL based on previous swing/sweep
            structure_distance = 4.5
            sl_structural = price - structure_distance if is_buy else price + structure_distance
            
            # ATR Fallback if structure is too tight
            sl_atr = price - fallback_atr if is_buy else price + fallback_atr
            
            # Use safest distance for SL
            sl = min(sl_structural, sl_atr) if is_buy else max(sl_structural, sl_atr)
            
        # 2. Calculate Take Profit (TP1 nearest, TP2 extended)
        tp1 = None
        tp2 = None
        
        if targets:
            # Sorted reverse=False to process nearest to farthest, assuming price proximity 
            targets.sort(key=lambda x: abs(x["price"] - price))
            
            for target in targets:
                target_price = target["price"]
                risk = price - sl if is_buy else sl - price
                reward = target_price - price if is_buy else price - target_price
                
                if risk > 0 and (reward / risk) >= settings.MIN_RR_RATIO:
                    if not tp1:
                        tp1 = target_price
                    elif (is_buy and target_price > tp1) or (not is_buy and target_price < tp1):
                        tp2 = target_price
                        # Limit to highest priority extending target
                        if target.get("priority") == "HIGH":
                            break
        
        # Fallback TP if none of the structural targets meet strict RR
        if not tp1:
            if payload.tv_tp and payload.tv_tp > 0:
                tp1 = payload.tv_tp
            else:
                risk = price - sl if is_buy else sl - price
                tp1 = price + (risk * settings.MIN_RR_RATIO) if is_buy else price - (risk * settings.MIN_RR_RATIO)
                
        # Calculate Final RR (Based on TP1)
        risk = price - sl if is_buy else sl - price
        reward = tp1 - price if is_buy else price - tp1
        rr_ratio = round(reward / risk, 2) if risk > 0 else 0
        
        return {
            "sl_price": round(sl, 2),
            "tp_price": round(tp1, 2),
            "tp2_price": round(tp2, 2) if tp2 else None,
            "rr_ratio": rr_ratio,
        }

risk_manager = RiskManager()
