# ADR 0004: Money・為替・評価履歴の契約

## Status

Accepted — A0.6の設計契約。ソース基準`07d5e65`。
Money/FX値オブジェクト・新API・新テーブルは未実装。値オブジェクトはX2開始前までに実装する。
以下の数値例は検証用の仮定であり、現在相場・実際の手数料ではない。

## Context and decision

Coreは金額・為替の値契約を持ち、CrossBorderが取得、費用、配送、利益試算を組み合わせる。
純粋計算はDB/HTTPへ依存しない。既存JPY APIと保存列は維持し、新しい外貨経路だけに適用する。

### Money

- `amount`は有限Decimal、`currency`は対応通貨コード。JSONではamountを10進文字列とする。
  binary float、bool、NaN、Infinityを受け付けない。nullは不明、`"0"`は明示的なゼロ。
- 新契約の最小対応はJPY（小数0桁）とUSD（小数2桁）。市場・配送先の採用とは別であり、
  対応外通貨はunsupported。対応通貨追加時は小数桁を明示する。
- 元入力は最大整数18桁、小数は通貨の桁数以内。桁超過を黙って丸めず入力エラーにする。
  指数表記はAPI入力で禁止。DB候補はDecimal(20,2)と通貨別検証、DDLはX1で確定。
- 観測売価・費用は非負。利益・差額は符号付き。同じMoney型でも用途別に符号を検証する。
- 通貨が違う加減算は明示的な換算がなければ不可。元Moneyと換算Moneyを別に保存する。

### ExchangeRate

最低項目は`base_currency`、`quote_currency`、正の有限`rate`、`observed_at`、
`source`、`source_kind`（manual/provider）、`rate_id`。rateは最大整数12桁・小数18桁。
計算はlocal Decimal contextのprecision=50を使用する。桁超過はエラーとし暗黙切捨てしない。

方向は **1 base = rate quote**。USD/JPYのrate=150ならUSD 100はJPY 15000。
逆方向は1/rateで計算し、元rateと逆変換であることを履歴に残す。逆数を先に丸めない。
同一通貨は換算不要。異通貨でrate不明・0・負値なら判定不可。
レートの許容経過時間はCrossBorderの評価ポリシーと入力snapshotに記録する。
期間未設定や時刻不明のレートは新しい確定的な判定に使用しない。過去評価表示はそのまま可能。

### 丸めと計算順序

- 元金額の精度は保持する。換算計算は高精度で行い、表示Moneyを作る時だけquote通貨桁へ
  `ROUND_HALF_UP`で丸める。逆換算から元値を復元して上書きしない。
- 一つの利益試算では全項目を同じ評価通貨へ換算し、丸め前の値で合計する。
  表示した個別換算額の足し算と最終表示が異なる場合、丸め差を説明できるよう保持する。
- 外部の請求規則で先に丸める費用は、その費用の通貨・計算基礎・丸め規則・丸め済み値を
  snapshotに記録する。未確認の販売手数料規則を一律の事実として設定しない。
- 利益表示はHALF_UP、購入上限は仕入通貨の最小単位へ`ROUND_FLOOR`。
  上限が負の場合は購入不可で、0へ補完しない。上限計算に必要な換算方向も記録する。
- 売価、買い手から受け取る送料、売り手の配送費、手数料基礎、税の負担者を別項目にする。
  費用不明は`insufficient`と不足項目を返す。0の仮定で利益を出さない。

### 既存JPY契約との互換

| 既存ソース | 固定する挙動 |
|---|---|
| `Main/domain/profitability.py` | 円整数、手数料はHALF_UPで円丸め、損益分岐売価はCEILING。利益は負値可 |
| `Main/domain/purchase_budget.py` | 不足値はinsufficient。手数料率は小数5桁以内。負の購入上限はno_budget/null |
| `Main/services/purchase_budget.py` | 根拠中央値はHALF_UPで円整数化。snapshotのversion=1を維持 |
| `Main/services/market_search.py` | medianPriceは既存float応答のまま。新Moneyへ既存JSON型を一括変更しない |
| `InventoryItem` / `SaleRecord` | 円の費用・確定利益として維持。外貨amountをそのままJPY列へ格納しない |

既存margin表示のfloatも変更しない。新外貨計算は既存関数を無条件に通さず、X1で専用経路を設計する。

### 評価版・履歴・再計算

新評価は`schema_version`（保存形式）、`algorithm_version`（計算規則）、`evaluated_at`、
所有者、`input_snapshot`、`result_snapshot`を持つ。inputには元Money、観測参照と利用可能な根拠、
照合状態、FXの方向/ID/時刻/値、費用、丸め規則、目標利益、鮮度ポリシーを含める。
過去評価は不変とし、設定変更・再計算は新評価IDで元評価を参照する。
同じ要求IDの再送は同じ評価を返し、別入力で同じ要求IDは競合とする。物理制約はX1で設計する。

既存`PurchaseDecision.snapshot.version=1`は既存形式の版でありalgorithm_versionではない。
新しい読取adapterが必要なら`legacy`とalgorithm不明を別メタデータで返し、既存JSONを改変しない。
WatchItemの最新scoreも版付きの過去評価とはみなさない。
根拠の期限・削除ではADR 0003が優先し、保持禁止のinputコピーを残さない。
その場合は根拠利用不可・再現不可を明示する。再現性のために保持条件を延長しない。

## Acceptance examples

| 仮定入力 | 期待結果 |
|---|---|
| USD `100.25`、USD/JPY `150` | 丸め前JPY `15037.50`、表示JPY `15038`。元USDは維持 |
| JPY `15038`を同rateで逆換算 | USD表示`100.25`。元JPYも維持し、往復完全一致を保証しない |
| USD送料null / `0.00` | nullは不足、0.00は明示的無料として区別 |
| USD `1.001`、NaN、bool、JPY `1.5` | 入力エラー |
| USD売価100、rate150、費用JPY1200、目標利益JPY2000 | 仕入上限JPY11800。仕入JPY10000なら利益JPY3800（他費用は明示0） |
| 丸め前仕入上限JPY11800.9 | 上限JPY11800。切上げて目標利益を割り込ませない |
| USD/JPY rateがnull、0、負、鮮度ポリシー不明 | 判定不可。利益を0で返さない |
| 元売価1000円、手数料率0.1005 | 既存JPY手数料101円（HALF_UP）。既存互換を維持 |
| FX設定変更後に以前の評価を表示 | 保存時のFXと結果のまま。再計算は別評価 |

X1で手数料・税・送料の具体入力とAPI/DDL、X2前にMoney/FXの単体試験を実装する。
A0.7では既存JPY境界を回帰確認する。本ADRの採用を新Moneyの実装済み証拠にしない。
