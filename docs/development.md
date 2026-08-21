# Development

## Local setup

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

データベースは既定でSQLiteです。PostgreSQLへ切り替える場合は、`docs/postgresql-bootstrap.md`に記載した環境変数と構築順を使用してください。

## Common commands

```bash
pytest -q
python manage.py check
python manage.py collectstatic
```

## Working approach

- Keep feature changes small and close to the relevant module.
- Prefer fixture-based tests for scraper regressions.
- Avoid broad refactors when the current Django structure is already working.
- Confirm request validation and JSON response behavior before changing API contracts.

## Migration notes

- Do not delete or rename migration files without a clear reason.
- New schema changes should be deliberate and reviewed.
