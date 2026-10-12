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

Claude Codeのクラウドセッションでは`.claude/hooks/session-start.sh`が依存関係をインストールし、`pytest`などのコマンドがDjango導入済みのPythonを使うよう`PATH`を調整します。PostgreSQLがないため、未指定時は`DB_ENGINE=sqlite`を設定します。イメージ同梱の単独インストール版`pytest`は別のPythonで動きDjangoを読み込めないため、フック適用前のセッションでは`python -m pytest`を使用してください。

クラウドイメージは`/opt/pw-browsers`にChromium（revision 1194）を同梱し、`playwright install`を禁止しています。`requirements-dev.txt`はこれに対応する`playwright==1.56.0`を固定しています。フロントエンドライブラリ（Bootstrap 5.3.8（全画面で統一）、Bootstrap Icons 1.10.5、Chart.js 4.4.7、D3.js 6.7.0）はCDNを使わず`Main/static/vendor/<名前>-<版>/`に同梱し、`{% static %}`で参照します。npm配布物から`.map`とLICENSEを含めて複製しており、本番の`CompressedManifestStaticFilesStorage`が`sourceMappingURL`を解決できるよう`.map`を削除しないでください。版を更新するときはディレクトリ名とテンプレート参照を同時に変更します。Google Fontsだけは外部読み込みのままです。PopperはBootstrapの`bootstrap.bundle.min.js`に含まれ、画面コードはjQueryを使用しないため、どちらも単独では読み込みません。Bootstrap 5.2以降、`.card-body`の余白は`.card`が定義する`--bs-card-spacer-*`変数を参照するため、`.card`を付けずに`.card-body`を使う場合は変数を自前で定義します（例: `introduction.html`の`.feature-card`）。

`__pycache__/`と`*.pyc`はGitで追跡しません（`.gitignore`済み）。

## Common commands

```bash
pytest -q
python manage.py check
python manage.py collectstatic
```

`run_systema.bat` preserves PostgreSQL variables from the current shell and prompts for a missing user or password without writing credentials to disk. It also sets `SYSTEMA_ALERT_SCHEDULER=true` unless that variable is already defined. The server then runs `run_alerts` hourly as a child process (`docs/features/alert-rules.md`, ADR 0006). The first run starts about 2 minutes after startup and fetches Yahoo for every active saved search. Set `SYSTEMA_ALERT_SCHEDULER=false` in the shell first to turn this off. Because local `DEBUG` defaults to false, it also runs `collectstatic --noinput` before `runserver --insecure`; restart the server after adding or changing static assets.

Static storage is configured through `STORAGES` (`System_Config/static_storage.py`); Django 5.1+ ignores the old `STATICFILES_STORAGE` setting, which had silently left production on plain storage. With `DEBUG=false` the static backend is WhiteNoise `CompressedManifestStaticFilesStorage`: `collectstatic` writes hashed, gzip-compressed files and `staticfiles.json`, and WhiteNoise serves them with long-lived immutable cache headers. A page that references a static file missing from the manifest raises an error, so always run `collectstatic --noinput` before serving with `DEBUG=false` (including plain `runserver`) and again after changing static assets. `DEBUG=true` and the test settings use plain `StaticFilesStorage` and need no `collectstatic`. `INSTALLED_APPS` lists `whitenoise.runserver_nostatic` before `django.contrib.staticfiles` so that `runserver` (including `run_systema.bat`'s `--insecure`) never serves static files itself: Django's handler only knows unhashed names and returned 404 for every hashed asset, which left pages unstyled. WhiteNoise serves `STATIC_ROOT` when `DEBUG=false` and the finders when `DEBUG=true`. `tests/integration/test_static_manifest.py` builds the production manifest and checks that every template `{% static %}` reference resolves.

## Working approach

- Keep feature changes small and close to the relevant module.
- Prefer fixture-based tests for scraper regressions.
- Avoid broad refactors when the current Django structure is already working.
- Confirm request validation and JSON response behavior before changing API contracts.

## Migration notes

- Do not delete or rename migration files without a clear reason.
- New schema changes should be deliberate and reviewed.
