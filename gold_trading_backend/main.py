from fastapi import FastAPI, BackgroundTasks, status
from models.signal import WebhookPayload, TradeAnalysis, SMCConditions
from core.logger import logger
from core.config import settings

# Engines
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

app = FastAPI(
    title="Gold Trading Assistant (Final)",
    version="3.0.0"
)

SIGNAL_STATE = {"last_signal_time": None}


# 🔥 GLOBAL REJECT HANDLER
async def reject_trade(reason: str):
    logger.warning(f"❌ Trade Rejected: {reason}")
    try:
        await telegram_bot.send_message(f"❌ Trade Rejected:\n{reason}")
    except:
        pass


# 🔥 MAIN ENGINE
async def process_signal(payload: WebhookPayload):

    try:
        logger.info(f"RAW PAYLOAD: {payload.dict()}")

        # --- Resolve pending trades ---
        closed_trades = performance_tracker.update_market_price(payload.price)
        if closed_trades:
            metrics = performance_tracker.get_metrics()
            if metrics.get("total_signals", 0) % 3 == 0:
                await telegram_bot.send_performance_report(metrics)

        modifiers = performance_tracker.get_adaptive_modifiers()

        # --- Session ---
        sessions, session_desc = session_manager.get_current_session()
        session_behavior = session_manager.get_session_behavior(sessions, adaptive_modifiers=modifiers)

        # --- Cooldown ---
        now = datetime.utcnow()
        last_time = SIGNAL_STATE["last_signal_time"]
        cooldown = session_behavior.get("cooldown_minutes", 5) * 60

        if last_time and (now - last_time).total_seconds() < cooldown:
            await reject_trade(f"Cooldown active ({cooldown//60} min)")
            return

        # --- Bias ---
        bias_info = bias_engine.detect_bias(payload)

        # --- Structure ---
        structure_info = market_structure.analyze_structure(payload)

        if structure_info.get("opposite_bos"):
            await reject_trade("Opposite BOS detected")
            return

        if session_behavior.get("fakeout_risk") == "High" and structure_info["is_consolidation"]:
            await reject_trade("Asian fakeout risk")
            return

        if structure_info.get("has_bos") and not session_behavior.get("allow_breakout"):
            if not structure_info["htf_alignment"]:
                await reject_trade("Breakout not allowed in session")
                return

        # --- Liquidity ---
        liquidity_info = liquidity_map.detect_liquidity(payload)

        # --- Strategy ---
        strategy_info = strategy_engine.analyze_smc_conditions(payload, structure_info, liquidity_info)
        smc: SMCConditions = strategy_info["smc_conditions"]

        if session_behavior.get("require_liquidity_taken") and not smc.liquidity_sweep:
            await reject_trade("No liquidity sweep (NY rule)")
            return

        if structure_info.get("has_bos") and not smc.displacement:
            await reject_trade("No displacement confirmation")
            return

        if smc.liquidity_sweep and not smc.sweep_confirmed:
            await reject_trade("Sweep not confirmed")
            return

        if modifiers.get("safe_mode_active", False):
            if smc.liquidity_sweep and smc.displacement and not structure_info.get("has_bos"):
                await reject_trade("SAFE MODE blocks early entry")
                return

        # --- Risk ---
        risk_info = risk_manager.calculate_risk_parameters(payload, liquidity_info)

        metrics = performance_tracker.get_metrics()
        equity_state = metrics.get("equity_state", "NORMAL")
        drawdown = metrics.get("drawdown_pct", 0)

        min_rr = 1.5
        if modifiers.get("safe_mode_active"):
            min_rr = 1.8
        if equity_state in ["DEFENSIVE", "CRITICAL"]:
            min_rr = 1.8

        if risk_info["rr_ratio"] < min_rr:
            await reject_trade(f"RR too low ({risk_info['rr_ratio']})")
            return

        # --- News ---
        news_clear, news_reason = news_filter.check_news_window()

        # --- Scoring ---
        base, sm, sess, conf, safe, rank, reasons = scoring_engine.generate_raw_modifiers(
            structure_info["confidence"],
            liquidity_info["confidence"],
            strategy_info["confidence"],
            news_clear,
            smc,
            structure_info["htf_alignment"],
            session_behavior,
            adaptive_modifiers=modifiers,
            strategies_used=strategy_info["strategies_used"]
        )

        dd_mod = -int(drawdown) if drawdown >= 5 else 0

        score, score_trace = decision_engine.normalize_score(
            base, sm, sess, dd_mod, conf, safe
        )

        quality = scoring_engine.determine_quality_tier(
            score, smc, structure_info["htf_alignment"], session_behavior, modifiers
        )

        if rank == "LOW":
            await reject_trade("All strategies LOW performance")
            return

        if equity_state in ["DEFENSIVE", "CRITICAL"]:
            if quality == "EARLY":
                await reject_trade("EARLY blocked in drawdown")
                return
            if score < 55:
                await reject_trade("Score too low for drawdown state")
                return

        # --- Position ---
        base_size, strat_m, sess_m, dd_m, conf_m, safe_m, pos_reason = position_manager.generate_raw_multipliers(
            quality, smc, risk_info["rr_ratio"], session_desc,
            modifiers.get("safe_mode_active"),
            metrics.get("recent_losses_last_5", 0),
            equity_state,
            metrics.get("consecutive_wins", 0),
            metrics.get("equity_momentum", "FLAT")
        )

        size, size_trace = decision_engine.normalize_position(
            base_size, strat_m, sess_m, dd_m, conf_m, safe_m
        )

        risk_level = position_manager.determine_risk_tier(size)

        analysis = TradeAnalysis(
            symbol=payload.symbol,
            action=payload.action,
            entry_price=payload.price,
            sl_price=risk_info["sl_price"],
            tp_price=risk_info["tp_price"],
            tp2_price=risk_info["tp2_price"],
            rr_ratio=risk_info["rr_ratio"],
            confidence_score=score,
            trade_quality=quality,
            position_size=size,
            risk_level=risk_level,
            session=session_desc,
            system_state=modifiers.get("system_state", "NORMAL")
        )

        analysis.validate_trade()

        if analysis.is_valid:
            SIGNAL_STATE["last_signal_time"] = datetime.utcnow()

            await telegram_bot.send_alert(analysis)

            # 🔥 DEBUG TRACE
            await telegram_bot.send_message(f"🧠 TRACE:\n{score_trace}")

            performance_tracker.register_trade(analysis)

        else:
            await reject_trade(analysis.invalidation_reason)

    except Exception as e:
        logger.exception("🔥 SYSTEM ERROR")
        try:
            await telegram_bot.send_message(f"🔥 SYSTEM ERROR:\n{str(e)}")
        except:
            pass


# 🔥 WEBHOOK
@app.post("/webhook", status_code=status.HTTP_202_ACCEPTED)
async def webhook(payload: WebhookPayload, background_tasks: BackgroundTasks):
    background_tasks.add_task(process_signal, payload)
    return {"status": "accepted"}


# 🔥 HEALTH (Railway fix)
@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
