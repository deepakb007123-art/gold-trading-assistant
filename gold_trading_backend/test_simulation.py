import asyncio

from .main import process_signal
from .models.signal import WebhookPayload


def test_signal_simulation_smoke():
    payload = WebhookPayload(
        symbol="XAUUSD",
        timeframe="15m",
        action="BUY",
        price=4415.20,
        strategy_rank="TOP",
        htf_bias="BULLISH",
        htf_alignment=True,
        price_zone="DISCOUNT",
        choch=True,
        liquidity_sweep=True,
        order_block=True,
        fvg_imbalance=True,
        displacement=True,
        sweep_confirmed=True,
        news_clear=True,
        pdh=4430.0,
    )

    result = asyncio.run(process_signal(payload))
    assert "approved" in result
