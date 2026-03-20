class EntryEngine:

    def get_entry(self, payload, smc, structure, liquidity):

        price = payload.price
        direction = payload.action

        # ❌ Fake breakout filter
        if structure.get("bos") and not smc.displacement:
            return None, "Fake breakout"

        # 🎯 Sniper entry (best)
        zone = liquidity.get("entry_zone")

        if zone:
            if direction == "BUY":
                entry = zone.get("low", price)
            else:
                entry = zone.get("high", price)

            return round(entry, 2), "Sniper Entry"

        # ⚡ Confirmation entry
        if smc.displacement:
            return price, "Confirmation Entry"

        # fallback
        return price, "Market Entry"


entry_engine = EntryEngine()
