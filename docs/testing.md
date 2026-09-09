# Testing

## Test structure

- `tests/unit/`: 外部I/Oを使用しないドメイン・パーサーの単体テスト
- `tests/integration/`: Django、DB、API契約の結合テスト
- `tests/e2e/`: 起動済みアプリケーションを対象にするE2Eテスト
- `tests/fixtures/yahoo/`: representative HTML fixtures for external HTML changes

## Local verification

通常の開発では、変更差分から必要なテストだけを選択する。

```bash
python manage.py verify
python manage.py verify --feature market-search
```

`verify`は成功時に各検査の要約だけを表示し、失敗時に限り末尾40行を表示する。
通常実行と機能単位実行では`slow`を除外する。

全体テストはPhase完了時またはCIでのみ実行する。

```bash
python manage.py verify --full
```

Coverageを含むCI相当の実行:

```bash
coverage run -m pytest
coverage report
```

## E2E browser testing (pytest-playwright)

E2Eテストは、起動済みのDjangoアプリケーションに対してPlaywright同期APIでブラウザー自動化を行う。
通知画面（`/taskle/notifications`）の以下を検証する:

- ログインと初期表示
- 通知の未読フィルター
- 個別・一括既読操作
- ユーザー間の所有者分離
- 390pxモバイルビューポートでのレスポンシブレイアウト
- JavaScriptコンソールエラー検出
- 通知なし時の空状態表示
- 外部通信（Yahoo! Auctionsへのアクセス）がないこと

### 前提条件

1. **SQLiteテストDB**: E2Eテストは本番DB接続なし。環境変数 `DB_ENGINE=sqlite` で隔離。
2. **Chromiumブラウザー**: Playwright経由でインストール・管理。
3. **外部通信allowlist**: 許可ホストに `localhost`、`127.0.0.1`、`cdn.jsdelivr.net`（Bootstrap CDN）、`fonts.googleapis.com`、`fonts.gstatic.com`（Google Fonts）のみ。
   - その他のホストへのリクエストはテスト失敗。
   - URLとホスト名をエラー出力に含める。
4. **ユーザー・通知フィクスチャ**: 各テストメソッドで独立したテストユーザーと通知を作成。

### Windows実行

```powershell
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
$env:DB_ENGINE = "sqlite"
pytest tests/e2e/test_notifications_browser.py -v
```

すべてのE2Eテストを実行:

```powershell
pytest -m e2e -v
```

### 設定ファイル

- `tests/e2e/conftest.py`: Windowsの非同期イベントループ設定、`db_for_e2e`フィクスチャ
- `tests/conftest.py`: e2e マーカー自動付与

### テスト安定性

- Playwrightの待機機構（`wait_for()`、`wait_for_load_state()`）を使用。任意の `time.sleep()` は回避。
- セレクターは既存のid/class/roleを優先し、テキスト部分一致のみに依存しない。
- テスト間でログイン状態やDBデータを共有しない。

## Windows Python execution

PowerShellではプロジェクトルートで `. .\.venv\Scripts\Activate.ps1` を実行してから
`python` を使用する。有効化しない場合は `.\.venv\Scripts\python.exe` を直接指定できる。

Codexの制限付き実行で仮想環境が起動に失敗しても、環境の破損とは限らない。
`pyvenv.cfg` のPython本体へのアクセス制限を確認し、許可された実行環境で
`--version` と `-m pip check` を試してから再作成を判断する。
通常実行で起動できる環境を削除・再作成しない。

PostgreSQLを使うDjangoコマンドには、同じシェルで `DB_NAME`、`DB_USER`、
`DB_PASSWORD` の設定が必要。これらの不足はPythonの起動失敗とは別問題であり、
認証情報をソースや検証ログへ記録しない。

### Local PostgreSQL credentials (Windows)

初回だけ、プロジェクトルートの対話PowerShellで実行する:

```powershell
.\scripts\Set-SystemaDatabase.ps1
```

DB名の既定値は既存起動スクリプトと同じ `Yahuoku_analyze_DB`。
別の接続先には `-DatabaseName`、`-DatabaseHost`、`-DatabasePort` を指定する。
表示される入力欄にPostgreSQLユーザー名・パスワードを入力する。
パスワードはWindows DPAPIで暗号化し、Git対象外の `.local/database.clixml` に保存する。
同じWindowsユーザー・端末で利用する。別端末へのコピー時やパスワード変更時は再設定する。

以後は仮想環境の有効化なしで実行できる:

```powershell
.\scripts\Invoke-Systema.ps1 check_database --require-standard --require-systema
.\scripts\Invoke-Systema.ps1 showmigrations Main
.\scripts\Invoke-Systema.ps1 verify --feature notifications
.\scripts\Invoke-Systema.ps1 runserver 127.0.0.1:8000 --insecure
```

ラッパーは既存のプロセス環境変数を優先し、不足分だけ保存設定で補う。
実行後は元の環境変数へ戻し、Pythonの終了コードを返す。
設定・起動だけでDB作成、マイグレーション、パッケージ更新は行わない。
従来の `run_systema.bat` は引き続き対話入力方式を使用する。
Codexから実行する場合も、Python本体へのアクセスが許可された実行環境が必要。

## Fixture strategy

Fixtures should cover representative HTML states such as:

- valid listing
- missing price
- missing bid count
- unexpected item shape
- page structure drift that can break selectors

## Regression guidance

When Yahoo changes its page structure, the failure should be detectable at the parser layer before it reaches the application API.

This keeps the troubleshooting path short:

- fixture fails
- parser logic is inspected
- targeted fix is applied
- targeted test confirms the fix
