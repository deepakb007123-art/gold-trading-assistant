import httpx
from models.signal import TradeAnalysis
from core.config import settings
from core.logger import logger


MAX_MESSAGE_LENGTH = 4000  # safe buffer


class TelegramBot:

    def __init__(self):
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}/sendMessage"

    # ✅ SAFE TEXT (prevent HTML crash)
    def _safe(self, text):
        return str(text).replace("<", "").replace(">", "")

    # ✅ TRIM MESSAGE
    def _trim(self, text: str) -> str:
        if len(text) > MAX_MESSAGE_LENGTH:
            return text[:MAX_MESSAGE_LENGTH] + "\n\n... (trimmed)"
        return text

    # ✅ RETRY SYSTEM
    async def _send(self, payload: dict) -> bool:
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    res = await client.post(self.base_url, json=payload)

                    if res.status_code == 200:
                        logger.info("✅ Telegram sent")
                        return True
                    else:
                        logger.error(f"Telegram error: {res.text}")

            except Exception as e:
                logger.error(f"Attempt {attempt+1} failed: {e}")

        return False

    # 🚀 MAIN ALERT
    async def send_alert(self, analysis: TradeAnalysis) -> bool:

        if not self.token or not self.chat_id:
            logger.warning("Telegram not configured")
            return False

        if analysis.trade_quality == "LOW":
            return False

        try:
            # SYSTEM STATE
            system_state = getattr(analysis, "system_state", "NORMAL")
            equity_state = getattr(analysis, "equity_state", "NORMAL")

            header = "🧠 <b>SYSTEM: NORMAL</b>\n\n"
            if system_state == "SAFE MODE":
                header = "🚨 <b>SAFE MODE ACTIVE</b>\n\n"
            elif equity_state in ["DEFENSIVE", "CRITICAL"]:
                header = f"🛡️ <b>{equity_state}</b>\n\n"

            # QUALITY
            quality_map = {
                "HIGH": "🔥 HIGH CONFIDENCE",
                "MEDIUM": "⚠️ MEDIUM SETUP",
                "EARLY": "⚡ EARLY ENTRY"
            }

            quality = analysis.trade_quality
            quality_text = quality_map.get(quality, "UNKNOWN")

            direction = "📈" if analysis.action == "BUY" else "📉"

            msg = header
            msg += f"{quality_text}\n\n"
            msg += f"{direction} <b>{analysis.action} {analysis.symbol}</b>\n\n"

            msg += f"<b>Entry:</b> <code>{analysis.entry_price}</code>\n"
            msg += f"<b>SL:</b> <code>{analysis.sl_price}</code>\n"
            msg += f"<b>TP1:</b> <code>{analysis.tp_price}</code>\n"

            if getattr(analysis, "tp2_price", None):
                msg += f"<b>TP2:</b> <code>{analysis.tp2_price}</code>\n"

            msg += f"<b>RR:</b> <code>{analysis.rr_ratio}R</code>\n\n"

            msg += f"<b>Score:</b> {analysis.confidence_score}%\n"
            msg += f"<b>Session:</b> {analysis.session}\n\n"

            # REASONS (SAFE)
            msg += "<b>Reason:</b>\n"
            for r in analysis.reasoning[:10]:  # limit reasons
                msg += f"• {self._safe(r)}\n"

            # TRIM MESSAGE
            msg = self._trim(msg)

            payload = {
                "chat_id": self.chat_id,
                "text": msg,
                "parse_mode": "HTML"
            }

            sent = await self._send(payload)

            # 🔁 FALLBACK MESSAGE
            if not sent:
                fallback = f"⚠️ {analysis.action} {analysis.symbol}\nEntry: {analysis.entry_price}"
                await self._send({
                    "chat_id": self.chat_id,
                    "text": fallback
                })

            return sent

        except Exception as e:
            logger.error(f"Telegram critical error: {e}")
            return False

    # 📊 PERFORMANCE REPORT
    async def send_performance_report(self, metrics: dict) -> bool:

        try:
            msg = "📊 PERFORMANCE REPORT\n\n"
            msg += f"Trades: {metrics.get('total_signals', 0)}\n"
            msg += f"Winrate: {metrics.get('win_rate', 0)}%\n"

            payload = {
                "chat_id": self.chat_id,
                "text": msg
            }

            return await self._send(payload)

        except Exception as e:
            logger.error(e)
            return False


telegram_bot = TelegramBot()
