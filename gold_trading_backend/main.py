from fastapi import FastAPI, BackgroundTasks, status
from models.signal import WebhookPayload, TradeAnalysis, SMCConditions
from core.logger import logger
from core.config import settings

from trading.session_manager import session_manager
from trading.bias_engine import bias_engine
from trading.market_structure import market_structure
from trading.liquidity_map import liquidity_map
from trading.strategy_engine import strategy_engine
from trading.risk_manager import risk_manager
from trading.scoring_engine import scoring_engine
from trading.performance_tracker import performance_tracker
from trading.position_manager import position_manager
from core.decision_engine import decision_engine

from services.news_filter import news_filter
from services.telegram_bot import telegram_bot

from datetime import datetime
import uuid

app = FastAPI(title="Gold Trading Assistant FIXED", version="4.0")

SIGNAL_STATE = {"last_signal_time": None}


# ✅ GLOBAL REJECTION HANDLER
async def reject_trade(reason: str, signal_id: str):
    logger.warning(f"[{signal_id}] ❌ {reason}")
    try:
        await telegram_bot.send_message(f"❌ [{signal_id}] {reason}")
    except:
        pass


# ✅ MAIN ENGINE
async def process_signal(payload: WebhookPayload):

    signal_id = str(uuid.uuid4())[:8]

    try:
        logger.info(f"[{signal_id}] Incoming: {payload.dict()}")

        # ✅ Payload safety
        if not payload.symbol or not payload.price:
            await reject_trade("Invalid payload", signal_id)
            return

        # ✅ Safe performance tracker
        try:
            closed = performance_tracker.update_market_price(payload.price)
        except Exception as e:
            logger.error(f"[{signal_id}] Tracker error: {e}")
            closed = []

        modifiers = performance_tracker.get_adaptive_modifiers()

        # ✅ Session
        sessions, session_desc = session_manager.get_current_session()
        session_behavior = session_manager.get_session_behavior(sessions, modifiers)

        # ✅ Cooldown
        now = datetime.utcnow()
        last = SIGNAL_STATE["last_signal_time"]
        cooldown = session_behavior.get("cooldown_minutes", 5) * 60

        if last and (now - last).total_seconds() < cooldown:
            await reject_trade("Cooldown active", signal_id)
            return

        # ✅ Bias + Structure
        bias = bias_engine.detect_bias(payload)
        structure = market_structure.analyze_structure(payload)

        if structure.get("opposite_bos"):
            await reject_trade("Opposite BOS", signal_id)
            return

        # ✅ Liquidity + Strategy
        liquidity = liquidity_map.detect_liquidity(payload)
        strategy = strategy_engine.analyze_smc_conditions(payload, structure, liquidity)
        smc: SMCConditions = strategy["smc_conditions"]

        if not smc.displacement:
            await reject_trade("No displacement", signal_id)
            return

        # ✅ Risk
        risk = risk_manager.calculate_risk_parameters(payload, liquidity)

        if risk["rr_ratio"] < 1.5:
            await reject_trade("RR too low", signal_id)
            return

        # ✅ News
        news_clear, news_reason = news_filter.check_news_window()

        # ✅ Scoring
        base, sm, sess, conf, safe, rank, _ = scoring_engine.generate_raw_modifiers(
            structure["confidence"],
            liquidity["confidence"],
            strategy["confidence"],
            news_clear,
            smc,
            structure["htf_alignment"],
            session_behavior,
            adaptive_modifiers=modifiers,
            strategies_used=strategy["strategies_used"]
        )

        score, trace = decision_engine.normalize_score(
            base, sm, sess, 0, conf, safe
        )

        quality = scoring_engine.determine_quality_tier(
            score, smc, structure["htf_alignment"], session_behavior, modifiers
        )

        if rank == "LOW":
            await reject_trade("Low strategy rank", signal_id)
            return

        # ✅ Position
        size = 1.0

        # ✅ FINAL OBJECT
        analysis = TradeAnalysis(
            symbol=payload.symbol,
            action=payload.action,
            entry_price=payload.price,
            sl_price=risk["sl_price"],
            tp_price=risk["tp_price"],
            tp2_price=risk.get("tp2_price"),
            rr_ratio=risk["rr_ratio"],
            confidence_score=score,
            trade_quality=quality,
            position_size=size,
            risk_level="MEDIUM",
            session=session_desc,
            reasoning=["Validated signal"],
            decision_trace={"score_components": trace}
        )

        analysis.validate_trade()

        if analysis.is_valid:
            SIGNAL_STATE["last_signal_time"] = datetime.utcnow()

            await telegram_bot.send_alert(analysis)

            await telegram_bot.send_message(
                f"🧠 [{signal_id}] TRACE:\n{trace}"
            )

            performance_tracker.register_trade(analysis)

        else:
            await reject_trade(analysis.invalidation_reason, signal_id)

    except Exception as e:
        logger.exception(f"[{signal_id}] SYSTEM ERROR")

        try:
            await telegram_bot.send_message(
                f"🔥 SYSTEM ERROR [{signal_id}]\n{str(e)}"
            )
        except:
            pass


# ✅ WEBHOOK
@app.post("/webhook", status_code=status.HTTP_202_ACCEPTED)
async def webhook(payload: WebhookPayload, background_tasks: BackgroundTasks):
    background_tasks.add_task(process_signal, payload)
    return {"status": "accepted"}


# ✅ HEALTH
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
