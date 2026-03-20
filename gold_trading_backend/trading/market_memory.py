from datetime import datetime


class MarketMemory:

    def __init__(self):
        self.current_day = None

        self.day_high = None
        self.day_low = None

        self.prev_day_high = None
        self.prev_day_low = None

    def update(self, price: float):

        today = datetime.utcnow().date()

        # 🆕 NEW DAY → SHIFT
        if self.current_day != today:

            if self.day_high is not None:
                self.prev_day_high = self.day_high
                self.prev_day_low = self.day_low

            self.current_day = today
            self.day_high = price
            self.day_low = price

        # 📈 UPDATE CURRENT DAY
        else:
            if self.day_high is None or price > self.day_high:
                self.day_high = price

            if self.day_low is None or price < self.day_low:
                self.day_low = price

    def get_levels(self):

        return {
            "pdh": self.prev_day_high,
            "pdl": self.prev_day_low
        }


market_memory = MarketMemory()
