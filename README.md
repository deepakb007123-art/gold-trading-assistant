# 🥇 Gold Trading Assistant

[![CI](https://github.com/deepakb007123-art/gold-trading-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/deepakb007123-art/gold-trading-assistant/actions/workflows/ci.yml)

A modular **XAUUSD (Gold) signal-analysis and decision-support backend** built with Python and FastAPI.

The system receives structured market signals through a webhook, enriches them with market context, evaluates SMC-style conditions, applies session/news/risk filters, scores the setup, validates the trade, and sends an analysis notification through Telegram.

> ⚠️ **Important:** This project is a signal-analysis and notification system. It does **not** directly place broker orders.

## 🎯 Project Objective

Instead of forwarding every TradingView alert, the backend attempts to turn an incoming signal into a structured, explainable decision.

```text
TradingView / Upstream Signal
            ↓
      Webhook Validation
            ↓
       Market Memory
            ↓
       Bias + Structure
            ↓
        Liquidity Map
            ↓
       SMC Strategy
            ↓
        Entry Engine
            ↓
      Risk / SL / TP / RR
            ↓
        News Decision
            ↓
      Scoring + Decision
            ↓
        Final Validation
            ↓
      Telegram Notification
            ↓
      Performance Tracking
```

## ✨ Core Features

| Module | Purpose |
|---|---|
| **FastAPI Webhook** | Receives validated trading signals through `POST /webhook` |
| **Webhook Authentication** | Optional `X-Webhook-Secret` protection for a public deployment |
| **Market Memory** | Maintains previous-day high/low context |
| **Bias Engine** | Evaluates higher-timeframe directional context |
| **Market Structure** | Tracks BOS/CHoCH and HTF/LTF alignment |
| **Liquidity Map** | Builds directional PDH/PDL, EQH/EQL and internal liquidity targets |
| **SMC Strategy Engine** | Tracks liquidity sweep, OB, FVG, inducement and displacement conditions |
| **Entry Engine** | Selects a sniper/confirmation/market entry candidate |
| **Risk Manager** | Calculates structural/volatility-aware SL, TP, TP2 and R:R |
| **News Filter** | Applies an upstream news decision without inventing calendar events |
| **Scoring Engine** | Combines structure, liquidity, strategy, confluence and session evidence |
| **Decision Engine** | Bounds scores and produces an explainable decision trace |
| **Performance Tracker** | Records accepted signals and derives basic adaptive telemetry |
| **Telegram Service** | Sends approved signals and rejection/error notifications |
| **Health Endpoints** | `/health`, `/healthz`, `/status` |
| **Smoke Test** | Deterministic script verifies public webhook connectivity without broker execution |

## 🧠 Decision Logic

The current processing path is:

1. Validate the webhook payload and optional shared secret.
2. Update market memory and enrich the signal with previous-day levels.
3. Determine the active trading session.
4. Apply a cooldown between signals.
5. Detect HTF bias and price zone.
6. Analyse BOS/CHoCH and HTF alignment.
7. Map directional liquidity.
8. Evaluate SMC conditions supplied by the upstream signal.
9. Select an entry model.
10. Calculate SL/TP/TP2 and R:R around the actual entry.
11. Apply the configured news decision.
12. Generate bounded score components.
13. Determine a quality tier: `HIGH`, `MEDIUM`, `EARLY`, or `LOW`.
14. Validate the final analysis.
15. Send the result to Telegram.
16. Register accepted signals for performance tracking.

The system intentionally avoids random pattern generation. Market-state fields are expected to come from the upstream TradingView/Pine signal or another trusted market-data layer.

## 📦 Repository Structure

```text
gold-trading-assistant/
├── .github/
│   └── workflows/
│       └── ci.yml
├── Dockerfile
├── Procfile
├── README.md
├── requirements.txt
├── .env.example
├── .gitignore
├── scripts/
│   └── send_test_signal.py
├── docs/
│   ├── ARCHITECTURE.md
│   └── LIVE_TRADING_SETUP.md
├── tests/
│   └── test_main.py
└── gold_trading_backend/
    ├── __init__.py
    ├── main.py
    ├── test_simulation.py
    ├── core/
    │   ├── config.py
    │   ├── decision_engine.py
    │   └── logger.py
    ├── models/
    │   └── signal.py
    ├── services/
    │   ├── news_filter.py
    │   └── telegram_bot.py
    ├── tools/
    │   └── simulate_equity.py
    └── trading/
        ├── Entry_engine.py
        ├── bias_engine.py
        ├── liquidity_map.py
        ├── market_memory.py
        ├── market_structure.py
        ├── performance_tracker.py
        ├── position_manager.py
        ├── risk_manager.py
        ├── scoring_engine.py
        ├── session_manager.py
        └── strategy_engine.py
```

## 🔌 API

### `POST /webhook`

The current payload model accepts structured market context. Example:

```json
{
  "symbol": "XAUUSD",
  "timeframe": "15m",
  "action": "BUY",
  "price": 4415.20,
  "drawdown_pct": 0.0,
  "strategy_rank": "TOP",
  "position_size": 1.0,
  "htf_bias": "BULLISH",
  "htf_alignment": true,
  "price_zone": "DISCOUNT",
  "bos": false,
  "choch": true,
  "liquidity_sweep": true,
  "order_block": true,
  "fvg_imbalance": true,
  "inducements": false,
  "displacement": true,
  "sweep_confirmed": true,
  "pdh": 4430.0,
  "eqh": 4428.0,
  "news_clear": true,
  "timestamp": "2026-08-12T08:00:00Z"
}
```

### Required fields

- `symbol`
- `timeframe`
- `action` (`BUY` or `SELL`)
- `price`

### Market-context fields

The following can be supplied by the TradingView/Pine layer when available:

- `htf_bias`
- `htf_alignment`
- `price_zone`
- `bos`
- `choch`
- `liquidity_sweep`
- `order_block`
- `fvg_imbalance`
- `inducements`
- `displacement`
- `sweep_confirmed`
- `liquidity_approaching`
- `pdh`, `pdl`, `eqh`, `eql`, `sweep_level`

### Risk fields

- `tv_sl`
- `tv_tp`
- `position_size`
- `drawdown_pct`

### News fields

- `news_clear`
- `news_reason`

The backend does not fabricate economic-calendar events. An upstream calendar/data service can provide the news decision through these fields.

### Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Basic health response |
| `GET` | `/healthz` | Liveness check |
| `GET` | `/status` | Module status |
| `POST` | `/webhook` | Signal ingestion |

If `WEBHOOK_SECRET` is configured, `/webhook` also requires the `X-Webhook-Secret` header.

## 📡 Live TradingView Integration

The project is ready to be used as a **live signal-analysis service** once the FastAPI application is deployed to a public HTTPS URL.

```text
TradingView Alert
       ↓ HTTPS POST
https://YOUR-DOMAIN/webhook
       ↓
FastAPI
       ↓
Analysis Pipeline
       ↓
Telegram Alert
```

### Production setup

Configure:

```env
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
WEBHOOK_SECRET=...
NEWS_FILTER_ENABLED=true
```

Then deploy the FastAPI application using the included `Dockerfile`/`Procfile` and set the TradingView webhook URL to:

```text
https://YOUR-DOMAIN/webhook
```

Send the same shared secret as:

```text
X-Webhook-Secret: <your secret>
```

The complete deployment procedure is documented in [`docs/LIVE_TRADING_SETUP.md`](docs/LIVE_TRADING_SETUP.md).

### Smoke test

The repository includes a deterministic connectivity test:

```bash
python scripts/send_test_signal.py https://YOUR-DOMAIN YOUR_WEBHOOK_SECRET
```

It checks `/healthz`, sends a known payload to `/webhook`, and verifies the HTTP response. It **does not place broker trades**.

### TradingView payload rule

Do not invent market fields in production. `htf_bias`, BOS, CHoCH, liquidity, OB, FVG, displacement and news fields should come from the actual Pine Script/upstream data provider or a trusted market-data integration.

## 📲 Telegram Output

Approved signals contain information such as:

```text
BUY XAUUSD
Entry
SL
TP1
RR
Score
Quality
Session
Bias
Reasoning
```

Rejected signals can include the exact reason, for example:

```text
Cooldown active
Opposite BOS
Unconfirmed breakout / no valid entry
Invalid R:R
Low trade quality
HTF/LTF disagreement
News restriction
```

## 🛡️ Trade Validation

The final validation layer currently requires:

- News decision is clear.
- Trade quality is not `LOW`.
- R:R is at least `1.5`.
- HTF and LTF direction are aligned.
- BUY stop loss is below entry and target above entry.
- SELL stop loss is above entry and target below entry.

These are decision-support filters, not guarantees of profitability.

## 🧪 Testing

The repository contains:

- Unit/smoke tests in `tests/test_main.py`
- A small process simulation in `gold_trading_backend/test_simulation.py`
- GitHub Actions CI in `.github/workflows/ci.yml`

Run locally:

```bash
pip install -r requirements.txt
pytest -q
```

## 🛠️ Local Development

### 1. Clone

```bash
git clone https://github.com/deepakb007123-art/gold-trading-assistant.git
cd gold-trading-assistant
```

### 2. Create a virtual environment

Windows:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Linux/macOS:

```bash
python -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
copy .env.example .env
```

Linux/macOS:

```bash
cp .env.example .env
```

Set Telegram credentials and other environment values in `.env`.

### 5. Run the API

```bash
uvicorn gold_trading_backend.main:app --reload --port 8000
```

Verify:

```text
http://localhost:8000/healthz
```

## 🚀 Docker / Deployment

The repository includes a Dockerfile and Procfile for cloud deployment.

Build locally:

```bash
docker build -t gold-trading-assistant .
```

Run locally:

```bash
docker run --rm -p 8000:8000 --env-file .env gold-trading-assistant
```

The application binds to `0.0.0.0` and honours the platform `PORT` environment variable.

A hosted deployment can expose:

```text
https://YOUR-DOMAIN/webhook
https://YOUR-DOMAIN/healthz
```

for TradingView delivery and service-health monitoring.

## 🔐 Security

Never commit secrets to GitHub.

Keep credentials such as:

```text
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
WEBHOOK_SECRET
```

inside environment variables or a local `.env` file excluded from Git.

Before publishing or sharing screenshots, verify that no bot tokens, passwords, broker credentials, private URLs or personal access tokens appear in the repository, logs or images.

## 📈 Future Work

- Connect to a real economic calendar/news source.
- Add OHLCV-backed structure/OB/FVG detection instead of relying on upstream flags.
- Add integration tests for the complete webhook pipeline.
- Add persistent database storage for signals and performance.
- Add dashboard integration.
- Add backtesting and historical evaluation.
- Add observability/metrics for production monitoring.

## ⚠️ Disclaimer

This project is for **educational, research and decision-support purposes**. It does not guarantee profitable trading and does not directly execute broker orders.

Financial markets involve substantial risk. Validate the system in controlled environments and apply appropriate risk management before using market data for real decisions.

## 👨‍💻 Tech Stack

**Python · FastAPI · Pydantic · TradingView Webhooks · Telegram Bot API · Docker · GitHub Actions · Modular trading-analysis engines**

## 📄 License

MIT
