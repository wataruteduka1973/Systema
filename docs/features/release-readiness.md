# Release readiness (Phase 9)

## Scope and acceptance

The deployment provider, public URL and scheduler are not selected. Phase 9 first
implements portable prerequisites and local verification. Production release is
NOT complete until the external evidence checklist below is satisfied.

No real database is migrated, no backup is restored over existing data, and no
scheduler is activated by these commands. Phase 7B recommendations and the
deferred search-history comparison are not release prerequisites.

## Read-only diagnostics

`python manage.py check_release` exits nonzero for unsafe production mode, DEBUG,
admin setup exposure, wildcard/local-only hosts, missing HTTPS CSRF origins,
non-PostgreSQL DB, disabled login/search throttles, process-local rate counters,
Django deployment warnings, migration drift or missing static manifest assets.
Only fixed labels/check IDs are printed; configuration values and exception
messages are excluded. Passing local prerequisites never asserts remote readiness.

Run `python manage.py check --deploy --fail-level WARNING` as well. Deploy with
`collectstatic --noinput`, then verify the actual HTTPS status, content type and
content of static assets through the public proxy.

The default cache is development-only. Deployment must choose a supported shared
Redis or Memcached service and install the matching Python client. Configure
`DJANGO_CACHE_BACKEND` and `DJANGO_CACHE_LOCATION` through the secret/environment
manager. This change does not purchase or provision a cache. The diagnostic checks
the backend type, not connectivity or atomic counter behavior; test both across
multiple web workers before release. DatabaseCache is not accepted for this
counter because its increment is not guaranteed atomic.

## Scheduled alerts

`python manage.py run_alerts --max-runtime-seconds 300` takes a global, nonblocking
PostgreSQL advisory lock before work. A second invocation exits nonzero without
processing. A dedicated session owns the lock and closes on success/failure;
the session identity is checked between work units. Use a direct/session-pooling
DB connection, not transaction-pooling PgBouncer. Lock loss during a work unit
cannot cancel its in-flight HTTP request; supervisor/network failure rehearsal is
still required. No DB transaction is held across external HTTP requests.

SQLite uses a stable OS-locked file under `.local/run-alerts.lock` for single-host
development only. The file is deliberately retained after unlock. PostgreSQL is
mandatory for production scheduling.

Time budget is cooperative: no new search/evaluation starts after the deadline.
It does not forcibly interrupt a DB call or in-flight search. The chosen scheduler
must enforce a hard process timeout, terminate the entire process tree and alert
on nonzero exit. Configure a bounded retry count with backoff; do not immediately
retry a busy lock. Killing a job may leave already-completed searches persisted;
the next invocation reuses notification cooldown/dedupe behavior.

HTTP GET retains three attempts with a per-read/connect timeout, adds a total
elapsed-time budget checked between attempts/body chunks, closes every response,
and retries only timeout/connection failures, HTTP 429 or 5xx. The elapsed budget
is cooperative, so a blocked read can exceed it by the remaining read timeout.
The scheduler hard timeout remains necessary. Ordinary 4xx, parse errors and
invalid/oversized/redirected responses are not retried by the HTTP layer.

Failed searches cause a nonzero final command exit after safe per-search diagnostics.
`--user-id` requires a positive ID. Disabled accounts are excluded.
`--saved-search-id` restricts work to that active saved search, including in
`--evaluate-only` mode; unrelated watches and sellers are not evaluated.
`--evaluate-only` never fetches Yahoo and evaluates only a latest successful
current-listing run (a later failed run suppresses evaluation).

## Backup and restore rehearsal

1. Use `pg_dump --format=custom --file=<new-private-backup-path> <source-db>` with a
   version compatible with the server. Supply credentials via a protected pgpass
   file or secret manager; never command-line passwords. Require zero exit status.
2. Record backup time, source revision/migration heads, size and SHA256 in a private
   operations record. Encrypt/restrict backup access; it contains user data. Keep
   copies off the application host according to a chosen retention/RPO policy.
3. Provision a **new, empty, isolated** restore database and role; verify its host
   and database name differ from production. Restore with `pg_restore --exit-on-error
   --no-owner --dbname=<new-restore-db> <backup-path>`. Do not use `--clean` or restore
   into the source DB. A restore into existing data requires separate approval.
4. Point an isolated app instance at the restored DB. Disable scheduler and outbound
   notifications/network access. Run `check_database`, `showmigrations`, and compare
   counts/ownership and sample search, watch, inventory, sale and notification rows.
5. Record elapsed recovery time and prove login/read workflows with test users.
   Decide RTO/RPO and retention before public release. Dispose of rehearsal data
   only after explicitly verifying its isolated target.

A successful dump or archive listing alone is not a restore test. Backups and
credentials must never be committed to this repository.

## External release evidence checklist

- [ ] Provider, deployment revision, domain and rollback revision recorded.
- [ ] Production environment/secret manager configured; no development key/DEBUG.
- [ ] PostgreSQL backup and isolated restore rehearsed; RTO/RPO/retention agreed.
- [ ] Migration plan reviewed and production migration applied with rollback plan.
- [ ] Public HTTPS, trusted proxy headers, secure cookies, CSRF and static assets verified.
- [ ] Anonymous and ordinary users cannot reach admin setup/monitoring.
- [ ] Login and search limits verified through proxy and multiple workers.
- [ ] Shared cache connectivity, atomic counters and failure behavior verified.
- [ ] Scheduler overlap, hard timeout, process kill/retry and notification dedupe verified.
- [ ] Saved search → rerun → watch → price update → notification workflow verified.
- [ ] Watch → inventory → listing → update → sale → confirmed profit verified.
- [ ] Cross-user access denied for all new resources; GitHub CI at release revision green.

These boxes remain unchecked until actual deployment evidence exists. Historical
search comparison and email outbox remain explicitly deferred, not silently tested.

## Verification

`python manage.py verify --feature release` covers release diagnostics, job lock
contention/release, bounds/failure exits, evaluate-only scope, HTTP retry cleanup,
existing auth/search/alert/notification contracts. Run on PostgreSQL to verify
advisory locks; SQLite only verifies local file locking. The main CI PostgreSQL
job runs non-E2E tests; the dedicated SQLite E2E job installs Chromium and runs
browser tests. `verify --full` remains the Phase-boundary local suite.

## Integration Status (2026-10-11)

Merged into `main`: `check_release`, `test_release_gate.py`, `test_release_workflow_browser.py`, and the
core-contracts browser test. **Not merged yet**: the alert-job lock and runtime budget
(`Main/services/job_lock.py`, `tests/integration/test_alert_job.py`) and the HTTP retry policy
(`tests/unit/test_http_retry.py`). Their tests expect `run_alerts`/`http.py` code that was never
written; `test_alert_job.py` also targets the pre-A0.4 `complex_market_data_logic` path that
`run_alerts` no longer uses. The files remain on the `local-wip` branch and must be reimplemented
against the shared target-search use case before the items above are treated as done.

## Related Files

- `Main/management/commands/check_release.py`
- `Main/management/commands/run_alerts.py`
- `Main/services/job_lock.py`
- `Main/infrastructure/http.py`
- `System_Config/settings.py`
- `.github/workflows/ci.yml`
- `tests/integration/test_release_gate.py`
- `tests/integration/test_alert_job.py`
- `tests/unit/test_http_retry.py`
- `tests/e2e/test_release_workflow_browser.py`
- `docs/deployment-security.md`
