# ADR 0006: アプリ内常駐スケジューラーによる`run_alerts`定期実行

## Status

Accepted (2026-10-11). Supersedes decision 6 of `docs/plans/release-feature-roadmap.md` ("定期実行はデプロイ工程まで開始しない") for local use.

## Context

`run_alerts` already has a job lock, a cooperative time budget and nonzero failure exits
(`docs/features/release-readiness.md`). The deployment provider is not selected, but the user wants
saved searches and alerts refreshed hourly now. The user chose an in-app scheduler over the Windows
Task Scheduler or a hosting provider's cron. `docs/design/api.md` forbids running jobs inside API
requests, and release readiness requires a hard process timeout.

## Decision

- The web server process starts a daemon timer thread, `Main/services/alert_scheduler.py`. It is
  started from `System_Config/wsgi.py` and `asgi.py`, and only when `SYSTEMA_ALERT_SCHEDULER=true`.
  Management commands and tests never import these modules, so they never start it.
- Each run is a separate `manage.py run_alerts --max-runtime-seconds N` child process. The timer
  waits for it and kills it at `N + 300` seconds. Request threads never run a job.
- The default interval is 3600 seconds and is measured from the last recorded start
  (`.local/alert-scheduler-last-start`). A restart therefore does not trigger an extra run. Any
  first run waits 120 seconds after startup.
- `run_alerts` exits 75 when another job holds the lock. The scheduler logs that run as skipped.
  This covers several server workers or a concurrent manual run.
- Failures and timeouts go to the error log and `ErrorLog` (`scheduled_alert_job`). Only fixed
  labels and the command's summary line are recorded.

## Consequences

- No new dependency and no schema change. Runs happen only while the server is running.
- Each worker of a multi-worker server runs its own timer; the job lock keeps one job running and
  the others log `skipped`. A production deployment should enable the scheduler on one process
  only, or replace it with the provider's scheduler calling the same command.
- The 120-second startup delay and start-time file are per host. A container with an ephemeral
  filesystem runs once about 2 minutes after each deploy.

## Related Files

- `Main/services/alert_scheduler.py`, `Main/services/job_lock.py`
- `Main/management/commands/run_alerts.py`
- `System_Config/wsgi.py`, `System_Config/asgi.py`, `System_Config/settings.py`
- `run_systema.bat`
- `tests/unit/test_alert_scheduler.py`, `tests/integration/test_alert_job.py`
