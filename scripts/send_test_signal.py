"""Send a deterministic XAUUSD payload to a running Gold Trading Assistant.

Usage:
    python scripts/send_test_signal.py http://localhost:8000 YOUR_SECRET

This is a connectivity/validation smoke test. It does not place broker orders.
"""

import json
import sys
from datetime import datetime, timezone

import requests


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python scripts/send_test_signal.py BASE_URL [WEBHOOK_SECRET]")
        return 2

    base_url = sys.argv[1].rstrip("/")
    secret = sys.argv[2] if len(sys.argv) > 2 else ""

    payload = {
        "symbol": "XAUUSD",
        "timeframe": "15m",
        "action": "BUY",
        "price": 4388.50,
        "position_size": 0.01,
        "strategy_rank": "TOP",
        "htf_bias": "BULLISH",
        "htf_alignment": True,
        "price_zone": "DISCOUNT",
        "bos": True,
        "choch": False,
        "liquidity_sweep": True,
        "order_block": True,
        "fvg_imbalance": True,
        "inducements": False,
        "displacement": True,
        "sweep_confirmed": True,
        "liquidity_approaching": True,
        "news_clear": True,
        "news_reason": "Smoke-test payload: no restricted news window supplied.",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    headers = {"Content-Type": "application/json"}
    if secret:
        headers["X-Webhook-Secret"] = secret

    print("Checking health...")
    health = requests.get(f"{base_url}/healthz", timeout=10)
    health.raise_for_status()
    print(json.dumps(health.json(), indent=2))

    print("Sending smoke-test signal...")
    response = requests.post(
        f"{base_url}/webhook",
        json=payload,
        headers=headers,
        timeout=10,
    )
    print(f"HTTP {response.status_code}")
    print(response.text)
    response.raise_for_status()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
