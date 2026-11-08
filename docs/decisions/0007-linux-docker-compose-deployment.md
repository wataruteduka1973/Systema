# ADR 0007: Linux deployment with Docker Compose

## Status

Accepted (2026-11-08).

## Context

Systema ran only on Windows: `run_systema.bat` starts Django's development server, stores the
PostgreSQL password with Windows DPAPI and runs the alert scheduler inside the web process
(ADR 0006). A future Linux server needs a production app server, a shared cache for rate-limit
counters across workers (`check_release` requires Redis or Memcached), one scheduler process
instead of one per worker, and a way to hold secrets without DPAPI. The hosting provider and
domain are not chosen yet.

## Decision

- Deploy on Linux with Docker Compose (`compose.yaml`): `db` (PostgreSQL 16), `redis`, a one-shot
  `migrate`, `web` (gunicorn, WhiteNoise for static files) and `scheduler`.
- The scheduler runs as its own service with `manage.py run_alert_scheduler`, which reuses the
  ADR 0006 loop (interval, hard timeout, last-start file) in the foreground and stops on SIGTERM
  after the current job. Web workers set `SYSTEMA_ALERT_SCHEDULER=false`. The advisory job lock
  still prevents overlap with manual runs.
- The cache is chosen by `DJANGO_CACHE_BACKEND` (`locmem`, `redis`, `memcached`) and
  `DJANGO_CACHE_LOCATION`; the default stays the per-process memory cache for development. This
  implements what `release-readiness.md` already described.
- Secrets live in `.env` (mode 600, git-ignored), created by `scripts/linux/create-env.sh` with
  random values. The container image holds no secrets.
- HTTPS is terminated by a reverse proxy in front of `web` (published on 127.0.0.1 by default). It
  is added once the server and domain are chosen.
- For development on Linux, `run_systema.sh` mirrors `run_systema.bat`. Saved database settings go
  to `~/.config/systema/database.env` (directory 700, file 600), outside the project folder, which
  may be synced; this replaces DPAPI on Linux in the same way `~/.pgpass` does.
- CI builds the image, starts the stack in production mode and runs `scripts/linux/smoke-test.sh`.

## Consequences

- Any Linux host with Docker runs the same stack, and Windows can try it with Docker Desktop.
- Docker becomes a prerequisite for the server. A non-Docker install (venv, gunicorn, systemd) is
  not provided; the same commands apply if it is needed later.
- Containers write application logs to the `app-logs` volume; the scheduler's last-start time is in
  `app-local`, so restarts do not trigger an extra Yahoo fetch.
- `.env` is plain text with owner-only permissions. A secret manager can replace it later without
  changing the application, which reads environment variables only.

## Related Files

- `Dockerfile`, `.dockerignore`, `compose.yaml`, `deploy/env.example`
- `scripts/linux/create-env.sh`, `scripts/linux/smoke-test.sh`, `run_systema.sh`
- `Main/management/commands/run_alert_scheduler.py`, `Main/services/alert_scheduler.py`
- `System_Config/cache.py`, `System_Config/settings.py`
- `docs/deployment-linux.md`
