from ..core.logger import logger
from ..models.signal import SMCConditions


class PositionManager:
    """Calculate position scaling factors from quality and risk telemetry."""

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
        equity_momentum: str = "FLAT",
    ) -> tuple[float, float, float, float, float, float, list[str]]:
        logger.info("Computing position multipliers")
        reasons: list[str] = []

        if trade_quality == "HIGH":
            base_size = 1.0
            reasons.append("Base 1.0x for HIGH quality")
        elif trade_quality == "MEDIUM":
            base_size = 0.5
            reasons.append("Base 0.5x for MEDIUM quality")
        elif trade_quality == "EARLY":
            base_size = 0.25
            reasons.append("Base 0.25x for EARLY setup")
        else:
            return 0.0, 1.0, 1.0, 1.0, 1.0, 1.0, ["LOW quality - no position"]

        conf_mult = 1.0
        sess_mult = 1.0
        dd_mult = 1.0
        safe_mult = 1.0
        strat_mult = 1.0

        if smc_conditions.liquidity_sweep and smc_conditions.displacement and smc_conditions.bos and rr_ratio >= 2.0:
            conf_mult = 1.25
            reasons.append("+25% confluence boost")

        if "London" in session_name or "New York" in session_name:
            sess_mult = 1.10
        elif "Asian" in session_name:
            sess_mult = 0.80
            reasons.append("-20% Asian session adjustment")

        if recent_losses_last_5 >= 3:
            dd_mult = 0.75
            reasons.append("-25% drawdown protection")

        if safe_mode_active:
            safe_mult = 0.50
            reasons.append("-50% SAFE MODE")

        if equity_state == "CAUTION":
            dd_mult *= 0.80
        elif equity_state == "DEFENSIVE":
            dd_mult *= 0.60
        elif equity_state == "CRITICAL":
            dd_mult *= 0.40

        if consecutive_wins >= 5 and equity_state == "NORMAL":
            strat_mult = 1.10
            reasons.append("+10% winning-streak expansion")

        return base_size, strat_mult, sess_mult, dd_mult, conf_mult, safe_mult, reasons

    def calculate_position_size(self, **kwargs):
        base, strat, sess, dd, conf, safe, reasons = self.generate_raw_multipliers(**kwargs)
        final_size = round(max(min(base * strat * sess * dd * conf * safe, 1.5), 0.0), 2)
        return final_size, self.determine_risk_tier(final_size), reasons

    @staticmethod
    def determine_risk_tier(final_size: float) -> str:
        if final_size >= 1.0:
            return "AGGRESSIVE"
        if final_size >= 0.75:
            return "HIGH"
        if final_size >= 0.40:
            return "NORMAL"
        return "LOW"


position_manager = PositionManager()
