"""市場に依存しない最小の商品観測値。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MarketListingObservation:
    marketplace: str
    external_id: str
    name: str
    price: int
    start_price: int
    bidding: int
    time: str
    url: str

    def as_closed_item(self) -> dict[str, object]:
        return {
            "name": self.name,
            "price": self.price,
            "startPrice": self.start_price,
            "bidding": self.bidding,
            "time": self.time,
            "url": self.url,
        }

    def as_current_item(self, remaining_time: str) -> dict[str, object]:
        return {
            "name": self.name,
            "currentPrice": self.price,
            "bidding": self.bidding,
            "remainingTime": remaining_time,
            "url": self.url,
        }
