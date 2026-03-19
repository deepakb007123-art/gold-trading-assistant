import httpx
import asyncio
from models.signal import TradeAnalysis
from core.config import settings
from core.logger import logger

class TelegramBot:
    """
    Handles formatting and sending signals to Telegram.
    Uses professional formatting with SMC reasoning.
    """
    
    def __init__(self):
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.chat_id = settings.TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.token}/sendMessage"

    def format_message(self, analysis: TradeAnalysis) -> str:
        """
        Formats the trade analysis into a professional, readable Telegram alert.
        """
        direction_emoji = "📈" if analysis.action == "BUY" else "📉"
        action = analysis.action
        symbol = analysis.symbol
        conf = analysis.confidence_score
        
        msg = f"{direction_emoji} *{action} {symbol}* | Confidence *{conf}%*\n\n"
        
        msg += f"Entry: `{analysis.entry_price}`\n"
        msg += f"SL: `{analysis.sl_price}`\n"
        msg += f"TP: `{analysis.tp_price}`\n"
        msg += f"RR: `{analysis.rr_ratio}R`\n\n"
        
        msg += f"Session: `{analysis.session}`\n"
        
        strategies = " + ".join(analysis.strategies_used) if analysis.strategies_used else "Market Structure"
        msg += f"Strategy: `{strategies}`\n\n"
        
        msg += "*Reason:*\n"
        for reason in analysis.reasoning:
            msg += f"• {reason}\n"
            
        return msg

    async def send_alert(self, analysis: TradeAnalysis) -> bool:
        """Constructs and sends an HTML formatted Telegram alert based on validated analysis."""
        if not self.token or not self.chat_id:
            logger.warning("Telegram credentials not configured. Skipping alert.")
            return False
            
        # 1. System State Inference
        system_state = getattr(analysis, "system_state", "NORMAL")
        equity_state = getattr(analysis, "equity_state", "NORMAL")
        drawdown_pct = getattr(analysis, "drawdown_pct", 0.0)
        
        state_header = "🧠 <b>SYSTEM STATE: NORMAL</b>\n\n"
        if system_state == "SAFE MODE":
            state_header = "🚨 <b>SYSTEM STATE: SAFE MODE</b> (Restrictive Filters Active)\n\n"
        elif equity_state in ["DEFENSIVE", "CRITICAL"]:
            state_header = f"🛡️ <b>SYSTEM STATE: {equity_state}</b> (Drawdown: {drawdown_pct}%)\n\n"
        elif system_state == "CAUTION" or equity_state == "CAUTION":
            state_header = "⚠️ <b>SYSTEM STATE: CAUTION</b> (Elevated Risk Detected)\n\n"

        # 2. Telegram Notification Filtering
        if analysis.trade_quality == "LOW":
            logger.warning("Telegram Bot blocked LOW quality signal entirely.")
            return False

        conf_category: str = analysis.trade_quality
        
        html_msg: str = str(state_header)
        
        # 1. Telegram Intelligence Upgrade: Dynamic Emojis/Warnings
        if conf_category == "HIGH":
            html_msg += "🔥 <b>HIGH CONFIDENCE SETUP</b>\n\n"
        elif conf_category == "MEDIUM":
            html_msg += "⚠️ <b>MEDIUM SETUP (Partial Confluence / High Volatility)</b>\n\n"
        elif conf_category == "EARLY":
            html_msg += "⚡ <b>EARLY ENTRY (High Risk / Pre-Structure Momentum)</b>\n\n"
            
        direction_emoji = "📈" if analysis.action == "BUY" else "📉"
        html_msg += f"{direction_emoji} <b>{analysis.action} {analysis.symbol}</b> | {conf_category} SCORE ({analysis.confidence_score}%)\n\n"
        
        html_msg += f"<b>Entry:</b> <code>{analysis.entry_price}</code>\n"
        html_msg += f"<b>SL:</b> <code>{analysis.sl_price}</code>\n"
        html_msg += f"<b>TP1:</b> <code>{analysis.tp_price}</code>\n"
        if getattr(analysis, "tp2_price", None):
            html_msg += f"<b>TP2:</b> <code>{analysis.tp2_price}</code>\n"
        html_msg += f"<b>RR:</b> <code>{analysis.rr_ratio}R</code>\n\n"
        
        html_msg += f"<b>Position:</b> {analysis.position_size}x ({analysis.risk_level} Risk)\n"
        html_msg += f"<b>Trade Quality:</b> {analysis.trade_quality}\n"
        if getattr(analysis, "strategy_rank", "UNKNOWN") != "UNKNOWN":
            html_msg += f"🧠 <b>Strategy Rank:</b> {analysis.strategy_rank}\n"
        html_msg += f"<b>Context:</b> {analysis.bias} Bias ({analysis.price_zone})\n"
        html_msg += f"<b>Session:</b> <code>{analysis.session}</code>\n"
        strategies = " + ".join(analysis.strategies_used) if analysis.strategies_used else "Market Structure"
        html_msg += f"<b>Strategy:</b> <code>{strategies}</code>\n\n"
        
        html_msg += "<b>Reason:</b>\n"
        for reason in analysis.reasoning:
            html_msg += f"• {reason}\n"
            
        if getattr(analysis, "decision_trace", None):
            trace = analysis.decision_trace
            score_comp = trace.get("score_components", {})
            html_msg += f"\n🧠 <b>Decision Breakdown:</b>\n"
            html_msg += f"Base: {score_comp.get('base', 0)}\n"
            if score_comp.get('strategy'): html_msg += f"Strategy: {score_comp.get('strategy'):+d}\n"
            if score_comp.get('session'): html_msg += f"Session: {score_comp.get('session'):+d}\n"
            if score_comp.get('confluence'): html_msg += f"Confluence: {score_comp.get('confluence'):+d}\n"
            if score_comp.get('drawdown'): html_msg += f"Drawdown: {score_comp.get('drawdown'):+d}\n"
            if score_comp.get('safe_mode'): html_msg += f"Safe Mode: {score_comp.get('safe_mode'):+d}\n"
            html_msg += f"Final Score: {analysis.confidence_score}\n"
            
        payload = {
            "chat_id": self.chat_id,
            "text": html_msg,
            "parse_mode": "HTML"
        }
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(self.base_url, json=payload)
                response.raise_for_status()
                logger.info("Successfully sent Telegram alert.")
                return True
        except Exception as e:
            logger.error(f"Failed to send Telegram alert: {e}")
            return False

    async def send_performance_report(self, metrics: dict) -> bool:
        """Sends an adaptive performance overview to the Telegram chat."""
        if not self.token or not self.chat_id:
            logger.warning("Telegram credentials not configured. Skipping performance report.")
            return False
            
        try:
            total = metrics.get('total_signals', 0)
            win_rate = metrics.get('win_rate', 0)
            
            html_msg = str(f"📊 <b>DAILY PERFORMANCE (V7 Equity Curve)</b>\n\n")
            html_msg += str(f"<b>Total Closed Signals:</b> {total}\n")
            html_msg += str(f"<b>Global Win Rate:</b> {win_rate}%\n")
            html_msg += str(f"<b>Equity:</b> {metrics.get('current_equity', 100.0)}R (Peak: {metrics.get('peak_equity', 100.0)}R)\n")
            html_msg += str(f"<b>Drawdown:</b> {metrics.get('drawdown_pct', 0.0)}% ({metrics.get('equity_state', 'NORMAL')})\n\n")
            
            q_metrics = metrics.get("quality_metrics", {})
            for q_tier in ["HIGH", "MEDIUM", "EARLY"]:
                data = q_metrics.get(q_tier, {})
                t = data.get("total", 0)
                w = data.get("wins", 0)
                if t > 0:
                    html_msg += str(f"• <b>{q_tier}:</b> {t} Trades → {w} Wins ({round((w/t)*100)}%)\n")
            
            html_msg += str(f"\n<i>The system is using this data to map session penalties and boost adaptive strictness modifiers automatically.</i>")
            
            payload = {
                "chat_id": self.chat_id,
                "text": html_msg,
                "parse_mode": "HTML"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(self.base_url, json=payload)
                response.raise_for_status()
                logger.info(f"Performance report sent successfully to Telegram")
                
            return True
        except Exception as e:
            logger.error(f"Failed to send performance report: {e}")
            return False

telegram_bot = TelegramBot()
