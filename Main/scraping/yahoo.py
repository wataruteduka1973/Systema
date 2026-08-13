import json
import re

from bs4 import BeautifulSoup


class YahooAuctionParser:
    @staticmethod
    def _safe_int(value):
        if value is None:
            return 0
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            digits = re.sub(r"[^\d]", "", value)
            return int(digits) if digits else 0
        return 0

    @staticmethod
    def _normalize_time_value(value):
        if value is None or value == "N/A":
            return "N/A"

        text = str(value).strip()
        if not text:
            return "N/A"
        if re.match(r"^\d{4}-\d{2}-\d{2}[T\s]", text):
            return text

        tokens = re.findall(r"(\d+)\s*(日|時間|分|秒)", text)
        if not tokens:
            return text

        return "".join(f"{amount}{unit}" for amount, unit in tokens)

    @staticmethod
    def _is_valid_title_text(text):
        if not text:
            return False

        cleaned = re.sub(r"\s+", " ", text).strip()
        if not cleaned or len(cleaned) < 2:
            return False
        if re.fullmatch(
            r"(?i)(?:商品リンクURL|商品リンク|help|ヘルプ|ログイン|マイページ|検索|トップ|カテゴリ|お問い合わせ|規約|プライバシー|検索条件)",
            cleaned,
        ):
            return False
        if re.fullmatch(r"(?i)(?:itemid|auctionid|id)[\s:：]*[a-z0-9]+", cleaned):
            return False
        if re.fullmatch(r"(?i)z\d+", cleaned):
            return False
        if re.fullmatch(r"[\d\s\-_/,]+", cleaned):
            return False
        # Exclude UI component names (Item prefix, camelCase patterns, common UI keywords)
        if cleaned.startswith("Item "):
            return False
        if re.search(
            r"(?:Filter|Expand|Sort|Mode|Link|Controls|Conditions|Select|__next|wrapper|acls)",
            cleaned,
            re.IGNORECASE,
        ):
            return False
        # Exclude pure camelCase identifiers without proper nouns (likely internal class/ID names)
        if re.fullmatch(r"[a-z][a-zA-Z0-9]*$", cleaned) and len(cleaned) < 5:
            return False
        return True

    @staticmethod
    def _pick_title_tag(card):
        selectors = [
            ".Product__titleLink.js-browseHistory-add.js-rapid-override",
            ".Product__titleLink.js-browseHistory-add",
            ".Product__titleLink",
        ]
        for selector in selectors:
            tag = card.select_one(selector)
            if tag and tag.get("title"):
                return tag
            if tag and YahooAuctionParser._is_valid_title_text(tag.get_text(" ", strip=True)):
                return tag

        # Fallback for generic product card markup that does not use Product__titleLink
        fallback = card.select_one(
            'a[href*="/jp/auction/"], a[href*="/item/"], a[href*="yahoo.co.jp/jp/auction/"], a[href*="paypayfleamarket.yahoo.co.jp/item/"], h3, h4, span.title, .title, .item-name'
        )
        if fallback and YahooAuctionParser._is_valid_title_text(fallback.get_text(" ", strip=True)):
            return fallback
        return None

    @staticmethod
    def _find_item_list(node):
        if isinstance(node, list):
            for item in node:
                result = YahooAuctionParser._find_item_list(item)
                if result is not None:
                    return result
            return None

        if isinstance(node, dict):
            if "items" in node and isinstance(node["items"], list):
                candidate_items = node["items"]
                if candidate_items and all(isinstance(item, dict) for item in candidate_items[:3]):
                    if any("title" in item or "name" in item for item in candidate_items[:3]):
                        return candidate_items
            for value in node.values():
                result = YahooAuctionParser._find_item_list(value)
                if result is not None:
                    return result

        return None

    @classmethod
    def extract_listing_items(cls, html):
        if not html:
            return []

        match = re.search(
            r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html, re.S | re.I
        )
        if match:
            try:
                payload = json.loads(match.group(1))
                items = cls._find_item_list(payload)
                if items:
                    return items
            except (TypeError, ValueError, json.JSONDecodeError):
                pass

        soup = BeautifulSoup(html, "html.parser")
        extracted = []
        seen_ids = set()

        # Match product containers only.  ``[class*="Product"]`` also matches
        # nested elements such as Product__badge and Product__titleLink, which
        # can turn promotional labels into duplicate, zero-price listings.
        product_cards = soup.select(".Product, [data-auction-id], [data-item-id]")
        if product_cards:
            for card in product_cards:
                if card.name in {"nav", "header", "footer", "aside", "script", "style"}:
                    continue
                if card.find_parent(["nav", "header", "footer", "aside"]):
                    continue

                title_tag = YahooAuctionParser._pick_title_tag(card)
                if not title_tag:
                    continue

                title_text = title_tag.get_text(" ", strip=True)
                if not YahooAuctionParser._is_valid_title_text(title_text):
                    continue

                href = title_tag.get("href") or ""
                auction_id = (
                    card.get("data-auction-id")
                    or card.get("data-item-id")
                    or card.get("id")
                    or re.search(r"z\d+", href or "")
                )
                if isinstance(auction_id, re.Match):
                    auction_id = auction_id.group(0)
                auction_id = str(auction_id) if auction_id else None

                if re.search(
                    r"^(yahoo!\s*japan|help|ヘルプ|ログイン|マイページ|検索|トップ|カテゴリ|お問い合わせ|規約|プライバシー)$",
                    title_text,
                    re.I,
                ):
                    continue

                price_tag = card.select_one(
                    '.Product__priceValue:not(.Product__priceValue--start), .Product__priceValue, .price, [class*="Product__priceValue"]'
                )
                price_text = price_tag.get_text(" ", strip=True) if price_tag else ""

                bid_tag = card.select_one(
                    '.Product__bid, dd[class*="Product__bid"], [class*="Product__bid"]'
                )
                bid_text = bid_tag.get_text(" ", strip=True) if bid_tag else ""

                time_tag = card.select_one('.Product__time, [class*="Product__time"]')
                time_text = time_tag.get_text(" ", strip=True) if time_tag else "N/A"

                key = str(
                    auction_id
                    or (re.search(r"z\d+", href or "") and re.search(r"z\d+", href or "").group(0))
                    or title_text
                )
                if key in seen_ids:
                    continue
                seen_ids.add(key)

                data = {
                    "title": title_text,
                    "price": cls._safe_int(price_text),
                    "bidding": cls._safe_int(bid_text),
                    "time": cls._normalize_time_value(time_text),
                    "auctionId": auction_id,
                    "url": cls.build_item_url(
                        href,
                        auction_id,
                        {
                            "isFleamarketItem": "paypayfleamarket.yahoo.co.jp" in href
                            or "item/" in href
                        },
                    ),
                }
                if not data["url"] or data["url"] == "#":
                    data["url"] = cls.build_item_url(
                        href or "",
                        auction_id,
                        {
                            "isFleamarketItem": "paypayfleamarket.yahoo.co.jp" in href
                            or "item/" in href
                        },
                    )
                extracted.append(data)
            return extracted

        for card in soup.select("article, li, div, tr"):
            if card.name in {"nav", "header", "footer", "aside", "script", "style"}:
                continue
            if card.find_parent(["nav", "header", "footer", "aside"]):
                continue

            auction_id = card.get("data-auction-id") or card.get("data-item-id") or card.get("id")
            title_tag = card.select_one(
                'a[href*="/jp/auction/"], a[href*="/item/"], a[href*="yahoo.co.jp/jp/auction/"], a[href*="paypayfleamarket.yahoo.co.jp/item/"], h3, h4, span.title, .title, .item-name'
            )
            href = title_tag.get("href") if title_tag else ""
            if not (title_tag or auction_id or href):
                continue

            title_text = title_tag.get_text(" ", strip=True) if title_tag else ""
            if not title_text and auction_id:
                title_text = f"Item {auction_id}"

            if not title_text or len(title_text) < 2:
                continue

            if re.search(
                r"^(yahoo!\s*japan|help|ヘルプ|ログイン|マイページ|検索|トップ|カテゴリ|お問い合わせ|規約|プライバシー)$",
                title_text,
                re.I,
            ):
                continue

            auction_match = re.search(r"z\d+", href or str(auction_id or ""))
            if not auction_id and not auction_match:
                continue

            price_text = None
            for candidate in card.select("span, strong, div, p"):
                text = candidate.get_text(" ", strip=True)
                if re.search(r"\d", text) and len(text) <= 40:
                    price_text = text
                    break
            if not price_text and not auction_id:
                continue

            key = str(auction_id or (auction_match.group(0) if auction_match else title_text))
            if key in seen_ids:
                continue
            seen_ids.add(key)

            data = {
                "title": title_text,
                "price": cls._safe_int(price_text) if price_text else 0,
            }
            if auction_id:
                data["auctionId"] = auction_id
            if href:
                data["url"] = href
            extracted.append(data)

        return extracted

    @staticmethod
    def build_item_url(raw_url, auction_id=None, item=None):
        if raw_url:
            value = str(raw_url).strip()
            if value.startswith("http://") or value.startswith("https://"):
                return value
            if value.startswith("//"):
                return "https:" + value
            if value.startswith("/item/") or value.startswith("item/") or value.startswith("z"):
                if value.startswith("z"):
                    return (
                        f"https://paypayfleamarket.yahoo.co.jp/item/{value}"
                        if auction_id is None or value.startswith(str(auction_id))
                        else f"https://paypayfleamarket.yahoo.co.jp/item/{auction_id}"
                    )
                return (
                    f"https://paypayfleamarket.yahoo.co.jp/{value}"
                    if value.startswith("item/")
                    else f"https://paypayfleamarket.yahoo.co.jp/item/{value.lstrip('/')}"
                )
            if "paypayfleamarket.yahoo.co.jp" in value:
                return value if value.startswith("http") else f'https://{value.lstrip("/")}'
            if value.startswith("/"):
                return "https://auctions.yahoo.co.jp" + value
            if value.startswith("jp/auction/") or value.startswith("auction/"):
                return "https://auctions.yahoo.co.jp/" + value
            return value
        if not auction_id:
            return "#"

        is_flea = bool(item and item.get("isFleamarketItem") is True)
        if is_flea:
            return f"https://paypayfleamarket.yahoo.co.jp/item/{auction_id}"

        return f"https://auctions.yahoo.co.jp/jp/auction/{auction_id}"

    @classmethod
    def normalize_item(cls, item):
        if not isinstance(item, dict):
            return {}

        auction_id = item.get("auctionId") or item.get("itemId") or item.get("id")
        raw_url = (
            item.get("url")
            or item.get("auctionUrl")
            or item.get("itemUrl")
            or item.get("link")
            or item.get("itemPath")
            or item.get("auctionUrlPath")
        )
        normalized_url = cls.build_item_url(raw_url, auction_id, item)

        title = item.get("title") or item.get("name") or item.get("itemName") or "N/A"
        price = cls._safe_int(
            item.get("currentPrice")
            or item.get("price")
            or item.get("current_price")
            or item.get("priceValue")
        )
        start_price = cls._safe_int(
            item.get("startPrice")
            or item.get("initPriceNoTax")
            or item.get("startingPrice")
            or item.get("initialPrice")
            or item.get("price")
        )
        bidding = cls._safe_int(
            item.get("bidCount")
            or item.get("bidding")
            or item.get("bidderCount")
            or item.get("bidNum")
        )
        time_value = (
            item.get("endTime")
            or item.get("remainingTime")
            or item.get("time")
            or item.get("endAt")
            or "N/A"
        )

        return {
            "title": title,
            "name": title,
            "price": price,
            "startPrice": start_price,
            "bidding": bidding,
            "time": cls._normalize_time_value(time_value),
            "url": normalized_url,
            "auctionId": auction_id,
        }
