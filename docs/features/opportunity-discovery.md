# Opportunity Discovery Scan

## Status

Proposed — 設計のみ、未実装。

## Purpose

利用者が事前に指定したキーワード・商品だけでなく、相場から大きく乖離した新着出品に気づけるようにする。既存の`WatchItem`/`AlertRule`は「追跡対象を自分で指定する」設計であり、未知の掘り出し物を発見する機能ではない。本機能はその発見部分を担う。

## Behavior (proposed)

- 利用者は「監視カテゴリ」（複数キーワードの集合、または既存`SavedSearch`の集合）を登録できる。
- 定期的に（`run_alerts`と同じ管理コマンド経由。常駐プロセスは追加しない）各カテゴリ内の新着出品を取得し、既存の`Main/domain/buying_opportunity.py`のロジックで相場中央値との乖離を評価する。
- 乖離が閾値を超えた出品を「発見候補」として一覧化する。既存の`AlertRule`の`new_listing`タイプと役割が近いため、実装は`AlertRule`/`Notification`の仕組みを拡張する形とし、新しい通知経路を別途作らない。
- 発見候補はワンクリックで既存の`WatchItem`へ登録できる（既存の変換動線を再利用する）。
- `docs/features/domestic-cross-market.md`が先行実装されている場合は、ヤフオク・PayPayフリマ両方を対象にできる。未実装でもヤフオク単独で提供できる（依存関係は緩い）。

## Non-Goals

- 全カテゴリ・全キーワードを無制限に監視することはしない。利用者が明示登録したカテゴリのみを対象とする。
- 自動購入・自動入札は行わない。

## Related Files (to be created/extended)

- `Main/services/alert_rules.py`（拡張）
- `Main/models/alertrule.py`（`rule_type`にdiscovery系を追加する場合はmigrationが必要）
- `Main/management/commands/run_alerts.py`（拡張）
- `tests/integration/test_alert_rules.py`（拡張）

## Verification (proposed)

- 初回実行で全件を新着扱いにしない（既存`AlertRule`の`new_listing`と同じ方針を踏襲）。
- 監視カテゴリごとの実行時間・API呼び出し回数の上限を確認する（Yahoo/PayPayフリマ双方への負荷を抑える）。
- 所有者スコープの確認。
