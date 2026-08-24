import json

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from Main.models.savedsearch import SavedSearch
from Main.models.searchrun import SearchRun
from Main.models.searchwordlog import searchwordlog
from Main.views import utils

pytestmark = pytest.mark.django_db


def payload(**overrides):
    values = {
        "name": "中古カメラ",
        "keyword": "カメラ",
        "condition": "used",
        "minimumPrice": 1000,
        "maximumPrice": 10000,
        "excludedKeywords": ["ジャンク"],
        "sortOrder": "price-asc",
        "isActive": True,
    }
    return {**values, **overrides}


def test_saved_search_crud_requires_login(client):
    assert client.get(reverse("saved_searches")).status_code == 401
    assert (
        client.post(
            reverse("saved_searches"), data="{}", content_type="application/json"
        ).status_code
        == 401
    )


def test_saved_search_crud_is_limited_to_owner(client):
    first = get_user_model().objects.create_user("saved-first", password="password")
    second = get_user_model().objects.create_user("saved-second", password="password")
    client.force_login(first)
    created_response = client.post(
        reverse("saved_searches"),
        json.dumps(payload()),
        content_type="application/json",
    )
    item_id = created_response.json()["item"]["id"]

    assert created_response.status_code == 201
    assert client.get(reverse("saved_searches")).json()["items"][0]["keyword"] == "カメラ"

    client.force_login(second)
    detail_url = reverse("saved_search_item", args=(item_id,))
    assert client.get(detail_url).status_code == 404
    assert client.patch(detail_url, data="{}", content_type="application/json").status_code == 404
    assert client.delete(detail_url).status_code == 404
    assert client.post(reverse("run_saved_search", args=(item_id,))).status_code == 404


def test_saved_search_update_validates_common_search_criteria(client):
    user = get_user_model().objects.create_user("saved-update", password="password")
    item = SavedSearch.objects.create(
        user=user,
        name="更新前",
        keyword="時計",
    )
    client.force_login(user)

    response = client.patch(
        reverse("saved_search_item", args=(item.pk,)),
        json.dumps({"minimumPrice": 5000, "maximumPrice": 1000}),
        content_type="application/json",
    )

    assert response.status_code == 400
    item.refresh_from_db()
    assert item.minimum_price == 0
    assert item.maximum_price is None


def test_target_auto_save_replaces_same_named_condition(client):
    user = get_user_model().objects.create_user("saved-auto", password="password")
    existing = SavedSearch.objects.create(
        user=user,
        name="カメラ",
        keyword="古い条件",
    )
    client.force_login(user)

    response = client.post(
        reverse("saved_searches"),
        json.dumps(payload(name="カメラ", keyword="新しい条件", replaceExisting=True)),
        content_type="application/json",
    )

    assert response.status_code == 200
    assert SavedSearch.objects.filter(user=user, name="カメラ").count() == 1
    existing.refresh_from_db()
    assert existing.keyword == "新しい条件"


def test_saved_search_run_links_snapshot_and_survives_saved_search_deletion(client, monkeypatch):
    user = get_user_model().objects.create_user("saved-run", password="password")
    item = SavedSearch.objects.create(
        user=user,
        name="実行条件",
        keyword="カメラ",
        minimum_price=1000,
        ending_within_minutes=60,
    )
    monkeypatch.setattr(
        utils,
        "scrape_data",
        lambda keyword: [{"name": "中古カメラ", "price": 3000}],
    )
    monkeypatch.setattr(
        utils,
        "scrape_current_listings",
        lambda keyword: [
            {
                "name": "中古カメラ出品",
                "currentPrice": 2000,
                "bidding": 1,
                "remainingTime": "30分",
                "url": "https://example.com/camera",
            }
        ],
    )
    client.force_login(user)

    response = client.post(reverse("run_saved_search", args=(item.pk,)))
    runs = list(SearchRun.objects.order_by("search_type"))
    current_run = next(run for run in runs if run.search_type == SearchRun.CURRENT)

    assert response.status_code == 200
    assert len(runs) == 2
    assert all(run.user == user for run in runs)
    assert all(run.saved_search == item for run in runs)
    assert all(run.trigger == "saved" for run in runs)
    assert all(run.criteria_snapshot["minimumPrice"] == 1000 for run in runs)
    assert current_run.result_snapshot["recommend_items"][0]["name"] == "中古カメラ出品"
    assert current_run.result_snapshot["medianPrice"] == 3000
    item.refresh_from_db()
    assert item.last_run_at is not None
    profile_content = client.get(reverse("profile"), {"saved_search": item.pk}).content.decode(
        "utf-8"
    )
    assert "中古カメラ出品" in profile_content

    assert client.delete(reverse("saved_search_item", args=(item.pk,))).status_code == 200
    for run in runs:
        run.refresh_from_db()
        assert run.saved_search is None
        assert run.criteria_snapshot["keyword"] == "カメラ"


def test_profile_owns_saved_search_management_and_market_search_has_no_save_controls(client):
    user = get_user_model().objects.create_user("saved-profile", password="password")
    other = get_user_model().objects.create_user("saved-other", password="password")
    SavedSearch.objects.create(
        user=user,
        name="プロフィール条件",
        keyword="レンズ",
    )
    SavedSearch.objects.create(user=other, name="他人の条件", keyword="非公開キーワード")
    client.force_login(user)

    profile_content = client.get(reverse("profile")).content.decode("utf-8")
    market_content = client.get(reverse("market_search")).content.decode("utf-8")
    target_content = client.get(reverse("Deep_Analysis_now")).content.decode("utf-8")

    assert "プロフィール条件" in profile_content
    assert "条件を作成して実行" in profile_content
    assert "条件を保存" not in market_content
    assert "保存条件を適用" not in market_content
    assert 'id="targetSearchForm"' in target_content
    assert target_content.count('id="search"') == 1
    assert "検索・分析・自動保存" in target_content
    assert "保存した分析条件" in target_content
    assert "この条件で分析" in target_content
    assert "変更を保存" in target_content
    assert "削除" in target_content
    assert 'class="saved-search-edit row g-2 align-items-end mt-2"' in target_content
    assert 'class="btn btn-sm btn-outline-danger saved-search-delete"' in target_content
    assert "レンズ" in target_content
    assert "非公開キーワード" not in target_content
    assert 'data-saved-search-surface="target"' in target_content
    assert 'id="targetSavedName"' not in target_content
    assert 'id="savedName"' not in profile_content
    assert 'name="maximumPrice"' in profile_content
    assert 'name="excludedKeywords"' in profile_content
    assert 'name="endingWithinMinutes"' in profile_content
    assert 'name="searchType"' not in profile_content
    assert 'name="searchType"' not in target_content


def test_popular_words_are_limited_to_current_user(client):
    first = get_user_model().objects.create_user("words-first", password="password")
    second = get_user_model().objects.create_user("words-second", password="password")
    searchwordlog.objects.create(user=first, word="private-camera")
    searchwordlog.objects.create(user=second, word="private-watch")

    client.force_login(first)
    words = client.get(reverse("get_popular_words")).json()["words"]

    assert "private-camera" in words
    assert "private-watch" not in words
