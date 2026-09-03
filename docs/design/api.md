# API Design

## 1. Purpose and Status

本書はSystemaの現行HTTP APIと、`docs/plans/release-feature-roadmap.md`を実現する将来APIを分けて定義する。将来APIは設計であり、未実装である。

## 2. Current API Baseline

すべて`/taskle/`配下。Djangoセッションを使用し、変更系はCSRF必須。検索・ウォッチはログインユーザーまたは匿名セッションを所有者として扱う。

| Method | Path | Current purpose | Persistence |
|---|---|---|---|
| GET | `perform_search?keyword=` | 落札検索、状態・相場統計 | `SearchRun(closed)`と商品行 |
| GET | `RealtimeSearch?keyword=` | 現在出品検索、状態・相場統計 | `SearchRun(current)`と商品行 |
| GET | `get_search_words` | 所有者の落札検索キーワード | 参照のみ |
| GET | `get_market_data?keyword=` | 最新保存結果と履歴分析 | 参照のみ |
| POST | `update_market_data?keyword=` | 落札データ再取得 | 新しいrunと商品行 |
| DELETE | `delete_market_data?keyword=` | キーワード単位の落札履歴削除 | 関連runを削除 |
| GET | `complex_market_data?keyword=` | 落札・現在出品の比較、買い時判定 | closed/current runと商品行 |
| GET | `prediction_market?keyword=` | 30日予測とバックテスト | prediction run |
| GET | `get_popular_words?top=` | 検索語ランキング | 参照のみ |
| GET | `watchlist` | 所有者の購入候補一覧 | 参照のみ |
| POST | `watchlist` | 購入候補登録・再登録時更新 | `WatchItem` |
| PATCH | `watchlist/{id}` | 本人のメモ・優先度・判断状態更新 | `WatchItem` |
| DELETE | `watchlist/{id}` | 本人の購入候補解除 | `WatchItem`削除 |
| GET | `watchlist/{id}/snapshots` | 本人の価格・入札履歴と分析要約 | 参照のみ |

### Current response characteristics

- 検索成功は主に`{"data": [...]}`を返す。
- 分析APIは`marketStatistics`、`conditionSummary`、`analysis`等を追加する。
- エラーは`{"error": "message", "code": "machine_code"}`または`{"error": "message"}`で統一されていない。
- ページングはなく、検索取得数と画面側ページングに依存する。
- `perform_search`等はGETだが外部アクセスとDB書込みを伴う。

## 3. Compatibility Strategy

- 現行エンドポイントは既存画面の互換層として当面維持する。
- 新機能は`/taskle/api/v1/`へ追加する。
- 既存レスポンスを一括変更しない。画面移行後に非推奨化し、アクセスログで未使用を確認してから削除する。
- 新APIの検索実行は副作用があるため`POST /search-runs`とする。
- API viewは認証、HTTP、入力変換までとし、条件・利益・通知・比較ロジックはservice/domainへ置く。

## 4. Common v1 Contract

### Authentication and ownership

- Django session authenticationを使用する。
- POST/PATCH/PUT/DELETEはCSRFトークン必須。
- `SavedSearch`、通知、アラート、在庫、出品、販売実績はログイン必須。
- 既存の匿名検索・匿名`WatchItem`は継続可能だが、v1の永続的ユーザー機能へはログイン後に移管する。
- リソース取得は必ず`request.user`を起点にし、他ユーザーのIDは存在しても404を返す。
- staff APIは`is_staff`を必須とする。

### Success envelope

```json
{
  "data": {},
  "meta": {
    "requestId": "optional-id"
  }
}
```

一覧は以下を追加する。

```json
{
  "data": [],
  "meta": {"page": 1, "pageSize": 20, "total": 0}
}
```

- `pageSize`既定20、最大100。
- 日時はtimezone付きISO 8601、金額は円単位の非負整数。
- フィールド名はcamelCase、DB内部名はsnake_caseでよい。
- 更新成功は更新後リソースを返す。削除成功は204。

### Error envelope

```json
{
  "error": {
    "code": "validation_error",
    "message": "入力内容を確認してください。",
    "fields": {"minimumPrice": ["0以上で入力してください。"]}
  }
}
```

| Status | Meaning |
|---|---|
| 400 | JSON形式、状態遷移、入力値が不正 |
| 401 | 未ログイン |
| 403 | CSRFまたはstaff権限不足 |
| 404 | 本人所有の対象が存在しない |
| 409 | 重複、状態競合、同時更新競合 |
| 422 | 形式は正しいが業務規則を満たさない |
| 429 | レート制限。`Retry-After`を付与 |
| 503 | Yahoo等の外部サービス取得失敗 |

ログやレスポンスへセッションキー、Cookie、認証情報、他ユーザーIDを出さない。

## 5. Search Criteria Contract

手動検索、保存検索、アラート、自動実行で共通化する。

```json
{
  "keyword": "camera body",
  "searchType": "closed",
  "condition": "used",
  "minimumPrice": 1000,
  "maximumPrice": 50000,
  "excludedKeywords": ["ジャンク", "部品取り"],
  "endingWithinMinutes": null,
  "sortOrder": "price-asc"
}
```

- `searchType`: `closed | current | target | prediction`
- `condition`: `new | used | junk | unknown | null`
- `minimumPrice <= maximumPrice`
- `excludedKeywords`は空文字除去、重複除去、件数・文字長制限を行う。
- `endingWithinMinutes`はcurrent/targetだけで有効。
- 正規化後の値を`SearchRun.criteria_snapshot`へ保存する。

## 6. Planned v1 Endpoints

### 6.1 Search execution and history

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/v1/search-runs` | 共通条件で検索を実行 |
| GET | `/api/v1/search-runs` | 本人の履歴一覧、種別・期間・成功可否で絞込 |
| GET | `/api/v1/search-runs/{id}` | 条件スナップショット、統計、商品一覧 |
| DELETE | `/api/v1/search-runs/{id}` | 本人の1実行を削除 |
| POST | `/api/v1/search-run-comparisons` | 2実行の比較 |

`POST /search-runs` request:

```json
{"criteria": {}, "savedSearchId": null, "trigger": "manual"}
```

ユーザー入力からの`trigger`は`manual`または`saved`だけを許可し、`scheduled`等はサーバー内部で設定する。

Comparison request:

```json
{"leftRunId": 10, "rightRunId": 20}
```

Responseはsummary差分、condition composition、新規・消失・継続商品、日数差を返す。初期版は成功済みclosed run同士に限定する。

### 6.2 Saved searches

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/api/v1/saved-searches` | 一覧・作成 |
| GET/PATCH/DELETE | `/api/v1/saved-searches/{id}` | 参照・部分更新・削除 |
| POST | `/api/v1/saved-searches/{id}/run` | 保存条件を即時実行 |

作成・更新は`name`とSearch Criteriaを受け取る。削除しても過去`SearchRun`は残り、FKはNULLになる。
保存条件は検索種別を受け取らず、即時実行は常にターゲット分析を行う。表示した結果は`SearchRun.result_snapshot`へ保存する。
ターゲット分析とユーザーページの「作成して実行」は`replaceExisting: true`を付ける。同一所有者・同一キーワード名の条件があれば更新し、続けて`/{id}/run`を呼び出すことで表示結果も保存する。

### 6.3 Buyer watchlist

Legacy `/taskle/watchlist` endpoints now support Phase 2 decisions, filtering, snapshots, and analysis while the v1 envelope remains planned. Observation refreshes update observed listing fields only and never overwrite note, priority, category, or lifecycle status. History analysis is calculated from snapshots rather than persisted as duplicate derived columns.

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/api/v1/watch-items` | 購入候補一覧・登録 |
| GET/PATCH/DELETE | `/api/v1/watch-items/{id}` | 詳細・メモ等更新・解除 |
| GET | `/api/v1/watch-items/{id}/snapshots` | 価格・入札推移 |
| POST | `/api/v1/watch-items/{id}/convert-to-inventory` | 購入候補を仕入済み在庫へ変換 |
| GET/POST | `/api/v1/watch-tags` | 本人のタグ一覧・作成 |

PATCHで変更できるユーザー項目と、検索更新が変更する観測項目を分離する。検索更新はnote、priority、tags、lifecycleStatusを上書きしない。

### 6.4 Inventory and seller listings

Phase 3A implements the inventory endpoints below on the existing v1 path. Seller-listing endpoints remain planned.

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/api/v1/inventory-items` | 在庫一覧・手動登録 |
| GET/PATCH/DELETE | `/api/v1/inventory-items/{id}` | 在庫詳細・更新・削除 |
| POST | `/api/v1/inventory-items/{id}/profit-simulation` | 保存せず出品前の見込み利益を再計算 |
| POST | `/api/v1/watch-items/{id}/convert-to-inventory` | 本人の購入候補を重複なく仕入済み在庫へ変換 |
| GET/POST | `/api/v1/seller-listings` | 自分の出品一覧・URL登録 |
| GET/PATCH/DELETE | `/api/v1/seller-listings/{id}` | 出品詳細・費用/状態更新・削除 |
| POST | `/api/v1/seller-listings/{id}/refresh` | 公開出品ページを再取得 |
| GET | `/api/v1/seller-listings/{id}/snapshots` | 価格・入札・見込み利益推移 |
| POST | `/api/v1/seller-listings/{id}/profit-simulations` | 保存せず価格・費用シミュレーション |
| PUT | `/api/v1/seller-listings/{id}/sale` | 販売実績を確定または修正 |
| GET | `/api/v1/seller-analytics/summary` | 期間別売上・利益・販売日数 |

Seller listing create request:

```json
{
  "inventoryItemId": 12,
  "url": "https://auctions.yahoo.co.jp/...",
  "acquisitionCost": 12000,
  "shippingCostEstimate": 1000,
  "packagingCostEstimate": 200,
  "otherCostEstimate": 0,
  "feeRate": "0.1000",
  "targetProfit": 5000
}
```

Profit simulation response:

```json
{
  "data": {
    "salePrice": 22000,
    "feeEstimate": 2200,
    "totalCost": 15400,
    "estimatedProfit": 6600,
    "profitMarginPercent": 30.0,
    "breakEvenPrice": 14667
  }
}
```

- サーバー側が利益を再計算し、クライアント計算値は信用しない。
- Phase 3Aの利益計算では永続化済みの仕入価格を正とし、手数料は1円単位で四捨五入、損益分岐価格は赤字を避ける方向へ切り上げる。シミュレーション入力は保存しない。
- URL host allowlistと商品識別子正規化を行う。
- Yahooログイン情報、Cookie、アクセストークンは受け取らない。
- refreshは検索APIと別のユーザー単位レート制限を持つ。

### 6.5 Seller recommendations (Phase 7)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/seller-listings/{id}/recommendations` | 早期売却・標準・利益重視価格、売れ残りリスク |
| POST | `/api/v1/seller-tools/title-suggestions` | 類似落札語からタイトル候補 |
| GET | `/api/v1/seller-tools/end-time-suggestions?keyword=` | 曜日・時間帯候補 |
| GET | `/api/v1/seller-analytics/forecast-accuracy` | 想定利益と確定利益の検証 |

根拠件数と品質を必ず返し、データ不足時は提案を生成せず`available: false`と理由を返す。

### 6.6 Notifications and alerts

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/notifications` | 本人通知一覧。`unreadOnly`対応 |
| PATCH | `/api/v1/notifications/{id}` | 既読・未読更新 |
| POST | `/api/v1/notifications/read-all` | 一括既読 |
| GET/POST | `/api/v1/alert-rules` | 本人ルール一覧・作成 |
| GET/PATCH/DELETE | `/api/v1/alert-rules/{id}` | 詳細・更新・削除 |

Alert rule types:

- buyer: `price_below`, `median_discount`, `ending_soon`, `low_bids`, `buy_score`
- seller: `bid_stalled`, `ending_without_bids`, `loss_risk`, `target_profit`, `market_decline`

重複イベントは`dedupe_key`とcooldownで抑止する。メール配信は通知作成とは別のoutbox処理とする。

### 6.7 Staff monitoring

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/admin/metrics` | 成功率、失敗分類、実行時間、DB量 |
| GET | `/api/v1/admin/events` | 構造化イベントの安全な検索 |

完全な検索語、メール、セッションキー、Cookieは返さない。検索語別分析が必要な場合は不可逆ハッシュまたは短期限定の明示的にマスクした値を使う。

## 7. Concurrency, Idempotency, and Jobs

- 登録系の重複はDB unique constraintで防ぐ。
- refresh、保存検索run、通知生成はidempotency keyまたは実行ロックを持つ。
- `updatedAt`をPATCHに渡し、古い画面からの上書きは409にできる設計を推奨する。
- 定期ジョブはAPI request内で常駐させない。管理コマンドから開始し、デプロイ時にschedulerへ接続する。
- 外部取得失敗時も`SearchRun`/operation eventへfailure codeとdurationを残す。

## 8. Migration and Deprecation

1. v1共通serializer、error、ownership、paginationを追加する。
2. 新画面から順にv1へ切り替える。
3. legacy endpointごとに利用ログを確認する。
4. 呼出しがなくなったendpointを非推奨化し、リリースノート後に削除する。
5. `searchwordlog`は`SearchRun`集計へ移行後に廃止候補とする。

## 9. Required Tests

- 全ID指定APIで別ユーザーのリソースが404になる。
- 変更系はCSRFなしで403になる。
- anonymousからloginへの既存watch/search移管が壊れない。
- 利益計算は負数、0、丸め、手数料率境界を検証する。
- refreshのURL allowlist、rate limit、timeout、外部失敗を検証する。
- 通知重複、ジョブ再実行、同時更新を検証する。
- legacy response contractの回帰テストをv1移行完了まで残す。
