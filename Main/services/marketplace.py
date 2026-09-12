"""検索ユースケースが利用する最小の市場取得契約。"""

from __future__ import annotations

from typing import Protocol

from Main.domain.market_listing import MarketListingObservation


class MarketplaceProvider(Protocol):
    marketplace: str

    def search_closed(self, keyword: str) -> list[MarketListingObservation]: ...

    def search_current(self, keyword: str) -> list[MarketListingObservation]: ...
