# X0 取得・用途台帳（下書き）

確認日: 2026-10-11。状態: **下書き。判断前のレビュー用**。
前提（2026-10-11 ユーザー決定）: 配送先は**米国**。利用形態は**当面は本人の仕入れ判断用、将来は他ユーザーへ提供**。カテゴリは未定（候補比較は下記）。

証拠の区分:
- **公式**: 提供元の公式ページを確認した。
- **公式（検索要約）**: 公式ページを検索結果で確認したが、原文を開けていない。
- **二次情報**: 第三者の記事や計算ツール。判断の根拠にしない。

公式ページの原文（developer.ebay.com、lycorp.co.jp）は、作成環境のネットワーク制限で直接開けなかった。
「要原文確認」の行は、判断前にブラウザで原文を確認する。

## 1. 国内側: Yahoo!オークション

| 記録項目 | 内容 | 証拠 |
|---|---|---|
| 取得経路 | Systemaは現在、公開検索ページを取得して解析している。公式Web API（2006年公開の「Yahoo!オークションWebサービス」）の現状は確認できなかった。終了の告知も、現在の提供ページも見つからなかった | [2006年公開記事](https://internet.watch.impress.co.jp/cda/news/2006/03/30/11455.html)、[2017年仕様変更](https://developer.yahoo.co.jp/changelog/2017-02-16-auction156.html)（公式）。**要原文確認**: Yahoo!デベロッパーネットワークの現行API一覧 |
| 利用規約 | ヤフオク!はLINEヤフー共通利用規約とガイドラインに従う。自動取得・複製・商用再利用の禁止条項の有無は未確認 | [App Store案内](https://apps.apple.com/jp/app/yahoo-%25E3%2582%25AA%25E3%2583%25BC%25E3%2582%25AF%25E3%2582%25B7%25E3%2583%25A7%25E3%2583%25B3/id356968629?uo=4)（二次情報）。**要原文確認**: https://www.lycorp.co.jp/ja/company/terms/ |
| 価格の意味 | 落札検索は終了オークションの落札価格。出品検索は現在価格（入札中）。どちらも成約日時・送料の取得は限定的（実装済みの解析を参照） | 既存実装 `Main/infrastructure/marketplaces/yahoo.py` |
| 用途・保持 | 既存の取得実装は商用用途の許諾の証拠ではない（ロードマップ既定）。本人用の調査で使う場合と、他ユーザーへの提供は分けて判断する | — |
| 結論（暫定） | **本人用: 現行どおり限定可（規約確認待ち）。他ユーザーへの提供: 不明**。提供前に規約原文の確認と、必要なら問い合わせ | — |

## 2. 海外側: eBay（米国）

| 記録項目 | 内容 | 証拠 |
|---|---|---|
| 出品中の検索 | Browse API（`item_summary/search`）。キーワード・GTIN・カテゴリ等で検索でき、1検索あたり最大10,000件。sandboxは誰でも使えるが、production利用には資格要件・承認・契約が必要 | [Browse API overview](https://developer.ebay.com/api-docs/buy/browse/overview.html)（公式（検索要約））。**要原文確認**: [Buy API要件](https://developer.ebay.com/api-docs/buy/static/buy-requirements.html) |
| 販売済み（成約）価格 | Finding APIの`findCompletedItems`は2020-10-15に非推奨となり、2025-02-05にFinding API全体が廃止された。代替のMarketplace Insights APIは限定公開で、事業部門が承認した開発者のみが使える。過去90日の販売履歴。対象カテゴリはパートナーごとに許可制。Browse APIでは販売済み情報は取れない | [findCompletedItems](https://developer.ebay.com/DevZone/finding/CallRef/findCompletedItems.html)、[Marketplace Insights](https://developer.ebay.com/api-docs/buy/marketplace-insights/overview.html)（公式（検索要約））、[開発者フォーラム](https://community.ebay.com/t5/eBay-APIs-Talk-to-your-fellow/Marketplace-Insights-API-access/m-p/34838736)（二次情報） |
| 用途・保持 | API License Agreementでは、eBayコンテンツの中間コピーは許可された目的に必要な範囲に限り、不要になれば削除する。保持時間の具体値は未確認。最近の改定で、Restricted APIとAIコンテンツの制限が追加された | [License](https://developer.ebay.com/products/license)（公式（検索要約））。**要原文確認**: キャッシュ・保存・再表示の条項 |
| 費用（販売手数料） | 米国の最終価値手数料は多くのカテゴリで約13.6%＋1注文$0.30〜0.40。国際手数料（約1.65%）はeBay International Shipping利用時は対象外との記載あり。日本在住セラーの条件は未確認 | [fee guide](https://www.underpriced.app/blog/ebay-fees-complete-guide-2026)、[litcommerce](https://litcommerce.com/ebay-fee-calculator/)（二次情報）。**要原文確認**: eBay公式手数料表（日本セラー） |
| 結論（暫定） | **出品中価格: API承認待ち（それまでは手入力）。販売済み価格: 自動取得は不可に近い（限定公開APIのみ）**。ロードマップ既定どおり、成約根拠がなければ「出品価格比較と仮定の利益試算」に用途を限定する | — |

## 3. 配送・関税（日本 → 米国）

| 項目 | 内容 | 証拠 |
|---|---|---|
| 少額免税の停止 | 2025-08-29から、米国は全ての国からの少額輸入（$800以下）の免税を停止した。郵便物も金額にかかわらず関税の対象 | [Thompson Hine](https://www.thompsonhinesmartrade.com/2025/07/president-suspends-duty-free-de-minimis-imports-for-all-countries-and-imposes-new-tariffs-on-low-value-shipments/)、[CSCB](https://cscb.ca/en/article/us-executive-order-suspending-duty-free-de-minimis-treatment-all-countries)（二次情報） |
| 日本郵便 | 2025-08-27から米国宛て商品の引受を停止し、2026-04-14に再開した。再開後は認定アプリ（Zonos等）での関税前払いが条件。前払い対象の上限は2026-07-24に$800から$2,500へ引き上げ。$100以下の書類・贈答品は免税 | [日本郵便 2026-04-13](https://www.post.japanpost.jp/int/information/2026/0413_01_en.html)、[日本郵便 2026-07-17](https://www.post.japanpost.jp/service/send/oversea/information/2026/0717_01_en.html)（公式（検索要約））、[Zonos](https://zonos.com/japan-post) |
| 国際宅配便 | FedEx・DHL・UPS・ヤマト国際は継続。DDU（関税は受取人払い）とDDP（発送者払い・後日請求）で負担者が変わる | [Ship&co](https://support.shipandco.com/hc/en-us/articles/50069163619225-End-of-U-S-De-Minimis-from-Aug-29-2025-What-Ship-co-Users-Need-to-Know)（二次情報） |
| 利益計算への影響 | 関税・通関手数料・前払いアプリ手数料を、売り手と買い手のどちらが負担するかを入力項目にする。品目ごとの関税率は一律にしない（ロードマップ既定）。不明は0円にしない | — |

## 4. カテゴリ候補の比較（未決定）

| 候補 | 照合しやすさ | 注意点 |
|---|---|---|
| ゲーム機・ソフト | 型番・リージョン（NTSC-J等）・付属品で照合しやすい | 地域仕様の差で米国での需要・動作が変わる。リチウム電池入り本体は配送制限の確認が必要 |
| カメラ・レンズ | 型番で照合しやすく単価が高い | 状態差が大きく、送料・保険・関税額への影響も大きい。$2,500超は郵便の前払い対象外 |
| トレカ・ホビー | 型番・版で照合しやすく軽量 | 真贋と鑑定（PSA等）の扱いが必要。単価の幅が大きい |

## 5. 手入力版の範囲（X1開始条件の案）

自動取得の許諾を待たずにX1を始めるための最小範囲。

- 国内: Yahoo!の検索結果（既存機能）と、ユーザーが手入力した仕入れ価格。
- 海外: eBay米国の比較価格を**ユーザーが手入力**する。価格種別（出品価格・販売済み表示価格・本人の確定売価）、URL、観測日時、状態を一緒に記録する。
- 費用: 国際送料、関税・通関・前払い手数料（負担者を含む）、eBay手数料、為替レート（取得元と時点）を手入力。未入力は「不明」で、0にしない。
- 用途: 本人の仕入れ判断のみ。他ユーザーへの提供は、規約原文の確認後に再判定する。
- 自動取得: 有効にしない（eBay APIの承認、Yahoo規約の確認後に別途判断）。

## 6. 判断が必要なこと

1. この手入力版の範囲（5章）でX1を開始してよいか。
2. 対象カテゴリ（4章）。
3. eBay開発者アカウントとBrowse APIのproduction申請を行うか（対外申請のため、承認が必要）。
4. LINEヤフー規約とeBay License Agreementの原文確認を、誰がどの環境で行うか（作成環境では開けなかった）。
