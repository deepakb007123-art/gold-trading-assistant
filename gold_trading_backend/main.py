from trading.entry_engine import entry_engine
from fastapi import FastAPI, BackgroundTasks, status
from models.signal import WebhookPayload, TradeAnalysis, SMCConditions
from core.logger import logger

from trading.session_manager import session_manager
from trading.bias_engine import bias_engine
from trading.market_structure import market_structure
from trading.liquidity_map import liquidity_map
from trading.strategy_engine import strategy_engine
from trading.risk_manager import risk_manager
from trading.scoring_engine import scoring_engine
from trading.performance_tracker import performance_tracker

from core.decision_engine import decision_engine
from services.news_filter import news_filter
from services.telegram_bot import telegram_bot

from datetime import datetime
import uuid

app = FastAPI(title="Gold Trading Assistant FINAL", version="5.0")

SIGNAL_STATE = {"last_signal_time": None}


# -------------------------
# REJECTION HANDLER
# -------------------------
async def reject_trade(reason: str, signal_id: str):
    logger.warning(f"[{signal_id}] ❌ {reason}")
    try:
        await telegram_bot.send_message(f"❌ [{signal_id}] {reason}")
    except:
        pass


# -------------------------
# MAIN PROCESS ENGINE
# -------------------------
async def process_signal(payload: WebhookPayload):

    signal_id = str(uuid.uuid4())[:8]

    try:
        logger.info(f"[{signal_id}] Incoming: {payload.dict()}")

        # -------------------------
        # BASIC VALIDATION
        # -------------------------
        if not payload.symbol or not payload.price:
            await reject_trade("Invalid payload", signal_id)
            return

        # -------------------------
        # PERFORMANCE TRACKING
        # -------------------------
        try:
            performance_tracker.update_market_price(payload.price)
        except Exception as e:
            logger.error(f"[{signal_id}] Tracker error: {e}")

        modifiers = performance_tracker.get_adaptive_modifiers()

        # -------------------------
        # SESSION
        # -------------------------
        sessions, session_desc = session_manager.get_current_session()
        session_behavior = session_manager.get_session_behavior(sessions, modifiers)

        # -------------------------
        # COOLDOWN CONTROL
        # -------------------------
        now = datetime.utcnow()
        last = SIGNAL_STATE["last_signal_time"]
        cooldown = session_behavior.get("cooldown_minutes", 5) * 60

        if last and (now - last).total_seconds() < cooldown:
            await reject_trade("Cooldown active", signal_id)
            return

        # -------------------------
        # MARKET ANALYSIS
        # -------------------------
        bias = bias_engine.detect_bias(payload)
        structure = market_structure.analyze_structure(payload)

        if structure.get("opposite_bos"):
            await reject_trade("Opposite BOS", signal_id)
            return

        liquidity = liquidity_map.detect_liquidity(payload)
        strategy = strategy_engine.analyze_smc_conditions(payload, structure, liquidity)
        smc: SMCConditions = strategy["smc_conditions"]

        # -------------------------
        # SOFT FILTERS (NO HARD REJECTION)
        # -------------------------
        penalty = 0

        if not smc.displacement:
            penalty -= 10

        if not smc.liquidity_sweep:
            penalty -= 5

        # -------------------------
        # RISK MANAGEMENT
        # -------------------------
        risk = risk_manager.calculate_risk_parameters(payload, liquidity)

        if risk["rr_ratio"] <= 0:
            await reject_trade("Invalid RR", signal_id)
            return

        # -------------------------
        # NEWS FILTER
        # -------------------------
        news_clear, news_reason = news_filter.check_news_window()

        # -------------------------
        # SCORING ENGINE
        # -------------------------
        base, sm, sess, conf, safe, rank, reasons = scoring_engine.generate_raw_modifiers(
            structure["confidence"],
            liquidity["confidence"],
            strategy["confidence"],
            news_clear,
            smc,
            structure["htf_alignment"],
            session_behavior,
            adaptive_modifiers=modifiers,
            strategies_used=strategy.get("strategies_used", [])
        )

        score, trace = decision_engine.normalize_score(
            base + penalty, sm, sess, 0, conf, safe
        )

        quality = scoring_engine.determine_quality_tier(
            score,
            smc,
            structure["htf_alignment"],
            session_behavior,
            modifiers
        )

        # -------------------------
        # STRATEGY SOFT FILTER
        # -------------------------
        if rank == "LOW":
            penalty -= 10

        # -------------------------
        # POSITION SIZING (SIMPLE & EFFECTIVE)
        # -------------------------
        size = 1.0

        if quality == "HIGH":
            size = 1.25
        elif quality == "MEDIUM":
            size = 0.75
        elif quality == "EARLY":
            size = 0.5

        # -------------------------
        # BUILD FINAL ANALYSIS
        # -------------------------
        analysis = TradeAnalysis(
            symbol=payload.symbol,
            action=payload.action,
            entry_price, entry_type = entry_engine.get_entry(
    payload, smc, structure, liquidity
)

if entry_price is None:
    await reject_trade("Fake breakout detected", signal_id)
    return
            sl_price=risk["sl_price"],
            tp_price=risk["tp_price"],
            tp2_price=risk.get("tp2_price"),
            rr_ratio=risk["rr_ratio"],
            confidence_score=score,
            trade_quality=quality,
            position_size=size,
            risk_level="MEDIUM",
            session=session_desc,
            reasoning=reasons,
            decision_trace={"score_components": trace}
        )

        analysis.validate_trade()

        # -------------------------
        # FINAL EXECUTION
        # -------------------------
        if analysis.is_valid:

            SIGNAL_STATE["last_signal_time"] = datetime.utcnow()

            await telegram_bot.send_alert(analysis)

            performance_tracker.register_trade(analysis)

            logger.info(f"[{signal_id}] ✅ TRADE SENT | Score: {score} | {quality}")

        else:
            await reject_trade(analysis.invalidation_reason, signal_id)

    except Exception as e:
        logger.exception(f"[{signal_id}] SYSTEM ERROR")

        try:
            await telegram_bot.send_message(
                f"🔥 ERROR [{signal_id}]\n{str(e)}"
            )
        except:
            pass


# -------------------------
# WEBHOOK
# -------------------------
@app.post("/webhook", status_code=status.HTTP_202_ACCEPTED)
async def webhook(payload: WebhookPayload, background_tasks: BackgroundTasks):
    background_tasks.add_task(process_signal, payload)
    return {"status": "accepted"}


# -------------------------
# HEALTH CHECKS
# -------------------------
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
