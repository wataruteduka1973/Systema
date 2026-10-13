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

Registered rules are grouped by target (kind badge, name and rule count; saved searches, then
watches, then listings). Each rule shows its threshold with a unit (`25,000円`, `20%`, `60分`;
conditions without a threshold say so), the cooldown, and the last notification time or
「まだ通知していません」. A switch on each rule toggles `isEnabled` with a partial PATCH. When creating a
rule, choosing a condition fills a suggested threshold (e.g. 割安率 20%, 終了まで 60分, 買い時点数 70,
入札停滞 24時間, 相場下落 10%); price and target-profit conditions start empty so the user must enter
an amount. Notification titles name the target and condition (`<name>：<condition>`).

## Manual execution

`python manage.py run_alerts` refreshes active saved searches, records their normal search results, evaluates saved-search rules, and evaluates persisted watch and seller observations. `--evaluate-only` never calls Yahoo and evaluates each saved search's latest current-listing run only when it succeeded (a newer failed run suppresses evaluation). `--user-id` and `--saved-search-id` (positive IDs) narrow the run; a `--saved-search-id` run does not evaluate watches or sellers.

Only one job runs at a time (PostgreSQL advisory lock; local SQLite uses `.local/run-alerts.lock`). An overlapping invocation exits 75 with "Alert job is already running" before doing any work. `--max-runtime-seconds` (default 1800) is a cooperative budget: no new saved search, watch or seller starts after it, and the command prints the summary and exits 1. When any saved search fails, the command prints the summary and exits 1 with `N failed searches`; per-search stderr shows only the exception class. See `release-readiness.md` for scheduler requirements.

Scheduled refresh calls the same HTTP-independent target-search use case as the web flow. The
command passes the authenticated owner, saved criteria, Yahoo provider, repository, `scheduled`
trigger, and saved-search reference directly. It does not construct an `HttpRequest` or import a
view. Only active searches owned by active users are refreshed. A successful current run is
counted in the owner's daily update notification and gets one alert-rule evaluation; a partial or complete failure
records and notifies the failed run without evaluating saved-search alert rules.

Invalid stored criteria fail only that saved search: the command reports the exception class,
updates its last attempt time, and continues with later searches. It does not expose the invalid
value or create a successful run. This validation failure occurs before acquisition and does not
create a search run or status notification.

The command is the scheduler boundary.

## Scheduled execution

With `SYSTEMA_ALERT_SCHEDULER=true` (set by `run_systema.bat`), the web server process starts the
in-app scheduler (ADR 0006, `Main/services/alert_scheduler.py`). Every
`SYSTEMA_ALERT_INTERVAL_SECONDS` (default 3600), counted from the last recorded start in
`.local/alert-scheduler-last-start`, it runs `manage.py run_alerts --max-runtime-seconds
<SYSTEMA_ALERT_MAX_RUNTIME_SECONDS>` (default 1800) as a child process. A child still running 300
seconds past that budget is killed. The first run after a server start waits at least 120 seconds,
so restarting the server does not cause an extra fetch.

Outcomes are logged to `server_logger` as `scheduled_alert_job outcome=...`:
- `succeeded` includes the summary line.
- `skipped` means exit 75: another job held the lock.
- `failed` and `timed_out` are also written to `ErrorLog` (`scheduled_alert_job`, visible on the
  developer dashboard) with only the exit status and summary line.

The child's stderr goes to the server console. Management commands and tests never start the
scheduler; it is started only from `System_Config/wsgi.py` and `asgi.py`. Email delivery remains deferred until in-app notification behavior is stable and will use a separate outbox model.

## Related Files

- `Main/models/alertrule.py`, `Main/migrations/0021_alert_rules_phase6.py`
- `Main/services/alert_rules.py`, `Main/services/watchlist.py`, `Main/services/seller_listings.py`
- `Main/views/api.py`, `Main/views/urls.py`, `Main/urls.py`
- `Main/templates/alert_rules.html`, `Main/static/JS/AlertRules.js`
- `Main/templates/notifications.html`, `Main/static/JS/Notifications.js`
- `Main/management/commands/run_alerts.py`, `Main/services/job_lock.py`, `Main/services/alert_scheduler.py`, `Main/management/commands/verify.py`
- `tests/integration/test_alert_command_usecase.py`, `tests/integration/test_alert_job.py`, `tests/integration/test_alert_rules.py`
- `tests/e2e/test_alert_rules_browser.py`, `tests/e2e/test_alert_notification_readability_browser.py`, `tests/unit/test_alert_scheduler.py`
- `docs/decisions/0006-in-process-alert-scheduler.md`

## Verification

Run `python manage.py verify --feature alerts`, `node --check Main/static/JS/AlertRules.js`, and `node --check Main/static/JS/Notifications.js`. Browser verification uses `DB_ENGINE=sqlite pytest tests/e2e/test_alert_rules_browser.py -v`.

Local verification on 2026-09-10 passed: `verify --feature alerts`, targeted mypy, Sphinx with warnings treated as errors, JavaScript syntax checks, `291 passed, 1 skipped` non-E2E regression tests, and `9 passed` SQLite Playwright E2E tests. The E2E suite includes the 390px alert-rule CRUD workflow and the existing notification workflow.

Production migration, PostgreSQL behavior, scheduler connection, email outbox, production browser behavior, and GitHub Actions remain **NOT VERIFIED** and belong to the Phase 9 release gate or later deployment work.
