# Notification Center

## Purpose

Phase 5 gives each authenticated user one place to review actionable Systema events. It covers watch price drops, watches ending within 24 hours, and saved-search success or failure. Alert thresholds, scheduled execution, and email delivery belong to Phase 6 or deployment work.

## Behavior and ownership

- `Notification` is always owned by one authenticated user. Anonymous watches never create persistent notifications.
- List, read/unread, and read-all operations start from `request.user`. Another user's ID returns 404.
- The profile page shows only the unread count and a link. The full list is at `/taskle/notifications` to avoid adding more workflow controls to the profile.
- Watch creation is not a price-drop event. A later lower observation creates one price-drop notification, and ending-soon is emitted at most once per watch per local day.
- A saved-search request creates a notification for the final `SearchRun`. Failure text exposes only a stable classification and never raw exceptions or upstream content.
- `(user, dedupe_key)` is database-unique. Application `get_or_create` handles normal retries and the constraint resolves PostgreSQL races.

## API

- `GET /taskle/api/v1/notifications?unreadOnly=false&page=1&pageSize=20`
- `PATCH /taskle/api/v1/notifications/{id}` with exactly `{ "read": true|false }`
- `POST /taskle/api/v1/notifications/read-all`

Mutations use Django session CSRF protection. Page size is 1 through 100. The list response includes `total`, `hasNext`, and the owner's current `unreadCount`.

## Related Files

- `Main/models/notification.py`, `Main/migrations/0020_notification_phase5.py`
- `Main/services/notifications.py`, `Main/services/watchlist.py`
- `Main/views/api.py`, `Main/views/urls.py`, `Main/urls.py`
- `Main/templates/notifications.html`, `Main/static/JS/Notifications.js`
- `tests/integration/test_notifications.py`
- `tests/e2e/test_notifications_browser.py`
- `docs/design/api.md`, `docs/design/database.md`

## Verification

Run `python manage.py verify --feature notifications` with the PostgreSQL environment variables set. Also run `node --check Main/static/JS/Notifications.js`.

### E2E browser testing with SQLite

For E2E browser testing with Playwright (requires pytest-playwright and Chromium), set `DB_ENGINE=sqlite` and run:

```
pytest tests/e2e/test_notifications_browser.py -v
```

All 8 tests verify:
1. Login flow and initial notification display with ownership isolation
2. Unread-only filter toggle
3. Individual notification read/unread toggle
4. Mark all as read action
5. Responsive layout at 390px (mobile viewport)
6. Ownership isolation across multiple users
7. No external requests to Yahoo! Auctions (allowlist: localhost, 127.0.0.1, cdn.jsdelivr.net, fonts.googleapis.com, fonts.gstatic.com)
8. Empty notification list and empty state display

**Test database**: SQLite only (no production DB connection, no saved credentials, no Yahoo! Auctions connection)

**Console errors**: JavaScript console errors are collected and cause test failure

Copilot reported 8 tests passed against SQLite with Chromium on Windows 11. Independent rerun in this environment is **NOT VERIFIED** because the execution usage limit was reached.

Production migration, scheduler behavior, and email delivery are separate deployment evidence. Browser confirmation in production environment is deferred to Phase 9 release gate.
