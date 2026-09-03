"""公開商品詳細の取得・解析。検索結果の候補を出品本体として扱わない。"""

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from Main.domain.seller_listing import money, normalize_listing_url
from Main.infrastructure.http import get_with_retry


class ListingParseError(ValueError):
    pass


@dataclass(frozen=True)
class ListingObservation:
    name: str
    current_price: int
    bidding: int
    ends_at: datetime
    status: str
    start_price: int = 0
    buyout_price: int | None = None
    starts_at: datetime | None = None


def _timestamp(value: object) -> datetime:
    result = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError
    return result


def parse_listing(html: str, auction_id: str) -> ListingObservation:
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")
    try:
        if script is None:
            raise ValueError
        item = json.loads(script.get_text())["props"]["pageProps"]["initialState"]["item"][
            "detail"
        ]["item"]
        if not isinstance(item, dict) or str(item.get("auctionId", "")).lower() != auction_id:
            raise ValueError
        name = item.get("title") or item.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError
        price = money(item["price"])
        bidding = money(item["bids"])
        if bidding > 2_147_483_647:
            raise ValueError
        ends_at = _timestamp(item["endTime"])
        if item.get("status") not in {"open", "closed", "ended"}:
            raise ValueError
        status = "ended" if ends_at <= datetime.now(timezone.utc) else "active"
        if item.get("status") in {"closed", "ended"}:
            status = "ended"
        return ListingObservation(
            name[:1000],
            price,
            bidding,
            ends_at,
            status,
            start_price=money(item["initPrice"]) if "initPrice" in item else 0,
            buyout_price=money(item["bidorbuy"]) if item.get("bidorbuy") is not None else None,
            starts_at=_timestamp(item["startTime"]) if item.get("startTime") else None,
        )
    except (ValueError, TypeError, KeyError, RecursionError) as error:
        raise ListingParseError(
            "商品詳細を解析できませんでした。保存済み情報は変更していません"
        ) from error


def fetch_listing(url: str) -> ListingObservation:
    canonical, auction_id = normalize_listing_url(url)
    response = get_with_retry(canonical, {"User-Agent": "Mozilla/5.0"}, max_retries=1, timeout=15)
    try:
        return parse_listing(response.text, auction_id)
    finally:
        response.close()
