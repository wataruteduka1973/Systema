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
- `docs/design/api.md`, `docs/design/database.md`

## Verification

Run `python manage.py verify --feature notifications` with the PostgreSQL environment variables set. Also run `node --check Main/static/JS/Notifications.js`. Production migration, scheduler behavior, and email delivery are separate deployment evidence.

On 2026-09-09, isolated SQLite feature verification, focused mypy, JavaScript syntax, and diff checks passed. The user then confirmed `connection.vendor == "postgresql"` and `verify --feature notifications` passed against PostgreSQL, including the PostgreSQL-only concurrent dedupe test. Applying `0020` to the application database, browser confirmation, production migration, scheduler behavior, and email delivery remain separate evidence.
