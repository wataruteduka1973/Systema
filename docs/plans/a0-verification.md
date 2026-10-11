# A0.7 検証記録

状態: **ローカル検証完了（2026-10-11）。CIは対象PRのrunで確定する**。
基準: main `4c52d50`（PR #3マージ後）に本変更を追加した作業ツリー。

## 2026-10-11 で閉じた項目

- **再送・同時実行契約（案A: 現行挙動の固定）**: `tests/integration/test_search_resend_contract.py`。
  ADR 0003の`acquisition_id`はX1で実装する。それまでは次を契約とする。
  - 同じ条件の再送（`run_alerts`の再実行）は新しい`SearchRun`と商品行を作る。runごとの行は重複しない。
  - 成功通知はrun単位で重複しない（逐次・PostgreSQL同時の両方）。
  - 同時保存はそれぞれ完全なrunとして残り、別所有者のrunや行は混ざらない。
  - 保持上限（50件）は、同時保存の間だけ同時実行数ぶん超えることがあり、次の保存で収束する。
- **見つけて修正した不具合**: `_prune_runs`は「残すID以外」を削除していた。PostgreSQLの
  READ COMMITTEDでは、2文の間に別トランザクションがコミットした成功runまで削除し、
  成功を返したrunと商品行が消えた。上限を超えた古いIDだけを削除する形に修正した。
  修正前のコードでは同時保存テスト（20ラウンド）が5/5で失敗し、修正後は5/5で通過する。
- **検索・ウォッチのブラウザ動線**: `tests/e2e/test_target_search_watch_browser.py`。
  ログイン → ターゲット分析で検索 → 推奨結果 → ウォッチ追加 → 再読み込み後も表示、
  他ユーザーには表示されないことを確認する。Yahooには接続せず、HTTP取得の境界で
  HTML fixture（`tests/fixtures/yahoo/target_search_*.html`）を返し、実際のParser・UseCase・保存を通す。
  DBでは保存条件に紐づくclosed/currentのrun、件数、trigger、ウォッチの所有者を検算する。
- **SQLite E2Eの不安定さ**: in-memoryのテストDBでは、live serverのスレッドが1接続を共有する。
  ブラウザが並行APIを呼ぶと`InterfaceError`になっていた（再現率は約1/4）。
  `System_Config/test_settings.py`でSQLiteのテストDBをプロセスごとのファイルにして解消した。
- **full / CI**: ローカルの`verify --full`はCIと同じruff・black・mypyと全テストを実行する（PR #2）。
  main `4c52d50`のCIはすべて成功した（run 45）。

## 実行結果

| 環境 | コマンド | 結果 |
|---|---|---|
| SQLite | `python manage.py verify --full` | ruff・format・mypy・pytest・django 通過 |
| SQLite | `pytest -m e2e`（3回） | 13 passed ×3 |
| PostgreSQL 16.15（ローカル一時クラスタ） | `pytest`（E2E含む全件） | 444 passed, skip 0 |
| PostgreSQL 16.15 | `verify --feature core-contracts` | 通過 |
| PostgreSQL 16.15 | 再送・同時実行契約（反復） | 修正後 25/25 回通過 |

CIのTestsジョブはPostgreSQL 18、E2EジョブはSQLiteで実行する。

## 残る項目（A0.7の範囲外）

- 取得実行全体の冪等性（`acquisition_id`）: ADR 0003のとおりX1で実装する。
- 実Yahoo通信、本番スケジューラー、多重起動・強制終了: P0の確認事項。
- X0の入力範囲・用途の確定: X1開始条件の残り。
- 以前の記録にあったPhase 9の未追跡テストは、このリポジトリには含まれていない。
  手元に残っていれば、統合するかをP0で判断する。

## 2026-09-13 の記録（要約）

core-contracts（Web/CLIの結果一致、所有者、失敗run、snapshot失敗時の更新）を追加し、
SQLiteとPostgreSQL 18.6で通過。不正な保存条件で後続の検索が止まる問題を修正した。
