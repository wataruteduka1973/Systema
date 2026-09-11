# Administrator monitoring

**Status:** Completed and locally verified on 2026-09-11. Production PostgreSQL,
production browser behavior, deployment settings and GitHub CI are NOT VERIFIED.

## Scope and access

Phase 8 extends the existing `/taskle/developer/` staff-only, read-only dashboard.
Anonymous and ordinary users are redirected to login; responses are not cached.
There is no new API, schema, paid service, automatic blocking or deletion.

## Metrics and filters

- Rolling 1, 7 (default), or 30 days, inclusive bounds through the captured current time.
- Search success rate = successful stored `SearchRun` rows / all rows in the period.
  A successful empty search remains successful; prediction's `no_data` and
  `insufficient_data` outcomes remain failures. No rows displays an em dash.
- Mean and maximum duration include all measured rows (including failures and zero),
  excluding null durations. The measured count is displayed.
- Actor categories: logged-in user, anonymous session, neither owner. Trigger
  categories: manual, saved, alert, scheduled, or other. No identities are displayed.
- Failure categories use an allowlist; unknown and blank failed codes become unclassified.
- Error filters: HTTP/browser/other and warning/error. HTTP 400–499 maps to warning;
  HTTP 500–599, browser and unknown codes map to error. This is a dashboard mapping,
  not a persisted logging severity. Only errors use level/type filters.
- Daily errors use Asia/Tokyo. Recent events show timestamp, safe kind and level only,
  capped at 20 rows. Invalid filter choices return 400 without running aggregates
  or echoing arbitrary input. Empty results and reset are supported.
- Concentration warning: at least 60 stored search rows in the last rolling hour,
  grouped separately by user and anonymous session. Only the number of matching
  actors is returned. Unowned rows are excluded. Compound searches may produce
  multiple rows; this is not an HTTP request counter or the rate limiter's state.
- DB volume is all-time row counts for Systema models, not disk bytes.
- Unowned search/watch rows have neither user nor session. Unowned item rows have
  no search run, or belong to an unowned run. Valid anonymous sessions are excluded.

Search history pruning means these are **retained-record metrics**, not a complete
traffic ledger. No inference about scheduler availability or live Yahoo access is made.

## Failure classification and compatibility

`html_parse_error` extends the existing free-text `SearchRun.failure_code` without
migration. `SearchParseError` subclasses `ExternalServiceError`; existing external
HTTP 503 payloads keep `external_service_unavailable` for API compatibility.
Search fetch failures retain their existing code. Parser exceptions and malformed
NEXT_DATA without usable HTML fallback now fail instead of silently returning success.
Unrecognized empty HTML alone cannot prove structure drift; empty-result semantics
remain compatible. Existing partial transport-fetch behavior is unchanged.

## Privacy and implementation boundaries

The dashboard never reads log files or selects raw error messages/paths for display.
Legacy error codes, failure codes and triggers are mapped to fixed labels. Usernames
(including email-shaped usernames), emails, session keys, cookies and full keywords
are omitted. Even the shared header uses a generic profile label on this page.
Search logging sites omit keywords/URLs at source. The shared logging filter also
redacts email, session and header-style values and discards exception/stack text.
Existing stored logs are not rewritten or retrospectively sanitized.

`Main/views/developer.py` validates form choices; `Main/services/admin_monitoring.py`
performs ORM aggregation. Parser errors originate at parsing boundaries; existing
search orchestration records only the safe failure code. No data is collected from
external services while rendering monitoring.

The earlier OperationalEvent design remains a future option for a durable traffic
ledger, structured operational events and richer severity. Existing SearchRun and
ErrorLog supply Phase 8's accepted scope; creating another event store is deferred.

## Verification

Entrypoint: `python manage.py verify --feature admin-monitoring`.
Tests cover permissions, time bounds, metric denominators, zero/missing timing,
classification, invalid/empty filters, legacy secret omission, ownerless data,
concentration thresholds, malformed Yahoo fixtures, safe compatible responses,
and desktop/mobile browser filtering and layout.

## Related Files

- `Main/services/admin_monitoring.py`
- `Main/views/developer.py`
- `Main/templates/developer/dashboard.html`
- `Main/templates/header.html`
- `Main/services/search_observability.py`
- `Main/services/exceptions.py`
- `Main/scraping/yahoo.py`
- `Main/views/api.py`
- `Main/views/utils.py`
- `Main/logging_filters.py`
- `tests/integration/test_admin_monitoring.py`
- `tests/e2e/test_admin_monitoring_browser.py`
- `tests/integration/test_external_search_api.py`
- `tests/unit/test_external_search.py`
- `tests/unit/test_logging_safety.py`
