# Release Feature Roadmap

## Goal

リリースに向け、保存検索、ウォッチリスト、履歴比較、通知、価格アラート、管理監視を、既存の所有者分離と検索フローを壊さず段階的に追加する。

## Current Baseline

- `SearchRun`は所有者、キーワード、検索種別、件数、成功可否、実行日時を保持する。
- `scraping`は`SearchRun`単位の商品スナップショットを保持する。
- `WatchItem`は追加時・現在価格、状態、相場中央値、買い時判定を保持し、検索時に更新される。
- ユーザーページとAPIには所有者分離テストがある。
- 管理者画面には基本件数、直近エラー、ログ末尾表示がある。
- 本番用Secret、DEBUG禁止、Hosts、HTTPS、Secure Cookie、CSRF、外部検索レート制限は設定済み。

## Conflicts and Decisions

1. **保存検索と検索履歴を分離する。** `SearchRun`は実行記録、`SavedSearch`は再利用可能な条件とする。`SearchRun`へ`criteria_snapshot`と任意の`saved_search`参照を追加し、条件変更後も過去実行を再現できるようにする。
2. **UIの「保存済みデータ」と名称を分ける。** 現在の保存済みデータは結果スナップショットなので、「検索履歴データ」と「保存した検索条件」に分ける。
3. **検索条件をサーバーでも適用する。** 現在、価格・状態・並び順は主にブラウザー内処理である。保存検索、アラート、自動実行で同じ結果にするため、共通`SearchCriteria`とフィルターサービスを作る。
4. **ウォッチ価格を上書きだけにしない。** `WatchItem.current_price`は維持し、`WatchPriceSnapshot`へ価格、入札、残り時間、状態、観測日時を追記する。
5. **通知とアラートを分離する。** `AlertRule`は判定条件、`Notification`は発生イベントとし、重複通知防止キーと既読日時を持たせる。
6. **定期実行はデプロイ工程まで開始しない。** ローカルでは検索・ウォッチ更新時の同期判定と手動管理コマンドまで実装し、サーバー選定後にスケジューラーを接続する。
7. **履歴比較は本人所有・成功済み・同一検索種別を原則とする。** 初期版は落札検索を対象とし、現在出品比較は終了判定の精度確認後に拡張する。

## Proposed Models

### SavedSearch

- user（ログイン必須）、name、keyword、search_type
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

## Implementation Phases

### Phase 0: Release foundation and contracts

- 共通`SearchCriteria`の検証・正規化・適用サービスを作る。
- `SearchRun`へ条件スナップショット、trigger、duration、failure codeを追加する。
- 現行のキーワード・種別ごと50実行保持を、比較機能の保存期間と整合させる。
- 本番時に`admin_setup`を404にする。
- ログイン試行制限とログの個人情報マスキングを追加する。

**Done:** 手動・保存・将来自動実行で同じ条件解釈になり、所有者分離と本番セキュリティがテストされる。

### Phase 1: Saved searches

- `SavedSearch`と所有者限定CRUDを追加する。
- 市場検索画面に「条件を保存」「保存条件を適用」を追加する。
- ユーザーページに一覧、編集、削除、ワンクリック再実行を追加する。
- 実行時に`SearchRun.saved_search`と条件スナップショットを記録する。

### Phase 2: Watchlist enhancement and price history

- メモ、優先度、カテゴリ、タグ、購入済み／見送り／終了を追加する。
- 更新APIと状態・優先度・商品状態フィルターを追加する。
- 登録時と更新時に価格履歴を保存し、登録後の変化を表示する。
- 終了商品を通常一覧とアーカイブに分離する。
- 検索更新でメモ等のユーザー入力を上書きしない。

### Phase 3: Search run comparison

- 本人所有・成功済み・同一種別の2実行を選択するAPIを追加する。
- 中央値、IQR、件数、状態構成、価格変化率を共通統計サービスで算出する。
- URLから商品キーを正規化し、新規・消失・継続商品を分類する。
- ユーザーページに比較選択と日次／週次変化を表示する。
- 初期範囲は落札検索のみとし、算出不能な指標を明示する。

### Phase 4: Notification center

- 所有者限定の通知一覧、既読、一括既読APIを追加する。
- ユーザーページに未読件数と通知欄を追加する。
- ウォッチ値下げ、終了間近、保存検索更新完了、検索失敗を接続する。
- `dedupe_key`で同一事象の連続通知を防ぐ。

### Phase 5: Alert rules

- 価格、中央値差、終了時間、入札数、買い時点数の条件CRUDと評価サービスを追加する。
- 検索結果・ウォッチ更新時に同期評価し、通知を作成する。
- 保存検索更新とアラート評価を手動実行できる管理コマンドを作る。
- デプロイ先決定後、管理コマンドをスケジューラーへ接続する。
- メール通知はin-app通知安定後にoutbox方式で追加する。

### Phase 6: Administrator monitoring

- 既存管理画面に検索成功率、失敗分類、実行時間、主体別件数、日次エラー、DB量、所有者なしデータ、過剰検索を追加する。
- Yahoo取得失敗とHTML解析失敗を`failure_code`で分離する。
- DB上の構造化情報を優先し、安全な期間・レベル・種別フィルターを付ける。
- メール、セッションキー、Cookie、完全な検索語をログ・画面へ表示しない。

### Phase 7: Deployment release gate

- `manage.py check --deploy`、環境変数、HTTPS/proxy、静的ファイル、DBバックアップ・復元を確認する。
- ログイン・検索レート制限を実環境で検証する。
- 全新規モデル・APIのユーザー間分離を確認する。
- 定期ジョブの多重実行防止、タイムアウト、再試行、通知重複防止を検証する。
- E2Eで保存検索→再実行→ウォッチ→価格更新→通知→履歴比較を確認する。

## Test Strategy

- Unit: 条件正規化、比較統計、商品キー、価格履歴、アラート判定、通知重複防止
- Integration: CRUD認証、CSRF、所有者分離、SearchRunスナップショット、管理者権限
- Regression: 市場検索、ターゲット分析、ウォッチ登録、プロフィール、匿名データ引継ぎ
- UI/E2E: 空・エラー状態、モバイル、キーボード操作、二重送信、未読更新
- Operations: migration rehearsal、PostgreSQL、バックアップ復元、定期ジョブ再実行

## Recommended Order

`Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6 → Phase 7`

通知センターは価格アラートより先、ウォッチ価格履歴は値下げ通知より先に実装する。監視用メタデータはPhase 0で記録を開始し、管理画面はPhase 6で完成させる。
