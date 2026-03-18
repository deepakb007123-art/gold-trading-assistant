import os
import json
import sys
from datetime import datetime
from typing import List, Dict

# Setup sys path so python can find the core modules
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from trading.performance_tracker import performance_tracker
from trading.position_manager import position_manager
from models.signal import SMCConditions

def clear_logs():
    if os.path.exists("performance_log.json"):
        os.remove("performance_log.json")
    performance_tracker.trades = []
        
# A dummy analysis class to mock TradeAnalysis models
class MockAnalysis:
    def __init__(self, action, quality, session, entry, sl, tp, rr):
        self.action = action
        self.trade_quality = quality
        self.session = session
        self.entry_price = entry
        self.sl_price = sl
        self.tp_price = tp
        self.tp2_price = None
        self.rr_ratio = rr

def run_simulation():
    print("🚀 Starting V7 Equity Curve Intelligence Simulation...\n")
    clear_logs()
    
    # 1. Emulate a standard cycle of 5 Losses to trigger SAFE MODE / DEFENSIVE Drawdown
    print(">> Phase 1: Inducing Drawdown Scenario (5 Consecutive Losses)")
    for i in range(5):
        analysis = MockAnalysis("BUY", "EARLY", "London", 2000, 1990, 2020, 2.0)
        performance_tracker.register_trade(analysis)
        # Hit SL (market goes against)
        performance_tracker.update_market_price(1990)
        
    metrics = performance_tracker.get_metrics()
    print(f"Equity: {metrics['current_equity']}R (Peak: {metrics['peak_equity']}R)")
    print(f"Drawdown: {metrics['drawdown_pct']}% | State: {metrics['equity_state']}")
    print(f"SAFE MODE Active: {metrics['safe_mode_active']}")
    print("-" * 50)
    
    # 2. Emulate an incoming signal during DEFENSIVE mode to verify sizing drops
    print(">> Phase 2: Testing Position Manager during Equity Drawdown")
    smc = SMCConditions(liquidity_sweep=True, fakeout=False, displacement=True, fvg_present=True, choch_present=True, sweep_confirmed=True)
    
    size, risk, reasons = position_manager.calculate_position_size(
        trade_quality="MEDIUM",
        smc_conditions=smc,
        rr_ratio=3.0,
        session_name="New York",
        safe_mode_active=metrics["safe_mode_active"],
        recent_losses_last_5=metrics["recent_losses_last_5"],
        equity_state=metrics["equity_state"],
        consecutive_wins=0,
        equity_momentum=metrics["equity_momentum"]
    )
    
    print(f"Position Output: {size}x | Risk Level: {risk}")
    for r in reasons:
        print(f" - {r}")
    print("-" * 50)
        
    # 3. Winning Streak Expansion Test
    print(">> Phase 3: Healing Equity and Test Winning Streak Expansion")
    # First, win 5 trades to normalize equity and break safe mode
    for i in range(5):
        analysis = MockAnalysis("SELL", "HIGH", "New York", 2000, 2010, 1980, 2.0)
        performance_tracker.register_trade(analysis)
        performance_tracker.update_market_price(1980) # Hit TP
        
    metrics = performance_tracker.get_metrics()
    print(f"Equity: {metrics['current_equity']}R (Peak: {metrics['peak_equity']}R)")
    print(f"Drawdown: {metrics['drawdown_pct']}% | State: {metrics['equity_state']}")
    print(f"Momentum: raise to {metrics['equity_momentum']}")
    print(f"Winning Streak: {metrics['consecutive_wins']}")
    
    size, risk, reasons = position_manager.calculate_position_size(
        trade_quality="HIGH",
        smc_conditions=smc,
        rr_ratio=2.5,
        session_name="London",
        safe_mode_active=metrics["safe_mode_active"],
        recent_losses_last_5=0,
        equity_state=metrics["equity_state"],
        consecutive_wins=metrics["consecutive_wins"],
        equity_momentum=metrics["equity_momentum"]
    )
    
    print(f"\nNew Position Output: {size}x | Risk Level: {risk}")
    for r in reasons:
        print(f" - {r}")
        
    print("\n✅ Simulation Complete!")

if __name__ == "__main__":
    run_simulation()
