# Release Feature Roadmap

Related designs: `docs/design/api.md` and `docs/design/database.md`.

## Goal

リリースに向け、保存検索、ウォッチリスト、履歴比較、通知、価格アラート、出品・利益管理、管理監視を、既存の所有者分離と検索フローを壊さず段階的に追加する。購入判断から仕入れ、出品、販売結果、利益検証までを一つの循環として扱う。

## Current Baseline

- `SearchRun`は所有者、キーワード、検索種別、件数、成功可否、実行日時を保持する。
- `scraping`は`SearchRun`単位の商品スナップショットを保持する。
- `WatchItem`は追加時・現在価格、状態、相場中央値、買い時判定を保持し、検索時に更新される。
- ユーザーページとAPIには所有者分離テストがある。
- 管理者画面には基本件数、直近エラー、ログ末尾表示がある。
- 本番用Secret、DEBUG禁止、Hosts、HTTPS、Secure Cookie、CSRF、外部検索レート制限は設定済み。
- 在庫、出品、費用、出品観測履歴はPhase 3A/3Bで実装済み。Phase 7Aは確定販売実績の集計、Phase 7Bは十分な実績が得られた後の推薦を扱う。本番適用の検証状況は各PhaseのStatusを参照する。

## Conflicts and Decisions

1. **保存検索と検索履歴を分離する。** `SearchRun`は実行記録、`SavedSearch`は再利用可能な条件とする。`SearchRun`へ`criteria_snapshot`と任意の`saved_search`参照を追加し、条件変更後も過去実行を再現できるようにする。
2. **UIの「保存済みデータ」と名称を分ける。** 現在の保存済みデータは結果スナップショットなので、「検索履歴データ」と「保存した検索条件」に分ける。
3. **検索条件をサーバーでも適用する。** 現在、価格・状態・並び順は主にブラウザー内処理である。保存検索、アラート、自動実行で同じ結果にするため、共通`SearchCriteria`とフィルターサービスを作る。
4. **ウォッチ価格を上書きだけにしない。** `WatchItem.current_price`は維持し、`WatchPriceSnapshot`へ価格、入札、残り時間、状態、観測日時を追記する。
5. **通知とアラートを分離する。** `AlertRule`は判定条件、`Notification`は発生イベントとし、重複通知防止キーと既読日時を持たせる。
6. **定期実行はデプロイ工程まで開始しない。** ローカルでは検索・ウォッチ更新時の同期判定と手動管理コマンドまで実装し、サーバー選定後にスケジューラーを接続する。
7. **履歴比較は本人所有・成功済み・同一検索種別を原則とする。** 初期版は落札検索を対象とし、現在出品比較は終了判定の精度確認後に拡張する。
8. **購入候補と自分の出品を分離する。** `WatchItem`は購入候補、`SellerListing`はユーザー自身の出品とし、一覧・状態・通知を混在させない。
9. **出品連携はURL手動登録から始める。** Yahooアカウントの認証情報やCookieは保存しない。自動取込は公式かつ安全な連携方式を確認できた場合だけ別工程で検討する。
10. **利益は入力値と計算結果を分ける。** 仕入、送料、梱包、手数料率、その他費用を保存し、見込み利益はサービスで計算する。販売完了時の実績は`SaleRecord`へ固定する。
11. **仕入れ時の予測と販売結果を接続する。** 購入候補を`InventoryItem`へ変換できるようにし、想定販売価格・想定利益と確定利益の差を将来バックテストできる構造にする。

## Proposed Models

### SavedSearch

- user（ログイン必須）、name、keyword
- condition、minimum_price、maximum_price
- excluded_keywords（JSON list）、ending_within_minutes、sort_order
- is_active、created_at、updated_at、last_run_at

### SearchRun additions

- saved_search（nullable FK、削除時SET_NULL）
- criteria_snapshot（JSON）
- trigger（manual / saved / alert / scheduled）
- duration_ms、failure_code（監視用、個人情報を含めない）

### Watchlist additions

- `WatchItem`: note、priority、category、lifecycle_status、ended_at、archived_at
- `WatchTag`: ユーザー所有タグ。`WatchItem`と多対多
- `WatchPriceSnapshot`: watch_item、price、bidding、remaining_seconds、condition、observed_at

### Alerts and notifications

- `AlertRule`: user、saved_search/watch_item、rule_type、threshold、is_enabled、cooldown、last_triggered_at
- `Notification`: user、event_type、title、message、target_url、source、dedupe_key、created_at、read_at

### Seller and inventory

- `InventoryItem`: user、source_watch_item、name、condition、acquisition_cost、acquired_at、status
- `SellerListing`: user、inventory_item、URL、商品識別子、状態、開始・現在・即決価格、終了日時、相場中央値、費用入力
- `SellerListingSnapshot`: listing、価格、入札数、残り時間、相場、予測価格、見込み利益、観測日時
- `SaleRecord`: listing、販売価格、実手数料、実送料、その他費用、販売日時、確定利益

## Implementation Phases

### Phase 0: Release foundation and contracts

Phase 0は後続機能の依存関係に沿って分割し、検索契約を先に安定させる。

#### Phase 0A: Search contract

- 共通`SearchCriteria`の検証・正規化・適用サービスを作る。
- `SearchRun`へ条件スナップショットとtriggerを追加する。
- 現行検索画面からも正規化対象の条件をサーバーへ送り、画面内処理と結果を一致させる。
- 保存検索と将来自動実行は同じサービスを使用し、独自の条件解釈を持たせない。

#### Phase 0B: Minimum observability

- `SearchRun`へ`duration_ms`と個人情報を含まない`failure_code`を追加する。
- failure codeは`external_service_unavailable`、`unexpected_error`、`no_data`、`insufficient_data`に限定し、例外詳細を保存しない。
- 詳細な監視画面や運用イベントはPhase 8で完成させる。

#### Later release prerequisites

- 現行のキーワード・種別ごと50実行保持は直ちに変更せず、Phase 4着手前に比較対象期間を決めて整合させる。
- 本番時の`admin_setup` 404、ログイン試行制限、ログの個人情報マスキングは初回本番公開前のrelease security gateとする。

**Done:** 手動・保存・将来自動実行で同じ条件解釈になり、所有者分離と本番セキュリティがテストされる。

### Phase 1: Saved searches

**Status:** Completed on 2026-08-25. Saved searches are limited to the profile and target-analysis pages. Target analysis uses one integrated search/criteria form, uses the keyword as its name, and saves and executes it in one action without same-keyword duplication. Profile creation also executes immediately and refreshes the persisted result. Saved searches always run target analysis; market search is not involved.

- `SavedSearch`と所有者限定CRUDを追加する。
- 市場検索画面には「条件を保存」「保存条件を適用」を追加しない。頻出ワードの追加操作と役割が近く、検索画面を複雑にするため廃止する。
- ユーザーページに新規作成、一覧、編集、削除、ワンクリック再実行を追加する。
- ターゲット分析画面から現在の全条件を保存できるようにする。
- 保存条件は検索種別を持たず、常にターゲット分析として実行する。
- ユーザーページで保存条件の最新結果を永続表示し、手動の最近の検索履歴と分離する。
- 実行時に`SearchRun.saved_search`と条件スナップショットを記録する。

`SavedSearch`は検索画面の入力補助ではなく、本人だけが管理できる名前付きの検索条件と、Phase 5以降の自動実行・通知が参照する永続データとして扱う。頻出ワードは検索履歴から得た単語を現在のキーワードへ追加するだけで、保存条件のCRUDや自動実行の識別子にはしない。

### Phase 1.5: Authentication security

**Status:** Completed on 2026-08-25.

- Add database-backed throttling for failed logins using hashed IP and account identities.
- Rate limit signup and development-only initial administrator setup.
- Disable the web initial-administrator endpoint in production; use `createsuperuser` instead.
- Shorten authentication sessions, expire them when the browser closes, and explicitly secure cookie behavior.
- Enforce a Django 6.x Content Security Policy compatible with the current application assets.
- Upgrade Requests to a version containing the CVE-2024-47081 fix.
- Cover throttling, production setup closure, security headers, CSRF, and ownership with focused tests.

### Phase 2: Watchlist enhancement and price history

**Status:** Core completed locally on 2026-09-02. Watch decisions, lifecycle filtering, price snapshots, owner-scoped update/history APIs, and snapshot-derived analysis are implemented and covered by the `target-analysis` verification suite. The user confirmed the feature behavior on 2026-09-02. Tag management remains deferred as a separate follow-up because tags require a login-only ownership contract while legacy watch items still support anonymous sessions.

- メモ、優先度、カテゴリ、タグ、購入済み／見送り／終了を追加する。
- 更新APIと状態・優先度・商品状態フィルターを追加する。
- 登録時と更新時に価格履歴を保存し、登録後の変化を表示する。
- 観測回数、価格変化率、最安・最高価格、入札増加、相場差、値上がり／値下がり傾向を履歴から算出し、材料不足を明示する。
- 終了商品を通常一覧とアーカイブに分離する。
- 検索更新でメモ等のユーザー入力を上書きしない。

### Phase 3: Seller listing and profitability foundation

**Status:** Phase 3A implemented and locally feature-verified on 2026-09-02. Phase 3B implemented on 2026-09-03: owner-scoped seller CRUD, explicit public-page refresh, cost-preserving snapshots, lifecycle UI, and paginated history deltas. The user confirmed the added workflow on 2026-09-03. Repository-wide Black, mypy, Ruff, the 231-test full regression suite, Django/migration checks, documentation build, JavaScript syntax check, diff check, and isolated SQLite browser workflow passed locally; one live public page was parsed successfully. Production DB migration, PostgreSQL concurrency and GitHub CI remain NOT VERIFIED. No real user DB migration was applied by this implementation.

- 購入候補から在庫へ移す操作と、在庫の手動登録を追加する。
- 自分の出品URLを手動登録し、現在価格、入札、残り時間、状態を取得する。
- 仕入、送料、梱包、手数料率、その他費用、目標利益を入力できるようにする。
- 相場中央値、想定販売価格、損益分岐価格、見込み利益・利益率を表示する。
- 出品スナップショットを保存し、価格・入札・見込み利益の推移を表示する。
- 出品終了、落札、見送り、再出品待ちを区別する。

**初期範囲:** Yahoo認証情報は扱わず、URL手動登録とユーザー入力を正とする。

### Phase 4: Seller workflow support

**Status:** 出品・在庫管理画面に集約する。Phase 4Aの状態判定、4Bの優先順位・絞り込み、4Cの操作導線、4Dの対応状況集計、4Eの販売結果・確定利益入力を実装済み。2026-09-09に `verify --feature seller-outcomes`、`verify --feature purchase-budget`、JavaScript構文確認、差分確認、検証用SQLiteでの操作確認を通過し、ユーザーによる主要10項目の画面確認も完了。2026-09-09に開発用PostgreSQLで全マイグレーション適用、販売結果テスト3件、`verify --feature seller-outcomes`も通過。本番DB・PostgreSQL・GitHub CIは **NOT VERIFIED**。

- 出品一覧で、公開情報・出品状態・次の作業を一画面で確認できるようにする。
- 価格・入札・残り時間・見込み利益の変化から、更新が必要な出品を識別する。
- 赤字見込み、目標利益未達、終了間近、入札停滞、費用不足を明示する。
- 出品ごとに「費用を補完」「公開情報を更新」「状態を確認」「販売結果を入力」などの次の作業を表示する。
- 出品時点の想定値と販売結果の確定値を同じ出品から確認できるようにする。
- Yahooの自動出品・自動編集・認証情報保存は対象外とする。

#### Deferred: Search run comparison

保存済み検索履歴の比較は、ユーザーページへの機能集中を避けるため保留する。比較API、IQR、新規・継続・消失分類、除外再集計は、出品支援の利用状況を確認した後に再評価する。

### Phase 5: Notification center

**Status:** Implemented and locally verified on 2026-09-09. The development application database was confirmed as PostgreSQL 18.6, all migrations through `0020_notification_phase5` were applied, and `verify --feature notifications` passed, including PostgreSQL concurrent notification dedupe. GitHub CI for the pushed revision was confirmed successful by the user on 2026-09-09, covering documentation, lint/type checks, tests, and documentation build/deploy. Browser confirmation and production migration remain **NOT VERIFIED** and are intentionally deferred to the Phase 9 release gate after the remaining feature implementation is complete.

- 所有者限定の通知一覧、既読、一括既読APIを追加する。
- ユーザーページには未読件数と専用通知画面への導線を追加し、通知一覧は`/taskle/notifications`へ分離する。
- ウォッチ値下げ、終了間近、保存検索更新完了、検索失敗を接続する。
- `dedupe_key`で同一事象の連続通知を防ぐ。

### Phase 6: Alert rules

- 価格、中央値差、終了時間、入札数、買い時点数の条件CRUDと評価サービスを追加する。
- 検索結果・ウォッチ更新時に同期評価し、通知を作成する。
- 保存検索更新とアラート評価を手動実行できる管理コマンドを作る。
- デプロイ先決定後、管理コマンドをスケジューラーへ接続する。
- メール通知はin-app通知安定後にoutbox方式で追加する。
- 出品向けに、入札停滞、終了間近で入札ゼロ、赤字見込み、目標利益到達、相場下落を追加する。
- 新着候補と購入上限内の候補を通知対象に加える。相場根拠、費用前提、更新日時を通知先で確認でき、ウォッチへ登録できること。
- 通知頻度、停止、重複抑制を用意する。初回検索結果を全件新着扱いせず、取得失敗を商品消失や値下げと判定しない。

**Status:** Implemented and locally verified on 2026-09-10: owner-scoped rule CRUD/UI, watch and saved-search buyer evaluation, new and within-budget candidate evidence with watch registration, five seller evaluations, cooldown/dedupe, and the `run_alerts` management command. `verify --feature alerts`, targeted mypy, Sphinx, JavaScript syntax checks, 291 non-E2E regression tests (one skipped), and 9 SQLite Playwright E2E tests passed. Scheduler connection and email outbox remain intentionally deferred until deployment and in-app stability. Production migration, PostgreSQL behavior, production browser behavior, scheduler, email, and GitHub CI remain **NOT VERIFIED**.

### Phase 7: Seller intelligence and outcome learning

- 開始価格・即決価格・送料条件を変える利益シミュレーターを追加する。
- 早期売却、標準、利益重視の推奨価格を提示する。
- 相場差、入札推移、類似出品数から売れ残りリスクと改善理由を表示する。
- 類似落札タイトルから重要語、状態、型番、付属品を抽出し、タイトル改善候補を提示する。
- 曜日・時間帯別実績が十分な場合だけ終了日時候補を提示する。
- 販売完了時の確定費用・利益の保存と、在庫/出品の次の作業表示はPhase 4で提供する。Phase 7Aでは想定値との差、販売日数、カテゴリ別利益の集計へ拡張する。
- 高度な推奨や学習をPhase 7Bとする。7Bは販売実績の蓄積後に着手する。
- 仕入れ時の買い時スコア・予測利益と販売実績をバックテストする。

### Phase 8: Administrator monitoring

**Status:** Completed and locally verified on 2026-09-11. The staff-only monitoring dashboard now provides bounded search success/duration, safe failure, actor/trigger, daily error, retained DB volume, unowned-data and search-concentration aggregates. Yahoo fetch and HTML parsing failures are separated internally while the public 503 contract remains compatible. `verify --feature admin-monitoring`, the full verification suite, mypy, migration drift check, Sphinx build, and desktop/mobile SQLite Playwright E2E passed. Production PostgreSQL behavior, production browser behavior, deployment settings and GitHub CI remain **NOT VERIFIED** and belong to Phase 9.

- 既存管理画面に検索成功率、失敗分類、実行時間、主体別件数、日次エラー、DB量、所有者なしデータ、過剰検索を追加する。
- Yahoo取得失敗とHTML解析失敗を`failure_code`で分離する。
- DB上の構造化情報を優先し、安全な期間・レベル・種別フィルターを付ける。
- メール、セッションキー、Cookie、完全な検索語をログ・画面へ表示しない。

### Phase 9: Deployment release gate

- `manage.py check --deploy`、環境変数、HTTPS/proxy、静的ファイル、DBバックアップ・復元を確認する。
- ログイン・検索レート制限を実環境で検証する。
- 全新規モデル・APIのユーザー間分離を確認する。
- 定期ジョブの多重実行防止、タイムアウト、再試行、通知重複防止を検証する。
- E2Eで保存検索→再実行→ウォッチ→価格更新→通知→履歴比較を確認する。
- E2Eで購入候補→在庫→出品→価格更新→販売結果→確定利益を確認する。

## Test Strategy

- Unit: 条件正規化、比較統計、商品キー、価格履歴、利益計算、損益分岐、アラート判定、通知重複防止
- Integration: CRUD認証、CSRF、所有者分離、SearchRunスナップショット、管理者権限
- Regression: 市場検索、ターゲット分析、ウォッチ登録、プロフィール、匿名データ引継ぎ
- UI/E2E: 空・エラー状態、モバイル、キーボード操作、二重送信、未読更新
- Operations: migration rehearsal、PostgreSQL、バックアップ復元、定期ジョブ再実行

## Recommended Order

2026-09-12追加: 国内仕入れ→海外販売は[越境ECリサーチロードマップ](cross-border-research-roadmap.md)で管理する。Systema内の独立領域として、P0のベースライン確認→A0 Core StabilizationのRequired項目→X1契約設計→X2手入力MVP→X3取得接続/X4在庫連携→X5自動更新と進め、X6利用検証を小さな提供単位で行う。X0取得調査はP0/A0と並行し、A0のRecommended/Cleanup完了や本番公開先決定をX1の必須条件にしない。外部取得未確定でも既存版公開を止めず、M2/M3を越境リサーチの必須前提にしない。現在は計画のみで、各機能・本番利用は未検証。

完了済みのPhase 3A/3B以降は、`Phase 3C → Phase 4（出品支援） → Phase 5 → Phase 6 → Phase 7A → Phase 8 → Phase 9`を基本とする。検索履歴比較は保留し、Phase 7Bは十分な販売実績蓄積後に着手する。CSVは対象データが完成した単位で追加する。外部市場の調査M0はこの順序と独立して進められるが、取得経路が未確定でもYahoo単独版の改善・公開を止めない。

通知センターは価格アラートより先、ウォッチ価格履歴は値下げ通知より先に実装する。出品者向け高度分析は販売実績が蓄積してから実装する。監視用メタデータはPhase 0で記録を開始し、管理画面はPhase 8で完成させる。

## Usability and monetization expansion (2026-09-03)

**Status: 計画へ採用、未実装。** オークファンの検索アラート、期間比較、利益計算、出品モニター、売上集計、CSVを参考に、既存フローをつなぐ。料金は未決定で、有料提供開始を意味しない。複数市場の詳細は[Multi-market sourcing](../features/multi-market-sourcing.md)を参照する。

### Phase 3C: Buying budget and reusable cost assumptions

**Status:** Implemented in the working tree on 2026-09-06. Local feature verification previously passed before the final evidence and unknown-cost propagation refinements; the final rerun is **NOT VERIFIED** because the approved test runtime reached its usage limit. Production database migration, PostgreSQL behavior, browser workflow, CSV output, and live deployment remain **NOT VERIFIED**.

- **目的:** 購入候補画面で費用を含む見込み利益と購入上限額を確認し、候補→在庫→出品へ入力を引き継ぐ。
- **着手条件:** Phase 3A/3Bの利益計算・所有者境界を再確認する。想定売価の根拠、仕入送料と販売送料の区別、丸め、未知の費用の扱いをAPI/DB設計へ記録してから実装する。
- **範囲:** 想定売価、販売手数料、仕入送料、発送送料、梱包・その他費用、目標利益。費用設定はログインユーザーごとに保存し、商品単位の上書きを許す。
- **計算:** 購入上限 = 想定売価 − 販売手数料 − 仕入/販売の付随費用 − 目標利益。端数と手数料計算は既存domain規則に合わせ、0未満なら条件を満たす購入額なしとする。現在入札価格を最終取得価格と断定しない。
- **互換:** 既存の買い時ラベルは価格比較として維持し、利益判定とは区別する。費用不明時は判定材料不足とし、既存ゼロ既定値から新機能の費用が既知とは推測しない。
- **完了条件:** 根拠件数・対象期間・参照商品と費用前提を確認可能。赤字、費用不明、上限境界、丸め、他人の設定参照、二重変換を検証し、設定変更で過去の購入判断・出品履歴が書き換わらない。

### CSV and outcome workflow

- 候補/在庫のCSVはPhase 3C後、販売実績/確定費用のCSVはPhase 7A後に追加する。列名、通貨、観測日時、見込み/確定の区別を明示する。
- 着手前に出力範囲・件数上限・個人情報・外部データの再配布条件を確定する。出力は本人所有のみ、数式注入対策を実施し、日本語・改行・引用符を含む表計算取込を検証する。
- Phase 7Aは販売額・実費の追加入力だけで結果を確定できること。公開ページの終了を売却完了と扱わず、費用や想定値の引継ぎにより再入力を減らす。

### Multi-market delivery track

| Unit | Scope | Start condition | Done condition |
|---|---|---|---|
| M0 | メルカリと海外ECの取得可能性調査 | 公式資料から開始可能 | 市場ごとに検索/販売済み/履歴保持/分析/商用表示/CSV/通知の可否、利用料、上限、接続条件を記録し、採否と理由を決める |
| M1 | 市場識別・金額・観測情報の追加設計 | 最初の取得元でM0通過 | Yahoo互換、所有者、通貨精度、移行/戻し方、取得失敗の契約をAPI/DB設計へ反映し、fixture検証 |
| M2 | メルカリを検索・比較・ウォッチ・在庫へ接続 | メルカリのM0とM1通過 | 市場別相場、根拠表示、候補→在庫、失敗時の既存結果保持を検証。販売済みデータが使えなければ出品中比較のみと明示 |
| M3 | 海外仕入れ候補と国内売価の比較 | 海外取得元のM0、M1、Phase 3C通過 | まず1市場・限定カテゴリで取得、総仕入原価、配送可否、不明費用、為替の前提を確認できる |
| M4 | 複数市場の保存条件・通知・販売実績接続 | 対象connectorとPhase 6/7Aの該当部分完成 | 市場横断の重複抑制、根拠の引継ぎ、確定利益、取得元停止時の縮退を検証 |

M2とM3は相互に待たず、取得条件を満たした市場から提供する。各connectorの本番提供にはPhase 9相当の運用確認を行う。公開前に少人数で候補判断時間、再入力回数、誤通知、翌週の継続利用、支払い意思を測り、検索・通知の原価と合わせて課金範囲を決める。
