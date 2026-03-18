from fastapi import FastAPI, BackgroundTasks, HTTPException, status
from models.signal import WebhookPayload, TradeAnalysis, SMCConditions
from core.logger import logger
from core.config import settings

# Import Engines
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
import asyncio

app = FastAPI(
    title="Gold Trading Assistant (V2.1 Strict SMC Mode)",
    description="Institutional-Grade Gold Trading Assistant Webhook Processor",
    version="2.0.0"
)

# Global state for rate limiting/cooldowns
SIGNAL_STATE = {
    "last_signal_time": None
}

async def process_signal(payload: WebhookPayload):
    """
    Main Orchestrator: Chains engines together and dispatches valid alerts.
    """
    logger.info(f"Processing new {payload.action} signal for {payload.symbol}")
    
    # --- RESOLVE PENDING TRADES ---
    # Because we don't have a live price feed, we simulate outcome 
    # checking based on the incoming webhook price.
    closed_trades = performance_tracker.update_market_price(payload.price)
    if closed_trades:
        # Check if we should send a performance report (e.g., every 3rd closed trade)
        metrics = performance_tracker.get_metrics()
        if metrics.get("total_signals", 0) > 0 and metrics["total_signals"] % 3 == 0:
            await telegram_bot.send_performance_report(metrics)
            
    # --- GET ADAPTIVE MODIFIERS ---
    modifiers = performance_tracker.get_adaptive_modifiers()
            
    # 1. Session Detection
    sessions, session_desc = session_manager.get_current_session()
    session_behavior = session_manager.get_session_behavior(sessions, adaptive_modifiers=modifiers)
    logger.debug(f"Detected Session: {session_desc} | Behavior: {session_behavior['expected_action']}")
    
    # --- SMART COOLDOWN CHECK ---
    now = datetime.utcnow()
    last_time = SIGNAL_STATE["last_signal_time"]
    cooldown_seconds = session_behavior.get("cooldown_minutes", 5) * 60
    
    if last_time and (now - last_time).total_seconds() < cooldown_seconds:
        logger.warning(f"Trade rejected: Dynamic signal cooldown active. Wait {cooldown_seconds//60} minutes between signals in {session_desc}.")
        return
    
    # 2. Market Context & Bias
    bias_info = bias_engine.detect_bias(payload)
    
    # 3. Market Structure Analysis
    structure_info = market_structure.analyze_structure(payload)
    
    # --- STRICT SYSTEM INVALIDATIONS ---
    # 3a. Opposite BOS Rejection
    if structure_info.get("opposite_bos"):
        logger.warning("Trade rejected due to opposite BOS indicating structural shift.")
        return
        
    # 3b. Asian Fakeout Risk (Consolidation Breakout)
    if session_behavior.get("fakeout_risk") == "High" and structure_info["is_consolidation"]:
        logger.warning("Trade rejected due to Asian Session Fakeout Risk (consolidation breakout).")
        return
        
    # 3c. Session Breakout Rules (Strict Mode)
    if structure_info.get("has_bos") and not session_behavior.get("allow_breakout"):
        if not (session_behavior.get("require_htf_alignment") and structure_info["htf_alignment"]):
            logger.warning(f"Trade rejected: {session_desc} session does not permit breakouts without pure HTF alignment.")
            return
    
    # 4. Liquidity Mapping
    liquidity_info = liquidity_map.detect_liquidity(payload)
    
    # 5. SMC Strategy Engine (Checks confluence)
    strategy_info = strategy_engine.analyze_smc_conditions(payload, structure_info, liquidity_info)
    smc_conditions: SMCConditions = strategy_info["smc_conditions"]
    
    # --- STRICT SYSTEM INVALIDATIONS (Post-SMC Checks) ---
    # 5a. NY Continuation Rules
    if session_behavior.get("require_liquidity_taken") and not smc_conditions.liquidity_sweep:
         logger.warning("Trade rejected: NY Session continuation requires prior liquidity Sweep.")
         return
         
    # 5b. False Breakout Detection (No displacement)
    if structure_info.get("has_bos") and not smc_conditions.displacement:
         logger.warning("Trade rejected: Structure breakout detected without confirming displacement (volume/momentum proxy).")
         return
         
    # 5c. Sweep Confirmation Upgrade
    if smc_conditions.liquidity_sweep and not smc_conditions.sweep_confirmed:
         logger.warning("Trade rejected: Liquidity sweep occurred but lacked structural rejection/displacement.")
         return
         
    # 5d. SAFE MODE Constraints
    if modifiers.get("safe_mode_active", False):
         is_early_entry = smc_conditions.liquidity_sweep and smc_conditions.displacement and not structure_info.get("has_bos")
         if is_early_entry:
             logger.warning("Trade rejected: SAFE MODE active. EARLY entries (pre-structure risk) are entirely disabled.")
             return
    
    # 6. Risk Management (Smart SL, TP1, TP2, RR)
    risk_info = risk_manager.calculate_risk_parameters(payload, liquidity_info)
    
    metrics = performance_tracker.get_metrics()
    equity_state = metrics.get("equity_state", "NORMAL")
    drawdown_pct = metrics.get("drawdown_pct", 0.0)
    
    # 6a. Risk Filter Refinement
    min_rr = 1.5
    if modifiers.get("safe_mode_active", False):
        min_rr = 1.8
    if equity_state in ["DEFENSIVE", "CRITICAL"]:
        min_rr = max(min_rr, 1.8)
        
    if risk_info["rr_ratio"] < min_rr:
        logger.warning(f"Trade rejected: TP too close to entry or SL too wide. RR = {risk_info['rr_ratio']} < {min_rr}R")
        return
    
    # 7. News Filter
    news_clear, news_reason = news_filter.check_news_window()
    
    # 8. Scoring Engine (Adaptive compilation and V8 Strategy Selection)
    base_score, strat_mod, sess_mod, conf_mod, safe_mod, strat_rank, strat_reasons = scoring_engine.generate_raw_modifiers(
        structure_info["confidence"],
        liquidity_info["confidence"],
        strategy_info["confidence"],
        news_clear,
        smc_conditions,
        structure_info["htf_alignment"],
        session_behavior,
        adaptive_modifiers=modifiers,
        strategies_used=strategy_info["strategies_used"]
    )
    
    dd_score_mod = 0
    if drawdown_pct >= 5.0:
        dd_score_mod = -int(drawdown_pct)
        
    score, score_trace = decision_engine.normalize_score(
        base_score=base_score,
        strategy_modifier=strat_mod,
        session_modifier=sess_mod,
        drawdown_modifier=dd_score_mod,
        confluence_modifier=conf_mod,
        safe_mode_modifier=safe_mod
    )
    
    trade_quality = scoring_engine.determine_quality_tier(
        score, smc_conditions, structure_info["htf_alignment"], session_behavior, modifiers
    )
    
    # --- V8 PORTFOLIO AUTO-DISABLE LOGIC ---
    if strat_rank == "LOW":
        # Ensure all strategies used are LOW (no MID or TOP present to salvage it)
        # Using modifiers check to see if all evaluated as LOW explicitly.
        # Check explicit array output logic: highest_rank bubbles up. So if strat_rank is "LOW", there are NO top/mid strategies.
        logger.warning(f"Trade rejected: V8 Portfolio Auto-Disable activated. All active strategies classified as LOW (<40% win rate).")
        return
    
    # --- V7 EQUITY STATE RESTRICTIONS ---
    if equity_state in ["DEFENSIVE", "CRITICAL"]:
        if trade_quality == "EARLY":
            logger.warning(f"Trade rejected: Equity State is {equity_state}. EARLY entries completely disabled.")
            return
            
        if score < 55:
            logger.warning(f"Trade rejected: Equity State {equity_state} requires > 55 Confidence (Got {score}).")
            return
    
    all_reasons = []
    all_reasons.extend(bias_info["context_reasoning"])
    all_reasons.extend(structure_info["structure_reasoning"])
    all_reasons.extend(liquidity_info["liquidity_reasons"])
    all_reasons.extend(strategy_info["smc_reasoning"])
    all_reasons.extend(strat_reasons) # V8 Strategy Ranks
    
    if not news_clear:
        all_reasons.append(f"WARNING: {news_reason}")
    else:
        all_reasons.append(news_reason)
                
    # 10. Position Intelligence Engine (V6 Sizing Matrix)
    base_size, strat_mult, sess_mult, dd_mult, conf_mult, safe_mult, pos_reason = position_manager.generate_raw_multipliers(
        trade_quality=trade_quality,
        smc_conditions=smc_conditions,
        rr_ratio=risk_info["rr_ratio"],
        session_name=session_desc,
        safe_mode_active=modifiers.get("safe_mode_active", False),
        recent_losses_last_5=metrics.get("recent_losses_last_5", 0),
        equity_state=equity_state,
        consecutive_wins=metrics.get("consecutive_wins", 0),
        equity_momentum=metrics.get("equity_momentum", "FLAT")
    )
    
    pos_size, size_trace = decision_engine.normalize_position(
        base_size=base_size,
        strategy_multiplier=strat_mult,
        session_multiplier=sess_mult,
        drawdown_multiplier=dd_mult,
        confluence_multiplier=conf_mult,
        safe_mode_multiplier=safe_mult
    )
    
    pos_risk = position_manager.determine_risk_tier(pos_size)
    pos_reason_str = " | ".join(pos_reason)
    
    decision_trace = {
        "score_components": score_trace,
        "size_components": size_trace
    }

    analysis = TradeAnalysis(
        symbol=payload.symbol,
        action=payload.action,
        entry_price=payload.price,
        sl_price=risk_info["sl_price"],
        tp_price=risk_info["tp_price"],
        tp2_price=risk_info["tp2_price"],
        rr_ratio=risk_info["rr_ratio"],
        confidence_score=score,
        trade_quality=trade_quality,
        position_size=pos_size,
        risk_level=pos_risk,
        position_reasoning=pos_reason_str,
        bias=bias_info["bias"],
        price_zone=bias_info["zone"],
        htf_alignment=structure_info["htf_alignment"],
        trend_alignment="NEUTRAL",
        session=session_desc,
        system_state=modifiers.get("system_state", "NORMAL"),
        equity_state=equity_state,
        drawdown_pct=drawdown_pct,
        strategy_rank=strat_rank,
        smc_conditions=smc_conditions,
        reasoning=all_reasons,
        decision_trace=decision_trace,
        strategies_used=strategy_info["strategies_used"],
        news_clear=news_clear,
        news_reason=news_reason
    )
    
    # 10. Validation & Dispatch
    analysis.validate_trade()
    
    if analysis.is_valid:
        logger.info(f"Trade is valid (Score: {score}% | Quality: {trade_quality}). Dispatching to Telegram.")
        # Mark successful valid signal timestamp
        SIGNAL_STATE["last_signal_time"] = datetime.utcnow()
        await telegram_bot.send_alert(analysis)
        performance_tracker.register_trade(analysis)
    else:
        logger.warning(
            f"Trade rejected internally inside analysis validation module: {analysis.invalidation_reason} (Quality: {trade_quality}, RR: {analysis.rr_ratio})"
        )

@app.post("/webhook", status_code=status.HTTP_202_ACCEPTED)
async def webhook_receiver(payload: WebhookPayload, background_tasks: BackgroundTasks):
    """
    Receives the TradingView webhook and schedules background processing
    to prevent blocking the Railway HTTP router.
    """
    # Accept immediately, process in background
    background_tasks.add_task(process_signal, payload)
    return {"status": "Accepted", "message": "Signal queued for processing"}

@app.get("/health")
def health_check():
    """Health check endpoint for Railway."""
    return {"status": "ok", "service": settings.APP_NAME}
