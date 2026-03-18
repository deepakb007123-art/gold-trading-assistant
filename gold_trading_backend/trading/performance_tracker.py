import json
import os
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
from core.logger import logger

class PerformanceTracker:
    def __init__(self, log_file: str = "performance_log.json"):
        self.log_file = log_file
        self.trades = self._load_trades()
        self.timeout_minutes = 240 # 4 hours

    def _load_trades(self) -> List[Dict]:
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load performance log: {e}")
        return []

    def _save_trades(self):
        temp_file = f"{self.log_file}.tmp"
        try:
            with open(temp_file, "w") as f:
                json.dump(self.trades, f, indent=4)
            os.replace(temp_file, self.log_file)
        except Exception as e:
            logger.error(f"Failed to safely save performance log: {e}")
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass

    def register_trade(self, analysis) -> str:
        trade_id = str(uuid.uuid4())[:8]
        trade_record = {
            "id": trade_id,
            "timestamp": datetime.utcnow().isoformat(),
            "action": analysis.action,
            "quality": analysis.trade_quality,
            "session": analysis.session.split("/")[0].strip(), # Simplify session name
            "strategies": getattr(analysis, "strategies_used", []),
            "entry": analysis.entry_price,
            "sl": analysis.sl_price,
            "tp1": analysis.tp_price,
            "tp2": analysis.tp2_price,
            "rr": analysis.rr_ratio,
            "status": "PENDING",
            "outcome": None,
            "close_time": None
        }
        self.trades.append(trade_record)
        self._save_trades()
        logger.info(f"Registered trade {trade_id} into Performance Tracker.")
        return trade_id

    def update_market_price(self, current_price: float) -> List[Dict]:
        """
        Since we have no live feed, we use subsequent webhook prices to resolve trades.
        Returns a list of trades that just closed for reporting.
        """
        now = datetime.utcnow()
        closed_trades = []
        updated = False

        for t in self.trades:
            if t["status"] != "PENDING":
                continue
                
            entry_time = datetime.fromisoformat(t["timestamp"])
            minutes_elapsed = (now - entry_time).total_seconds() / 60.0
            
            is_buy = t["action"] == "BUY"
            
            # Check TIMEOUT
            if minutes_elapsed > self.timeout_minutes:
                t["status"] = "CLOSED"
                t["outcome"] = "TIMEOUT"
                t["close_time"] = now.isoformat()
                closed_trades.append(t)
                updated = True
                continue
                
            # Check SL/TP
            if is_buy:
                if current_price <= t["sl"]:
                    t["status"] = "CLOSED"
                    t["outcome"] = "LOSS"
                    t["close_time"] = now.isoformat()
                    closed_trades.append(t)
                    updated = True
                elif t["tp2"] and current_price >= t["tp2"]:
                    t["status"] = "CLOSED"
                    t["outcome"] = "WIN"
                    t["close_time"] = now.isoformat()
                    closed_trades.append(t)
                    updated = True
                elif current_price >= t["tp1"]:
                    # In a real system, we'd move SL to BE. Here, we mark PARTIAL if it hasn't hit TP2 yet
                    # For simplicity of exact resolution without tick data, we'll mark WIN if TP1 hit
                    t["status"] = "CLOSED"
                    t["outcome"] = "WIN" # Treating TP1 as a win for baseline metrics
                    t["close_time"] = now.isoformat()
                    closed_trades.append(t)
                    updated = True
            else: # SELL
                if current_price >= t["sl"]:
                    t["status"] = "CLOSED"
                    t["outcome"] = "LOSS"
                    t["close_time"] = now.isoformat()
                    closed_trades.append(t)
                    updated = True
                elif t["tp2"] and current_price <= t["tp2"]:
                    t["status"] = "CLOSED"
                    t["outcome"] = "WIN"
                    t["close_time"] = now.isoformat()
                    closed_trades.append(t)
                    updated = True
                elif current_price <= t["tp1"]:
                    t["status"] = "CLOSED"
                    t["outcome"] = "WIN"
                    t["close_time"] = now.isoformat()
                    closed_trades.append(t)
                    updated = True

        if updated:
            self._save_trades()
            
        return closed_trades

    def get_metrics(self) -> Dict:
        closed = [t for t in self.trades if t["status"] == "CLOSED"]
        if not closed:
            return {
                "total_signals": 0, 
                "win_rate": 0, 
                "quality_metrics": {},
                "system_state": "NORMAL",
                "safe_mode_active": False
            }

        # Deterministic State Calculation
        state: str = "NORMAL"
        consec_wins: int = 0
        consec_losses: int = 0
        
        # Sort chronologically to correctly replay state
        closed_sorted: List[Dict[str, Any]] = sorted(closed, key=lambda x: x["close_time"] if x.get("close_time") else x["timestamp"])
        
        for i, t in enumerate(closed_sorted):
            if t["outcome"] == "WIN":
                consec_wins += 1
                consec_losses = 0
            elif t["outcome"] == "LOSS":
                consec_losses += 1
                consec_wins = 0
            else:
                consec_wins = 0
                consec_losses = 0
                
            if state in ["NORMAL", "CAUTION"]:
                if consec_losses >= 3:
                    state = "CAUTION"
                if consec_losses >= 5:
                    logger.warning("ANOMALY DETECTED: 5 consecutive losses. Entering SAFE MODE.")
                    state = "SAFE MODE"
            elif state == "SAFE MODE":
                # Exit Safemode condition
                if consec_wins >= 3:
                    logger.info("SAFE MODE EXIT: 3 consecutive wins achieved. Restoring NORMAL.")
                    state = "NORMAL"
                else:
                    # Check rolling 10
                    start_idx = max(0, i - 9)
                    last_10 = closed_sorted[start_idx:i+1]
                    wins = len([x for x in last_10 if x["outcome"] == "WIN"])
                    if len(last_10) == 10 and (wins / 10) >= 0.6:
                        logger.info("SAFE MODE EXIT: 60%+ win rate over last 10 trades. Restoring NORMAL.")
                        state = "NORMAL"

        total: int = len(closed)
        wins: int = len([t for t in closed if t["outcome"] == "WIN"])
        
        # V7 Equity Curve Mathematics
        current_equity: float = 100.0 # Base 100R account
        peak_equity: float = 100.0
        equity_curve: List[float] = []
        
        for t in closed_sorted:
            if t["outcome"] == "WIN":
                rr = float(t.get("rr", 2.0) or 2.0)
                current_equity += rr
            elif t["outcome"] == "LOSS":
                current_equity -= 1.0 # Fixed 1R risk logic
                
            if current_equity > peak_equity:
                peak_equity = current_equity
            equity_curve.append(current_equity)
            
        drawdown_pct: float = 0.0
        if peak_equity > 0.0:
            drawdown_pct = float(((peak_equity - current_equity) / peak_equity) * 100.0)
        drawdown_pct = float(round(drawdown_pct, 2))
        
        # Map Drawdown State Matrix
        equity_state: str = "NORMAL"
        if drawdown_pct < 5.0:
            equity_state = "NORMAL"
        elif drawdown_pct < 10.0:
            equity_state = "CAUTION"
        elif drawdown_pct < 15.0:
            equity_state = "DEFENSIVE"
        else:
            equity_state = "CRITICAL"
            
        momentum: str = "FLAT"
        if len(equity_curve) >= 5:
            last_5: List[float] = equity_curve[-5:]
            if last_5[-1] > last_5[0] and drawdown_pct == 0.0:
                momentum = "RISING"
            elif last_5[-1] < last_5[0]:
                momentum = "FALLING"
        
        metrics: Dict[str, Any] = {
            "total_signals": total,
            "win_rate": float(round((wins / total) * 100.0, 1)) if total > 0 else 0.0,
            "quality_metrics": {"HIGH": {"total": 0, "wins": 0}, "MEDIUM": {"total": 0, "wins": 0}, "EARLY": {"total": 0, "wins": 0}},
            "session_metrics": {},
            "recent_losses_last_5": len([x for x in closed_sorted[-5:] if x["outcome"] == "LOSS"]),
            "system_state": state,
            "safe_mode_active": state == "SAFE MODE",
            "current_equity": float(round(current_equity, 2)),
            "peak_equity": float(round(peak_equity, 2)),
            "drawdown_pct": float(drawdown_pct),
            "equity_state": equity_state,
            "equity_momentum": momentum,
            "consecutive_wins": consec_wins
        }

        # Cast for safe dict mutations natively
        quality_map: Dict[str, Dict[str, int]] = metrics["quality_metrics"]
        session_map: Dict[str, Dict[str, int]] = metrics["session_metrics"]

        for t in closed:
            q: str = t.get("quality", "LOW")
            if q in quality_map:
                quality_map[q]["total"] = quality_map[q].get("total", 0) + 1
                if t["outcome"] == "WIN":
                    quality_map[q]["wins"] = quality_map[q].get("wins", 0) + 1
                    
            sess: str = t.get("session", "Unknown")
            if sess not in session_map:
                session_map[sess] = {"total": 0, "wins": 0}
            session_map[sess]["total"] = session_map[sess].get("total", 0) + 1
            if t["outcome"] == "WIN":
                session_map[sess]["wins"] = session_map[sess].get("wins", 0) + 1

        metrics["quality_metrics"] = quality_map
        metrics["session_metrics"] = session_map

        return metrics

    def get_adaptive_modifiers(self) -> Dict:
        """
        Self-evaluation logic to dynamically penalize or boost behavior.
        Now uses Rolling Averages (Last 20) and Minimum Sample Sizes (10) to avoid overfitting.
        """
        metrics = self.get_metrics()
        closed = [t for t in self.trades if t["status"] == "CLOSED"]
        closed_sorted = sorted(closed, key=lambda x: x["close_time"] if x.get("close_time") else x["timestamp"])
        
        modifiers = {
            "early_score_penalty": 0,
            "medium_strictness_boost": False,
            "asian_breakout_allowed": False,
            "safe_mode_active": metrics.get("safe_mode_active", False),
            "system_state": metrics.get("system_state", "NORMAL")
        }
        
        # 1. EARLY signal evaluation (Smoothed last 20 TRADES)
        early_trades = [t for t in closed_sorted if t.get("quality") == "EARLY"][-20:]
        early_total = len(early_trades)
        if early_total >= 10:
            early_wins = len([t for t in early_trades if t["outcome"] == "WIN"])
            early_wr = early_wins / early_total
            if early_wr < 0.45:
                # Max penalty limit is -15. Gradual recovery embedded mathematically via the moving average window
                penalty = int((0.45 - early_wr) * 50) # e.g. 0.30 -> diff 0.15 * 50 = 7.5
                modifiers["early_score_penalty"] = -min(15, penalty) 
                
        # 2. MEDIUM/HIGH signal evaluation (Smoothed rolling 20)
        med_trades = [t for t in closed_sorted if t.get("quality") == "MEDIUM"][-20:]
        med_total = len(med_trades)
        if med_total >= 10:
            med_wins = len([t for t in med_trades if t["outcome"] == "WIN"])
            med_wr = med_wins / med_total
            if med_wr < 0.45:
                # Cap restrictions at a maximum downgrade layer
                modifiers["medium_strictness_boost"] = True

        # 3. Session Stability Lock (Asian)
        asian_trades = [t for t in closed_sorted if t.get("session") == "Asian"][-20:]
        asian_total = len(asian_trades)
        if asian_total >= 20: # Requires high stability lock (20 trades) before changing DNA
            asian_wins = len([t for t in asian_trades if t["outcome"] == "WIN"])
            asian_wr = asian_wins / asian_total
            if asian_wr >= 0.65:
                modifiers["asian_breakout_allowed"] = True 
                
        # 4. V8 Strategy Intelligence & Ranking
        strategy_stats: Dict[str, Dict[str, int]] = {}
        session_strategy_stats: Dict[str, Dict[str, int]] = {}
        
        for t in closed_sorted:
            outcome = t.get("outcome")
            sess = t.get("session", "Unknown")
            strats = t.get("strategies", [])
            for s in strats:
                s_str = str(s)
                # Global strategy tracking
                if s_str not in strategy_stats:
                    strategy_stats[s_str] = {"total": 0, "wins": 0}
                strategy_stats[s_str]["total"] = strategy_stats[s_str].get("total", 0) + 1
                if outcome == "WIN":
                    strategy_stats[s_str]["wins"] = strategy_stats[s_str].get("wins", 0) + 1
                    
                # Session-Strategy pairing
                pair_key = f"{sess}_{s_str}"
                if pair_key not in session_strategy_stats:
                    session_strategy_stats[pair_key] = {"total": 0, "wins": 0}
                session_strategy_stats[pair_key]["total"] = session_strategy_stats[pair_key].get("total", 0) + 1
                if outcome == "WIN":
                    session_strategy_stats[pair_key]["wins"] = session_strategy_stats[pair_key].get("wins", 0) + 1

        strategy_ranks: Dict[str, Dict[str, Any]] = {}
        for s_key, stats in strategy_stats.items():
            if stats["total"] >= 15:
                wr = float(stats.get("wins", 0)) / float(stats.get("total", 1))
                if wr >= 0.55:
                    strategy_ranks[s_key] = {"rank": "TOP", "wr": float(round(wr*100.0, 1)), "total": stats["total"]}
                elif wr >= 0.40:
                    strategy_ranks[s_key] = {"rank": "MID", "wr": float(round(wr*100.0, 1)), "total": stats["total"]}
                else:
                    strategy_ranks[s_key] = {"rank": "LOW", "wr": float(round(wr*100.0, 1)), "total": stats["total"]}
        
        session_strategy_ranks: Dict[str, str] = {}
        for pair, pair_stats in session_strategy_stats.items():
            if pair_stats["total"] >= 10: # slightly lower threshold for session-pairs
                wr = float(pair_stats.get("wins", 0)) / float(pair_stats.get("total", 1))
                if wr >= 0.60:
                    session_strategy_ranks[pair] = "STRONG"
                elif wr < 0.40:
                    session_strategy_ranks[pair] = "WEAK"

        modifiers["strategy_ranks"] = strategy_ranks
        modifiers["session_strategy_ranks"] = session_strategy_ranks

        return modifiers

performance_tracker = PerformanceTracker()
