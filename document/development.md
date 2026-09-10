# 開発ガイド

## 必要環境

- Python 3
- pip
- SQLite（Python同梱のものを使用）

## Windowsでの起動

プロジェクト直下の `run_systema.bat` を実行します。スクリプトは `.venv` を使用し、依存関係の導入とマイグレーション後に開発サーバーを起動します。

## 手動セットアップ

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver --insecure
```

## テストと検査

```powershell
python -m pip install -r requirements-dev.txt
ruff check .
black --check Main System_Config tests
mypy
coverage run -m pytest
coverage report
python manage.py check
```

設定は`pyproject.toml`へ集約しています。テストは`tests/unit/`、`tests/integration/`、`tests/e2e/`に分類します。

### Playwright E2Eテスト

通知画面とアラート条件画面のE2Eテストは`pytest-playwright`とChromiumを使い、SQLiteのテストDBで実行します。本番DBの認証情報やYahoo! Auctionsへの通信は使用しません。

**テスト対象**:
- ログイン・初期表示・所有者分離
- 未読フィルター・既読操作
- 390px幅レスポンシブレイアウト（横スクロールなし）
- JavaScriptコンソールエラー
- 通知なし時の空状態表示
- 外部通信（Yahoo! Auctions）なし
- アラート条件の作成・編集・削除、所有者分離

Phase 6の保存済みデータだけを評価する場合は`python manage.py run_alerts --evaluate-only`を実行します。外部取得を含む保存検索更新は`python manage.py run_alerts`で手動実行し、スケジューラー接続はデプロイ工程で行います。

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

Yahoo!オークションのHTML変更へ対応するときは、ライブ通信を使う大規模なテストではなく、`tests/fixtures/yahoo/` のfixtureと `tests/test_yahoo_parser.py` を更新します。

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

## GitHub Pages公開

`main` ブランチへpushすると `.github/workflows/docs.yml` がSphinxをビルドし、GitHub Pagesへ公開します。初回のみGitHubリポジトリの **Settings → Pages → Build and deployment → Source** を **GitHub Actions** に設定してください。

Pull Requestではビルド検証だけを行い、公開は行いません。Actions画面から手動実行することもできます。
