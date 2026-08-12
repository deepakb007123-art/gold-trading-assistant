from ..core.logger import logger


class ScoringEngine:
    """Combine structure, liquidity, strategy and session evidence into a bounded score."""

    def generate_raw_modifiers(
        self,
        structure_conf: int,
        liquidity_conf: int,
        strategy_conf: int,
        news_clear: bool,
        smc_conditions,
        htf_alignment: bool,
        session_behavior: dict,
        adaptive_modifiers: dict | None = None,
        strategies_used: list | None = None,
    ):
        adaptive_modifiers = adaptive_modifiers or {}
        strategies_used = strategies_used or []

        base_score = int((structure_conf * 0.4) + (liquidity_conf * 0.3) + (strategy_conf * 0.3))
        conf_mod = 0
        sess_mod = 0
        strat_mod = 0
        safe_mod = 0
        reasonings = []

        if smc_conditions.liquidity_sweep:
            conf_mod += 10
            reasonings.append("Liquidity sweep detected")
        if smc_conditions.order_block:
            conf_mod += 8
            reasonings.append("Order block present")
        if smc_conditions.fvg_imbalance:
            conf_mod += 8
            reasonings.append("FVG imbalance")
        if smc_conditions.displacement:
            conf_mod += 12
            reasonings.append("Strong displacement")
        if not smc_conditions.sweep_confirmed:
            conf_mod -= 8
            reasonings.append("Sweep confirmation not established")

        if htf_alignment:
            base_score += 8
            reasonings.append("HTF alignment")
        else:
            base_score -= 8
            reasonings.append("Against HTF bias")

        if not news_clear:
            base_score -= 10
            reasonings.append("News risk window active")

        if session_behavior.get("is_low_volatility"):
            sess_mod -= 8
            reasonings.append("Low-volatility session")
        if session_behavior.get("is_high_volatility"):
            sess_mod += 5
            reasonings.append("Active volatility session")

        strategy_ranks = adaptive_modifiers.get("strategy_ranks", {})
        ranks_found = []
        for strategy in strategies_used:
            rank_data = strategy_ranks.get(strategy)
            if not rank_data:
                continue
            rank = rank_data.get("rank")
            ranks_found.append(rank)
            if rank == "TOP":
                strat_mod += 8
            elif rank == "LOW":
                strat_mod -= 10

        highest_rank = "TOP" if "TOP" in ranks_found else "MID" if "MID" in ranks_found else "LOW" if "LOW" in ranks_found else "UNKNOWN"

        if adaptive_modifiers.get("safe_mode_active"):
            safe_mod -= 15
            reasonings.append("Safe mode active")

        logger.info("Score generated: base=%s strategy=%s session=%s confluence=%s", base_score, strat_mod, sess_mod, conf_mod)
        return base_score, strat_mod, sess_mod, conf_mod, safe_mod, highest_rank, reasonings

    def determine_quality_tier(self, final_score, smc_conditions, htf_alignment, session_behavior, adaptive_modifiers):
        has_liquidity = smc_conditions.liquidity_sweep
        has_structure = smc_conditions.bos or smc_conditions.choch
        has_displacement = smc_conditions.displacement
        is_early = has_liquidity and has_displacement and not has_structure

        if final_score >= 75 and has_liquidity and has_displacement and htf_alignment:
            return "HIGH"
        if is_early and final_score >= 55:
            return "EARLY"
        if final_score >= 55 and htf_alignment:
            return "MEDIUM"
        return "LOW"


scoring_engine = ScoringEngine()
