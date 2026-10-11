# ADR 0005: 国内複数市場対応とMoney/FX非適用

## Status

Proposed — 設計のみ。実装・移行は未着手。**対象marketplaceはD0調査により`mercari_jp`から`paypay_frima`（候補、技術検証待ち）へ変更**。楽天ラクマは対象外と判定済み。

## Context

越境ECリサーチロードマップ（`docs/plans/cross-border-research-roadmap.md`）の検討の結果、2025年以降の輸入関税制度の変化（米国de minimis撤廃等）とeBay等の越境プラットフォーム手数料により、海外販売を前提とした価格差モデルの採算性が悪化していることを確認した。一方、ADR 0003で定義したCore契約（Marketplace / Product / MarketListing / PriceObservation）は特定市場・特定通貨に依存しない設計であり、国内の複数市場に対しても同じ契約で拡張できる。

当面は海外展開ではなく、国内で完結する価格差検出を優先する。

当初の候補はメルカリだったが、[D0調査](../plans/d0-mercari-research.md)（2026-09-14）で規約上の明示的禁止（非公式インターフェイスアクセス・BOT・リバースエンジニアリング禁止）と技術構造（検索結果がJavaScriptレンダリングのSPAで静的HTML取得が不可）の両面から自動取得不可と判定された。代替候補調査（[D0b](../plans/d0-second-market-candidates.md)）の結果、楽天ラクマも同水準の規約禁止で対象外、PayPayフリマは既存Yahooオークション実装と同一のLINEヤフー共通規約に拘束されるため規約面での新規リスクが生じないと判定された。ただしPayPayフリマの技術構造（静的HTML取得の可否）は未確認であり、これがD1着手の条件になる。

## Decision

- ADR 0003のCore契約に、`paypay_frima`を2つ目のMarketplace識別子として追加する（候補。技術検証で静的HTML取得不可と判明した場合はこのADRの対象marketplaceを再度見直す）。
- ADR 0004（Money/FX）は適用しない。国内複数市場は既存どおりJPY整数のみで扱い、為替・関税ロジックは導入しない。
- 越境（CrossBorder, X系）ロードマップの着手は、本ADRおよび`docs/plans/domestic-expansion-roadmap.md`（D系）より優先度を下げる。A0で作成したCore契約・Provider抽象化はX系ではなくD系で先に活用する。
- 新規実装は`Main/infrastructure/marketplaces/paypay_frima.py`（Yahoo adapterと同一interface）と、市場横断の価格比較を担う`Main/services/cross_market_search.py`（仮称）に閉じる。既存`Main` app label、既存テーブル・API契約は変更しない。
- PayPayフリマへの新規HTTP許可ホストは、既存のYahoo専用allowlistとは別に明示追加する。
- メルカリ・楽天ラクマは対象外とする。将来これらが公式APIや提携経路を提供した場合は再調査する。

## Consequences

- 越境で必要だった外貨Money型・FX・関税対応の実装コストを当面回避できる。
- PayPayフリマの技術構造（静的HTML取得の可否）が未確認のまま本ADRを採用しており、D1着手前に確認が必須。確認できなければ国内複数市場対応そのものを一時保留する。
- 越境ロードマップ（X系）はA0-Required完了まで凍結ではなく「D系より低優先」として扱う。X0（調査）は独立して継続してよい。
- 自動入札・自動出品は本ADRの範囲外であり、意図的に実装しない。取得は分析・意思決定支援の範囲に留める。

## Related Files

- `docs/decisions/0003-market-identity-and-observation-contract.md`
- `docs/decisions/0004-money-fx-and-evaluation-contract.md`
- `docs/plans/domestic-expansion-roadmap.md`
- `docs/plans/d0-mercari-research.md`
- `docs/plans/d0-second-market-candidates.md`
- `docs/plans/cross-border-research-roadmap.md`
