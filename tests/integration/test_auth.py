import json

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from Main.models.watchitem import WatchItem
from Main.models.searchrun import SearchRun
from Main.models.scraping import scraping
from Main.views import api


@pytest.mark.django_db
class TestAuthentication:
    def test_account_pages_render(self, client):
        assert client.get(reverse("login")).status_code == 200
        assert client.get(reverse("signup")).status_code == 200
        assert client.get(reverse("admin_setup")).status_code == 200

    def test_signup_creates_normal_user_and_logs_in(self, client):
        response = client.post(
            reverse("signup"),
            {
                "username": "new-user",
                "email": "new@example.com",
                "password1": "Long-test-password-2026",
                "password2": "Long-test-password-2026",
            },
        )

        user = get_user_model().objects.get(username="new-user")
        assert response.status_code == 302
        assert not user.is_staff
        assert not user.is_superuser
        assert client.session.get("_auth_user_id") == str(user.pk)

    def test_admin_setup_creates_only_first_superuser(self, client):
        response = client.post(
            reverse("admin_setup"),
            {
                "username": "initial-admin",
                "email": "admin@example.com",
                "password1": "Long-admin-password-2026",
                "password2": "Long-admin-password-2026",
            },
        )

        user = get_user_model().objects.get(username="initial-admin")
        assert response.status_code == 302
        assert user.is_staff
        assert user.is_superuser
        client.logout()
        blocked = client.get(reverse("admin_setup"))
        assert blocked.status_code == 302
        assert blocked.url.startswith(reverse("login"))

    def test_developer_dashboard_requires_staff(self, client):
        normal = get_user_model().objects.create_user("normal-user", password="password")
        client.force_login(normal)
        denied = client.get(reverse("developer_dashboard"))
        assert denied.status_code == 302

        staff = get_user_model().objects.create_user(
            "staff-user", password="password", is_staff=True
        )
        client.force_login(staff)
        allowed = client.get(reverse("developer_dashboard"))
        assert allowed.status_code == 200
        assert "開発者ダッシュボード" in allowed.content.decode("utf-8")

    def test_watchlist_supports_anonymous_sessions_and_is_isolated_by_user(self, client):
        endpoint = reverse("watchlist")
        assert client.get(endpoint).status_code == 200
        first = get_user_model().objects.create_user("first-user", password="password")
        second = get_user_model().objects.create_user("second-user", password="password")
        payload = {
            "name": "テスト商品",
            "url": "https://auctions.yahoo.co.jp/jp/auction/x123456789",
            "currentPrice": 5000,
            "marketMedian": 8000,
        }

        client.force_login(first)
        assert client.post(endpoint, json.dumps(payload), content_type="application/json").status_code == 201
        client.force_login(second)
        assert client.get(endpoint).json()["items"] == []
        assert client.post(endpoint, json.dumps(payload), content_type="application/json").status_code == 201

        assert WatchItem.objects.filter(url=payload["url"]).count() == 2

    def test_anonymous_watchlist_is_claimed_on_login(self, client):
        endpoint = reverse("watchlist")
        payload = {
            "name": "匿名ウォッチ商品",
            "url": "https://auctions.yahoo.co.jp/jp/auction/z987654321",
            "currentPrice": 4000,
            "marketMedian": 6000,
        }
        assert client.post(
            endpoint, json.dumps(payload), content_type="application/json"
        ).status_code == 201
        anonymous_item = WatchItem.objects.get(url=payload["url"])
        assert anonymous_item.user is None
        assert anonymous_item.session_key

        user = get_user_model().objects.create_user(
            "claim-user", password="claim-password-2026"
        )
        response = client.post(
            reverse("login"),
            {"username": user.username, "password": "claim-password-2026"},
        )
        assert response.status_code == 302
        anonymous_item.refresh_from_db()
        assert anonymous_item.user == user
        assert anonymous_item.session_key == ""

    def test_search_history_is_isolated_between_anonymous_sessions(
        self, client, monkeypatch
    ):
        monkeypatch.setattr(
            api,
            "scrape_data",
            lambda keyword: [
                {
                    "name": "履歴テスト商品",
                    "price": 5000,
                    "startPrice": 1000,
                    "bidding": 2,
                    "url": "https://auctions.yahoo.co.jp/jp/auction/a123456789",
                }
            ],
        )
        assert client.get(reverse("perform_search"), {"keyword": "private-keyword"}).status_code == 200
        assert client.get(reverse("get_search_words")).json()["searchWords"] == [
            "private-keyword"
        ]

        from django.test import Client

        other_client = Client()
        assert other_client.get(reverse("get_search_words")).json()["searchWords"] == []

    def test_anonymous_search_history_is_claimed_on_login(self, client):
        client.get(reverse("get_search_words"))
        session_key = client.session.session_key
        SearchRun.objects.create(
            session_key=session_key,
            keyword="claim-keyword",
            search_type=SearchRun.CLOSED,
        )
        user = get_user_model().objects.create_user(
            "search-claim-user", password="claim-password-2026"
        )
        client.post(
            reverse("login"),
            {"username": user.username, "password": "claim-password-2026"},
        )
        run = SearchRun.objects.get(keyword="claim-keyword")
        assert run.user == user
        assert run.session_key == ""

    def test_profile_requires_login(self, client):
        response = client.get(reverse("profile"))
        assert response.status_code == 302
        assert response.url.startswith(reverse("login"))

    def test_profile_displays_only_the_current_users_data(self, client):
        first = get_user_model().objects.create_user(
            "profile-first", email="first@example.com", password="password"
        )
        second = get_user_model().objects.create_user(
            "profile-second", password="password"
        )
        first_run = SearchRun.objects.create(
            user=first, keyword="first-keyword", search_type=SearchRun.CLOSED, item_count=1
        )
        second_run = SearchRun.objects.create(
            user=second, keyword="second-keyword", search_type=SearchRun.CLOSED, item_count=1
        )
        scraping.objects.create(
            search_run=first_run,
            SearchWord="first-keyword",
            SearchDay="2026-08-15 10:00:00",
            Bidding="3",
            EndPrice=5000,
            StartPrice=1000,
            Name="first-product",
            URL="https://auctions.yahoo.co.jp/jp/auction/a123456789",
        )
        scraping.objects.create(
            search_run=second_run,
            SearchWord="second-keyword",
            SearchDay="2026-08-15 11:00:00",
            Bidding="1",
            EndPrice=9000,
            StartPrice=2000,
            Name="second-product",
            URL="https://auctions.yahoo.co.jp/jp/auction/b123456789",
        )
        WatchItem.objects.create(
            user=first,
            name="first-watch",
            url="https://auctions.yahoo.co.jp/jp/auction/c123456789",
        )
        WatchItem.objects.create(
            user=second,
            name="second-watch",
            url="https://auctions.yahoo.co.jp/jp/auction/d123456789",
        )

        client.force_login(first)
        response = client.get(reverse("profile"), {"run": second_run.pk})
        content = response.content.decode("utf-8")
        assert response.status_code == 200
        assert "first-keyword" in content
        assert "first-product" in content
        assert "first-watch" in content
        assert "second-keyword" not in content
        assert "second-product" not in content
        assert "second-watch" not in content

    def test_profile_admin_links_are_staff_only(self, client):
        normal = get_user_model().objects.create_user("profile-normal", password="password")
        staff = get_user_model().objects.create_user(
            "profile-staff", password="password", is_staff=True
        )

        client.force_login(normal)
        normal_content = client.get(reverse("profile")).content.decode("utf-8")
        assert "開発者画面" not in normal_content
        assert "Django管理画面" not in normal_content

        client.force_login(staff)
        staff_content = client.get(reverse("profile")).content.decode("utf-8")
        assert "開発者画面" in staff_content
        assert "Django管理画面" in staff_content

        index_content = client.get(reverse("index")).content.decode("utf-8")
        assert "開発者画面" not in index_content
        assert f'href="{reverse("profile")}"' in index_content
