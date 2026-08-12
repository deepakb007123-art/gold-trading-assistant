import json
import os
import uuid
from datetime import datetime
from typing import Any, Dict, List

from ..core.logger import logger


class PerformanceTracker:
    def __init__(self, log_file: str = "performance_log.json"):
        self.log_file = log_file
        self.trades = self._load_trades()
        self.timeout_minutes = 240

    def _load_trades(self) -> List[Dict]:
        if not os.path.exists(self.log_file):
            return []
        try:
            with open(self.log_file, "r", encoding="utf-8") as file:
                data = json.load(file)
            return data if isinstance(data, list) else []
        except Exception as exc:
            logger.error("Failed to load performance log: %s", exc)
            return []

    def _save_trades(self):
        temp_file = f"{self.log_file}.tmp"
        try:
            with open(temp_file, "w", encoding="utf-8") as file:
                json.dump(self.trades, file, indent=2)
            os.replace(temp_file, self.log_file)
        except Exception as exc:
            logger.error("Failed to save performance log: %s", exc)
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass

    def register_trade(self, analysis) -> str:
        trade_id = str(uuid.uuid4())[:8]
        record = {
            "id": trade_id,
            "timestamp": datetime.utcnow().isoformat(),
            "action": analysis.action,
            "quality": analysis.trade_quality,
            "session": analysis.session.split("/")[0].strip(),
            "strategies": list(analysis.strategies_used),
            "entry": analysis.entry_price,
            "sl": analysis.sl_price,
            "tp1": analysis.tp_price,
            "tp2": analysis.tp2_price,
            "rr": analysis.rr_ratio,
            "status": "PENDING",
            "outcome": None,
            "close_time": None,
        }
        self.trades.append(record)
        self._save_trades()
        return trade_id

    def update_market_price(self, current_price: float) -> List[Dict]:
        now = datetime.utcnow()
        closed = []
        changed = False

        for trade in self.trades:
            if trade.get("status") != "PENDING":
                continue

            entry_time = datetime.fromisoformat(trade["timestamp"])
            if (now - entry_time).total_seconds() / 60 > self.timeout_minutes:
                trade["status"] = "CLOSED"
                trade["outcome"] = "TIMEOUT"
                trade["close_time"] = now.isoformat()
                closed.append(trade)
                changed = True
                continue

            is_buy = trade["action"] == "BUY"
            hit_sl = current_price <= trade["sl"] if is_buy else current_price >= trade["sl"]
            hit_tp1 = current_price >= trade["tp1"] if is_buy else current_price <= trade["tp1"]
            hit_tp2 = trade.get("tp2") is not None and (
                current_price >= trade["tp2"] if is_buy else current_price <= trade["tp2"]
            )

            if hit_sl:
                trade["status"] = "CLOSED"
                trade["outcome"] = "LOSS"
            elif hit_tp2 or hit_tp1:
                trade["status"] = "CLOSED"
                trade["outcome"] = "WIN"
            else:
                continue

            trade["close_time"] = now.isoformat()
            closed.append(trade)
            changed = True

        if changed:
            self._save_trades()
        return closed

    def get_metrics(self) -> Dict[str, Any]:
        closed = [t for t in self.trades if t.get("status") == "CLOSED"]
        if not closed:
            return {
                "total_signals": 0,
                "win_rate": 0.0,
                "quality_metrics": {},
                "session_metrics": {},
                "system_state": "NORMAL",
                "safe_mode_active": False,
                "current_equity": 100.0,
                "peak_equity": 100.0,
                "drawdown_pct": 0.0,
                "equity_state": "NORMAL",
                "consecutive_wins": 0,
            }

        ordered = sorted(closed, key=lambda x: x.get("close_time") or x.get("timestamp"))
        total = len(ordered)
        wins = sum(1 for t in ordered if t.get("outcome") == "WIN")

        consecutive_wins = 0
        consecutive_losses = 0
        state = "NORMAL"
        for trade in ordered:
            if trade.get("outcome") == "WIN":
                consecutive_wins += 1
                consecutive_losses = 0
            elif trade.get("outcome") == "LOSS":
                consecutive_losses += 1
                consecutive_wins = 0
            else:
                consecutive_wins = consecutive_losses = 0

            if consecutive_losses >= 5:
                state = "SAFE MODE"
            elif consecutive_losses >= 3:
                state = "CAUTION"

        equity = 100.0
        peak = 100.0
        for trade in ordered:
            if trade.get("outcome") == "WIN":
                equity += float(trade.get("rr", 2.0) or 2.0)
            elif trade.get("outcome") == "LOSS":
                equity -= 1.0
            peak = max(peak, equity)

        drawdown_pct = round(((peak - equity) / peak) * 100, 2) if peak else 0.0
        equity_state = "NORMAL" if drawdown_pct < 5 else "CAUTION" if drawdown_pct < 10 else "DEFENSIVE" if drawdown_pct < 15 else "CRITICAL"

        return {
            "total_signals": total,
            "win_rate": round((wins / total) * 100, 1),
            "quality_metrics": {},
            "session_metrics": {},
            "system_state": state,
            "safe_mode_active": state == "SAFE MODE",
            "current_equity": round(equity, 2),
            "peak_equity": round(peak, 2),
            "drawdown_pct": drawdown_pct,
            "equity_state": equity_state,
            "consecutive_wins": consecutive_wins,
        }

    def get_adaptive_modifiers(self) -> Dict:
        metrics = self.get_metrics()
        closed = sorted(
            [t for t in self.trades if t.get("status") == "CLOSED"],
            key=lambda x: x.get("close_time") or x.get("timestamp"),
        )

        modifiers = {
            "early_score_penalty": 0,
            "medium_strictness_boost": False,
            "asian_breakout_allowed": False,
            "safe_mode_active": metrics.get("safe_mode_active", False),
            "system_state": metrics.get("system_state", "NORMAL"),
            "strategy_ranks": {},
            "session_strategy_ranks": {},
        }

        # Strategy ranking requires a meaningful sample before affecting decisions.
        strategy_stats: Dict[str, Dict[str, int]] = {}
        for trade in closed:
            for strategy in trade.get("strategies", []):
                stats = strategy_stats.setdefault(strategy, {"total": 0, "wins": 0})
                stats["total"] += 1
                if trade.get("outcome") == "WIN":
                    stats["wins"] += 1

        for strategy, stats in strategy_stats.items():
            if stats["total"] < 15:
                continue
            win_rate = stats["wins"] / stats["total"]
            rank = "TOP" if win_rate >= 0.55 else "MID" if win_rate >= 0.40 else "LOW"
            modifiers["strategy_ranks"][strategy] = {
                "rank": rank,
                "wr": round(win_rate * 100, 1),
                "total": stats["total"],
            }

        return modifiers


performance_tracker = PerformanceTracker()
