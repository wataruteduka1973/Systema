# Linuxでの運用（Docker Compose）

Linuxサーバーでは、Docker Composeで次の5つのサービスをまとめて動かします（ADR 0007）。

| サービス | 役割 |
|---|---|
| `db` | PostgreSQL 16。データは名前付きボリューム `pgdata` に保存 |
| `redis` | ログイン・外部検索の回数制限カウンター（ディスクには保存しない） |
| `migrate` | 起動のたびにマイグレーションを適用して終了する |
| `web` | gunicorn（`WEB_CONCURRENCY` 個のワーカー）。静的ファイルはWhiteNoiseが配信 |
| `scheduler` | `manage.py run_alert_scheduler`。1時間ごとに `run_alerts` を実行（このサービスだけ） |

`web` は定期実行を起動しません（`SYSTEMA_ALERT_SCHEDULER=false`）。定期実行は `scheduler` の1プロセスだけで行い、同時実行はPostgreSQLのアドバイザリーロックでも防ぎます。

## 必要なもの

- Docker Engine と Docker Compose プラグイン（`docker compose version` で確認）
- このリポジトリのクローン

## 初回の起動

```bash
git clone https://github.com/wataruteduka1973/Systema.git
cd Systema
scripts/linux/create-env.sh --domain example.com   # 公開するドメインを指定
docker compose up -d --build
scripts/linux/smoke-test.sh example.com
docker compose exec web python manage.py createsuperuser
```

`create-env.sh` は `deploy/env.example` をもとに `.env` を作り、Djangoの秘密鍵とデータベースのパスワードをランダムに生成します。`.env` は所有者だけが読めるモード600で作られ、Gitの管理対象外です。既にある `.env` は上書きしません。

本番モード（`SYSTEMA_ENV=production`）ではHTTPからHTTPSへのリダイレクト、Secure Cookie、HSTSが有効になります。`web` は既定で `127.0.0.1:8000` にだけ公開されるので、HTTPSを終端するリバースプロキシ（nginx、Caddyなど）を前に置き、`Host` と `X-Forwarded-Proto` を渡してください。HTTPSとドメインの設定は、公開するサーバーとドメインが決まってから追加します。

`smoke-test.sh` は、リバースプロキシ経由と同じヘッダーでトップページと静的ファイルを確認し、`check_release` と `scheduler` の起動状態も確認します。

## このマシンだけで試す（HTTP）

```bash
scripts/linux/create-env.sh --local
docker compose up -d --build
```

`http://127.0.0.1:8000/taskle/` を開けます。開発モードで動くので、インターネットへ公開しないでください。本番用に切り替えるときは `.env` を削除して `--domain` で作り直します（データベースのボリュームはそのまま使えます）。

## 日常の操作

| 操作 | コマンド |
|---|---|
| 状態の確認 | `docker compose ps` |
| ログ | `docker compose logs -f web scheduler` |
| 更新（新しいコードの反映） | `git pull && docker compose up -d --build` |
| 停止 | `docker compose down`（データは残る） |
| 管理コマンド | `docker compose exec web python manage.py <command>` |
| 定期実行を手動で1回 | `docker compose exec scheduler python manage.py run_alerts` |

`docker compose down -v` はデータベースを含むボリュームを削除します。運用中のサーバーでは使わないでください。

アプリのログファイル（`logs/`）はボリューム `app-logs`、定期実行の最終開始時刻（`.local/`）はボリューム `app-local` に残るので、再起動しても余分な取得は起きません。

## バックアップと復元

```bash
# バックアップ（カスタム形式）
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > systema-$(date +%Y%m%d).dump

# 復元（空のデータベースへ。既存データを上書きする前に必ずバックアップを取ってください）
docker compose exec -T db sh -c 'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' < systema-YYYYMMDD.dump
```

復元の手順は、本番データへ適用する前に別の環境で確認してください（`docs/features/release-readiness.md` のチェックリスト）。

## Linuxでの開発（`run_systema.sh`）

Windowsの `run_systema.bat` と同じ流れをLinuxで1コマンドで行います。

```bash
./run_systema.sh
```

`.venv` の作成、依存関係の導入、PostgreSQLへの接続確認、マイグレーション、静的ファイルの収集のあと、`127.0.0.1:8000` で開発サーバーと定期実行を起動します。

- 環境変数で指定したDB設定はそのまま使います。足りない値は `~/.config/systema/database.env` から読み、まだ足りなければ入力を求めます。
- 接続に成功すると、入力した値を `~/.config/systema/database.env` に保存するか確認します。LinuxにはWindowsのDPAPIがないため、プロジェクトの外に所有者だけが読める形（フォルダー700・ファイル600）で保存します。`~/.pgpass` と同じ考え方です。接続に失敗した値は保存しません。
- Windowsと共有しているフォルダーにWindows用の `.venv` がある場合は、`.venv-linux` を使います。
- `SYSTEMA_ALERT_SCHEDULER=false` で定期実行を止められます。`DB_ENGINE=sqlite` を指定するとSQLiteで起動します。

## 関連ファイル

- `Dockerfile`, `.dockerignore`, `compose.yaml`, `deploy/env.example`
- `scripts/linux/create-env.sh`, `scripts/linux/smoke-test.sh`, `run_systema.sh`
- `Main/management/commands/run_alert_scheduler.py`, `Main/services/alert_scheduler.py`
- `System_Config/cache.py`（`DJANGO_CACHE_BACKEND` / `DJANGO_CACHE_LOCATION`）
- `.github/workflows/ci.yml`（`Linux container` ジョブ）
- `docs/decisions/0007-linux-docker-compose-deployment.md`
