# 情報分析ツール システマ

![Version](https://img.shields.io/badge/Version-1.0.0-blue) [![Documentation](https://github.com/wataruteduka1973/Systema/actions/workflows/docs.yml/badge.svg)](https://github.com/wataruteduka1973/Systema/actions/workflows/docs.yml)

このツールは、ヤフオクの**購入**や**出品**に関する商品の価格や傾向を分析し、ユーザーに最適な意思決定をサポートします。相場データや現在出品中の商品を活用し、市場動向を可視化します。

## ✨ 特徴
- **統一相場検索**: 落札・現在出品・保存済みデータを1画面で検索。
- **ターゲット分析**: 現在出品と落札相場を比較し、購入判断・ウォッチリストを管理。
- **在庫・出品管理**: 購入候補を在庫化し、利益シミュレーションを実施。
- **アラート・通知**: 価格下落や終了間近などの条件を監視し、アプリ内通知で知らせる。

## 📋 主な機能

| 機能名 | 概要 | 用途 |
|--------|------|------|
| **統一相場検索** (`/taskle/market-search`) | 落札・現在出品・保存済みデータを1つの検索条件で取得 | 購入・出品戦略の策定 |
| **ターゲット分析** (`/taskle/Deep_Analysis_now`) | 現在出品と落札中央値を比較し、購入判断とウォッチリストを管理 | お買い得商品の特定 |
| **相場分析** (`/taskle/Deep_Analysis`) | 保存済み落札データの推移・中央値・四分位範囲を可視化 | 市場トレンドの理解 |
| **相場予想** (`/taskle/Yahuoku_prediction`) | 直近90日の中央値から30日後の価格を予測し、過去予測の精度を検証 | 落札価格の推測・出品分析 |
| **出品・在庫管理** (`/taskle/seller-management`) | 購入候補を在庫化し、取得費用・想定利益を計算 | 出品前の採算確認 |
| **アラートルール** (`/taskle/alerts`) | 価格下落・終了間近・入札停滞などの条件をオーナー単位で設定 | 見逃し防止 |
| **通知センター** (`/taskle/notifications`) | アラート・保存検索の結果を1画面で確認 | 対応漏れの防止 |
| **管理者モニタリング** (`/taskle/developer/`) | staffユーザー向けの読み取り専用ダッシュボード | 稼働状況の把握 |

一部の機能（メルカリ連携によるドメスティック複数市場比較、掘り出し物発見スキャン、商品画像表示）は設計段階で未実装です。詳細は [docs/PROJECT.md](docs/PROJECT.md) と `docs/features/` を参照してください。

## 🚀 インストール

### すぐに使う（Windows）

1. リポジトリをクローン:
   ```bash
   git clone https://github.com/wataruteduka1973/Systema.git
   cd Systema
   ```

2. `run_systema.bat` を実行（PostgreSQL接続情報が未設定の場合は入力を求められます）

3. `http://127.0.0.1:8000/taskle/` を開く

### 開発環境

標準データベースはPostgreSQLです（一時的な確認のみ`DB_ENGINE=sqlite`でSQLiteを使用可能）。

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Windowsで仮想環境の有効化なしにコマンドを実行したい場合は、`.\scripts\Set-SystemaDatabase.ps1` でPostgreSQL資格情報を一度だけ保存し、以後`.\scripts\Invoke-Systema.ps1 <command>`を使用してください。詳細は [docs/development.md](docs/development.md) と [docs/testing.md](docs/testing.md) を参照してください。

## 📚 ドキュメント

本番公開時は、事前に [本番環境のセキュリティ設定](docs/deployment-security.md) を確認してください。
PostgreSQLの初期スキーマを手動構築する場合は、[PostgreSQLスキーマ構築手順](docs/postgresql-bootstrap.md) を参照してください。

ローカルでは次のコマンドで生成できます。

```powershell
.\document\make.bat clean html
```

`main` ブランチへpushすると、GitHub ActionsがSphinxドキュメントをビルドしてGitHub Pagesへ公開します。初回のみリポジトリの **Settings → Pages → Source** を **GitHub Actions** に設定してください。

## ✅ 品質チェック

通常の開発では、変更差分から必要なテストだけを選ぶ`verify`管理コマンドを使います（Ruff・Black・関連pytest・`manage.py check`・必要に応じてマイグレーション整合性チェックをまとめて実行）。

```powershell
python -m pip install -r requirements-dev.txt
python manage.py verify
python manage.py verify --feature market-search
python manage.py verify --full   # Phase完了時・CI相当のフルスイート
```

CIと同等のカバレッジ計測、および個別ツールの直接実行:

```powershell
mypy
coverage run -m pytest
coverage report
```

ローカル本番前提条件（DEBUG無効化・許可ホスト・レート制限・マイグレーション等）を、データを変更せず確認する場合:

```powershell
python manage.py check_release
```

pytest・Ruff・Black・mypy・SphinxはpushとPull RequestごとにGitHub Actionsでも検証されます。詳細は [docs/testing.md](docs/testing.md) を参照してください。

### ブラウザーE2Eテスト

Playwrightを使った通知・アラート条件画面のE2Eテストは、本番DBに接続せず、SQLiteのテストDBで実行します。Windowsでは次の手順でChromiumを準備します。

```powershell
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
$env:DB_ENGINE = "sqlite"
pytest tests/e2e/test_notifications_browser.py -v
```

すべてのE2Eテストを実行する場合:

```powershell
$env:DB_ENGINE = "sqlite"
pytest -m e2e -v
```

E2Eテスト対象:
- ログイン・初期表示・所有者分離
- 未読フィルター切り替え
- 個別通知の既読・未読トグル
- すべて既読アクション
- 390px幅でのレスポンシブレイアウト（横スクロールなし）
- JavaScriptコンソールエラー検出
- 通知なし時の空状態表示
- Yahoo! Auctionsへの外部通信がないこと
- アラート条件の作成・編集・削除、所有者分離、390px幅での表示

Phase 6のアラートを保存済みデータだけで手動評価する場合:

```powershell
python manage.py run_alerts --evaluate-only
```

テスト実行環境:
- SQLiteテストDB（本番DB接続なし）
- Chromiumブラウザー
- 仮想テストサーバー (localhost)
- 許可ホスト: localhost, 127.0.0.1, cdn.jsdelivr.net, fonts.googleapis.com, fonts.gstatic.com

本番環境のブラウザー確認はPhase 9のリリースゲートで行います。

本アプリケーションのドキュメントは以下より閲覧できます
https://wataruteduka1973.github.io/Systema/

## 🧭 プロジェクト構成・設計方針

- [AGENTS.md](AGENTS.md): 実装・検証・ドキュメント更新の進め方
- [docs/PROJECT.md](docs/PROJECT.md): 全体構成、機能別ドキュメントへのリンク、現行の製品方針
- [docs/architecture.md](docs/architecture.md): スクレイピング境界を含むアーキテクチャ
- `docs/features/`: 機能ごとの仕様・所有権・関連ファイル
- `docs/decisions/`: ADR（設計決定記録）
- `docs/plans/`: 進行中のロードマップ

## 🤝 貢献
バグ報告や機能リクエストは [GitHub Issues](https://github.com/wataruteduka1973/Systema/issues) へ。  
ご質問は [agtmpdd992@gmail.com](mailto:agtmpdd992@gmail.com)まで
