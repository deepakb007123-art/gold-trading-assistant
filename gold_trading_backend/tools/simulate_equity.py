from ..models.signal import SMCConditions
from ..trading.performance_tracker import performance_tracker
from ..trading.position_manager import position_manager


class MockAnalysis:
    def __init__(self, action, quality, session, entry, sl, tp, rr):
        self.action = action
        self.trade_quality = quality
        self.session = session
        self.strategies_used = ["Order Block (OB)"]
        self.entry_price = entry
        self.sl_price = sl
        self.tp_price = tp
        self.tp2_price = None
        self.rr_ratio = rr


def clear_logs():
    performance_tracker.trades = []


def run_simulation():
    print("Starting equity-curve simulation")
    clear_logs()

    for _ in range(5):
        analysis = MockAnalysis("BUY", "EARLY", "London", 2000, 1990, 2020, 2.0)
        performance_tracker.register_trade(analysis)
        performance_tracker.update_market_price(1990)

    metrics = performance_tracker.get_metrics()
    print(f"Equity: {metrics['current_equity']}R | State: {metrics['equity_state']}")

    smc = SMCConditions(
        liquidity_sweep=True,
        displacement=True,
        bos=True,
        choch=True,
        fvg_imbalance=True,
        sweep_confirmed=True,
    )

    size, risk, reasons = position_manager.calculate_position_size(
        trade_quality="MEDIUM",
        smc_conditions=smc,
        rr_ratio=3.0,
        session_name="New York",
        safe_mode_active=metrics["safe_mode_active"],
        recent_losses_last_5=sum(1 for t in performance_tracker.trades[-5:] if t.get("outcome") == "LOSS"),
        equity_state=metrics["equity_state"],
        consecutive_wins=metrics["consecutive_wins"],
        equity_momentum="FLAT",
    )

    print(f"Position output: {size}x | Risk tier: {risk}")
    for reason in reasons:
        print(f" - {reason}")


if __name__ == "__main__":
    run_simulation()
