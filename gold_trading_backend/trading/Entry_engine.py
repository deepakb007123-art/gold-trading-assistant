class EntryEngine:
    """Select a candidate entry from the supplied setup context."""

    def get_entry(self, payload, smc, structure, liquidity):
        price = payload.price
        direction = payload.action

        # A BOS without displacement is treated as an unconfirmed breakout.
        if structure.get("has_bos") and not smc.displacement:
            return None, "Fake breakout"

        zone = liquidity.get("entry_zone")
        if zone:
            entry = zone.get("low" if direction == "BUY" else "high", price)
            return round(entry, 2), "Sniper Entry"

        if smc.displacement:
            return round(price, 2), "Confirmation Entry"

        return round(price, 2), "Market Entry"


entry_engine = EntryEngine()
