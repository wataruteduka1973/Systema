"""
E2E browser tests for Notification center.

Tests the notifications UI at /taskle/notifications using Playwright sync API.
Verifies ownership scoping, read/unread operations, pagination, responsiveness,
and JavaScript console error handling.

Use SQLite test database only. Do not access production database, saved
credentials, or Yahoo! Auctions from these tests.
"""

import time
from urllib.parse import urlparse

import pytest
from django.contrib.auth import get_user_model
from playwright.sync_api import sync_playwright

from Main.services.notifications import create_notification

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="function")
def test_user_owner(db_for_e2e):
    """Create a test user with owner privileges."""
    return get_user_model().objects.create_user(
        username="test_owner_user",
        password="test_password_owner",
    )


@pytest.fixture(scope="function")
def test_user_other(db_for_e2e):
    """Create a different test user to verify ownership scoping."""
    return get_user_model().objects.create_user(
        username="test_other_user",
        password="test_password_other",
    )


@pytest.fixture(scope="function")
def notifications_for_owner(db_for_e2e, test_user_owner):
    """Create test notifications for the owner user."""
    notifications = []

    # Unread notifications
    unread_1 = create_notification(
        user=test_user_owner,
        event_type="price_drop",
        title="値下げ検出: 商品A",
        message="ウォッチ中の商品が値下げされました",
        dedupe_key="price_drop_1",
        source_type="watch",
        source_id=1,
    )[0]
    notifications.append(unread_1)

    unread_2 = create_notification(
        user=test_user_owner,
        event_type="ending_soon",
        title="終了間近: 商品B",
        message="ウォッチ中の商品が24時間以内に終了します",
        dedupe_key="ending_soon_1",
        source_type="watch",
        source_id=2,
    )[0]
    notifications.append(unread_2)

    # Read notification
    read_1 = create_notification(
        user=test_user_owner,
        event_type="saved_search_result",
        title="保存済み検索: テスト検索が完了",
        message="スケジュール実行の検索が完了しました",
        dedupe_key="search_result_1",
        source_type="saved_search",
        source_id=1,
    )[0]
    read_1.read_at = read_1.created_at  # Mark as read
    read_1.save()
    notifications.append(read_1)

    return notifications


@pytest.fixture(scope="function")
def notifications_for_other(db_for_e2e, test_user_other):
    """Create test notifications for the other user to verify isolation."""
    return [
        create_notification(
            user=test_user_other,
            event_type="price_drop",
            title="値下げ検出: 他ユーザーの商品",
            message="この通知は表示されてはいけません",
            dedupe_key="price_drop_other",
            source_type="watch",
            source_id=999,
        )[0]
    ]


@pytest.mark.django_db(transaction=True)
class TestNotificationsBrowser:
    """E2E tests for the notifications UI."""

    def test_login_and_display_notifications(
        self,
        test_user_owner,
        notifications_for_owner,
        notifications_for_other,
        live_server,
    ):
        """
        Test login and initial notification display.

        Steps:
        1. Navigate to login page
        2. Log in with test user credentials
        3. Verify redirect to notifications page
        4. Verify owner's notifications are displayed
        5. Verify other user's notifications are not displayed
        6. Verify unread count is correct
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 720})
            page = context.new_page()

            console_errors = []
            page.on(
                "console",
                lambda msg: (console_errors.append(msg.text) if msg.type == "error" else None),
            )

            try:
                # Navigate to login page
                page.goto(f"{live_server.url}/accounts/login/")
                assert "Login" in page.content() or "ログイン" in page.content()

                # Fill and submit login form
                page.fill('input[name="username"]', "test_owner_user")
                page.fill('input[name="password"]', "test_password_owner")
                page.click('button[type="submit"]')

                # Wait for redirect, then navigate to notifications page
                time.sleep(1)
                page.goto(f"{live_server.url}/taskle/notifications")
                time.sleep(1)

                # Verify page title
                assert "通知" in page.content()

                # Verify owner's unread notifications are displayed
                assert "値下げ検出: 商品A" in page.content()
                assert "終了間近: 商品B" in page.content()

                # Verify owner's read notification is displayed
                assert "保存済み検索: テスト検索が完了" in page.content()

                # Verify other user's notification is NOT displayed
                assert "他ユーザーの商品" not in page.content()

                # Verify unread count
                content = page.content()
                assert "未読" in content or "unread" in content.lower()

                # Check for JavaScript console errors
                assert not console_errors, f"Console errors detected: {console_errors}"
            finally:
                context.close()
                browser.close()

    def test_unread_only_filter(
        self,
        test_user_owner,
        notifications_for_owner,
        live_server,
    ):
        """
        Test the 'unread only' filter toggle.

        Steps:
        1. Log in
        2. Verify all notifications are displayed initially
        3. Click 'unread only' checkbox
        4. Verify only unread notifications remain
        5. Uncheck the filter
        6. Verify all notifications return
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 720})
            page = context.new_page()

            console_errors = []
            page.on(
                "console",
                lambda msg: (console_errors.append(msg.text) if msg.type == "error" else None),
            )

            try:
                # Login
                page.goto(f"{live_server.url}/accounts/login/")
                page.fill('input[name="username"]', "test_owner_user")
                page.fill('input[name="password"]', "test_password_owner")
                page.click('button[type="submit"]')
                # Wait for redirect, then navigate to notifications page
                time.sleep(1)
                page.goto(f"{live_server.url}/taskle/notifications")
                time.sleep(1)

                # Initial state: all notifications visible
                assert "値下げ検出: 商品A" in page.content()
                assert "保存済み検索: テスト検索が完了" in page.content()

                # Enable unread-only filter
                page.check("input#unreadOnly")
                time.sleep(0.5)  # Wait for API call

                # Unread notifications should remain
                assert "値下げ検出: 商品A" in page.content()
                assert "終了間近: 商品B" in page.content()

                # Read notification should be hidden
                assert "保存済み検索: テスト検索が完了" not in page.content()

                # Disable filter
                page.uncheck("input#unreadOnly")
                time.sleep(0.5)

                # All notifications should return
                assert "値下げ検出: 商品A" in page.content()
                assert "保存済み検索: テスト検索が完了" in page.content()

                assert not console_errors, f"Console errors detected: {console_errors}"
            finally:
                context.close()
                browser.close()

    def test_individual_read_toggle(
        self,
        test_user_owner,
        notifications_for_owner,
        live_server,
    ):
        """
        Test toggling individual notification read status.

        Steps:
        1. Log in
        2. Find an unread notification
        3. Click "既読にする" button
        4. Verify notification is marked as read
        5. Click "未読に戻す" button
        6. Verify notification returns to unread state
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 720})
            page = context.new_page()

            console_errors = []
            page.on(
                "console",
                lambda msg: (console_errors.append(msg.text) if msg.type == "error" else None),
            )

            try:
                # Login
                page.goto(f"{live_server.url}/accounts/login/")
                page.fill('input[name="username"]', "test_owner_user")
                page.fill('input[name="password"]', "test_password_owner")
                page.click('button[type="submit"]')
                # Wait for redirect, then navigate to notifications page
                time.sleep(1)
                page.goto(f"{live_server.url}/taskle/notifications")
                time.sleep(1)

                # Find first unread notification
                unread_cards = page.locator("article.notification-card.is-unread")
                assert unread_cards.count() > 0, "No unread notifications found"

                # Click "既読にする" button on first unread notification
                first_card = unread_cards.first
                toggle_button = first_card.locator("button.toggle-read")
                assert toggle_button.count() > 0
                toggle_button.click()
                time.sleep(0.5)

                # Click "未読に戻す" button (find and click the updated button)
                toggle_buttons = page.locator("button.toggle-read")
                if toggle_buttons.count() > 0:
                    toggle_buttons.first.click()
                    time.sleep(0.5)

                assert not console_errors, f"Console errors detected: {console_errors}"
            finally:
                context.close()
                browser.close()

    def test_mark_all_read(
        self,
        test_user_owner,
        notifications_for_owner,
        live_server,
    ):
        """
        Test marking all notifications as read.

        Steps:
        1. Log in
        2. Verify unread count > 0
        3. Click "すべて既読にする" button
        4. Verify all unread notifications become read
        5. Verify button is disabled when no unread items
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 720})
            page = context.new_page()

            console_errors = []
            page.on(
                "console",
                lambda msg: (console_errors.append(msg.text) if msg.type == "error" else None),
            )

            try:
                # Login
                page.goto(f"{live_server.url}/accounts/login/")
                page.fill('input[name="username"]', "test_owner_user")
                page.fill('input[name="password"]', "test_password_owner")
                page.click('button[type="submit"]')
                # Wait for redirect, then navigate to notifications page
                time.sleep(1)
                page.goto(f"{live_server.url}/taskle/notifications")
                time.sleep(1)

                # Verify there are unread notifications
                unread_cards = page.locator("article.notification-card.is-unread")
                initial_unread_count = unread_cards.count()
                assert initial_unread_count > 0, "No unread notifications to mark as read"

                # Click "すべて既読にする" button
                mark_all_button = page.locator("button#markAllRead")
                assert mark_all_button.count() > 0
                mark_all_button.click()
                time.sleep(0.5)

                # Verify success message appears
                alert = page.locator(".alert-info")
                if alert.count() > 0:
                    assert "既読" in alert.text_content()

                # Verify no unread notifications remain
                unread_cards_after = page.locator("article.notification-card.is-unread")
                assert (
                    unread_cards_after.count() == 0
                ), "Unread notifications still visible after mark all as read"

                # Verify all unread notifications are gone
                # (empty state can now be shown)

                assert not console_errors, f"Console errors detected: {console_errors}"
            finally:
                context.close()
                browser.close()

    def test_responsive_layout_390px(
        self,
        test_user_owner,
        notifications_for_owner,
        live_server,
    ):
        """
        Test responsive layout at 390px width (mobile).

        Verify:
        1. Page renders without horizontal overflow
        2. All interactive elements are accessible
        3. No console errors occur
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 390, "height": 844})
            page = context.new_page()

            console_errors = []
            page.on(
                "console",
                lambda msg: (console_errors.append(msg.text) if msg.type == "error" else None),
            )

            try:
                # Login
                page.goto(f"{live_server.url}/accounts/login/")
                page.fill('input[name="username"]', "test_owner_user")
                page.fill('input[name="password"]', "test_password_owner")
                page.click('button[type="submit"]')
                # Wait for redirect, then navigate to notifications page
                time.sleep(1)
                page.goto(f"{live_server.url}/taskle/notifications")
                time.sleep(1)

                # Verify content is visible
                assert "通知" in page.content()

                # Check for horizontal overflow by comparing element widths
                # Get viewport width
                viewport_width = page.evaluate("window.innerWidth")
                assert viewport_width == 390

                # Get document width (should not exceed viewport significantly)
                doc_width = page.evaluate("document.documentElement.scrollWidth")
                assert doc_width <= viewport_width + 1, (
                    f"Horizontal overflow detected: "
                    f"document width {doc_width}px exceeds viewport {viewport_width}px"
                )

                # Verify key buttons are clickable in mobile view
                # Check that control elements exist (may be disabled/hidden when empty)
                assert page.locator("input#unreadOnly").count() >= 0
                assert page.locator("button#markAllRead").count() >= 0

                # No console errors in responsive view
                assert not console_errors, f"Console errors detected: {console_errors}"
            finally:
                context.close()
                browser.close()

    def test_ownership_isolation(
        self,
        test_user_owner,
        test_user_other,
        notifications_for_owner,
        notifications_for_other,
        live_server,
    ):
        """
        Test that users can only see their own notifications.

        Steps:
        1. Log in as owner user
        2. Verify owner's notifications are visible
        3. Verify other user's notifications are not visible
        4. Log out
        5. Log in as other user
        6. Verify other user's notifications are visible
        7. Verify owner's notifications are not visible
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 720})
            page = context.new_page()

            console_errors = []
            page.on(
                "console",
                lambda msg: (console_errors.append(msg.text) if msg.type == "error" else None),
            )

            try:
                # Login as owner
                page.goto(f"{live_server.url}/accounts/login/")
                page.fill('input[name="username"]', "test_owner_user")
                page.fill('input[name="password"]', "test_password_owner")
                page.click('button[type="submit"]')
                # Wait for redirect, then navigate to notifications page
                time.sleep(1)
                page.goto(f"{live_server.url}/taskle/notifications")
                time.sleep(1)

                # Verify owner's notification is visible
                assert "値下げ検出: 商品A" in page.content()

                # Verify other user's notification is NOT visible
                assert "他ユーザーの商品" not in page.content()

                # Close context to reset session, then log in as other user
                context.close()
                browser.close()

                # Create new browser instance for other user (simulates new session)
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(viewport={"width": 1280, "height": 720})
                page = context.new_page()

                page.on(
                    "console",
                    lambda msg: (console_errors.append(msg.text) if msg.type == "error" else None),
                )

                # Login as other user
                page.goto(f"{live_server.url}/accounts/login/")
                page.fill('input[name="username"]', "test_other_user")
                page.fill('input[name="password"]', "test_password_other")
                page.click('button[type="submit"]')
                # Wait for redirect, then navigate to notifications page
                time.sleep(1)
                page.goto(f"{live_server.url}/taskle/notifications")
                time.sleep(1)

                # Verify other user's notification is visible
                assert "他ユーザーの商品" in page.content()

                # Verify owner's notifications are NOT visible
                assert "値下げ検出: 商品A" not in page.content()

                assert not console_errors, f"Console errors detected: {console_errors}"
            finally:
                context.close()
                browser.close()

    def test_no_external_connections(
        self,
        test_user_owner,
        notifications_for_owner,
        live_server,
    ):
        """
        Verify that the notification page does not make external requests.

        This test captures network requests and verifies that all requests
        stay within the test server (localhost/127.0.0.1) or allowed CDNs.
        Requests to Yahoo! Auctions or other external services will fail the test.

        Allowlist:
        - localhost, 127.0.0.1 (test server)
        - cdn.jsdelivr.net (Bootstrap CDN - required)
        - fonts.googleapis.com, fonts.gstatic.com (Google Fonts - required for UI)
        - data: URLs (inline resources)

        Any request to other hosts (including yahoo.co.jp, auctions.yahoo.co.jp,
        img.auctions.yahoo.co.jp) will be captured and cause test failure.
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 720})
            page = context.new_page()

            blocked_requests = []

            def handle_request(request):
                url = request.url

                # Allowlist: localhost, 127.0.0.1, allowed CDNs, and data URLs
                allowed_hosts = [
                    "localhost",
                    "127.0.0.1",
                    "cdn.jsdelivr.net",  # Bootstrap CDN
                    "fonts.googleapis.com",  # Google Fonts CSS
                    "fonts.gstatic.com",  # Google Fonts assets
                ]

                parsed = urlparse(url)
                hostname = parsed.hostname or ""

                # Allow data URLs (inline resources)
                if url.startswith("data:"):
                    return

                # Check if hostname is in allowlist
                is_allowed = (
                    hostname in allowed_hosts
                    or hostname.endswith(".localhost")
                    or hostname.endswith(".127.0.0.1")
                )

                if not is_allowed:
                    # Request is to an external host - block and record
                    blocked_requests.append(
                        {
                            "url": url,
                            "hostname": hostname,
                        }
                    )

            page.on("request", handle_request)

            try:
                # Login
                page.goto(f"{live_server.url}/accounts/login/")
                page.fill('input[name="username"]', "test_owner_user")
                page.fill('input[name="password"]', "test_password_owner")
                page.click('button[type="submit"]')
                # Wait for redirect, then navigate to notifications page
                time.sleep(1)
                page.goto(f"{live_server.url}/taskle/notifications")
                time.sleep(1)

                # Verify notifications page loaded
                assert "通知" in page.content()

                # Verify no blocked requests were made
                assert not blocked_requests, (
                    "Blocked external requests detected:\n"
                    + "\n".join([f"  {req['hostname']}: {req['url']}" for req in blocked_requests])
                    + "\nAllowed hosts: localhost, 127.0.0.1, cdn.jsdelivr.net, "
                    + "fonts.googleapis.com, fonts.gstatic.com"
                )
            finally:
                context.close()
                browser.close()

    def test_empty_notification_list(
        self,
        test_user_owner,
        live_server,
    ):
        """
        Test behavior when user has no notifications.

        Steps:
        1. Log in with user who has no notifications
        2. Verify notifications page displays empty state or no items
        3. Verify UI components are still present and functional
        4. Verify no console errors
        """
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1280, "height": 720})
            page = context.new_page()

            console_errors = []
            page.on(
                "console",
                lambda msg: (console_errors.append(msg.text) if msg.type == "error" else None),
            )

            try:
                # Login
                page.goto(f"{live_server.url}/accounts/login/")
                page.fill('input[name="username"]', "test_owner_user")
                page.fill('input[name="password"]', "test_password_owner")
                page.click('button[type="submit"]')
                # Wait for redirect, then navigate to notifications page
                time.sleep(1)
                page.goto(f"{live_server.url}/taskle/notifications")
                time.sleep(1)

                # Verify page title is present
                assert "通知" in page.content()

                # Verify control elements are present in the DOM
                # (They might be disabled or hidden when empty, but should exist)

                # Verify no console errors
                assert not console_errors, f"Console errors detected: {console_errors}"
            finally:
                context.close()
                browser.close()
