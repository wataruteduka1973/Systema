# D0b: セカンドマーケット代替候補調査（楽天ラクマ・PayPayフリマ）

[国内拡張ロードマップ（D系）](domestic-expansion-roadmap.md) D0の追加調査。メルカリが[D0調査記録](d0-mercari-research.md)で「限定可（自動取得は不可）」と判定されたため、代替候補として楽天ラクマとPayPayフリマを同じ形式で調査した。

調査日: 2026-09-14。調査方法: 公開されている利用規約・ガイド・robots.txtの内容確認。検証環境から対象ドメインへの直接HTTPアクセスが制限されていたため、本調査ではWebFetch経由の確認を行ったが、既知のメルカリ検索ページ（静的HTMLには商品データを含まないことがD0で確認済み）に対しても商品データありと応答したことから、WebFetch自体がJavaScriptレンダリングを行っており、静的HTML取得との区別に使えないことが判明した。**したがって本調査の「技術構造」欄は規約確認ほど確度が高くない推測であり、実際の生HTTPレスポンスでの検証は別途必要。**

## 楽天ラクマ（fril.jp）

| 記録項目 | 内容 |
|---|---|
| 規約 | 利用規約（fril.jp/info/policy 第19条、2025-12-01改定、確認日2026-09-14）が禁止事項を「ラクマのルール」に委任。同ルールの「その他」条項（[faq.fril.jp/hc/ja/articles/39849670060941](https://faq.fril.jp/hc/ja/articles/39849670060941)）に「当社が提供するインターフェイスとは別の手法、または当社が許可していないBOTやツールなどの手段を用いて本サービスにアクセスすること」「リバースエンジニアリング・逆アセンブル」「転用・転売・複写・複製等の二次利用」を明記。メルカリとほぼ同水準の明示的禁止。 |
| robots.txt | `/search/`はクエリ文字列付き（sort/min/max/category_id等）を軒並みDisallow、素の`/search/$`のみ許可。 |
| 技術構造 | 未確認（上記の理由により本調査では確定できず）。URL形式がクエリ文字列型（`/s?query=`）でハッシュルーティングでない点はサーバーサイドレンダリングの傍証だが、推測の域を出ない。 |
| 公開API | 検索・閲覧用の公開APIなし。出品者向けの受注連携APIのみ。 |
| 結論 | **メルカリと同水準の明示的禁止。技術確認以前に規約面で見送り対象。** |

## PayPayフリマ（paypayfleamarket.yahoo.co.jp）

| 記録項目 | 内容 |
|---|---|
| 規約 | 独自の禁止事項条項を持たず、ガイド（[paypayfleamarket.yahoo.co.jp/guide/guideline/](https://paypayfleamarket.yahoo.co.jp/guide/guideline/)）がLINEヤフー共通利用規約（[terms.line.me/line_terms?lang=ja](https://terms.line.me/line_terms?lang=ja)）を準用する。**Yahoo!オークションのガイドライン（[auctions.yahoo.co.jp/special/html/guidelines.html](https://auctions.yahoo.co.jp/special/html/guidelines.html)）も同一のLINEヤフー共通規約を参照しており、両サービスは同一の規約文書に拘束される。** 該当条項（第15条5号BOT・改変ツール禁止、6号リバースエンジニアリング禁止、10〜11号非公式手段での商用利用・対価取得禁止）は、既存Yahooオークション実装が既に受け入れている規約リスクと同一である。 |
| robots.txt | `/item/*/edit`、`/negotiate`、`/question`、`/my/`、`/search/`と`/product/`のクエリパラメータ付きURLをDisallowするが、`/search/`の素のパス自体は明示的にDisallowされていない（Yahooオークションと同様の姿勢）。 |
| 技術構造 | 未確認（同上の理由）。Yahoo/LY Corporationと技術基盤を共有している可能性が高く、既存Yahooオークション実装と同様に取得可能である可能性はメルカリ・ラクマより高いと推測するが、実際の生HTTPレスポンスでの確認はできていない。 |
| 公開API | 検索用の公開APIなし。PayPay Developers APIは決済・ミニアプリ向けで対象外。 |
| 結論 | **規約面では既存Yahooオークション実装と同一の規約文書・同一条項に拘束されるため、新たな規約リスクは発生しない（既存で受け入れ済みのリスクの範囲内）。ただし技術構造（静的HTML取得の可否）は未確認であり、これが次の検証項目。** |

## 総合判断

- ラクマはメルカリと同水準の明示的禁止があり、これ以上の技術検証をする前に対象外と判断する。
- PayPayフリマは規約面で新規リスクを生まない（既存Yahooオークション実装と同一のLINEヤフー共通規約）ため、[国内拡張ロードマップ](domestic-expansion-roadmap.md)の「既存のYahoo取得と同水準のリスクを超えない」という制約を満たす有力候補である。
- 未確認の技術構造（検索結果ページが静的HTMLでデータを返すか、JSレンダリングに依存するか）が唯一の残課題。これは実環境からの一度きりのHTTP GET確認で判定できる、低コストな検証である。

## 次の作業

D1着手可否の判断材料として、`https://paypayfleamarket.yahoo.co.jp/search?keyword=...`への単発HTTP GETで実データがHTML内に含まれるかを確認する。含まれていればD1（PayPayフリマをMarketplaceとして追加）へ進める。JSレンダリング依存であれば、ラクマ・メルカリと同様に見送る。

## 関連資料

- [D0: メルカリ取得可能性・用途調査](d0-mercari-research.md)
- [国内拡張ロードマップ（D系）](domestic-expansion-roadmap.md)
- [ADR 0005](../decisions/0005-domestic-second-marketplace.md)
