from models.signal import WebhookPayload, TradeAnalysis
from core.logger import logger

class ScoringEngine:
    """
    Categorizes the signal into a final confidence score (0-100)
    and trade quality bucket (LOW, MEDIUM, HIGH).
    """

    def generate_raw_modifiers(
        self,
        structure_conf: int,
        liquidity_conf: int,
        strategy_conf: int,
        news_clear: bool,
        smc_conditions,
        htf_alignment: bool,
        session_behavior: dict,
        adaptive_modifiers: dict = None,
        strategies_used: list = None
    ) -> tuple[int, int, int, int, int, str, list]:
        """
        Calculates raw base metrics and extracts non-clamped modifiers for the Decision Engine.
        Returns: base_score, strat_mod, sess_mod, conf_mod, safe_mod, highest_rank, reasonings
        """
        logger.info("Generating Raw Scoring Modifiers for V9 Centralization")
        if adaptive_modifiers is None:
            adaptive_modifiers = {}
            
        base_score = structure_conf + liquidity_conf + strategy_conf
        
        conf_mod = 0
        sess_mod = 0
        strat_mod = 0
        safe_mod = 0
        
        reasonings = []
        
        # Confluence / Base Environment Mechanics
        if smc_conditions.liquidity_sweep and smc_conditions.order_block and smc_conditions.fvg_imbalance:
            conf_mod += 25
            reasonings.append("Boost: Perfect Synergy (Sweep + OB + FVG)")
            
        if smc_conditions.liquidity_sweep and not smc_conditions.sweep_confirmed:
            conf_mod -= 20
            reasonings.append("Penalty: Unconfirmed sweep displacement")
            
        if not htf_alignment:
            base_score -= 20
            reasonings.append("Penalty: Against HTF Trend")
            
        if not news_clear:
            base_score -= 15
            reasonings.append("Penalty: Near news window")
            
        if news_clear and htf_alignment:
            base_score += 10
            
        # Session Analytics
        if session_behavior.get("is_low_volatility", False):
            sess_mod -= 10
            reasonings.append("Penalty: Low volatility session")
            
        # V8 Strategy Modifiers
        if strategies_used is None:
            strategies_used = []
            
        highest_rank = "UNKNOWN"
        ranks_found = []
        
        strat_ranks = adaptive_modifiers.get("strategy_ranks", {})
        session_strat_ranks = adaptive_modifiers.get("session_strategy_ranks", {})
        sess_name = session_behavior.get("name", "Unknown").split("/")[0].strip()
        
        for s in strategies_used:
            rank_data = strat_ranks.get(s)
            if rank_data:
                ranks_found.append(rank_data["rank"])
                if rank_data["rank"] == "TOP":
                    strat_mod += 10
                    reasonings.append(f"Boost: TOP Strategy ({s} @ {rank_data['wr']}%)")
                elif rank_data["rank"] == "LOW":
                    strat_mod -= 15
                    reasonings.append(f"Penalty: LOW Strategy ({s} @ {rank_data['wr']}%)")
            
            pair_key = f"{sess_name}_{s}"
            pair_rank = session_strat_ranks.get(pair_key)
            if pair_rank == "STRONG":
                sess_mod += 10
                reasonings.append(f"Boost: STRONG session pairing ({s} in {sess_name})")
            elif pair_rank == "WEAK":
                sess_mod -= 10
                reasonings.append(f"Penalty: WEAK session pairing ({s} in {sess_name})")
                
        if "TOP" in ranks_found:
            highest_rank = "TOP"
        elif "MID" in ranks_found:
            highest_rank = "MID"
        elif "LOW" in ranks_found:
            highest_rank = "LOW"
            
        # Safe Mode
        if adaptive_modifiers.get("safe_mode_active", False):
            safe_mod -= 30
            reasonings.append("Penalty: SAFE MODE Global Restrictive Constraint")
            
        return base_score, strat_mod, sess_mod, conf_mod, safe_mod, highest_rank, reasonings
        
    def determine_quality_tier(self, final_score: int, smc_conditions, htf_alignment: bool, session_behavior: dict, adaptive_modifiers: dict) -> str:
        """
        Evaluates Final normalized score to establish trade bucket category.
        """
        has_liquidity = smc_conditions.liquidity_sweep or smc_conditions.inducements
        has_structure = smc_conditions.bos or smc_conditions.choch
        has_imbalance = smc_conditions.fvg_imbalance or smc_conditions.displacement
        is_high_vol = session_behavior.get("is_high_volatility", False)
        strict_confluence_met = has_liquidity and has_structure and has_imbalance
        
        is_early_entry = smc_conditions.liquidity_sweep and smc_conditions.displacement and not has_structure and smc_conditions.liquidity_approaching
        
        if strict_confluence_met and final_score >= 80 and htf_alignment:
            return "HIGH"
        elif is_early_entry:
            return "EARLY"
        elif (has_liquidity and has_structure) and final_score >= 60:
            return "MEDIUM"
        elif (not strict_confluence_met and is_high_vol) and final_score >= 60:
            if smc_conditions.sweep_confirmed and smc_conditions.displacement and not adaptive_modifiers.get("medium_strictness_boost", False):
                return "MEDIUM"
        return "LOW"

scoring_engine = ScoringEngine()
