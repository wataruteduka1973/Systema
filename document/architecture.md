# アーキテクチャ

## 構成

- `Main/views/urls.py`: HTML画面を返すビュー
- `Main/views/api.py`: HTTPリクエストの検証とJSONエンドポイント
- `Main/views/utils.py`: 検索、保存、分析処理
- `Main/scraping/yahoo.py`: Yahoo!オークションHTMLの抽出と正規化
- `Main/models/`: 検索結果、検索語、エラーログのモデル
- `Main/templates/`: Djangoテンプレート
- `Main/static/`: JavaScript、CSS、画像
- `System_Config/`: Django設定とルーティング

## データフロー

1. ブラウザが `/taskle/` 配下の画面を開きます。
2. JavaScriptがJSONエンドポイントへ検索条件を送信します。
3. APIビューが入力を検証し、ユーティリティ層へ処理を委譲します。
4. スクレイパーが外部HTMLを取得し、パーサーが共通形式へ正規化します。
5. 必要に応じてSQLiteへの保存やNumPy・scikit-learnによる分析を行います。
6. JSONを受け取ったフロントエンドが表やグラフを更新します。

## 保守境界

外部HTMLの変更は `Main/scraping/yahoo.py` に閉じ込め、APIレスポンス形式や分析処理へ波及させないことを基本方針とします。公開APIの項目を変更するときは、フロントエンドとAPIテストも同時に更新します。
