# Listing Images (商品画像の取得・表示)

## Status

Phase A 一部実装済み（2026-10-11）。ヤフオク検索結果からの画像URL抽出（HTMLカードと`__NEXT_DATA__`、
`https`の`*.yimg.jp`だけを許可）、現在出品と`recommend_items`への`imageUrl`追加、トップページの
おすすめカードでの表示とフォールバックを実装した（`docs/features/recommendations.md`）。
2026-10-12に、ターゲット分析の検索結果とウォッチリストを画像付きカードにした。
あわせて`WatchItem.primary_image_url`（`0023`）を追加した。値は登録時と検索の再取得時に保存し、
画像のない値では上書きしない。APIでは`imageUrl`として返す。
残るDBカラム（`scraping`、`InventoryItem`、`SellerListing`）、`seller_listing.py`、
他画面のサムネイル表示は未実装。

## Purpose

現状、検索結果・ウォッチリスト・在庫・出品管理はテキストと数値のみで構成されており、商品状態を目視で確認できない。画像を取得・表示し、利用者がより速く正確に状態判断できるようにする。

## Behavior (proposed)

### Phase A: 画像URLの保存と表示（推奨する最初の一歩）

- ヤフオクの検索結果・商品詳細ページの`__NEXT_DATA__`には元々画像URLが含まれる。既存パーサー（`Main/scraping/yahoo.py`、`Main/infrastructure/marketplaces/yahoo.py`、seller-management向けの`Main/scraping/seller_listing.py`）に画像URL抽出を追加する。新しい取得経路は不要。
- 取得した画像URLはそのまま保存し、表示時はヤフオクのCDNへ直接リンクする（ホットリンク）。画像ファイル自体はダウンロード・保存しない。
- 対象: 相場検索・現在価格検索の結果一覧、ターゲット分析の比較カード、`WatchItem`、`InventoryItem`、`SellerListing`、通知一覧。

### Phase B: 長期追跡向けの画像キャッシュ（必要になった場合のみ着手）

- ヤフオクの画像URLはオークション終了後に失効することがある。`WatchItem`や`InventoryItem`など長期間参照する対象で「画像が表示できない」問題が実際に発生した場合に限り、画像ファイルのダウンロード・キャッシュを追加する。
- Phase Aの運用実績を見てから着手を判断する。最初から作り込まない。

## Data Model (sketch, additive only)

既存の「nullable追加 → 段階移行」方針（`docs/design/database.md`）に従う。

| Table | Field | Type |
|---|---|---|
| `scraping` | `image_url` | CharField, blank, null許容 |
| `WatchItem` | `primary_image_url` | CharField, blank |
| `InventoryItem` | `primary_image_url` | CharField, blank |
| `SellerListing` | `primary_image_url` | CharField, blank |

複数画像が必要になった場合は`image_urls`（JSONField, default=list）を別途追加する。Phase Aでは主要1枚のみで十分と考える。

## API

既存レスポンスへ`imageUrl`（camelCase、既存契約に合わせる）を追加フィールドとして加える。既存フィールドの型・意味は変更しない（既存API契約の「一括変更しない」方針に従う）。

## UI (proposed)

- `Main/static/JS/MarketSearch.js`、`MarketComparison.js`、`InventoryManagement.js`、`SellerListings.js`、`Notifications.js`の各結果描画部分にサムネイル`<img>`を追加する。
- `loading="lazy"`を指定し、画像URL失効時のフォールバック（プレースホルダー画像 + 代替テキスト）を用意する。
- カード形式のレイアウトへの寄せは`docs/ui-design.md`の既存パターン（白カード・角丸）を踏襲する。

## Non-Goals

- 画像に基づく自動状態判定（AI画像分析）は対象外。目視確認の補助に留める。
- Phase Aでは画像ファイルの自社保存・再配布は行わない。

## Related Files (to be created/extended)

- `Main/scraping/yahoo.py`, `Main/infrastructure/marketplaces/yahoo.py`, `Main/scraping/seller_listing.py`
- `Main/static/JS/MarketSearch.js`, `MarketComparison.js`, `InventoryManagement.js`, `SellerListings.js`, `Notifications.js`
- 新規migration（`scraping`, `WatchItem`, `InventoryItem`, `SellerListing`への`image_url`系カラム追加）
- `tests/fixtures/yahoo/`（画像あり/なし/複数枚のfixtureケース追加）

## Verification (proposed)

- パーサーが画像なし商品でも失敗しないことを確認する（missing-image fixtureケース）。
- 画像URL失効時にUIが崩れずプレースホルダーを表示することを確認する（既存の390pxモバイルE2E方針に合わせる）。
- 既存APIレスポンスへのフィールド追加が既存クライアント（テンプレート）を壊さないことを回帰確認する。
