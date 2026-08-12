import asyncio

from fastapi.testclient import TestClient

from gold_trading_backend.main import app, process_signal
from gold_trading_backend.models.signal import SMCConditions, WebhookPayload
from gold_trading_backend.trading.Entry_engine import EntryEngine
from gold_trading_backend.trading.liquidity_map import LiquidityMap
from gold_trading_backend.trading.risk_manager import RiskManager


client = TestClient(app)


def sample_payload(**overrides):
    data = {
        "symbol": "XAUUSD",
        "timeframe": "15m",
        "action": "BUY",
        "price": 4415.20,
        "drawdown_pct": 0.0,
        "strategy_rank": "TOP",
        "position_size": 1.0,
        "htf_bias": "BULLISH",
        "htf_alignment": True,
        "price_zone": "DISCOUNT",
        "bos": False,
        "choch": True,
        "liquidity_sweep": True,
        "order_block": True,
        "fvg_imbalance": True,
        "inducements": False,
        "displacement": True,
        "sweep_confirmed": True,
        "liquidity_approaching": True,
        "news_clear": True,
        "pdh": 4430.0,
        "eqh": 4428.0,
        "timestamp": "2026-08-12T08:00:00Z",
    }
    data.update(overrides)
    return WebhookPayload(**data)


def test_healthz():
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_status():
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"
    assert "modules" in data
    assert data["modules"]["risk_manager"] is True


def test_invalid_payload_is_rejected_by_pydantic():
    response = client.post("/webhook", json={"symbol": "XAUUSD"})
    assert response.status_code == 422


def test_payload_model_accepts_smc_context():
    payload = sample_payload()
    assert payload.action == "BUY"
    assert payload.liquidity_sweep is True
    assert payload.order_block is True


def test_liquidity_map_returns_directional_target():
    payload = sample_payload()
    liquidity = LiquidityMap().detect_liquidity(payload)
    assert liquidity["targets"]
    assert liquidity["best_target"]["price"] > payload.price


def test_entry_engine_returns_sniper_entry():
    payload = sample_payload()
    smc = SMCConditions(
        liquidity_sweep=True,
        order_block=True,
        fvg_imbalance=True,
        choch=True,
        displacement=True,
        sweep_confirmed=True,
    )
    structure = {"has_bos": False, "has_choch": True}
    liquidity = LiquidityMap().detect_liquidity(payload)
    entry, entry_type = EntryEngine().get_entry(payload, smc, structure, liquidity)
    assert entry is not None
    assert entry_type == "Sniper Entry"
    assert entry < payload.price


def test_risk_manager_generates_valid_levels():
    payload = sample_payload()
    liquidity = LiquidityMap().detect_liquidity(payload)
    risk = RiskManager().calculate_risk_parameters(payload, liquidity, entry_price=4413.0)
    assert risk["sl_price"] < risk["entry_price"] < risk["tp_price"]
    assert risk["rr_ratio"] >= 1.5


def test_webhook_returns_accepted():
    response = client.post("/webhook", json=sample_payload().model_dump())
    assert response.status_code == 202
    assert response.json()["status"] == "accepted"


def test_process_signal_rejects_against_htf(monkeypatch):
    async def fake_send_message(_):
        return True

    monkeypatch.setattr("gold_trading_backend.main.telegram_bot.send_message", fake_send_message)
    payload = sample_payload(action="SELL", htf_bias="BULLISH", htf_alignment=False)
    result = asyncio.run(process_signal(payload))
    assert result["approved"] is False
