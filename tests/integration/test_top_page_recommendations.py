from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from Main.models.savedsearch import SavedSearch
from Main.models.searchrun import SearchRun
from Main.models.watchitem import WatchItem
from Main.services.recommendations import recommendations_for

pytestmark = pytest.mark.django_db


def _item(auction_id, *, name=None, status="strong_buy", score=90, image=True):
    return {
        "name": name or f"おすすめ商品 {auction_id}",
        "url": f"https://auctions.yahoo.co.jp/jp/auction/{auction_id}",
        "imageUrl": f"https://auctions.c.yimg.jp/images/{auction_id}.jpg" if image else "",
        "price": 12000,
        "remainingSeconds": 7200,
        "remainingTime": "2時間",
        "marketMedian": 22500,
        "condition": "used",
        "conditionLabel": "中古・動作品",
        "bidding": 2,
        "buyDecision": {"status": status, "label": "かなり買い時", "score": score},
        "marketComparison": {"differenceRate": -46.7},
    }


def _run(saved, items, *, succeeded=True, minutes_ago=10):
    run = SearchRun.objects.create(
        user=saved.user,
        saved_search=saved,
        keyword=saved.keyword,
        search_type=SearchRun.CURRENT,
        item_count=len(items),
        succeeded=succeeded,
        result_snapshot={"medianPrice": 22500, "recommend_items": items} if succeeded else {},
        trigger="saved",
    )
    SearchRun.objects.filter(pk=run.pk).update(
        created_at=timezone.now() - timedelta(minutes=minutes_ago)
    )
    run.refresh_from_db()
    return run


def _user(name):
    return get_user_model().objects.create_user(name, password="password")


def test_recommendations_are_owner_scoped_and_skip_inactive_or_failed_runs():
    owner, other = _user("rec-owner"), _user("rec-other")
    saved = SavedSearch.objects.create(user=owner, name="ゲーム機", keyword="ゲーム機")
    inactive = SavedSearch.objects.create(
        user=owner, name="停止中", keyword="停止中", is_active=False
    )
    others = SavedSearch.objects.create(user=other, name="他人", keyword="他人")
    _run(saved, [_item("a10000001")])
    _run(saved, [], succeeded=False, minutes_ago=1)  # newer failure is ignored
    _run(inactive, [_item("a10000002")])
    _run(others, [_item("a10000003")])

    section = recommendations_for(owner)

    assert section.has_saved_searches is True
    assert [item.url[-9:] for item in section.items] == ["a10000001"]
    assert [item.url[-9:] for item in recommendations_for(other).items] == ["a10000003"]


def test_items_missing_from_the_previous_snapshot_are_marked_new():
    owner = _user("rec-new")
    saved = SavedSearch.objects.create(user=owner, name="カメラ", keyword="カメラ")
    _run(saved, [_item("a10000001")], minutes_ago=120)
    _run(saved, [_item("a10000001"), _item("a10000002", score=80)], minutes_ago=5)

    items = recommendations_for(owner).items

    assert [(item.url[-9:], item.is_new) for item in items] == [
        ("a10000002", True),
        ("a10000001", False),
    ]


def test_watched_items_are_not_recommended_again():
    owner = _user("rec-watch")
    saved = SavedSearch.objects.create(user=owner, name="カメラ", keyword="カメラ")
    _run(saved, [_item("a10000001"), _item("a10000002")])
    WatchItem.objects.create(
        user=owner, name="x", url="https://auctions.yahoo.co.jp/jp/auction/a10000001"
    )

    assert [item.url[-9:] for item in recommendations_for(owner).items] == ["a10000002"]


def test_anonymous_top_page_invites_login(client):
    content = client.get(reverse("index")).content.decode("utf-8")

    assert "あなたへのおすすめ" in content
    assert reverse("login") in content
    assert "サンプル表示" not in content
    assert "Recommendations.js" not in content


def test_user_without_saved_searches_is_pointed_to_target_analysis(client):
    client.force_login(_user("rec-empty"))

    content = client.get(reverse("index")).content.decode("utf-8")

    assert "ターゲット分析で検索すると条件が保存され" in content
    assert "recommendation-card" not in content


def test_saved_searches_without_candidates_show_last_fetch(client):
    owner = _user("rec-none")
    saved = SavedSearch.objects.create(user=owner, name="カメラ", keyword="カメラ")
    _run(saved, [_item("a10000001", status="consider", score=60)])
    client.force_login(owner)

    content = client.get(reverse("index")).content.decode("utf-8")

    assert "いまおすすめできる商品はありません" in content
    assert "の取得結果" in content


def test_cards_render_escaped_names_safe_images_and_watch_payloads(client):
    owner = _user("rec-cards")
    saved = SavedSearch.objects.create(user=owner, name="カメラ", keyword="カメラ")
    _run(
        saved,
        [
            _item("a10000001", name="<script>alert(1)</script>中古カメラ"),
            _item("a10000002", image=False),
        ],
    )
    client.force_login(owner)

    content = client.get(reverse("index")).content.decode("utf-8")

    assert content.count('class="hot-pick-card recommendation-card"') == 2
    assert "<script>alert(1)</script>" not in content
    assert "&lt;script&gt;alert(1)&lt;/script&gt;中古カメラ" in content
    assert 'src="https://auctions.c.yimg.jp/images/a10000001.jpg"' in content
    assert content.count('referrerpolicy="no-referrer"') == 1
    assert "相場より47%安い" in content
    assert "¥12,000" in content
    assert 'id="recommendationPayloads"' in content
    assert "Recommendations.js" in content
    assert 'rel="noopener noreferrer"' in content
