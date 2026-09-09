# 情報分析ツール システマ

![Version](https://img.shields.io/badge/Version-1.0.0-blue) [![Documentation](https://github.com/wataruteduka1973/Systema/actions/workflows/docs.yml/badge.svg)](https://github.com/wataruteduka1973/Systema/actions/workflows/docs.yml)

このツールは、ヤフオクの**購入**や**出品**に関する商品の価格や傾向を分析し、ユーザーに最適な意思決定をサポートします。相場データや現在出品中の商品を活用し、市場動向を可視化します。

## ✨ 特徴
- **リアルタイムデータ**: 最新の市場動向を即座に把握。
- **データ可視化**: グラフやワードクラウドでトレンドを視覚化。
- **価格予測**: AIを活用した将来の価格予測。

## 📋 主な機能

| 機能名       | 概要                                      | 特徴                                   | 用途                          |
|--------------|-------------------------------------------|----------------------------------------|--------------------------------|
| **相場検索** | 過去180日間の落札データを取得             | 落札金額・入札数確認、フィルタリング    | 購入・出品戦略の策定           |
| **現在価格検索** | 現在出品中の商品データを取得         | リアルタイム金額・入札数確認            | 市場価格の把握                 |
| **相場再検索** | 取得データを再度確認                  | データ更新・削除                       | データ管理                     |
| **相場分析** | 売れ筋商品を分析                         | ワードクラウド、棒グラフ               | 市場トレンドの理解             |
| **市場分析** | 注目商品をピックアップ                    | 相場との比較、お買い得商品特定         | 競争優位性の確保               |
| **相場予想** | 今後の商品価格を予想                      | 過去データベースのマーケット予想        | 落札価格の推測・出品分析       |



## 🚀 インストール

1. リポジトリをクローン:
   ```bash
   git clone https://github.com/wataruteduka1973/Systema.git
   cd Systema
   ```

2. Windowsでは `run_systema.bat` を実行

3. `http://127.0.0.1:8000/taskle/` を開く

## 📚 ドキュメント

本番公開時は、事前に [本番環境のセキュリティ設定](docs/deployment-security.md) を確認してください。
PostgreSQLの初期スキーマを手動構築する場合は、[PostgreSQLスキーマ構築手順](docs/postgresql-bootstrap.md) を参照してください。

ローカルでは次のコマンドで生成できます。

```powershell
.\document\make.bat clean html
```

`main` ブランチへpushすると、GitHub ActionsがSphinxドキュメントをビルドしてGitHub Pagesへ公開します。初回のみリポジトリの **Settings → Pages → Source** を **GitHub Actions** に設定してください。

## ✅ 品質チェック

```powershell
python -m pip install -r requirements-dev.txt
ruff check .
black --check Main System_Config tests
mypy
coverage run -m pytest
coverage report
```

pytest・Ruff・Black・mypy・SphinxはpushとPull RequestごとにGitHub Actionsでも検証されます。

### ブラウザーE2Eテスト

Playwrightを使った通知画面のE2Eテストは、本番DBに接続せず、SQLiteのテストDBで実行します。Windowsでは次の手順でChromiumを準備します。

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

テスト実行環境:
- SQLiteテストDB（本番DB接続なし）
- Chromiumブラウザー
- 仮想テストサーバー (localhost)
- 許可ホスト: localhost, 127.0.0.1, cdn.jsdelivr.net, fonts.googleapis.com, fonts.gstatic.com

本番環境のブラウザー確認はPhase 9のリリースゲートで行います。

本アプリケーションのドキュメントは以下より閲覧できます
https://wataruteduka1973.github.io/Systema/

## 🤝 貢献
バグ報告や機能リクエストは [GitHub Issues](https://github.com/wataruteduka1973/Systema/issues) へ。  
ご質問は [agtmpdd992@gmail.com](mailto:agtmpdd992@gmail.com)まで
