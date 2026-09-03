import pytest
from django.test import RequestFactory

from Main.services.exceptions import SearchInputError
from Main.services.search_criteria import SearchCriteria


def query(**values):
    return RequestFactory().get("/", values).GET


def test_criteria_normalizes_and_serializes_contract():
    criteria = SearchCriteria.from_query(
        query(
            keyword="  カメラ　 レンズ  ",
            condition="used",
            minimumPrice="1000",
            maximumPrice="5000",
            excludedKeywords="ジャンク, 部品取り,ジャンク",
            sortOrder="price-desc",
        ),
        "closed",
    )

    assert criteria.snapshot() == {
        "keyword": "カメラ レンズ",
        "searchType": "closed",
        "condition": "used",
        "minimumPrice": 1000,
        "maximumPrice": 5000,
        "excludedKeywords": ["ジャンク", "部品取り"],
        "endingWithinMinutes": None,
        "sortOrder": "price-desc",
    }


def test_criteria_rejects_invalid_price_range_and_search_specific_fields():
    with pytest.raises(SearchInputError):
        SearchCriteria.from_query(
            query(keyword="camera", minimumPrice=10, maximumPrice=5), "closed"
        )
    with pytest.raises(SearchInputError):
        SearchCriteria.from_query(query(keyword="camera", endingWithinMinutes=30), "closed")


def test_criteria_applies_exclusions_condition_price_and_sorting():
    criteria = SearchCriteria.from_query(
        query(
            keyword="camera",
            condition="used",
            minimumPrice=1000,
            maximumPrice=5000,
            excludedKeywords="部品取り",
            sortOrder="price-desc",
        ),
        "closed",
    )
    items = [
        {"name": "中古 カメラ A", "price": 2000},
        {"name": "中古 カメラ B", "price": 4500},
        {"name": "新品 カメラ", "price": 3000},
        {"name": "中古 部品取り", "price": 4000},
        {"name": "中古 高級カメラ", "price": 6000},
    ]

    result = criteria.apply(items)

    assert [item["price"] for item in result] == [4500, 2000]
    assert all(item["condition"] == "used" for item in result)


def test_current_criteria_applies_human_readable_remaining_time():
    criteria = SearchCriteria.from_query(
        query(keyword="camera", endingWithinMinutes=60),
        "current",
    )

    result = criteria.apply(
        [
            {"name": "まもなく終了", "currentPrice": 1000, "remainingTime": "45分"},
            {"name": "終了まで余裕", "currentPrice": 1000, "remainingTime": "2時間"},
            {"name": "終了時刻不明", "currentPrice": 1000, "remainingTime": "N/A"},
        ]
    )

    assert [item["name"] for item in result] == ["まもなく終了"]
