# Development

## Local setup

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

Initial administrators for production must be created from the server shell:

```powershell
python manage.py createsuperuser
```

The `/accounts/admin-setup/` web endpoint is development-only and returns 404 in production. Authentication throttling defaults can be adjusted with `AUTH_LOGIN_ACCOUNT_MAX_FAILURES`, `AUTH_LOGIN_IP_MAX_FAILURES`, `AUTH_LOGIN_WINDOW_SECONDS`, `AUTH_SIGNUP_MAX_ATTEMPTS`, and `AUTH_REGISTRATION_WINDOW_SECONDS`. Trust `X-Forwarded-For` only behind a proxy that strips client-supplied forwarding headers, then set `AUTH_RATE_LIMIT_TRUST_X_FORWARDED_FOR=true`.
```

開発とテストの標準データベースはPostgreSQLです。`DB_NAME`、`DB_USER`、`DB_PASSWORD`を設定し、`docs/postgresql-bootstrap.md`の接続確認と構築順を使用してください。SQLiteは一時的なローカル確認に限り、`DB_ENGINE=sqlite`を明示した場合だけ使用します。

## Common commands

```bash
pytest -q
python manage.py check
python manage.py collectstatic
```

`run_systema.bat` preserves PostgreSQL variables from the current shell and prompts for a missing user or password without writing credentials to disk. Because local `DEBUG` defaults to false, it also runs `collectstatic --noinput` before `runserver --insecure`; restart the server after adding or changing static assets.

## Working approach

- Keep feature changes small and close to the relevant module.
- Prefer fixture-based tests for scraper regressions.
- Avoid broad refactors when the current Django structure is already working.
- Confirm request validation and JSON response behavior before changing API contracts.

## Migration notes

- Do not delete or rename migration files without a clear reason.
- New schema changes should be deliberate and reviewed.
