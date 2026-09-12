# ADR 0003: 市場・商品・出品・価格観測の契約

## Status

Accepted — A0.5の設計契約。既存実装の基準は`07d5e65`。
新モデル、外部市場接続、移行処理は未実装。市場別の利用許諾はX0で確認する。

## Context and scope

Yahoo取得と検索保存を再利用しても、商品同定、出品ID、価格の意味まで同一にはならない。
本ADRはX1の設計入力を固定する。既存Mainのapp label、PK/FK、API、匿名検索を維持する。
全面backfill、自動商品照合、共有カタログ、新規認証方式は含めない。

## Decision

| 概念 | 最低契約 | 責務 |
|---|---|---|
| Marketplace | 安定した市場コード。現在は`yahoo_auctions_jp` | Core。取得能力と利用条件は市場別adapter/configで確認 |
| Product | 内部ID、型番、版、地域仕様。同定根拠と未確認項目 | Coreの同定対象。照合判断はCrossBorder |
| MarketListing | `(marketplace, external_id)`、公開出典URL、任意Product参照 | Coreの出品識別。URLやタイトルだけで同一商品へ統合しない |
| PriceObservation | 出品参照、価格種別、Money、数量、状態、観測時刻、出典、所有者、保持条件 | Coreの時点値。取得実行と売買イベントを分ける |
| OpportunityEvaluation | 比較根拠、照合判断、費用・FX・結果の時点値 | CrossBorder。ADR 0004の評価契約を使う |
| WatchItem / InventoryItem / SellerListing / SaleRecord | 利用者の追跡意図、在庫、販売業務、確定実績 | Commerce。市場の出品情報と置換しない |

### 識別と未照合

- 外部IDはadapterが仕様に従い正規化する文字列。市場間で同じIDがあっても別出品。
- 市場がIDを再利用する場合は、その市場の識別契約をX0/X1で拡張するまで接続を保留する。
- ID不明の手入力候補は所有者内の内部IDで保存し、架空の外部IDを生成しない。
- Product参照は任意。`unmatched`、`needs_review`、`confirmed`と根拠を照合側で扱う。
  タイトル一致だけで`confirmed`にしない。同型番でも地域仕様・版・数量・付属品・状態を比較する。
- 照合修正は後続評価へ反映する。過去の評価が参照した組合せは自動更新しない。

### 価格と時刻

価格種別は少なくとも`asking`（提示価格）、`current_bid`（現在入札価格）、
`ended_listing`（終了商品表示）、`sold_reported`（取得元の販売済み表示）、
`confirmed_sale`（本人の確定売価）、`unknown`を区別する。
種別はadapterの根拠で決める。終了検索という経路だけで確定成約としない。
本人確定売価はCommerce所有データであり、共有市場価格へ自動転用しない。

- `observed_at`は観測時刻、`occurred_at`は根拠がある場合だけ記録する売買等の発生時刻。
  新規時刻はタイムゾーン付きで保存しUTCへ正規化する。不明な発生時刻はnull。
- 数量不明はnull。1点価格・セット総額・送料含有・税含有を別属性として記録する。
  不明なセット数から単価を作らない。
- provenanceは取得経路（手入力/API等）、出典参照、取得時刻、adapter版、価格種別の根拠を持つ。
  raw HTML、Cookie、認証情報を保存しない。

### 所有者・保持・再送

- 新しい越境候補、観測、評価はログイン所有者に限定する。Coreという区分は公開共有を意味しない。
  すべての読取・書込・関連付け・在庫移管で所有者を検査する。
- 同一の外部出品を別ユーザーが登録しても私有の観測・費用は混ざらない。
  識別の自然キーとDBの所有者付き一意制約は区別し、具体DDLはX1で確定する。
- 同じ取得実行の再送は`owner + acquisition_id + listing_ref + price_kind + source_event_key`
  を基準に一意化する。イベントキーがない場合の安定したページ内キーはadapterが定義する。
  同じキーで内容が違う再送は競合とし上書きしない。新規観測は新しい実行IDを使う。
  この契約のDB実装と同時実行試験は後続。既存SearchRunに再送防止が実装済みとはしない。
- 保持は`retention_policy_ref`と期限・用途に従う。未確認の外部データ保持を許可済み扱いしない。
  元根拠と派生値それぞれの保持可否をX0で記録する。
- 削除・期限切れでは禁止される根拠や派生値を除去する。許される最小メタデータだけで
  `evidence_unavailable`を表現し、再計算不可とする。監査目的の永久コピーは作らない。
- 空の成功、取得失敗、部分失敗、未対応、期限切れは別状態。取得失敗を売切れや消失としない。

## Legacy mapping and migration

| 現在 | 新契約への対応と制限 |
|---|---|
| `MarketListingObservation` | Yahoo互換の整数JPY DTO。timeは文字列、通貨・所有者・価格種別・保持情報がないためPriceObservation完成形ではない |
| `SearchRun` | 取得/分析実行。created_atは成約時刻ではない。閉札/現在の成功・失敗は別run |
| `scraping.EndPrice` | closedでは終了表示価格、currentでは現在価格。列名だけで確定売価にしない |
| `scraping.SearchDay` | 保存時のnaive文字列。元値を残し、元タイムゾーンを立証できる行だけ変換 |
| `scraping.Bidding` | 検証して整数化。不明・不正を0へ補完しない |
| nullable `scraping.search_run` | owner不明行は通常表示や別所有者への移管対象にしない |
| `WatchItem` / `SellerListing` | 追跡と本人販売として維持。MarketListingへの強制置換なし |

移行は追加テーブル/nullable参照、再実行可能な分割backfill、件数・金額・所有者の検算、
限定読取切替の順。元のPKを移行対応キーに含めて二重移行を防ぐ。dual-writeが必要なら
同一DB transaction内で行い、外部I/Oをtransactionに含めない。
戻す場合は読取/書込経路を切り戻し、新規データを保全する。DROPや旧API削除は行わない。

## Acceptance examples and follow-up

1. 同じ外部IDのYahoo出品と別市場出品は衝突しない。
2. 同型番・異なる地域版は未照合/要確認のまま保持できる。
3. ended listingとaskingを、確定成約価格の統計へ混ぜない。
4. 他人の観測IDでは閲覧・更新・評価・在庫移管できない。
5. 同実行の再送は増殖せず、新しい時点の観測は保存できる。
6. 不明時刻・数量・所有者を推測で埋めない。期限切れ根拠を利用可能と表示しない。

X0は市場別能力と保持条件、X1はDDL/API・一意性・削除処理を確定する。
A0.7では既存検索互換を検証する。上記新モデルの実行試験はX2/X3で実装とともに追加する。
