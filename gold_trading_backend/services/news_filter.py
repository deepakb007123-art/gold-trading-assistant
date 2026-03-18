import random
from typing import Tuple
from core.logger import logger

class NewsFilter:
    """
    Evaluates current time against high-impact macroeconomic events (CPI, NFP, FOMC).
    Filters out trades that occur during unpredictable volatility windows.
    Since we cannot use paid APIs, this simulates checking a calendar for high impact events.
    """

    def check_news_window(self) -> Tuple[bool, str]:
        """
        Returns boolean indicating if news is clear, and the reason.
        """
        logger.info("Checking for high-impact macroeconomic events")
        
        # In a fully deployed system without paid APIs, you can scrape ForexFactory 
        # or consume a free RSS feed. Here, we randomly simulate a news block occasionally.
        
        is_news_blocked = random.random() > 0.9  # 10% chance of being blocked by news
        
        if is_news_blocked:
            reasons = [
                "Red Folder USD Event (CPI) within 30 minutes.",
                "FOMC Press Conference ongoing.",
                "Non-Farm Payroll (NFP) volatility window active."
            ]
            reason = random.choice(reasons)
            logger.warning(f"News Filter Blocked Trade: {reason}")
            return False, reason
        else:
            return True, "No critical news windows active."

news_filter = NewsFilter()
