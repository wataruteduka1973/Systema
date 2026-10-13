# HTTPエンドポイント

すべてのURLは `/taskle/` を基点とします。外部サイトにアクセスする検索系エンドポイントは、失敗時に `error` と `code` を含むJSONと4xxまたは5xxを返します。外部検索には利用者ごとの回数制限があり、超えると429と `Retry-After` を返します。変更を伴う操作はCSRFトークンが必要です。

## 検索と分析

| パス | メソッド | 概要 |
|---|---|---|
| `perform_search` | GET | `keyword` の落札商品を取得して保存し、状態別・相場の統計を返す |
| `RealtimeSearch` | GET | `keyword` の現在出品を取得し、保存済みの落札相場（`closedMarket`）との比較（`closedMarketComparison`）を付けて返す |
| `get_search_words` | GET | 保存済みの検索キーワード |
| `get_market_data` | GET | 指定キーワードの保存済みデータと分析 |
| `update_market_data` | POST | 保存済みデータを取り直す |
| `delete_market_data` | DELETE | 保存済みデータを削除 |
| `complex_market_data` | GET | 落札相場と現在出品を合わせたターゲット分析 |
| `prediction_market` | GET | 落札データからの30日後の相場予想とバックテスト |
| `get_popular_words` | GET | よく使われる検索語 |
| `watchlist`, `watchlist/{id}` | GET/POST, PATCH/DELETE | ウォッチリストの一覧・登録・更新・解除 |

## ログインが必要なAPI（`api/v1/`）

| パス | 概要 |
|---|---|
| `saved-searches`, `saved-searches/{id}`, `saved-searches/{id}/run` | 保存検索の一覧・作成・更新（取得頻度 `refreshIntervalHours` を含む）・削除・今すぐ取得。応答の `refresh` に取得状況を含む |
| `alert-rules`, `alert-rules/{id}` | アラート条件の一覧・作成・更新・削除 |
| `notifications`, `notifications/{id}`, `notifications/read-all` | 通知の一覧（`category` で絞り込み）・既読の切り替え・すべて既読 |
| `watch-items/{id}/purchase-budget`, `cost-settings` | 仕入れ予算の試算と共通の費用設定 |
| `watch-items/{id}/convert-to-inventory` | ウォッチ商品を在庫へ変換 |
| `inventory-items`, `inventory-items/{id}`, `inventory-items/{id}/profit-simulation` | 在庫の管理と利益の試算 |
| `seller-listings`, `seller-listings/{id}`, `seller-listings/{id}/refresh`, `seller-listings/{id}/snapshots` | 出品の管理、公開情報の取り直し、観測履歴 |
| `seller-listings/{id}/sale` | 販売結果の確定 |
| `seller-outcomes` | 販売実績の集計（`from`/`to` で期間指定） |

## 検索レスポンスの基本形

落札商品の検索に成功すると、`data` 配列に `name`、`price`、`startPrice`、`bidding`、`time`、`url` を持つ商品が入ります。現在出品の検索では `currentPrice`、`remainingTime`、`imageUrl` を使用します。

```json
{
  "data": [
    {
      "name": "商品名",
      "price": 12000,
      "startPrice": 1000,
      "bidding": 8,
      "time": "2026-08-13T10:00:00+09:00",
      "url": "https://auctions.yahoo.co.jp/jp/auction/example"
    }
  ]
}
```

入力値と詳細な応答項目は `Main/views/api.py`、`Main/services/` と `tests/integration/` のテストを正としてください。
