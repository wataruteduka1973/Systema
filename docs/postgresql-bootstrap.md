# PostgreSQLスキーマ構築手順

対象DDL: `sql/postgresql/001_systema_schema.sql`

## 方針

認証、権限、セッション、管理画面、マイグレーション履歴などのDjango標準テーブルは、利用するDjangoバージョン自身に作成させます。DDLはSystemaの`Main`アプリが現在使用する5テーブルだけを作成します。

このDDLは現行モデルとの互換性を優先しています。そのため、既存仕様の`Main_scraping.SearchDay`と`Bidding`はPostgreSQLでも`text`、旧来の大文字フィールド名も引用符付きで維持しています。これらの型変更はデータ移行後に別マイグレーションとして実施します。

## 前提

- PostgreSQL 16以上
- UTF-8データベース
- アプリケーション専用ユーザー
- DjangoからPostgreSQLへ接続できる設定
- DDL適用前のバックアップ

## 1. PostgreSQL接続環境変数

同じPowerShellウィンドウで、実際の値を設定します。パスワードをソース、DDL、Git、チャットへ記録しないでください。

```powershell
$env:DB_ENGINE = "postgresql"
$env:DB_NAME = "Yahuoku_analyze_DB"
$env:DB_USER = "systema_app"
$env:DB_PASSWORD = Read-Host "PostgreSQL password"
$env:DB_HOST = "localhost"
$env:DB_PORT = "5432"
$env:DB_SSLMODE = "prefer"
```

ローカルSQLiteへ戻す場合は、新しいPowerShellを開くか、`DB_ENGINE=sqlite`を設定します。本番では`DB_SSLMODE=require`以上を使用し、サーバー証明書を検証できる環境では`verify-full`を推奨します。

## 2. ドライバーと接続確認

```powershell
python -m pip install -r requirements.txt
python manage.py check_database
```

診断コマンドは接続先、バックエンド、サーバーバージョン、テーブル数だけを表示し、パスワードは表示しません。

## 適用順

1. 空のPostgreSQLデータベースと専用ユーザーを作成します。
2. 上記の環境変数を設定し、接続を確認します。
3. Djangoの`contenttypes`、`auth`、`admin`、`sessions`マイグレーションを適用します。
4. Django標準テーブルを診断します。
5. DDLを1回だけ適用します。
6. `Main`の既存マイグレーションを実行済みとして記録します。
7. Systemaテーブルとマイグレーション状態を確認します。

例:

```powershell
python manage.py migrate contenttypes
python manage.py migrate auth
python manage.py migrate admin
python manage.py migrate sessions
python manage.py check_database --require-standard

$env:PGPASSWORD = $env:DB_PASSWORD
psql --host $env:DB_HOST --port $env:DB_PORT --username $env:DB_USER --dbname $env:DB_NAME --set ON_ERROR_STOP=1 --file sql/postgresql/001_systema_schema.sql
Remove-Item Env:PGPASSWORD

python manage.py check_database --require-systema
python manage.py migrate Main 0009 --fake
python manage.py check_database --require-standard --require-systema
python manage.py showmigrations
python manage.py migrate --plan
```

`--fake`は、DDLで実テーブルを作成した後に限って使用します。DDLが途中失敗した場合や、既存テーブルの構造がDDLと一致しない場合に実行してはいけません。

`check_database --require-systema`が成功する前に`migrate Main ... --fake`へ進んではいけません。PowerShellへコマンドを1行ずつ貼り付ける場合、`throw`の後も次の行を手動実行できてしまうため、エラー発生時点で作業を止めてください。

DDLの日本語既定値は、Windows版`psql`のSJIS/UTF-8差異に影響されないPostgreSQL Unicodeエスケープ表記を使用しています。

`python manage.py migrate`を引数なしでDDLより先に実行すると、`Main`テーブルもDjangoが作成します。その場合はDDLを実行せず、Djangoマイグレーション方式へ統一してください。

## 環境変数一覧

| 変数 | PostgreSQL時 | 既定値 |
|---|---:|---|
| `DB_ENGINE` | 必須 | `sqlite` |
| `DB_NAME` | 必須 | SQLite時は`db.sqlite3` |
| `DB_USER` | 必須 | なし |
| `DB_PASSWORD` | 必須 | なし |
| `DB_HOST` | 任意 | `localhost` |
| `DB_PORT` | 任意 | `5432` |
| `DB_SSLMODE` | 任意 | `prefer` |
| `DB_CONN_MAX_AGE` | 任意 | `60`秒 |

## DDLが作るテーブル

| テーブル | 用途 |
|---|---|
| `Main_errorlog` | アプリケーションエラー |
| `Main_searchrun` | 所有者単位の検索実行 |
| `Main_scraping` | 検索で取得した商品 |
| `Main_searchwordlog` | 検索語履歴 |
| `Main_watchitem` | ウォッチ商品 |

外部キーは`auth_user`、`Main_searchrun`へ設定されます。ウォッチURLの一意性は、ログインユーザーと匿名セッションで別々の部分ユニークインデックスにより保証されます。

## SQLiteデータの移行

DDL適用とマイグレーション確認が完了した空のPostgreSQLに限り、専用コマンドで既存SQLiteデータを移します。通常移行へ含めるのは、ユーザー、グループ、所有者を確認できる検索実行・検索語・ウォッチ商品、および`SearchRun`に連結された商品です。所有者不明データ、未連結の旧商品、過去のエラーログはSQLiteバックアップだけに保存します。

### 1. SQLiteを停止してバックアップ・出力する

書き込み中の不一致を避けるため、開発サーバーやデータ取得処理を停止します。SQLiteを接続先にした新しいPowerShellで実行してください。出力先は既存ファイルを上書きしません。

```powershell
$env:DB_ENGINE = "sqlite"
$migrationDir = "C:\SystemaMigration"
New-Item -ItemType Directory -Force -Path $migrationDir
Copy-Item -LiteralPath .\db.sqlite3 -Destination "$migrationDir\db-before-postgresql.sqlite3"

python manage.py export_postgresql_data `
  --sqlite-backup "$migrationDir\db-before-postgresql.sqlite3" `
  --output "$migrationDir\systema-data.json"
```

コマンドは稼働SQLiteとバックアップのSHA-256が同一であることを確認し、`systema-data.json.manifest.json`へ出力ファイルのハッシュ、移行対象件数、除外件数を記録します。件数が事前調査と一致しない場合は投入へ進まないでください。

### 2. 空のPostgreSQLへ原子的に投入する

PostgreSQL環境変数を設定した別のPowerShellで実行します。投入先のユーザー、グループ、Systema 5テーブルのいずれかにデータがある場合、コマンドは処理を拒否します。

```powershell
python manage.py check_database --require-standard --require-systema
python manage.py import_postgresql_data "C:\SystemaMigration\systema-data.json"
```

投入処理は次を1トランザクションで行います。

1. manifestとfixtureのSHA-256を照合
2. 依存順にユーザー、グループ、検索実行、商品、検索語、ウォッチ商品を投入
3. テーブル別件数をmanifestと照合
4. 所有者不明・二重所有・未連結商品がないことを確認
5. PostgreSQLのIDシーケンスを最大IDへ調整

どれかが失敗すると投入全体がロールバックされます。

### 3. 投入後確認

```powershell
python manage.py check_database --require-standard --require-systema
python manage.py check
python manage.py test
```

画面ではログイン、検索履歴、検索結果詳細、検索語履歴、ウォッチリストをユーザーごとに確認します。匿名セッションのデータは所有権を維持して移しますが、古いブラウザーセッションが失われている場合は画面から再参照できないことがあります。

## ロールバック

DDL全体はトランザクション内で実行されます。途中で失敗した場合、5テーブルの作成はまとめてロールバックされます。適用後に削除する場合は、対象データベースとバックアップを確認してから、依存順に別の明示的なロールバックスクリプトを用意してください。
