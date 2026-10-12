from datetime import UTC, datetime, timedelta

from Main.services.recommendations import SnapshotPair, select_recommendations

NOW = datetime(2026, 10, 11, 12, 0, tzinfo=UTC)
OBSERVED = NOW - timedelta(hours=1)


def _item(auction_id: str, *, status="buy", score=75, remaining=7200, **extra):
    item = {
        "name": f"商品 {auction_id}",
        "url": f"https://auctions.yahoo.co.jp/jp/auction/{auction_id}",
        "imageUrl": f"https://auctions.c.yimg.jp/images/{auction_id}.jpg",
        "price": 10000,
        "remainingSeconds": remaining,
        "remainingTime": "2時間",
        "marketMedian": 20000,
        "condition": "used",
        "conditionLabel": "中古・動作品",
        "bidding": 1,
        "buyDecision": {"status": status, "label": "買い時", "score": score},
        "marketComparison": {"differenceRate": -50.0},
    }
    item.update(extra)
    return item


def _pair(items, previous_urls=None, name="カメラ"):
    return SnapshotPair(
        saved_search_name=name,
        keyword=name,
        observed_at=OBSERVED,
        items=items,
        median_price=20000,
        previous_urls=previous_urls,
    )


def _urls(recommendations):
    return [item.url.rsplit("/", 1)[1] for item in recommendations]


def test_only_buy_and_strong_buy_candidates_are_recommended():
    pair = _pair(
        [
            _item("a10000001", status="strong_buy", score=90),
            _item("a10000002", status="buy", score=75),
            _item("a10000003", status="consider", score=60),
            _item("a10000004", status="caution", score=30),
            _item("a10000005", buyDecision=None),
        ]
    )

    assert _urls(select_recommendations([pair], set(), now=NOW)) == ["a10000001", "a10000002"]


def test_watched_ended_and_unsafe_items_are_excluded():
    pair = _pair(
        [
            _item("a10000001"),
            _item("a10000002", remaining=1800),  # ended 30 minutes ago
            _item("a10000003", url="https://evil.example.com/jp/auction/a10000003"),
            _item("a10000004", url="javascript:alert(1)"),
            _item("a10000005", price=0),
            _item("a10000006"),
        ]
    )
    watched = {"https://auctions.yahoo.co.jp/jp/auction/a10000006"}

    assert _urls(select_recommendations([pair], watched, now=NOW)) == ["a10000001"]


def test_unknown_end_time_is_kept_and_disallowed_images_are_blanked():
    pair = _pair([_item("a10000001", remaining=None, imageUrl="https://evil.example.com/x.jpg")])

    [recommendation] = select_recommendations([pair], set(), now=NOW)

    assert recommendation.ends_at is None
    assert recommendation.image_url == ""


def test_new_items_come_first_then_score_then_earliest_end():
    previous = {"https://auctions.yahoo.co.jp/jp/auction/a10000001"}
    pair = _pair(
        [
            _item("a10000001", status="strong_buy", score=95),  # seen before
            _item("a10000002", score=75, remaining=9000),
            _item("a10000003", score=80, remaining=9000),
            _item("a10000004", score=75, remaining=5000),
        ],
        previous_urls=previous,
    )

    result = select_recommendations([pair], set(), now=NOW)

    assert _urls(result) == ["a10000003", "a10000004", "a10000002", "a10000001"]
    assert [item.is_new for item in result] == [True, True, True, False]


def test_first_snapshot_marks_nothing_new():
    [recommendation] = select_recommendations([_pair([_item("a10000001")])], set(), now=NOW)

    assert recommendation.is_new is False


def test_duplicates_across_saved_searches_keep_the_highest_score_and_limit_applies():
    first = _pair([_item("a10000001", score=75)], name="A")
    second = _pair([_item("a10000001", status="strong_buy", score=92)], name="B")
    many = _pair([_item(f"b{index:08d}") for index in range(10)], name="C")

    result = select_recommendations([first, second, many], set(), now=NOW, limit=6)

    assert len(result) == 6
    assert result[0].saved_search_name == "B"
    assert result[0].decision_score == 92


def test_card_values_and_watch_payload():
    [recommendation] = select_recommendations([_pair([_item("a10000001")])], set(), now=NOW)

    assert recommendation.difference_label == "相場比 -50.0%"
    assert recommendation.market_position == "below"
    assert recommendation.bidding == 1
    assert recommendation.condition == "used"
    assert recommendation.ends_at == OBSERVED + timedelta(seconds=7200)
    assert recommendation.watch_payload == {
        "name": "商品 a10000001",
        "url": "https://auctions.yahoo.co.jp/jp/auction/a10000001",
        "imageUrl": "https://auctions.c.yimg.jp/images/a10000001.jpg",
        "currentPrice": 10000,
        "marketMedian": 20000,
        "bidding": 1,
        "condition": "used",
        "conditionLabel": "中古・動作品",
        "remainingTime": "2時間",
        "remainingSeconds": 7200,
        "searchKeyword": "カメラ",
    }


def test_price_above_market_shows_a_positive_difference():
    pair = _pair([_item("a10000001", marketComparison={"differenceRate": 12.0})])

    [recommendation] = select_recommendations([pair], set(), now=NOW)

    assert recommendation.difference_label == "相場比 +12.0%"
    assert recommendation.market_position == "near"
