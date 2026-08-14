import pytest

from Main.domain.product_condition import (
    classify_product_condition,
    enrich_market_items,
    summarize_condition_market,
)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("title", "expected"),
    [
        ("新品 未開封 RTX3060", "new"),
        ("中古 動作確認済み RTX3060", "used"),
        ("未使用に近い GPU", "used"),
        ("ジャンク 部品取り GPU", "junk"),
        ("RTX3060 グラフィックボード", "unknown"),
    ],
)
def test_classify_product_condition(title, expected):
    assert classify_product_condition(title)["condition"] == expected


@pytest.mark.unit
def test_classify_product_attributes():
    result = classify_product_condition("中古 動作確認済 本体のみ 元箱あり 送料無料")
    assert result["attributes"] == ["tested", "body_only", "box_included", "free_shipping"]


@pytest.mark.unit
def test_enrich_market_items_preserves_existing_fields():
    result = enrich_market_items([{"name": "新品 商品", "price": 1000, "url": "#"}])
    assert result[0]["price"] == 1000
    assert result[0]["url"] == "#"
    assert result[0]["conditionLabel"] == "新品・未使用"


@pytest.mark.unit
def test_summarize_condition_market_excludes_junk_from_regular_median():
    items = enrich_market_items(
        [
            {"name": "新品 商品", "price": 3000},
            {"name": "中古 商品", "price": 2000},
            {"name": "ジャンク 商品", "price": 100},
            {"name": "状態記載なし", "price": 1000},
        ]
    )
    summary = summarize_condition_market(items)
    assert summary["medianPriceExcludingJunk"] == 2000
    assert summary["classifiedCount"] == 3
    assert summary["totalCount"] == 4


@pytest.mark.unit
def test_summarize_condition_market_uses_current_price_when_available():
    items = enrich_market_items(
        [
            {"name": "新品 商品", "price": 100, "currentPrice": 3000},
            {"name": "中古 商品", "currentPrice": 1000},
        ]
    )

    summary = summarize_condition_market(items)

    assert summary["medianPriceExcludingJunk"] == 2000
