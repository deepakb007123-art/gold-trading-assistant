# 🥇 Gold Trading Signal Assistant

A **production-ready FastAPI backend** that receives TradingView webhook alerts for XAUUSD, runs them through a multi-step analysis pipeline, and sends formatted Telegram notifications.

> ⚠️ **This system does NOT execute trades.** It is a signal analysis and notification tool only.

---

## Features

| Feature | Details |
|---------|---------|
| **Webhook receiver** | Accepts TradingView POST alerts |
| **7-step pipeline** | Probability → Market state → Strategy → News filter → Liquidity → R:R → Approval |
| **Telegram alerts** | Formatted Markdown messages with entry / SL / TP |
| **Signal logging** | Persistent JSONL log + in-memory ring buffer |
| **Health endpoints** | `/healthz` and `/status` for uptime monitoring |
| **Railway-ready** | Dockerfile + Procfile pre-configured |

---

## Repository Structure

```
gold-trading-assistant/
├── Dockerfile
├── Procfile
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
├── logs/
├── tests/
│   └── test_main.py
└── gold_trading_backend/
    ├── __init__.py
    ├── app/
    │   ├── __init__.py
    │   └── main.py            ← FastAPI routes
    └── server/
        ├── __init__.py
        ├── analyzer.py         ← Pipeline orchestrator
        ├── liquidity_predictor.py
        ├── news_filter.py
        ├── strategy_engine.py
        ├── logger.py
        └── telegram_bot.py
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/healthz` | Liveness probe |
| `GET` | `/status` | Module status |
| `GET` | `/logs?limit=50` | Recent signal logs |
| `POST` | `/webhook` | Receive TradingView alert |

### POST /webhook — Payload Schema

```json
{
  "symbol":      "XAUUSD",
  "signal":      "BREAKOUT_BUY",
  "price":       2345.20,
  "probability": 82,
  "strategy":    "breakout",
  "session":     "london"
}
```

Valid `signal` values (determines BUY/SELL direction): any string containing `BUY` or `SELL`.

Valid `session` values: `london`, `newyork`, `overlap`, `asian`

Valid `strategy` values: `breakout`, `trend`, `reversal`, `scalp`, `range`, `momentum`

### Example Telegram Alert

```
🚨 GOLD SIGNAL — XAUUSD
━━━━━━━━━━━━━━━━━━━━
🟢 Direction: BUY
📍 Entry:       2345.20
🛑 Stop Loss:   2340.20
🎯 Take Profit: 2355.20
📊 Probability: 82%
⚖️ R:R Ratio:   2.0
🔧 Strategy:    BREAKOUT
🕐 Session:     LONDON
━━━━━━━━━━━━━━━━━━━━
⚠️ Analysis only — no trade executed.
```

---

## Signal Analysis Pipeline

```
Incoming Webhook
      │
      ▼
1. Probability ≥ 70%?          → REJECT if not
      │
      ▼
2. Market state valid?          → REJECT if not (scalping/unknown blocked)
      │
      ▼
3. Strategy × session aligned?  → REJECT if not
      │
      ▼
4. No high-impact news?         → REJECT if news event within 30 min
      │
      ▼
5. Calculate Entry / SL / TP
      │
      ▼
6. R:R ratio ≥ 1.5?             → REJECT if not
      │
      ▼
7. APPROVED → Send Telegram alert
```

---

## Local Development

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/gold-trading-assistant.git
cd gold-trading-assistant
```

### 2. Create virtual environment

```bash
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
# .venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment

```bash
cp .env.example .env
# Edit .env and fill in TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
```

### 5. Run the server

```bash
uvicorn gold_trading_backend.app.main:app --reload --port 8000
```

Open http://localhost:8000/healthz to verify it's running.

### 6. Run tests

```bash
pip install pytest httpx
pytest tests/ -v
```

---

## Railway Deployment

### Step 1 — Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit — Gold Trading Signal Assistant"
git remote add origin https://github.com/YOUR_USERNAME/gold-trading-assistant.git
git push -u origin main
```

### Step 2 — Create Railway project

1. Go to [railway.app](https://railway.app) and log in.
2. Click **New Project** → **Deploy from GitHub repo**.
3. Select your `gold-trading-assistant` repository.
4. Railway will auto-detect the `Dockerfile`.

### Step 3 — Set environment variables

In Railway dashboard → your service → **Variables**, add:

| Variable | Value |
|----------|-------|
| `TELEGRAM_BOT_TOKEN` | Your bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Your chat/channel ID |
| `NEWS_FILTER_ENABLED` | `true` |
| `NEWS_BLACKOUT_MINUTES` | `30` |

> Railway automatically sets `PORT`. The Dockerfile uses `${PORT:-8000}` so no changes needed.

### Step 4 — Generate a public URL

In Railway dashboard → your service → **Settings** → **Networking** → click **Generate Domain**.

Your webhook URL will be: `https://YOUR-APP.railway.app/webhook`

### Step 5 — Health check (optional but recommended)

In Railway → **Settings** → **Health Check Path**, enter `/healthz`.

---

## TradingView Webhook Setup

### Step 1 — Create an alert in TradingView

1. Open your XAUUSD chart.
2. Click the **Alerts** clock icon → **Create Alert**.
3. Set your trigger condition (e.g. EMA crossover, RSI level, custom Pine Script).

### Step 2 — Configure the webhook

In the **Notifications** tab of the alert dialog:
- ✅ Enable **Webhook URL**
- Enter: `https://YOUR-APP.railway.app/webhook`

### Step 3 — Set the alert message (JSON body)

Paste this into the **Message** field (TradingView will POST this as the request body):

```json
{
  "symbol":      "{{ticker}}",
  "signal":      "BREAKOUT_BUY",
  "price":       {{close}},
  "probability": 82,
  "strategy":    "breakout",
  "session":     "london"
}
```

> TradingView supports dynamic placeholders: `{{ticker}}`, `{{close}}`, `{{time}}`, etc.
> Adjust `signal`, `probability`, `strategy`, and `session` to match your alert's context.

### Step 4 — Save and test

After saving the alert, you can send a test ping from TradingView.
Check Railway logs to confirm the signal was received and processed.

---

## Telegram Bot Setup

1. Message `@BotFather` on Telegram → `/newbot` → follow prompts → copy the **token**.
2. Add your bot to your target channel/group and make it an **admin**.
3. Get your **chat ID**:
   - For a private chat: message `@userinfobot`.
   - For a channel: use `https://api.telegram.org/bot<TOKEN>/getUpdates` after sending a message.
4. Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` in Railway variables.

---

## Strategy × Session Rules

| Strategy | Allowed Sessions |
|----------|-----------------|
| `breakout` | london, newyork, overlap |
| `trend` | london, newyork, overlap, asian |
| `reversal` | london, newyork |
| `scalp` | overlap only |
| `range` | asian only |
| `momentum` | london, newyork, overlap |

---

## Configuration Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `TELEGRAM_BOT_TOKEN` | — | Required for alerts |
| `TELEGRAM_CHAT_ID` | — | Required for alerts |
| `NEWS_FILTER_ENABLED` | `true` | Set `false` to bypass news filter |
| `NEWS_BLACKOUT_MINUTES` | `30` | Minutes around news events to suppress |
| `LOG_DIR` | `logs` | Directory for JSONL signal logs |
| `LOG_MAX_MEMORY` | `500` | Max signals held in memory |
| `PORT` | `8000` | Set automatically by Railway |

---

## License

MIT
