from pydantic import BaseModel
from typing import Dict, Tuple

class DecisionTrace(BaseModel):
    final_score: int
    score_components: Dict[str, int]
    final_size: float
    size_components: Dict[str, float]

class DecisionEngine:
    """
    V9 Decision Normalization Engine
    Centralizes and clamps all modifiers to prevent compounding instability.
    Returns normalized metrics and an explicit explainability trace.
    """
    
    def normalize_score(
        self,
        base_score: int,
        strategy_modifier: int,
        session_modifier: int,
        drawdown_modifier: int,
        confluence_modifier: int,
        safe_mode_modifier: int
    ) -> Tuple[int, Dict[str, int]]:
        """
        Clamps and evaluates all distinct score modifiers.
        Caps: Strategy (±15), Session (±10), Confluence (+20), Drawdown (-25), SAFE MODE (-30)
        """
        # 1. Component Level Caps
        strat = max(min(strategy_modifier, 15), -15)
        sess = max(min(session_modifier, 10), -10)
        conf = max(min(confluence_modifier, 20), -20)
        dd = max(min(drawdown_modifier, 0), -25)
        safe = max(min(safe_mode_modifier, 0), -30)

        # 2. Priority Conflict Resolution logic (Implicit in the strict boundaries)
        # If drawdown and safe mode are heavily active, they easily mathematically suppress any boosts.
        
        # 3. Aggregation and Pipeline Clamp
        final_score = base_score + strat + sess + conf + dd + safe
        final_score = int(max(min(final_score, 100), 0))
        
        trace = {
            "base": base_score,
            "strategy": strat,
            "session": sess,
            "confluence": conf,
            "drawdown": dd,
            "safe_mode": safe
        }
        
        return final_score, trace

    def normalize_position(
        self,
        base_size: float,
        strategy_multiplier: float,
        session_multiplier: float,
        drawdown_multiplier: float,
        confluence_multiplier: float,
        safe_mode_multiplier: float
    ) -> Tuple[float, Dict[str, float]]:
        """
        Calculates final position factor systematically.
        Applies all multipliers concurrently, then bounds between 0.25x and 1.5x.
        """
        final_size = (
            base_size * 
            strategy_multiplier * 
            session_multiplier * 
            drawdown_multiplier * 
            confluence_multiplier * 
            safe_mode_multiplier
        )
        
        final_size = round(max(min(final_size, 1.50), 0.25), 2)
        
        trace = {
            "base": float(base_size),
            "strategy": float(strategy_multiplier),
            "session": float(session_multiplier),
            "confluence": float(confluence_multiplier),
            "drawdown": float(drawdown_multiplier),
            "safe_mode": float(safe_mode_multiplier)
        }
        
        return final_size, trace

decision_engine = DecisionEngine()
