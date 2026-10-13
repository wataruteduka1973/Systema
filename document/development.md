# 開発ガイド

## 必要環境

- Python 3.13
- pip
- PostgreSQL（開発・本番の標準データベース）
- SQLite（テストとE2Eで `DB_ENGINE=sqlite` を指定したときに使用）

## Windowsでの起動

プロジェクト直下の `run_systema.bat` を実行します。スクリプトは `.venv` を使用し、依存関係の導入、PostgreSQLへの接続確認、マイグレーションのあとに開発サーバーを起動します。

PostgreSQLのユーザー名とパスワードは、`scripts\Set-SystemaDatabase.ps1` で `.local\database.clixml` に保存できます。パスワードはWindowsのDPAPIでそのユーザー専用に暗号化され、平文では保存しません。保存していない値は起動時に尋ね、接続に成功すると保存するか確認します。`.local` はGitの管理対象外です。

起動したサーバーの中では、アラートのスケジューラーが1時間ごとに `run_alerts` を実行します。止めるときは起動前に `SYSTEMA_ALERT_SCHEDULER=false` を設定します。間隔と1回の上限時間は `SYSTEMA_ALERT_INTERVAL_SECONDS`（既定3600）と `SYSTEMA_ALERT_MAX_RUNTIME_SECONDS`（既定1800）で変えられます。

## 手動セットアップ

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:DB_ENGINE = "postgresql"   # または sqlite
$env:DB_NAME = "Yahuoku_analyze_DB"
$env:DB_USER = "<ユーザー名>"
$env:DB_PASSWORD = "<パスワード>"
python manage.py migrate
python manage.py runserver --insecure
```

## テストと検査

まとめて検査するときは `verify` コマンドを使います。実装中は変更した機能の分だけ、区切りのよいところで全体を実行します。

```powershell
python -m pip install -r requirements-dev.txt
$env:DB_ENGINE = "sqlite"
python manage.py verify                     # 変更に関係する検査
python manage.py verify --feature alerts    # 機能単位
python manage.py verify --full              # ruff・black・mypy・pytest・Djangoチェック・マイグレーション
```

個別に実行する場合:

```powershell
ruff check .
black --check Main System_Config tests
mypy
coverage run -m pytest
coverage report
python manage.py check
python manage.py makemigrations --check --dry-run
```

設定は`pyproject.toml`へ集約しています。テストは`tests/unit/`、`tests/integration/`、`tests/e2e/`に分類します。

### Playwright E2Eテスト

E2Eテストは`pytest-playwright`とChromiumを使い、SQLiteのテストDBで実行します。本番DBの認証情報やYahoo!オークションへの通信は使用せず、取得処理はテスト内で決まったデータに差し替えます。

**主なテスト対象**:
- ログイン・初期表示・所有者分離
- トップページ（おすすめ、市場の動き、機能カードの配置）
- 市場検索（相場の要約、相場比、ウォッチ・仕入れ予算）と相場分析の2つのタブ
- ターゲット分析のカードとウォッチリスト
- 出品・在庫管理と販売実績分析
- 通知の絞り込みと既読操作、アラート条件と保存検索の取得状況
- 390px幅レスポンシブレイアウト（横スクロールなし）
- JavaScriptのエラーがないこと

保存済みデータだけでアラートを判定する場合は`python manage.py run_alerts --evaluate-only`、外部取得を含めて手動で実行する場合は`python manage.py run_alerts`を使います。`--saved-search-id`を付けると、その保存検索を取得頻度に関係なく取得します。

**Windowsでの実行**:

```powershell
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
$env:DB_ENGINE = "sqlite"
pytest tests/e2e/test_notifications_browser.py -v
```

すべてのE2Eテスト:

```powershell
pytest -m e2e -v
```

**前提条件**:
- SQLiteテストDB（`DB_ENGINE=sqlite`で隔離）
- 外部通信allowlist: localhost, 127.0.0.1, cdn.jsdelivr.net, fonts.googleapis.com, fonts.gstatic.com のみ許可
- 許可外ホストへのリクエストはテスト失敗（URL/ホスト名をエラー出力）
- 各テスト方法で独立したユーザー・通知フィクスチャ

GitHub Actionsはヘッドレス実行のみのため、通常のChromiumではなくheadless shellを取得します。

```bash
python -m playwright install --with-deps --only-shell
```

## CIとマージ保護

pushとPull Requestごとに、`.github/workflows/ci.yml`がlint・型検査・テスト・Sphinxビルドを実行します。GitHubの **Settings → Branches → Branch protection rules** で`main`を対象にし、次のRequired status checksを指定してください。

- `Lint and type check`
- `Tests`
- `E2E Tests`
- `Documentation`

このリポジトリ設定を有効にすると、いずれかが失敗したPull Requestはマージできません。

Yahoo!オークションのHTML変更へ対応するときは、ライブ通信を使う大規模なテストではなく、`tests/fixtures/yahoo/` のfixtureと `tests/unit/test_yahoo_parser.py` を更新します。

## Sphinxドキュメント

Windows:

```powershell
.\document\make.bat clean html
```

macOS/Linux:

```bash
make -C document clean html
```

生成結果は `document/build/html/index.html` です。警告をエラーとして扱うため、リンク切れやautodocの読み込み失敗もビルド失敗として検出されます。

画面・機能ガイドのスクリーンショット（`document/_static/screens/`）は、画面のデザインを変えたときに次のコマンドで撮り直します。Yahoo!オークションへは通信せず、生成したサンプルデータで実際の画面を表示します。

```bash
DOC_SCREENSHOT_DIR=document/_static/screens DB_ENGINE=sqlite \
    python -m pytest -m e2e tests/e2e/test_document_screenshots.py
```

## GitHub Pages公開

`main` ブランチへpushすると `.github/workflows/docs.yml` がSphinxをビルドし、GitHub Pagesへ公開します。初回のみGitHubリポジトリの **Settings → Pages → Build and deployment → Source** を **GitHub Actions** に設定してください。

Pull Requestではビルド検証だけを行い、公開は行いません。Actions画面から手動実行することもできます。
