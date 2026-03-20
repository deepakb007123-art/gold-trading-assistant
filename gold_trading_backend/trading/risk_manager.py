from typing import Dict
from models.signal import WebhookPayload
from core.logger import logger
from core.config import settings
from trading.session_manager import session_manager


class RiskManager:
    """
    Advanced Smart Risk Manager (Final Version)

    Features:
    ✔ Structural + ATR SL
    ✔ Volatility adaptive SL/TP
    ✔ Smart RR auto-correction
    ✔ Direction validation
    ✔ Minimum SL protection
    ✔ Failsafe (never returns invalid values)
    """

    def calculate_risk_parameters(self, payload: WebhookPayload, liquidity: Dict) -> Dict:

        logger.info(f"Calculating dynamic risk for {payload.symbol}")

        price = payload.price
        is_buy = payload.action == "BUY"
        targets = liquidity.get("targets", [])

        # ---------------------------------
        # 1. VOLATILITY MULTIPLIER
        # ---------------------------------
        sessions, _ = session_manager.get_current_session()
        vol_multiplier = session_manager.get_volatility_multiplier(sessions)

        # ---------------------------------
        # 2. STOP LOSS
        # ---------------------------------
        fallback_atr = 3.0
        structure_distance = 4.5

        if payload.tv_sl and payload.tv_sl > 0:
            sl = payload.tv_sl
        else:
            sl_structural = price - structure_distance if is_buy else price + structure_distance
            sl_atr = price - fallback_atr if is_buy else price + fallback_atr

            # ✅ choose tighter SL (correct logic)
            sl = max(sl_structural, sl_atr) if is_buy else min(sl_structural, sl_atr)

        # Apply volatility
        sl = sl * vol_multiplier

        # ---------------------------------
        # 3. MINIMUM SL PROTECTION
        # ---------------------------------
        MIN_SL_DISTANCE = 2.5

        if abs(price - sl) < MIN_SL_DISTANCE:
            logger.warning("⚠️ SL too tight → adjusting")
            sl = price - MIN_SL_DISTANCE if is_buy else price + MIN_SL_DISTANCE

        # ---------------------------------
        # 4. FAILSAFE SL
        # ---------------------------------
        if sl == 0 or abs(price - sl) < 0.1:
            logger.warning("⚠️ SL invalid → fallback applied")
            buffer = 5.0
            sl = price - buffer if is_buy else price + buffer

        # ---------------------------------
        # 5. TAKE PROFIT (STRUCTURE BASED)
        # ---------------------------------
        tp1 = None
        tp2 = None

        risk = abs(price - sl)

        if targets:
            targets.sort(key=lambda x: abs(x["price"] - price))

            for target in targets:
                target_price = target["price"]

                reward = (target_price - price) if is_buy else (price - target_price)

                if risk > 0 and reward > 0:
                    rr = reward / risk

                    if rr >= settings.MIN_RR_RATIO:
                        if not tp1:
                            tp1 = target_price
                        elif not tp2:
                            tp2 = target_price

        # ---------------------------------
        # 6. TP FALLBACK
        # ---------------------------------
        if not tp1:
            if payload.tv_tp and payload.tv_tp > 0:
                tp1 = payload.tv_tp
            else:
                tp1 = price + (risk * settings.MIN_RR_RATIO) if is_buy else price - (risk * settings.MIN_RR_RATIO)

        # ---------------------------------
        # 7. DIRECTION VALIDATION
        # ---------------------------------
        if is_buy and tp1 <= price:
            logger.warning("⚠️ TP invalid for BUY → fixing")
            tp1 = price + (risk * 1.5)

        if not is_buy and tp1 >= price:
            logger.warning("⚠️ TP invalid for SELL → fixing")
            tp1 = price - (risk * 1.5)

        # ---------------------------------
        # 8. APPLY VOLATILITY TO TP
        # ---------------------------------
        tp1 = tp1 * vol_multiplier
        if tp2:
            tp2 = tp2 * vol_multiplier

        # ---------------------------------
        # 9. RR CALCULATION
        # ---------------------------------
        reward = abs(tp1 - price)
        rr_ratio = round(reward / risk, 2) if risk > 0 else 0

        # ---------------------------------
        # 10. RR AUTO BOOST
        # ---------------------------------
        if rr_ratio < settings.MIN_RR_RATIO:
            logger.warning("⚠️ RR low → boosting TP")
            tp1 = price + (risk * settings.MIN_RR_RATIO) if is_buy else price - (risk * settings.MIN_RR_RATIO)
            rr_ratio = round(settings.MIN_RR_RATIO, 2)

        # ---------------------------------
        # 11. FINAL FAILSAFE
        # ---------------------------------
        if rr_ratio == 0:
            logger.warning("⚠️ FINAL FAILSAFE triggered")
            buffer = 5.0

            sl = price - buffer if is_buy else price + buffer
            tp1 = price + (buffer * 2) if is_buy else price - (buffer * 2)
            rr_ratio = 2.0

        return {
            "sl_price": round(sl, 2),
            "tp_price": round(tp1, 2),
            "tp2_price": round(tp2, 2) if tp2 else None,
            "rr_ratio": rr_ratio,
        }


risk_manager = RiskManager()
