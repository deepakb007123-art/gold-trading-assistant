from datetime import datetime, timezone
import uuid

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, status

from .core.config import settings
from .core.decision_engine import decision_engine
from .core.logger import logger
from .models.signal import TradeAnalysis, WebhookPayload
from .services.news_filter import news_filter
from .services.telegram_bot import telegram_bot
from .trading.Entry_engine import entry_engine
from .trading.bias_engine import bias_engine
from .trading.liquidity_map import liquidity_map
from .trading.market_memory import market_memory
from .trading.market_structure import market_structure
from .trading.performance_tracker import performance_tracker
from .trading.risk_manager import risk_manager
from .trading.scoring_engine import scoring_engine
from .trading.session_manager import session_manager
from .trading.strategy_engine import strategy_engine


app = FastAPI(title="Gold Trading Assistant", version="6.0")
SIGNAL_STATE = {"last_signal_time": None}


def _utc_now() -> datetime:
    """Return the current UTC time as a timezone-aware datetime."""
    return datetime.now(timezone.utc)


def _verify_webhook_secret(provided_secret: str | None) -> None:
    """Require the configured shared secret when WEBHOOK_SECRET is enabled."""
    expected = settings.WEBHOOK_SECRET.strip()
    if expected and provided_secret != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook secret")


async def reject_trade(reason: str, signal_id: str) -> None:
    logger.warning("[%s] REJECTED: %s", signal_id, reason)
    try:
        await telegram_bot.send_message(f"❌ [{signal_id}] {reason}")
    except Exception:
        logger.exception("[%s] Failed to notify rejection", signal_id)


def _parse_timestamp(timestamp: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp and normalize it to timezone-aware UTC."""
    if not timestamp:
        return None
    try:
        value = timestamp.replace("Z", "+00:00")
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


async def process_signal(payload: WebhookPayload) -> dict:
    signal_id = str(uuid.uuid4())[:8]

    try:
        logger.info("[%s] Incoming signal: %s", signal_id, payload.model_dump())

        market_memory.update(payload.price)
        levels = market_memory.get_levels()
        payload.extra.update({k: v for k, v in levels.items() if v is not None})

        now = _utc_now()
        last = SIGNAL_STATE["last_signal_time"]

        event_time = _parse_timestamp(payload.timestamp) or now
        active_sessions, session_desc = session_manager.get_current_session(event_time)
        modifiers = performance_tracker.get_adaptive_modifiers()
        session_behavior = session_manager.get_session_behavior(active_sessions, modifiers)
        cooldown_seconds = session_behavior.get("cooldown_minutes", 5) * 60

        if last and (now - last).total_seconds() < cooldown_seconds:
            reason = "Cooldown active"
            await reject_trade(reason, signal_id)
            return {"approved": False, "reason": reason, "signal_id": signal_id}

        bias = bias_engine.detect_bias(payload)
        structure = market_structure.analyze_structure(payload)

        if structure.get("opposite_bos"):
            reason = "Opposite BOS"
            await reject_trade(reason, signal_id)
            return {"approved": False, "reason": reason, "signal_id": signal_id}

        liquidity = liquidity_map.detect_liquidity(payload)
        strategy = strategy_engine.analyze_smc_conditions(payload, structure, liquidity)
        smc = strategy["smc_conditions"]

        entry_price, entry_type = entry_engine.get_entry(payload, smc, structure, liquidity)
        if entry_price is None:
            reason = "Unconfirmed breakout / no valid entry"
            await reject_trade(reason, signal_id)
            return {"approved": False, "reason": reason, "signal_id": signal_id}

        penalty = 0
        if not smc.displacement:
            penalty -= 10
        if not smc.liquidity_sweep:
            penalty -= 5

        risk = risk_manager.calculate_risk_parameters(payload, liquidity, entry_price)
        if risk["rr_ratio"] <= 0:
            reason = "Invalid R:R"
            await reject_trade(reason, signal_id)
            return {"approved": False, "reason": reason, "signal_id": signal_id}

        news_clear, news_reason = news_filter.check_news_window(payload)

        base, strat_mod, sess_mod, conf_mod, safe_mod, rank, score_reasons = scoring_engine.generate_raw_modifiers(
            structure["confidence"],
            liquidity["confidence"],
            strategy["confidence_contribution"],
            news_clear,
            smc,
            structure["htf_alignment"],
            session_behavior,
            adaptive_modifiers=modifiers,
            strategies_used=strategy.get("strategies_used", []),
        )

        score, trace = decision_engine.normalize_score(
            base + penalty,
            strat_mod,
            sess_mod,
            0,
            conf_mod,
            safe_mod,
        )

        quality = scoring_engine.determine_quality_tier(
            score,
            smc,
            structure["htf_alignment"],
            session_behavior,
            modifiers,
        )

        quality_factor = {"HIGH": 1.25, "MEDIUM": 1.0, "EARLY": 0.5, "LOW": 0.25}[quality]
        position_size = round(payload.position_size * quality_factor, 2)

        metrics = performance_tracker.get_metrics()
        reasoning = []
        reasoning.extend(bias.get("context_reasoning", []))
        reasoning.extend(structure.get("structure_reasoning", []))
        reasoning.extend(liquidity.get("liquidity_reasons", []))
        reasoning.extend(strategy.get("smc_reasoning", []))
        reasoning.extend(score_reasons)
        reasoning.append(f"Entry model: {entry_type}")

        analysis = TradeAnalysis(
            symbol=payload.symbol,
            action=payload.action,
            entry_price=risk["entry_price"],
            sl_price=risk["sl_price"],
            tp_price=risk["tp_price"],
            tp2_price=risk.get("tp2_price"),
            rr_ratio=risk["rr_ratio"],
            confidence_score=score,
            trade_quality=quality,
            position_size=position_size,
            system_state=metrics.get("system_state", "NORMAL"),
            equity_state=metrics.get("equity_state", "NORMAL"),
            drawdown_pct=metrics.get("drawdown_pct", 0.0),
            htf_alignment=structure["htf_alignment"],
            trend_alignment=structure["trend"],
            session=session_desc,
            risk_level="LOW" if quality in {"HIGH", "MEDIUM"} else "NORMAL",
            position_reasoning=f"Base size {payload.position_size} × quality factor {quality_factor}",
            smc_conditions=smc,
            reasoning=reasoning,
            strategies_used=strategy.get("strategies_used", []),
            bias=bias.get("bias", "NEUTRAL"),
            price_zone=bias.get("price_zone", "UNKNOWN"),
            strategy_rank=rank if rank != "UNKNOWN" else payload.strategy_rank,
            decision_trace={"score_components": trace},
            news_clear=news_clear,
            news_reason=news_reason,
        )

        analysis.validate_trade()

        if not analysis.is_valid:
            await reject_trade(analysis.invalidation_reason or "Trade rejected", signal_id)
            return {
                "approved": False,
                "reason": analysis.invalidation_reason,
                "signal_id": signal_id,
                "analysis": analysis.model_dump(),
            }

        SIGNAL_STATE["last_signal_time"] = now
        await telegram_bot.send_alert(analysis)
        performance_tracker.register_trade(analysis)

        logger.info(
            "[%s] APPROVED | score=%s quality=%s entry=%s",
            signal_id,
            score,
            quality,
            entry_type,
        )

        return {"approved": True, "signal_id": signal_id, "analysis": analysis.model_dump()}

    except Exception as exc:
        logger.exception("[%s] Pipeline error", signal_id)
        try:
            await telegram_bot.send_message(f"🔥 ERROR [{signal_id}] {exc}")
        except Exception:
            logger.exception("[%s] Failed to report pipeline error", signal_id)
        return {"approved": False, "reason": "Internal processing error", "signal_id": signal_id}


@app.post("/webhook", status_code=status.HTTP_202_ACCEPTED)
async def webhook(
    payload: WebhookPayload,
    background_tasks: BackgroundTasks,
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
):
    _verify_webhook_secret(x_webhook_secret)
    background_tasks.add_task(process_signal, payload)
    return {"status": "accepted"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.get("/status")
def status_endpoint():
    return {
        "status": "operational",
        "modules": {
            "bias_engine": True,
            "market_structure": True,
            "liquidity_map": True,
            "strategy_engine": True,
            "risk_manager": True,
            "news_filter": True,
            "scoring_engine": True,
            "telegram": bool(telegram_bot.token and telegram_bot.chat_id),
            "webhook_auth": bool(settings.WEBHOOK_SECRET),
        },
    }
