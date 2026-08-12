from typing import Dict

from ..core.config import settings
from ..core.logger import logger
from ..models.signal import WebhookPayload
from .session_manager import session_manager


class RiskManager:
    """Calculate structurally consistent SL/TP levels around the actual entry."""

    def calculate_risk_parameters(
        self, payload: WebhookPayload, liquidity: Dict, entry_price: float | None = None
    ) -> Dict:
        price = float(entry_price if entry_price is not None else payload.price)
        is_buy = payload.action == "BUY"
        targets = list(liquidity.get("targets", []))

        sessions, _ = session_manager.get_current_session()
        vol_multiplier = session_manager.get_volatility_multiplier(sessions)

        base_stop_distance = 3.0 * vol_multiplier
        structural_distance = 4.5 * vol_multiplier

        if payload.tv_sl:
            sl = float(payload.tv_sl)
        else:
            structural_sl = price - structural_distance if is_buy else price + structural_distance
            volatility_sl = price - base_stop_distance if is_buy else price + base_stop_distance
            sl = structural_sl if abs(price - structural_sl) >= abs(price - volatility_sl) else volatility_sl

        min_sl_distance = 2.5
        if abs(price - sl) < min_sl_distance:
            sl = price - min_sl_distance if is_buy else price + min_sl_distance

        if is_buy and sl >= price:
            sl = price - max(base_stop_distance, min_sl_distance)
        if not is_buy and sl <= price:
            sl = price + max(base_stop_distance, min_sl_distance)

        risk = abs(price - sl)
        if risk <= 0:
            raise ValueError("Unable to calculate positive trade risk")

        tp1 = None
        tp2 = None

        if payload.tv_tp:
            candidate = float(payload.tv_tp)
            if (is_buy and candidate > price) or (not is_buy and candidate < price):
                tp1 = candidate

        if tp1 is None:
            directional_targets = []
            for target in targets:
                target_price = target.get("price")
                if target_price is None:
                    continue
                reward = target_price - price if is_buy else price - target_price
                if reward > 0 and (reward / risk) >= settings.MIN_RR_RATIO:
                    directional_targets.append((reward, float(target_price)))

            directional_targets.sort(key=lambda x: x[0])
            if directional_targets:
                tp1 = directional_targets[0][1]
                if len(directional_targets) > 1:
                    tp2 = directional_targets[1][1]

        if tp1 is None:
            tp1 = price + risk * settings.MIN_RR_RATIO if is_buy else price - risk * settings.MIN_RR_RATIO

        if is_buy and tp1 <= price:
            tp1 = price + risk * settings.MIN_RR_RATIO
        if not is_buy and tp1 >= price:
            tp1 = price - risk * settings.MIN_RR_RATIO

        rr_ratio = round(abs(tp1 - price) / risk, 2)
        if rr_ratio < settings.MIN_RR_RATIO:
            tp1 = price + risk * settings.MIN_RR_RATIO if is_buy else price - risk * settings.MIN_RR_RATIO
            rr_ratio = round(settings.MIN_RR_RATIO, 2)

        if tp2 is not None:
            tp2 = round(tp2, 2)
            if is_buy and tp2 <= tp1:
                tp2 = None
            elif not is_buy and tp2 >= tp1:
                tp2 = None

        logger.info("Risk calculated: entry=%s sl=%s tp=%s rr=%s", price, sl, tp1, rr_ratio)

        return {
            "entry_price": round(price, 2),
            "sl_price": round(sl, 2),
            "tp_price": round(tp1, 2),
            "tp2_price": tp2,
            "rr_ratio": rr_ratio,
        }


risk_manager = RiskManager()
