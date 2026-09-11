# Alert Rules

## Purpose

Phase 6 turns persisted market observations into owner-scoped, configurable in-app alerts. An `AlertRule` stores a condition and cooldown; a `Notification` stores each matched event.

## Behavior and ownership

- Every rule belongs to one authenticated user and exactly one owned `SavedSearch`, `WatchItem`, or `SellerListing`.
- Buyer rules are `price_below`, `median_discount`, `ending_soon`, `low_bids`, and `buy_score`. Saved searches additionally support `new_listing` and `within_budget`.
- Seller rules are `bid_stalled`, `ending_without_bids`, `loss_risk`, `target_profit`, and `market_decline`.
- Watch rules run after a persisted observation. Saved-search rules run only after a successful current-listing snapshot. Seller rules run only after a successful public-page observation has been stored.
- A failed or incomplete search never means that a listing disappeared, became new, or changed price. The first successful saved-search run establishes the baseline and does not emit `new_listing`.
- `within_budget` uses the owner's reusable cost settings and the saved run's market median as sale-price evidence. Missing assumptions produce no budget alert.
- Cooldown and `(user, dedupe_key)` uniqueness prevent repeated notifications. Disabling a rule stops evaluation without deleting its history.
- Candidate notifications contain market evidence, cost assumptions when applicable, the observation time, and up to 20 candidates. The notification UI can add a candidate to the owner's watchlist.

## UI and API

- Page: `/taskle/alerts`
- `GET/POST /taskle/api/v1/alert-rules`
- `GET/PATCH/DELETE /taskle/api/v1/alert-rules/{id}`

The page supports create, edit, stop/resume through `isEnabled`, and delete. All mutations use session CSRF protection.

## Manual execution

`python manage.py run_alerts` refreshes active saved searches, records their normal search results, evaluates saved-search rules, and evaluates persisted watch and seller observations. Use `--evaluate-only` when external access is not wanted. `--user-id` and `--saved-search-id` narrow the run.

The command is the deployment boundary for a future scheduler. No scheduler or long-running process is started by Phase 6. Email delivery remains deferred until in-app notification behavior is stable and will use a separate outbox model.

Phase 9 adds a nonblocking job lock, positive option validation, cooperative
`--max-runtime-seconds`, nonzero exit on search failures, and saved-search-only
evaluation scope. Disabled accounts are excluded. See `release-readiness.md`
for production connection, cache and hard scheduler timeout requirements.

## Related Files

- `Main/models/alertrule.py`, `Main/migrations/0021_alert_rules_phase6.py`
- `Main/services/alert_rules.py`, `Main/services/watchlist.py`, `Main/services/seller_listings.py`
- `Main/views/api.py`, `Main/views/urls.py`, `Main/urls.py`
- `Main/templates/alert_rules.html`, `Main/static/JS/AlertRules.js`
- `Main/templates/notifications.html`, `Main/static/JS/Notifications.js`
- `Main/management/commands/run_alerts.py`, `Main/management/commands/verify.py`
- `tests/integration/test_alert_rules.py`, `tests/e2e/test_alert_rules_browser.py`

## Verification

Run `python manage.py verify --feature alerts`, `node --check Main/static/JS/AlertRules.js`, and `node --check Main/static/JS/Notifications.js`. Browser verification uses `DB_ENGINE=sqlite pytest tests/e2e/test_alert_rules_browser.py -v`.

Local verification on 2026-09-10 passed: `verify --feature alerts`, targeted mypy, Sphinx with warnings treated as errors, JavaScript syntax checks, `291 passed, 1 skipped` non-E2E regression tests, and `9 passed` SQLite Playwright E2E tests. The E2E suite includes the 390px alert-rule CRUD workflow and the existing notification workflow.

Production migration, PostgreSQL behavior, scheduler connection, email outbox, production browser behavior, and GitHub Actions remain **NOT VERIFIED** and belong to the Phase 9 release gate or later deployment work.
