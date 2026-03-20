class ScoringEngine:

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
    ):

        logger.info("Generating Balanced Score")

        if adaptive_modifiers is None:
            adaptive_modifiers = {}

        # -------------------------
        # BASE SCORE (NORMALIZED)
        # -------------------------
        base_score = (structure_conf * 0.4) + (liquidity_conf * 0.3) + (strategy_conf * 0.3)
        base_score = int(base_score)

        conf_mod = 0
        sess_mod = 0
        strat_mod = 0
        safe_mod = 0
        reasonings = []

        # -------------------------
        # CONFLUENCE (RELAXED)
        # -------------------------
        if smc_conditions.liquidity_sweep:
            conf_mod += 10
            reasonings.append("Liquidity Sweep detected")

        if smc_conditions.order_block:
            conf_mod += 8
            reasonings.append("Order Block present")

        if smc_conditions.fvg_imbalance:
            conf_mod += 8
            reasonings.append("FVG imbalance")

        if smc_conditions.displacement:
            conf_mod += 12
            reasonings.append("Strong displacement")

        if not smc_conditions.sweep_confirmed:
            conf_mod -= 8
            reasonings.append("Weak sweep confirmation")

        # -------------------------
        # HTF ALIGNMENT (SOFT)
        # -------------------------
        if htf_alignment:
            base_score += 8
        else:
            base_score -= 8
            reasonings.append("Against HTF (soft penalty)")

        # -------------------------
        # NEWS (SOFT)
        # -------------------------
        if not news_clear:
            base_score -= 10
            reasonings.append("Near news (reduced confidence)")

        # -------------------------
        # SESSION LOGIC
        # -------------------------
        if session_behavior.get("is_low_volatility", False):
            sess_mod -= 8
            reasonings.append("Low volatility session")

        if session_behavior.get("is_high_volatility", False):
            sess_mod += 5

        # -------------------------
        # STRATEGY ADAPTIVE
        # -------------------------
        highest_rank = "UNKNOWN"
        ranks_found = []

        strat_ranks = adaptive_modifiers.get("strategy_ranks", {})

        if strategies_used:
            for s in strategies_used:
                rank_data = strat_ranks.get(s)

                if rank_data:
                    rank = rank_data["rank"]
                    ranks_found.append(rank)

                    if rank == "TOP":
                        strat_mod += 8
                    elif rank == "LOW":
                        strat_mod -= 10

        if "TOP" in ranks_found:
            highest_rank = "TOP"
        elif "MID" in ranks_found:
            highest_rank = "MID"
        elif "LOW" in ranks_found:
            highest_rank = "LOW"

        # -------------------------
        # SAFE MODE (REDUCED IMPACT)
        # -------------------------
        if adaptive_modifiers.get("safe_mode_active", False):
            safe_mod -= 15
            reasonings.append("Safe mode active")

        return base_score, strat_mod, sess_mod, conf_mod, safe_mod, highest_rank, reasonings

    # ---------------------------------------------
    # QUALITY TIER (RELAXED & REALISTIC)
    # ---------------------------------------------
    def determine_quality_tier(self, final_score, smc_conditions, htf_alignment, session_behavior, adaptive_modifiers):

        has_liquidity = smc_conditions.liquidity_sweep
        has_structure = smc_conditions.bos or smc_conditions.choch
        has_displacement = smc_conditions.displacement

        is_early = smc_conditions.liquidity_sweep and smc_conditions.displacement and not has_structure

        # 🔥 HIGH (realistic)
        if final_score >= 75 and has_liquidity and has_displacement:
            return "HIGH"

        # ⚡ EARLY
        if is_early and final_score >= 55:
            return "EARLY"

        # ⚠️ MEDIUM (MOST IMPORTANT CATEGORY)
        if final_score >= 55:
            return "MEDIUM"

        # ❌ LOW
        return "LOW"
