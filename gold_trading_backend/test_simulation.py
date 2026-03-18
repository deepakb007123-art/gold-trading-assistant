import asyncio
from models.signal import WebhookPayload
from main import process_signal
import logging

logging.basicConfig(level=logging.INFO)

async def run_simulation():
    # 1. Provide a standard mock valid payload
    payload = WebhookPayload(
        symbol="XAUUSD",
        timeframe="15m",
        action="BUY",
        price=2000.50,
        drawdown_pct=0.0,
        strategy_rank="TOP"
    )

    print("--- STARTING SIMULATION ---")
    await process_signal(payload)
    print("--- SIMULATION FINISHED ---")

if __name__ == "__main__":
    asyncio.run(run_simulation())
