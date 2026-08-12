import httpx

from ..core.config import settings
from ..core.logger import logger
from ..models.signal import TradeAnalysis


MAX_MESSAGE_LENGTH = 4000


class TelegramBot:
    def __init__(self):
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}/sendMessage"

    @staticmethod
    def _safe(text) -> str:
        return str(text).replace("<", "").replace(">", "")

    @staticmethod
    def _trim(text: str) -> str:
        return text if len(text) <= MAX_MESSAGE_LENGTH else text[:MAX_MESSAGE_LENGTH] + "\n\n... (trimmed)"

    async def _send(self, payload: dict) -> bool:
        if not self.token or not self.chat_id:
            logger.warning("Telegram not configured")
            return False

        for attempt in range(3):
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.post(self.base_url, json=payload)
                if response.status_code == 200:
                    return True
                logger.error("Telegram error %s: %s", response.status_code, response.text)
            except Exception as exc:
                logger.error("Telegram attempt %s failed: %s", attempt + 1, exc)
        return False

    async def send_message(self, text: str) -> bool:
        return await self._send({"chat_id": self.chat_id, "text": self._trim(self._safe(text))})

    async def send_alert(self, analysis: TradeAnalysis) -> bool:
        if analysis.trade_quality == "LOW":
            return False

        system_state = analysis.system_state
        equity_state = analysis.equity_state
        header = "🧠 SYSTEM: NORMAL"
        if system_state == "SAFE MODE":
            header = "🚨 SAFE MODE ACTIVE"
        elif equity_state in {"DEFENSIVE", "CRITICAL"}:
            header = f"🛡️ {equity_state}"

        quality_map = {
            "HIGH": "🔥 HIGH CONFIDENCE",
            "MEDIUM": "⚠️ MEDIUM SETUP",
            "EARLY": "⚡ EARLY ENTRY",
        }

        direction = "📈" if analysis.action == "BUY" else "📉"
        lines = [
            header,
            quality_map.get(analysis.trade_quality, "UNKNOWN"),
            "",
            f"{direction} {analysis.action} {analysis.symbol}",
            f"Entry: {analysis.entry_price}",
            f"SL: {analysis.sl_price}",
            f"TP1: {analysis.tp_price}",
            f"RR: {analysis.rr_ratio}R",
            f"Score: {analysis.confidence_score}%",
            f"Quality: {analysis.trade_quality}",
            f"Session: {analysis.session}",
            f"Bias: {analysis.bias}",
            "",
            "Reason:",
        ]
        lines.extend(f"• {self._safe(reason)}" for reason in analysis.reasoning[:8])
        message = self._trim("\n".join(lines))
        return await self._send({"chat_id": self.chat_id, "text": message})

    async def send_performance_report(self, metrics: dict) -> bool:
        text = (
            "📊 PERFORMANCE REPORT\n\n"
            f"Signals: {metrics.get('total_signals', 0)}\n"
            f"Win rate: {metrics.get('win_rate', 0)}%\n"
            f"System state: {metrics.get('system_state', 'NORMAL')}"
        )
        return await self.send_message(text)


telegram_bot = TelegramBot()
