from typing import Tuple

from ..core.config import settings
from ..core.logger import logger
from ..models.signal import WebhookPayload


class NewsFilter:
    """Validate an upstream news decision without fabricating calendar data."""

    def check_news_window(self, payload: WebhookPayload) -> Tuple[bool, str]:
        if not settings.NEWS_FILTER_ENABLED:
            return True, "News filter disabled by configuration."

        if payload.news_clear is False:
            reason = payload.news_reason or "High-impact news window supplied by upstream signal."
            logger.warning("News filter blocked signal: %s", reason)
            return False, reason

        if payload.news_clear is True:
            return True, payload.news_reason or "Upstream calendar reports no restricted news window."

        # No calendar decision was supplied. Do not claim an external calendar check occurred.
        return True, "No upstream news restriction supplied; calendar validation is external."


news_filter = NewsFilter()
