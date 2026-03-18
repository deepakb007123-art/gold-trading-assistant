"""
Basic smoke tests for the Gold Trading Signal Assistant.

Run with:  pytest tests/ -v
"""

import pytest
from fastapi.testclient import TestClient

from gold_trading_backend.app.main import app
from gold_trading_backend.server.analyzer import SignalAnalyzer
from gold_trading_backend.server.liquidity_predictor import LiquidityPredictor
from gold_trading_backend.server.strategy_engine import StrategyEngine

client = TestClient(app)

SAMPLE_PAYLOAD = {
    "symbol": "XAUUSD",
    "signal": "BREAKOUT_BUY",
    "price": 2345.20,
    "probability": 82,
    "strategy": "breakout",
    "session": "london",
}


# ── Health endpoints ──────────────────────────────────────────────────────────

def test_healthz():
    resp = client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_status():
    resp = client.get("/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "operational"
    assert "modules" in data


def test_logs_empty():
    resp = client.get("/logs")
    assert resp.status_code == 200
    assert "logs" in resp.json()


# ── Webhook ───────────────────────────────────────────────────────────────────

def test_webhook_valid_signal():
    resp = client.post("/webhook", json=SAMPLE_PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert "approved" in data
    assert "analysis" in data


def test_webhook_low_probability():
    payload = {**SAMPLE_PAYLOAD, "probability": 50}
    resp = client.post("/webhook", json=payload)
    assert resp.status_code == 200
    assert resp.json()["approved"] is False


def test_webhook_missing_field():
    resp = client.post("/webhook", json={"symbol": "XAUUSD"})
    assert resp.status_code == 422  # Unprocessable Entity


# ── LiquidityPredictor ────────────────────────────────────────────────────────

def test_liquidity_buy():
    lp = LiquidityPredictor(sl_buffer=5.0, tp_multiplier=2.0)
    result = lp.calculate(2345.20, "BUY")
    assert result["entry"] == 2345.20
    assert result["stop_loss"] < result["entry"]
    assert result["take_profit"] > result["entry"]


def test_liquidity_sell():
    lp = LiquidityPredictor(sl_buffer=5.0, tp_multiplier=2.0)
    result = lp.calculate(2345.20, "SELL")
    assert result["stop_loss"] > result["entry"]
    assert result["take_profit"] < result["entry"]


# ── StrategyEngine ────────────────────────────────────────────────────────────

def test_strategy_aligned():
    se = StrategyEngine()
    assert se.is_aligned("breakout", "BUY", "london") is True


def test_strategy_not_aligned():
    se = StrategyEngine()
    assert se.is_aligned("scalp", "BUY", "asian") is False


# ── Full pipeline ─────────────────────────────────────────────────────────────

def test_analyzer_approves_good_signal():
    analyzer = SignalAnalyzer()
    result = analyzer.analyze(SAMPLE_PAYLOAD)
    assert result["approved"] is True
    assert result["stop_loss"] is not None
    assert result["take_profit"] is not None
    assert result["rr_ratio"] >= 1.5


def test_analyzer_rejects_low_probability():
    analyzer = SignalAnalyzer()
    result = analyzer.analyze({**SAMPLE_PAYLOAD, "probability": 40})
    assert result["approved"] is False
    assert "probability" in result["rejection_reason"].lower()
