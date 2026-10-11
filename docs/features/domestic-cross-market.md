# Domestic Cross-Market Price Gap Detection (PayPayフリマ連携候補)

## Status

Proposed — 設計のみ、未実装。**対象市場はD0調査によりメルカリからPayPayフリマ（候補、技術検証待ち）へ変更。詳細は[ADR 0005](../decisions/0005-domestic-second-marketplace.md)、[D0](../plans/d0-mercari-research.md)、[D0b](../plans/d0-second-market-candidates.md)を参照。**

## Purpose

同一商品についてヤフオクと第2の国内市場（PayPayフリマ、技術検証待ち）の価格差を検出し、購入判断を速く正確にする。対象はADR 0005で決定した国内複数市場対応であり、越境（海外販売）は対象外。

## Behavior (proposed)

- 既存の`MarketplaceProvider`インターフェース（`Main/infrastructure/marketplaces/yahoo.py`で確立済み）と同じ契約に従う`paypay_frima.py`アダプタを追加する。着手前に、検索結果ページが静的HTMLでデータを返すことを技術検証で確認する（D0bで未実施）。
- ターゲット分析のキーワード検索で、ヤフオク（closed/current）に加えてPayPayフリマの出品中データを取得し、`PriceObservation`（ADR 0003）として正規化する。
- 商品の同一性は自動照合せず、`unmatched` / `needs_review` / `confirmed`の状態を持たせる（ADR 0003のProduct照合方針を踏襲）。型番・状態が完全一致しない限り`confirmed`にしない。
- 価格差が閾値（設定可能、既定は相場中央値の20%以上を仮定）を超える組み合わせを候補として提示する。表示は「ヤフオク相場中央値」「PayPayフリマ相場中央値」「差額」「差の根拠件数」。
- 既存の買い時判定（`Main/domain/buying_opportunity.py`）とは独立した新しい判定ロジックとし、既存の表示ラベルの意味を変えない。

## Data Model (sketch)

既存`docs/design/database.md`のCore契約拡張として、新規テーブルは最小限にする。具体的なフィールド・制約・インデックスはX1/D1相当の設計確定作業として本ドキュメントでは未確定とする。

| 概念 | 主な項目 |
|---|---|
| `MarketListing` | marketplace（`yahoo_auctions_jp` / `paypay_frima`）, external_id, url, product参照（nullable） |
| `PriceObservation` | listing参照, price_kind（`asking` / `current_bid`等）, amount（JPY整数, 既存契約を維持）, quantity, condition, observed_at, owner |

## API (sketch)

- 既存`/taskle/`エンドポイントは変更しない。
- 新規: `GET /taskle/api/v1/cross-market-comparisons?keyword=` — 本人が指定したキーワードについて、両市場の中央値・差額・根拠件数を返す。既存v1共通envelope（`docs/design/api.md`）に従う。

## Non-Goals

- 自動購入・自動出品・自動入札は行わない（技術的にも意図的にも対象外）。
- 海外市場（eBay等）は対象外。ADR 0004（Money/FX）は適用しない。
- 全商品の自動照合は対象外。未照合のまま候補として提示することを許容する。

## Related Files (to be created)

- `Main/infrastructure/marketplaces/paypay_frima.py`
- `Main/services/cross_market_search.py`
- `Main/domain/market_listing.py`（既存ファイルの拡張）
- `tests/fixtures/paypay_frima/`
- `tests/unit/test_paypay_frima_marketplace.py`
- `tests/integration/test_cross_market_search.py`

## Verification (proposed)

- fixtureベースのPayPayフリマパーサーテスト（ADR 0001の方針を踏襲、実サイトへのライブスクレイピングはテストで行わない）。
- 価格差検出ロジックの単体テスト（閾値境界、根拠件数不足時の`insufficient`扱い）。
- 所有者スコープ・CSRF・他ユーザーの候補へのアクセス不可を既存パターンで検証。

## Product Decision

国内複数市場対応の採否は[ADR 0005](../decisions/0005-domestic-second-marketplace.md)を正とする。
