# Database Design

## 1. Purpose and Status

本書は現行DBの実態と、リリースロードマップに必要な将来スキーマを定義する。2026-09-12のソースにはMain migration `0022_sale_record_category_phase7`まで存在し、在庫・出品・購入判断・販売実績・通知・アラートのモデルも存在する。各DBへの適用状態は別途確認が必要。PostgreSQLを標準、SQLiteを明示的な互換環境としDjango migrationを使用する。下記の古いbaseline表や将来案は実装済み一覧とは区別する。

## 2. Current Schema Baseline

以下の表は`0009_search_ownership`時点を中心とする歴史的baseline。現在のSearchRunにはcriteria_snapshot/result_snapshot/trigger/duration_ms/failure_codeが追加済みであり、表の不足項目を現在も未実装と解釈しない。ソース上のheadは0022、実DB適用は本改訂で未検証。

A0保存境界は実装済み。新Core物理モデルは未実装: [越境ロードマップ](../plans/cross-border-research-roadmap.md)にCore/Commerce/CrossBorderと既存モデルの対応、原子保存、追加→backfill→検算→読取切替の契約を定義する。Mainのapp label/既存PK・FK・JPY列は維持し、scrapingの即時改名/削除は行わない。Product未照合、SearchDayの時刻不明、ownerless行を推測で補完しない。新物理スキーマはA0のADRとX1で確定し、既存PurchaseDecisionのversion=1を新algorithm_versionと同一視しない。rollbackは読取窓口の切戻しを基本とし、新データをDROPしない。

| Model/table | Main fields | Ownership/relations | Current issue |
|---|---|---|---|
| `SearchRun` | keyword, search_type, item_count, succeeded, created_at | userまたはsession_key、items | 条件、trigger、所要時間、失敗分類がない |
| `scraping` | SearchWord, SearchDay, Bidding, EndPrice, StartPrice, Name, URL | nullable SearchRun FK | legacy命名、日時/入札がtext、状態・商品キーがない |
| `searchwordlog` | word, searched_at | userまたはsession_key | SearchRunと役割が重複 |
| `WatchItem` | URL、追加/現在価格、入札、状態、相場、買い時判定、メモ、優先度、カテゴリ、ライフサイクル | userまたはsession_key、価格履歴 | タグは未実装 |
| `ErrorLog` | code, message, timestamp, file, line | なし | 生messageへ個人情報が混ざる可能性 |
| Django User/Session | 認証・セッション | Django標準 | 維持する |

### Current ownership invariant

- 認証済みデータ: `user_id IS NOT NULL`かつ`session_key = ''`
- 匿名データ: `user_id IS NULL`かつ`session_key != ''`
- ownerless legacy rowsが存在するため、現時点でDB CHECK制約にはできない。
- 通常参照は`owner_query()`で必ず絞り、ログイン時に匿名データをclaimする。

## 3. Design Principles

A0.5/6の新領域契約は[ADR 0003](../decisions/0003-market-identity-and-observation-contract.md)と
[ADR 0004](../decisions/0004-money-fx-and-evaluation-contract.md)を正とする。
以下の円整数原則は既存Commerce/JPY列へ適用し、新しい元通貨額へ流用しない。
新MoneyはDecimalとcurrency、観測は所有者・価格種別・時刻・保持条件を持つ。
具体的な追加テーブル名、FK、一意制約、インデックスはX1で確定し、本改訂でmigrationは追加しない。

移行は旧PKとの対応を保存して再実行可能にし、件数・金額・所有者・価格種別を検算してから
読取を切り替える。SearchDayの不明時刻、ownerless行、未照合Productは推測で補完しない。
戻す際は経路を切り戻し、新データをDROPしない。根拠の削除期限は評価snapshotにも適用する。

- 既存データを破壊的に置換せず、nullable追加→backfill→読取切替→制約強化の順で移行する。
- 金額は円単位`PositiveBigIntegerField`。率は`DecimalField`を使いfloatを保存しない。
- 時刻は`DateTimeField`と`USE_TZ=True`。表示時だけAsia/Tokyoへ変換する。
- 計算可能な見込み利益は原則serviceで算出し、履歴として必要な時点値だけsnapshotへ保存する。
- 新しい永続ユーザー機能はlogin必須とし、`user` FKをnullableにしない。
- 検索・ウォッチの既存匿名利用は互換性のため維持する。
- 外部URLは正規化し、可能な場合は`external_listing_id`を抽出して一意性に使う。
- JSONは条件スナップショットや可変メタデータに限定し、検索・集計対象の主要値は列にする。
- raw HTML、Yahoo認証情報、Cookie、アクセストークンは保存しない。

## 4. Relationship Overview

```text
User
 ├─ SavedSearch ──< SearchRun ──< scraping
 ├─ WatchItem ──< WatchPriceSnapshot
 │    └─ M:N WatchTag
 │    └─ optional conversion ──> InventoryItem
 ├─ InventoryItem ──< SellerListing ──< SellerListingSnapshot
 │                         └─ 0..1 SaleRecord
 ├─ AlertRule ──> SavedSearch | WatchItem | SellerListing
 ├─ Notification
 └─ OperationalEvent (actor optional, privacy-limited)
```

## 5. Existing Table Extensions

### 5.1 SearchRun

Add:

| Field | Type | Rule |
|---|---|---|
| saved_search | nullable FK SavedSearch, SET_NULL | 削除後も履歴維持 |
| criteria_snapshot | JSONField default=dict | 正規化済み条件 |
| result_snapshot | JSONField default=dict | ターゲット分析で実際に表示した商品・中央値・判定 |
| trigger | CharField(20), indexed | manual/saved/alert/scheduled/system |
| duration_ms | PositiveInteger nullable | 外部取得を含む所要時間 |
| failure_code | CharField(40), blank, indexed | raw exceptionを入れない |
| completed_at | DateTime nullable | 成功/失敗確定時刻 |

Indexes:

- `(user, -created_at)`
- `(session_key, -created_at)`
- `(user, search_type, -created_at)`
- `(succeeded, failure_code, -created_at)`
- `(saved_search, -created_at)`

`keyword`は既存UI互換で維持する。保存期間削除はFK cascadeに任せず、比較・通知参照を考慮した明示的retention serviceで行う。

### 5.2 scraping compatibility extension

既存テーブルをリリース前に全面置換しない。以下の正規化列をnullableで追加し、新規保存から埋める。

| Field | Type | Purpose |
|---|---|---|
| listing_key | CharField(255), blank, indexed | URLから抽出した商品識別子 |
| observed_at | DateTime nullable, indexed | `SearchDay`の正規化先 |
| bidding_count | PositiveInteger nullable | `Bidding`の正規化先 |
| condition | CharField(20), blank, indexed | new/used/junk/unknown |
| remaining_seconds | PositiveInteger nullable | 現在出品の残時間 |
| is_active | Boolean nullable | current listing状態 |

旧列はlegacy API移行完了まで維持する。backfill不能値はNULLのままとし、推測で補完しない。将来のモデル名・列名整理は別migrationで`db_table`互換を維持して行う。

### 5.3 WatchItem

Implemented by `0015_watchlist_phase2` except tags, which remain a login-only follow-up.

Add:

- note: TextField blank
- priority: SmallInteger choices 0..3, indexed
- category: CharField(100), blank, indexed
- lifecycle_status: active/purchased/skipped/ended/archived, indexed
- ended_at、archived_at: nullable DateTime
- last_price_change_at: nullable DateTime

観測更新ではこれらユーザー管理列を変更しない。

## 6. New Search and Watch Models

### 6.1 SavedSearch

| Field | Type/constraint |
|---|---|
| id | BigAutoField PK |
| user | FK User CASCADE, required |
| name | CharField(100) |
| keyword | CharField(255), indexed |
| condition | CharField(20), blank |
| minimum_price | PositiveBigInteger default=0 |
| maximum_price | PositiveBigInteger nullable |
| excluded_keywords | JSONField default=list |
| ending_within_minutes | PositiveInteger nullable |
| sort_order | CharField(30) |
| is_active | Boolean default=True, indexed |
| last_run_at | DateTime nullable |
| created_at/updated_at | DateTime |

Constraints:

- unique `(user, name)`
- check `maximum_price IS NULL OR minimum_price <= maximum_price`
- 保存条件は常にターゲット分析として実行し、終了時間条件は現在出品側だけに適用

### 6.2 WatchTag

- user FK required、name CharField(50)、color CharField(7)
- unique `(user, name)`
- WatchItemとの中間テーブルにもwatch/tag unique constraint

### 6.3 WatchPriceSnapshot

Implemented by `0015_watchlist_phase2`. Analysis is derived in `Main/services/watchlist_analysis.py`; calculated summaries are not duplicated in the database.

- watch_item FK CASCADE
- price PositiveBigInteger
- bidding PositiveInteger default=0
- remaining_seconds PositiveInteger nullable
- condition CharField(20)
- observed_at DateTime indexed

Index `(watch_item, -observed_at)`。登録時、価格変化時、または設定した最小観測間隔経過時だけ作成する。

## 7. Seller and Inventory Models

### 7.1 InventoryItem

Implemented by `0016_inventory_phase3a`. `source_watch_item` is a nullable one-to-one relation so retrying a conversion cannot create duplicate inventory.

| Field | Type/constraint |
|---|---|
| user | FK User CASCADE, required |
| source_watch_item | nullable FK WatchItem SET_NULL |
| name | TextField |
| condition | CharField(20), indexed |
| category | CharField(100), blank, indexed |
| acquisition_cost | PositiveBigInteger default=0 |
| acquired_at | DateTime nullable |
| status | planned/acquired/preparing/listed/sold/disposed, indexed |
| note | TextField blank |
| created_at/updated_at | DateTime |

WatchItemから変換するときはtransaction内でInventoryItemを作り、WatchItemを`purchased`にする。再試行で重複作成しない一意参照またはidempotencyを持たせる。

### 7.2 SellerListing

Implemented in Phase 3B migration `0017_seller_listing_phase3b` (additive tables; no existing-row backfill).

| Field | Type/constraint |
|---|---|
| user | FK User CASCADE, required |
| inventory_item | nullable FK InventoryItem SET_NULL |
| external_listing_id | CharField(255), blank, indexed |
| url | CharField(1000) |
| name | TextField |
| condition | CharField(20), indexed |
| status | draft/active/ended/sold/cancelled/relist, indexed |
| observed_status | unknown/active/ended; independent of manual outcome |
| start_price/current_price/buyout_price | PositiveBigInteger; buyout nullable |
| bidding | PositiveInteger default=0 |
| starts_at/ends_at | nullable DateTime |
| market_median | PositiveBigInteger default=0 |
| predicted_sale_price | nullable PositiveBigInteger; null selects latest current price or manual median |
| acquisition_cost | PositiveBigInteger default=0 |
| shipping_cost_estimate | PositiveBigInteger default=0 |
| packaging_cost_estimate | PositiveBigInteger default=0 |
| other_cost_estimate | PositiveBigInteger default=0 |
| fee_rate | Decimal(6,5), default configured rate |
| target_profit | PositiveBigInteger default=0 |
| note | TextField blank |
| last_checked_at | nullable DateTime |
| created_at/updated_at | DateTime |

Constraints and indexes:

- unique `(user, external_listing_id)` and `(user, url)`; Phase 3B requires a valid external ID on every registration, so blank-ID fallback is unnecessary
- checks: `0 <= fee_rate <= 1`、全金額非負
- indexes: `(user, status, -updated_at)`、`(user, ends_at)`

`acquisition_cost`等は出品時のスナップショットとして保持する。InventoryItemの値を後で変更しても当時の利益計算を変えない。

### 7.3 SellerListingSnapshot

- seller_listing FK CASCADE
- current_price、bidding、remaining_seconds、market_median
- predicted_sale_price、estimated_fee、estimated_profit
- calculation_inputs JSON: acquisition/shipping/packaging/other cost, fee rate as decimal string, sale price, price source, target profit
- observed_status: active/ended
- sell_through_risk is deferred to Phase 7 (not persisted yet)
- observed_at DateTime indexed
- unique `(seller_listing, observed_at)`; one row per accepted manual refresh, including unchanged values. Refresh rejects a stale updated_at under a row lock before writing.

Index `(seller_listing, -observed_at)`。推奨根拠を再現するため、計算に使った時点値を保存する。

Both models are added without changing existing tables or ownership. Inventory deletion uses SET_NULL; listing deletion cascades snapshots. Reversing `0017` drops these two new tables and loses their data: export/backup before any real rollback. SQLite local tests do not prove PostgreSQL row-lock behavior under production concurrency.

### 7.4 SaleRecord

| Field | Type/constraint |
|---|---|
| seller_listing | OneToOne FK CASCADE |
| sale_price | PositiveBigInteger |
| actual_fee | PositiveBigInteger default=0 |
| actual_shipping_cost | PositiveBigInteger default=0 |
| actual_packaging_cost | PositiveBigInteger default=0 |
| actual_other_cost | PositiveBigInteger default=0 |
| sold_at | DateTime |
| confirmed_profit | BigInteger | 負利益を許可 |
| category | CharField(100), blank, indexed | 販売確定時の在庫カテゴリ |
| created_at/updated_at | DateTime |

`confirmed_profit`は確定時の監査用スナップショット。serviceで再計算した値だけ保存し、入力された計算結果は採用しない。
`category`も同時に固定し、在庫の編集・削除によって過去の集計を変えない。空値は集計画面で未分類として扱う。

## 8. Alerts and Notifications

### 8.1 AlertRule

- user FK required
- nullable FK: saved_search、watch_item、seller_listing
- rule_type CharField(40), indexed
- threshold_value Decimal(18,4)
- is_enabled Boolean indexed
- cooldown_minutes PositiveInteger
- last_triggered_at nullable DateTime
- created_at/updated_at

Buyer rule types are `price_below`, `median_discount`, `ending_soon`, `low_bids`, `buy_score`, `new_listing`, and `within_budget`. Seller rule types are `bid_stalled`, `ending_without_bids`, `loss_risk`, `target_profit`, and `market_decline`.

DB CHECKで対象FKがちょうど1つだけ非NULLになるようにする。対象リソースのuserとrule.user一致はserviceとテストで保証する。

### 8.2 Notification

- user FK required
- event_type CharField(40), indexed
- title CharField(200)、message TextField、target_url CharField(1000, blank)
- source_type CharField(40)、source_id BigInteger nullable
- dedupe_key CharField(255)
- payload JSONField default=dict（機密情報禁止）
- created_at indexed、read_at nullable indexed

Unique `(user, dedupe_key)`。同じ条件が再通知可能な場合、dedupe keyへ評価期間bucketを含める。

メール追加時はNotificationへ送信状態を混ぜず、`NotificationDelivery`またはoutboxを追加する。

## 9. Operational Monitoring

### OperationalEvent

Future design, deferred from Phase 8: the accepted monitoring scope aggregates
existing `SearchRun` and `ErrorLog` rows. No OperationalEvent table or migration is
introduced. See `docs/features/admin-monitoring.md` for retained-record limits and
the safe dashboard severity mapping. `SearchRun.failure_code` additionally accepts
`html_parse_error`; existing values and column definitions remain unchanged.

- event_type、severity、failure_code、duration_ms、status_code
- actor_type: user/anonymous/system（user FKは必要時のみnullable）
- request_id、occurred_at
- metadata JSON（allowlistした数値・分類値のみ）

検索語、メール、セッションキー、Cookie、stack trace全文をmetadataへ入れない。詳細例外はアクセス制御されたログへ短期保持し、DB集計は分類値を使う。

`ErrorLog`は既存互換で維持し、新規処理はOperationalEvent中心へ移す。移行後にretentionと廃止可否を判断する。

## 10. Profit Calculation Rules

見込み値:

```text
estimated_fee = round(sale_price * fee_rate)
estimated_profit = sale_price
  - estimated_fee
  - acquisition_cost
  - shipping_cost_estimate
  - packaging_cost_estimate
  - other_cost_estimate
profit_margin = estimated_profit / sale_price * 100  (sale_price > 0)
```

損益分岐価格は手数料を含むため、`ceil(fixed_cost / (1 - fee_rate))`。`fee_rate >= 1`は禁止する。

確定利益はSaleRecordのactual値で再計算する。丸め規則はdomain serviceに一元化し、API・画面・jobで同じ関数を使う。

## 11. Retention and Deletion

- SearchRun/scraping: 比較に必要な期間を設定化し、現行の一律50件削除を置換する。
- Snapshot: 日次集約後の詳細保持期間を設定可能にする。削除前に集約値が必要か確認する。
- Notification: 既読を一定期間後に削除可能。未読は自動削除しない。
- Seller/Sale: ユーザーが明示削除するまで保持。ただし退会時の方針を利用規約と整合させる。
- OperationalEvent/log: 最短限の保持期間とローテーションを設定する。
- Django User削除はuser-owned modelsをCASCADEする。販売実績の法的保持要件が発生する場合は実装前に方針を再決定する。

## 12. Migration Plan

実際のmigration名は生成時に確認する。現在の`0009`から概ね以下の単位で分割する。

1. SearchRun metadataとscraping正規化nullable列
2. SavedSearchとSearchRun FK
3. WatchItem拡張、WatchTag、WatchPriceSnapshot
4. InventoryItem、SellerListing、SellerListingSnapshot、SaleRecord
5. Notification
6. AlertRule
7. OperationalEventと監視index
8. backfill完了後の制約・不要index整理

各migrationで実施すること:

- SQLiteとPostgreSQLの両方で`makemigrations --check`とmigration rehearsal
- schema migrationと重いdata migrationを分ける
- batch処理し、全テーブルロック時間を抑える
- reverse可能性を確認し、不可逆ならバックアップ・復元手順を先に用意する
- legacy ownerless rowsを新機能へ自動帰属させない

## 13. Required Database Tests

- user/session所有者のunique constraintとclaim処理
- 他ユーザーFKをAlertRule等へ設定できないservice validation
- minimum/maximum、fee rate、非負金額の制約
- WatchItem→InventoryItem変換のtransactionと再試行
- SellerListing refresh時にユーザー入力費用が上書きされない
- SaleRecordの利益再計算と負利益
- Notification dedupeの同時作成
- SQLite→PostgreSQL移行対象件数と除外件数
- cascade/SET_NULL動作と退会時削除範囲

## Phase 3C storage and migration

`0018_purchase_budget_phase3c` adds `CostSettings` (unique user and JSON nullable defaults), append-only `PurchaseDecision` (watch FK, snapshot JSON version 1, creation time), and immutable `purchase_decision` JSON copies on InventoryItem and SellerListing. Watch ownership is the access boundary; inventory/listing copies remain owner-scoped after source deletion. Defaults are not joined when rendering old decisions.

SellerListing adds separate `purchase_shipping_cost` and `missing_cost_fields`. Legacy rows receive 0 acquisition shipping and empty decision/missing metadata, preserving existing behavior. New decision-derived rows keep unknown costs in metadata, rather than treating legacy zero defaults as known. SellerListingSnapshot fee/profit become nullable to represent unknown costs without inventing zero profit. No existing amount is converted or backfilled from guesses.

Forward migration adds tables/columns and relaxes two null constraints. Verification uses isolated SQLite; production migration and PostgreSQL locking must be rehearsed separately. Back up before application. A reverse migration drops new decision data and cannot restore NOT NULL if unknown-cost observations exist: roll back using a pre-migration backup, not by replacing unknowns with zero. Never reverse against user data without a data-preserving plan and explicit authorization.
