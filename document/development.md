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

## CIとマージ保護

pushとPull Requestごとに、`.github/workflows/ci.yml`がlint・型検査・テスト・Sphinxビルドを実行します。GitHubの **Settings → Branches → Branch protection rules** で`main`を対象にし、次のRequired status checksを指定してください。

- `Lint and type check`
- `Tests`
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
