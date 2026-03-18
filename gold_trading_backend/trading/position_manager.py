from core.logger import logger
from models.signal import SMCConditions

class PositionManager:
    """
    V6 Position Intelligence Engine.
    Dynamically sizes trades based on systemic confidence, session behavior, and recent anomaly telemetry.
    """

    def generate_raw_multipliers(
        self,
        trade_quality: str,
        smc_conditions: SMCConditions,
        rr_ratio: float,
        session_name: str,
        safe_mode_active: bool,
        recent_losses_last_5: int,
        equity_state: str = "NORMAL",
        consecutive_wins: int = 0,
        equity_momentum: str = "FLAT"
    ) -> tuple[float, float, float, float, float, float, list]:
        """
        Extracts position scaling factors for the Decision Engine.
        Returns: base_size, strat_mult, sess_mult, drawdown_mult, conf_mult, safe_mult, reasonings
        """
        logger.info("Computing active Position Raw Size metrics...")
        reasons = []
        
        # 1. Base Sizing Matrix
        if trade_quality == "HIGH":
            base_size = 1.0
            reasons.append("Base 1.0x (HIGH Quality Signal).")
        elif trade_quality == "MEDIUM":
            base_size = 0.50
            reasons.append("Base 0.5x (MEDIUM Quality Signal).")
        elif trade_quality == "EARLY":
            base_size = 0.25
            reasons.append("Base 0.25x (EARLY High-Risk Entry).")
        else:
            return 0.0, 1.0, 1.0, 1.0, 1.0, 1.0, ["LOW Quality - Zero Vol"]
            
        conf_mult = 1.0
        sess_mult = 1.0
        dd_mult = 1.0
        safe_mult = 1.0
        strat_mult = 1.0 # Will track momentum/strategy boosts here
        
        # 2. Perfect Confluence Boost
        is_perfect = smc_conditions.liquidity_sweep and smc_conditions.displacement and smc_conditions.bos
        if is_perfect and rr_ratio >= 2.0:
            conf_mult = 1.25
            reasons.append("Boost: +25% (Perfect SMC Confluence & RR >= 2).")

        # 3. Session Scaling Defaults
        if "London" in session_name or "New York" in session_name:
            sess_mult = 1.10
            reasons.append("Boost: +10% (High Volume LND/NY Session).")
        elif "Asian" in session_name:
            sess_mult = 0.80
            reasons.append("Penalty: -20% (Asian Range Profiling).")

        # 4. Drawdown Telemetry Protection
        if recent_losses_last_5 >= 3:
            dd_mult = 0.75
            reasons.append("Penalty: -25% (Drawdown Protection: 3+ losses in last 5).")

        # 5. Global Safe Mode Constraint
        if safe_mode_active:
            safe_mult = 0.50
            reasons.append("Penalty: -50% (SAFE MODE Restrictive Constraint Active).")

        # 6. V7 Equity Curve Intelligence Scaling
        if equity_state == "CAUTION":
            dd_mult *= 0.80
            reasons.append("Penalty: -20% (Equity State: CAUTION).")
        elif equity_state == "DEFENSIVE":
            dd_mult *= 0.60
            reasons.append("Penalty: -40% (Equity State: DEFENSIVE).")
        elif equity_state == "CRITICAL":
            dd_mult *= 0.40
            reasons.append("Penalty: -60% (Equity State: CRITICAL).")
            
        # 7. V7 Winning Streak Expansion
        if consecutive_wins >= 5 and equity_state == "NORMAL":
            strat_mult = 1.10
            reasons.append(f"Boost: +10% (Winning Streak Expansion: {consecutive_wins} Wins).")

        return base_size, strat_mult, sess_mult, dd_mult, conf_mult, safe_mult, reasons

    def determine_risk_tier(self, final_size: float) -> str:
        """
        Maps the finalized position volume to an explicit Risk semantic category.
        """
        if final_size >= 1.0:
            return "AGGRESSIVE"
        elif final_size >= 0.75:
            return "HIGH"
        elif final_size >= 0.40:
            return "NORMAL"
        else:
            return "LOW"

position_manager = PositionManager()
