# Live TradingView → Gold Trading Assistant Setup

This project can be run as a live **signal-analysis and notification service** for XAUUSD.
It does **not** place broker orders.

## 1. Run the API

Install dependencies:

```bash
pip install -r requirements.txt
```

Start FastAPI:

```bash
uvicorn gold_trading_backend.main:app --host 0.0.0.0 --port 8000
```

Verify:

```bash
curl http://localhost:8000/healthz
curl http://localhost:8000/status
```

## 2. Configure Telegram

Create a Telegram bot and set:

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

Do not commit these values.

## 3. Protect the webhook

For a public deployment, set a strong random value:

```env
WEBHOOK_SECRET=replace_with_a_long_random_secret
```

The API then requires:

```text
X-Webhook-Secret: <your secret>
```

Do not expose the secret in screenshots or source code.

## 4. Connect TradingView

Create a TradingView alert from the Pine Script that produces the market observations used by this backend.

Set the webhook URL to:

```text
https://YOUR_PUBLIC_HOST/webhook
```

If your TradingView setup supports a custom header, send:

```text
X-Webhook-Secret: <your secret>
```

The alert body should contain the `WebhookPayload` fields that your Pine Script actually computes.

Example:

```json
{
  "symbol": "XAUUSD",
  "timeframe": "15m",
  "action": "BUY",
  "price": 4388.50,
  "position_size": 0.01,
  "strategy_rank": "TOP",
  "htf_bias": "BULLISH",
  "htf_alignment": true,
  "price_zone": "DISCOUNT",
  "bos": true,
  "choch": false,
  "liquidity_sweep": true,
  "order_block": true,
  "fvg_imbalance": true,
  "inducements": false,
  "displacement": true,
  "sweep_confirmed": true,
  "liquidity_approaching": true,
  "news_clear": true,
  "news_reason": "No restricted news window.",
  "timestamp": "2026-08-12T06:00:00Z"
}
```

Do not invent values in production. Every market field should come from the actual TradingView/Pine logic or a trusted external data integration.

## 5. Smoke test the deployment

The repository includes:

```bash
python scripts/send_test_signal.py https://YOUR_PUBLIC_HOST YOUR_WEBHOOK_SECRET
```

The script:

1. Checks `/healthz`.
2. Sends a deterministic XAUUSD payload to `/webhook`.
3. Prints the HTTP result.

This verifies connectivity, authentication and webhook acceptance without placing any broker order.

## 6. What happens after a real signal arrives?

```text
TradingView
    ↓
POST /webhook
    ↓
Payload validation
    ↓
Market memory
    ↓
Session detection
    ↓
Bias
    ↓
Market structure
    ↓
Liquidity
    ↓
SMC strategy
    ↓
Entry model
    ↓
Risk / SL / TP / R:R
    ↓
News decision
    ↓
Scoring
    ↓
Trade validation
    ↓
Telegram alert
    ↓
Performance tracking
```

## 7. Live deployment requirements

You need a public HTTPS endpoint. Railway, Render, Fly.io, or another Python hosting service can provide this.

Required environment variables:

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
WEBHOOK_SECRET=...
NEWS_FILTER_ENABLED=true
```

## 8. Important limitation

The current news filter validates a news decision supplied by the upstream signal. The backend does not independently obtain an economic calendar by itself. For a real production setup, feed the actual calendar decision into `news_clear` / `news_reason` or add a trusted calendar integration before relying on the news filter.

## 9. Trading safety

This service is a decision-support and notification system. It should be validated on a demo account before any live trading use. A passed webhook and Telegram alert only prove that the software path works; they do not prove that the trading strategy is profitable.
