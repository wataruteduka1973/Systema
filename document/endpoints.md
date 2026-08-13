# HTTPエンドポイント

すべてのURLは `/taskle/` を基点とします。検索系エンドポイントは外部サイトの応答に依存するため、失敗時には `error` を含むJSONと4xxまたは5xxを返すことがあります。

| パス | メソッド | 概要 |
|---|---|---|
| `perform_search` | GET | `keyword` の終了商品を取得して保存 |
| `RealtimeSearch` | GET | `keyword` の現在出品商品を取得 |
| `get_search_words` | GET | 保存済み検索キーワードを取得 |
| `get_market_data` | GET | 指定キーワードの保存済み相場データを取得 |
| `update_market_data` | POST | 保存済みデータを更新 |
| `delete_market_data` | DELETE | 保存済みデータを削除 |
| `complex_market_data` | GET | 終了相場と現在出品商品を複合分析 |
| `prediction_market` | GET | 過去データの価格推移と予測を取得 |
| `get_popular_words` | GET | 使用頻度の高い検索語を取得 |

## 検索レスポンスの基本形

終了商品の検索に成功すると、`data` 配列に `name`、`price`、`startPrice`、`bidding`、`time`、`url` を持つ商品が入ります。現在出品検索では `currentPrice` と `remainingTime` を使用します。

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

入力値と詳細なレスポンス項目は `Main/views/api.py`、`Main/views/utils.py` および `tests/api_test.py` を正としてください。
