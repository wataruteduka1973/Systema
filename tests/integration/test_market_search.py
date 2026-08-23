from pathlib import Path

import pytest
from django.urls import reverse


@pytest.mark.django_db
@pytest.mark.parametrize("mode", ["closed", "current", "history"])
def test_market_search_renders_all_modes_and_selects_requested_mode(client, mode):
    response = client.get(reverse("market_search"), {"mode": mode})

    assert response.status_code == 200
    assert response.context["active_mode"] == mode
    assert [item["key"] for item in response.context["modes"]] == [
        "closed",
        "current",
        "history",
    ]
    content = response.content.decode()
    assert "落札相場" in content
    assert "現在価格" in content
    assert "保存済みデータ" in content
    assert f'data-mode="{mode}"' in content
    assert "<iframe" not in content
    assert "JS/MarketSearch.js" in content


@pytest.mark.django_db
def test_market_search_falls_back_to_closed_mode(client):
    response = client.get(reverse("market_search"), {"mode": "invalid"})

    assert response.status_code == 200
    assert response.context["active_mode"] == "closed"


def test_popular_word_button_appends_without_overwriting_existing_input():
    script = Path("Main/static/JS/MarketSearch.js").read_text(encoding="utf-8")

    assert "currentWords.push(word)" in script
    assert "el.keyword.value = currentWords.join(' ')" in script
    assert "el.keyword.value = word" not in script


def test_saved_data_refresh_uses_the_same_criteria_parameters_as_search():
    script = Path("Main/static/JS/MarketSearch.js").read_text(encoding="utf-8")

    assert "function criteriaParams(keyword)" in script
    assert "update_market_data?${criteriaParams(keyword).toString()}" in script


@pytest.mark.django_db
@pytest.mark.parametrize("view_name", ["yahuoku", "yahuoku_now", "yahuoku_history"])
def test_embedded_market_pages_hide_duplicate_navigation(client, view_name):
    response = client.get(reverse(view_name), {"embedded": "1"})

    assert response.status_code == 200
    assert "navbarNav" not in response.content.decode()
