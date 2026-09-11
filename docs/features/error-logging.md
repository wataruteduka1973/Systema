# Error logging

## HTTP failure capture

The outermost ErrorLoggingMiddleware records HTTP 4xx/5xx responses, including
CSRF and other inner middleware rejections. Successful responses are not stored.
Each response carries a server-generated X-Request-ID, also stored in ErrorLog's
message. A view exception and its resulting response produce one database entry.

Diagnostic data is limited to status, resolved route name, exception class and
up to twenty code frame locations (basename, line, function). Request paths,
query strings, bodies, cookies, headers, exception messages, source lines and
local variables are not stored by this middleware. Existing log records are not
retroactively sanitized. Other Python loggers still require a separate privacy audit.

Database logging uses a savepoint and falls back to error_logger on persistence
failure. Missing migrations or DB outages must not replace the original response.
The existing ErrorLog schema and staff dashboard remain compatible.

Browser `error`, resource-load failure and unhandled-rejection events are sent as
kind-only signals to `/taskle/api/v1/client-errors`. Client messages, stacks, URLs
and page data are never accepted. The endpoint is payload-limited and rate-limited
by a one-way hash of the connection address.

Uncaught management-command failures are logged centrally by `manage.py` using
only the validated command name and exception class. Command arguments and
exception messages are omitted.

All file handlers use size-based rotation. Defaults are 10 MiB per file and five
backups, configurable with `LOG_MAX_BYTES` and `LOG_BACKUP_COUNT`. `ErrorLog` rows
default to 90-day retention (`ERROR_LOG_RETENTION_DAYS`): expired rows are pruned
at most once per day when a new error is saved. Operations can also run
`python manage.py prune_error_logs` explicitly.

## Verification

Run `python manage.py verify --feature error-logging`.
Local SQLite verification passed for correlation, exception deduplication,
secret omission, database failure isolation, CSRF rejection, browser signals,
management-command sanitization, automatic retention and explicit pruning.
Production PostgreSQL and CI are NOT VERIFIED.

## Remaining coverage

Streaming response iteration and failures before Django logging configuration are
not persisted in ErrorLog. An exception caught inside a service is visible here
only when it produces an error HTTP response or the service logs it. Client error
signals intentionally provide categories rather than debugging content, so detailed
browser reproduction remains a separate diagnostic step.

## Related Files

The staff dashboard uses the safe aggregate contract in
`docs/features/admin-monitoring.md`; it no longer reads file tails or displays raw
legacy error messages. Source search logs omit keywords; the shared filter also
removes email/session/header values and preformatted exception/stack text.

- `Main/middleware/error_logging_middleware.py`
- `Main/logging_filters.py`
- `Main/services/error_logging.py`
- `Main/models/errorlog.py`
- `Main/static/JS/ClientErrors.js`
- `Main/management/commands/prune_error_logs.py`
- `manage.py`
- `Main/views/developer.py`
- `System_Config/settings.py`
- `tests/integration/test_error_logging.py`
