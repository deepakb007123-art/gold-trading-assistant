from datetime import datetime
from typing import List, Literal, Tuple, Dict

class SessionManager:
    """
    Auto-detects UTC trading sessions and adjusts volatility expectations.
    Doesn't rely on TradingView session inputs.
    """
    
    # Session Hours in UTC
    # Asian: 23:00 - 08:00
    # London: 07:00 - 16:00
    # NY: 12:00 - 21:00
    
    @staticmethod
    def get_current_session(dt_utc: datetime = None) -> Tuple[List[str], str]:
        """
        Returns active sessions and a primary descriptive string 
        (e.g., 'London/NY Overlap').
        """
        if dt_utc is None:
            dt_utc = datetime.utcnow()
            
        hour = dt_utc.hour
        active_sessions = []
        
        # Asian Session (23:00 - 08:00)
        if hour >= 23 or hour < 8:
            active_sessions.append("Asian")
            
        # London Session (07:00 - 16:00)
        if 7 <= hour < 16:
            active_sessions.append("London")
            
        # NY Session (12:00 - 21:00)
        if 12 <= hour < 21:
            active_sessions.append("New York")
            
        # Determine descriptive string
        if "London" in active_sessions and "New York" in active_sessions:
            desc = "London/NY Overlap"
        elif "Asian" in active_sessions and "London" in active_sessions:
            desc = "Asian/London Overlap"
        elif len(active_sessions) == 1:
            desc = active_sessions[0]
        else:
            desc = "Off-Peak/Dead Zone"
            
        return active_sessions, desc

    @staticmethod
    def get_session_behavior(sessions: List[str], adaptive_modifiers: Dict = None) -> Dict:
        """
        Determines the expected behavior of the market based on the active session.
        Modifies rules dynamically based on past self-evaluated performance.
        """
        if adaptive_modifiers is None:
            adaptive_modifiers = {}
            
        behavior = {
            "name": sessions[0] if sessions else "Dead Zone",
            "is_low_volatility": False,
            "is_high_volatility": False,
            "expected_action": "Neutral",
            "fakeout_risk": "Low",
            "allow_breakout": True,
            "require_htf_alignment": False,
            "require_liquidity_taken": False,
            "cooldown_minutes": 5
        }
        
        if "London" in sessions and "New York" in sessions:
            behavior["expected_action"] = "Expansion / Continuation"
            behavior["fakeout_risk"] = "Low"
            behavior["is_high_volatility"] = True
            behavior["cooldown_minutes"] = 2
        elif "New York" in sessions:
            behavior["expected_action"] = "Continuation / Reversal"
            behavior["fakeout_risk"] = "Medium"
            behavior["require_liquidity_taken"] = True
            behavior["is_high_volatility"] = True
            behavior["cooldown_minutes"] = 3
        elif "London" in sessions:
            behavior["expected_action"] = "Expansion / Sweep"
            behavior["fakeout_risk"] = "Medium"
            behavior["cooldown_minutes"] = 3
        elif "Asian" in sessions:
            behavior["expected_action"] = "Range / Manipulation"
            behavior["fakeout_risk"] = "High"
            behavior["is_low_volatility"] = True
            behavior["require_htf_alignment"] = True # Asian only valid if aligned
            behavior["cooldown_minutes"] = 10
            
            # Auto-Calibration override
            if adaptive_modifiers.get("asian_breakout_allowed"):
                behavior["allow_breakout"] = True
            else:
                behavior["allow_breakout"] = False # Rejects breakouts
        else:
            behavior["expected_action"] = "Dead Zone"
            behavior["fakeout_risk"] = "High"
            behavior["is_low_volatility"] = True
            behavior["allow_breakout"] = False
            behavior["cooldown_minutes"] = 15
            
        return behavior

    @staticmethod
    def get_volatility_multiplier(sessions: List[str]) -> float:
        """
        Returns an expected volatility multiplier based on active sessions.
        Used to adjust SL/TP padding if necessary.
        """
        if "London" in sessions and "New York" in sessions:
            return 1.5  # Highest volatility
        elif "New York" in sessions:
            return 1.2
        elif "London" in sessions:
            return 1.2
        elif "Asian" in sessions:
            return 0.8  # Lower volatility
        else:
            return 0.5  # Dead zone

session_manager = SessionManager()
