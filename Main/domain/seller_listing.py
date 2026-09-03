"""出品URLとユーザー入力値の厳密な検証。"""

import re
from urllib.parse import urlsplit

MAX_MONEY = 1_000_000_000_000


def normalize_listing_url(value: object) -> tuple[str, str]:
    if not isinstance(value, str) or re.search(r"[\x00-\x20\x7f]", value):
        raise ValueError("YahooオークションのHTTPS商品URLを指定してください")
    try:
        url = urlsplit(value)
        if (
            url.scheme != "https"
            or url.hostname != "auctions.yahoo.co.jp"
            or url.username is not None
            or url.password is not None
            or url.port not in (None, 443)
        ):
            raise ValueError
        match = re.fullmatch(r"/jp/auction/([a-z]?\d{8,20})/?", url.path, re.I)
        if not match:
            raise ValueError
    except ValueError as error:
        raise ValueError("YahooオークションのHTTPS商品URLを指定してください") from error
    auction_id = match.group(1).lower()
    return f"https://auctions.yahoo.co.jp/jp/auction/{auction_id}", auction_id


def money(value: object) -> int:
    if isinstance(value, bool) or not re.fullmatch(r"\d{1,13}", str(value), re.ASCII):
        raise ValueError("金額は0〜1兆円の整数で指定してください")
    result = int(str(value))
    if result > MAX_MONEY:
        raise ValueError("金額は0〜1兆円の整数で指定してください")
    return result
