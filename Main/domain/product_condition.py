"""商品名からコンディションを分類し、状態別相場を集計する。"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from statistics import median
from typing import Any

CONDITION_LABELS = {
    "new": "新品・未使用",
    "used": "中古・動作品",
    "junk": "ジャンク・故障品",
    "unknown": "未分類",
}

ATTRIBUTE_LABELS = {
    "tested": "動作確認済み",
    "body_only": "本体のみ",
    "accessories_included": "付属品あり",
    "box_included": "箱あり",
    "lot": "まとめ売り",
    "free_shipping": "送料無料",
}

_JUNK_WORDS = ("ジャンク", "故障", "不動", "動作未確認", "部品取り", "訳あり")
_NEW_WORDS = ("新品", "未開封", "未使用", "新品同様")
_USED_WORDS = ("中古", "used", "動作品", "動作確認済", "美品", "現状品")

_ATTRIBUTE_WORDS = {
    "tested": ("動作確認済", "動作品", "正常動作", "動作良好"),
    "body_only": ("本体のみ", "本体単品"),
    "accessories_included": ("付属品あり", "付属品完備", "一式", "フルセット"),
    "box_included": ("箱あり", "元箱", "外箱", "箱付き"),
    "lot": ("まとめ売り", "まとめて", "セット売り", "大量"),
    "free_shipping": ("送料無料", "送料込み"),
}


def classify_product_condition(title: object) -> dict[str, Any]:
    """商品名を主状態と補助属性へ分類する。"""
    text = str(title or "").strip()
    normalized = text.casefold().replace("　", " ")

    if any(word in normalized for word in _JUNK_WORDS):
        condition = "junk"
    elif "未使用に近い" in normalized:
        condition = "used"
    elif any(word in normalized for word in _NEW_WORDS):
        condition = "new"
    elif any(word in normalized for word in _USED_WORDS):
        condition = "used"
    else:
        condition = "unknown"

    attributes = [
        key for key, words in _ATTRIBUTE_WORDS.items() if any(word in normalized for word in words)
    ]
    return {
        "condition": condition,
        "conditionLabel": CONDITION_LABELS[condition],
        "attributes": attributes,
        "attributeLabels": [ATTRIBUTE_LABELS[key] for key in attributes],
    }


def enrich_market_items(items: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """既存の商品項目を維持し、コンディション項目を付加する。"""
    return [dict(item) | classify_product_condition(item.get("name")) for item in items]


def summarize_condition_market(items: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    """状態別の件数・価格中央値と、ジャンク除外中央値を返す。"""
    grouped: dict[str, list[float]] = {key: [] for key in CONDITION_LABELS}
    counts = {key: 0 for key in CONDITION_LABELS}

    for item in items:
        condition = str(item.get("condition", "unknown"))
        if condition not in CONDITION_LABELS:
            condition = "unknown"
        counts[condition] += 1
        price = item.get("currentPrice")
        if not isinstance(price, (int, float)) or isinstance(price, bool) or price <= 0:
            price = item.get("price")
        if isinstance(price, (int, float)) and not isinstance(price, bool) and price > 0:
            grouped[condition].append(float(price))

    conditions = [
        {
            "condition": condition,
            "label": label,
            "count": counts[condition],
            "medianPrice": int(median(grouped[condition])) if grouped[condition] else None,
        }
        for condition, label in CONDITION_LABELS.items()
    ]
    regular_prices = grouped["new"] + grouped["used"] + grouped["unknown"]
    return {
        "conditions": conditions,
        "medianPriceExcludingJunk": int(median(regular_prices)) if regular_prices else None,
        "classifiedCount": counts["new"] + counts["used"] + counts["junk"],
        "totalCount": sum(counts.values()),
    }
