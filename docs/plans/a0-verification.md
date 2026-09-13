# A0.7 検証記録

2026-09-13。基準`17a8d03`に本変更を追加した作業ツリーで検証。
状態: **ローカル契約検証通過、A0.7全体は未完了**。

## 実装と確認

- `verify --feature core-contracts`を追加。Web/CLIのpayload・商品行・条件・所有者一致、
  同じrunの状態通知再送、他ユーザー条件ID拒否、snapshot失敗時の既存run更新を検証。
- 不正保存条件が後続検索まで中断する問題を修正。例外クラスだけ報告し次の検索へ進む。
- SQLite: alerts、core-contracts通過。保存原子性/外部検索の追加実行14件通過。
- PostgreSQL 18.6: 既存設定のcheck_database、alerts、core-contracts通過。
  pytestのテストDBで検証し、実運用データへの障害注入は行っていない。
- Black/Ruff/Django checkは上記verifyで通過。変更にmigrationなし。
- mypy: 対象38ソースでエラーなし。git diff --check通過。

## 残るゲート

- GitHub CI: NOT VERIFIED。gh CLIが未認証でrun結果を取得できない。
- Coreの同時再送、取得実行全体の冪等性: 未保証。同じrun通知の重複防止と、別実行で新runを
  作る挙動を区別する。新しいacquisition_id方式はADRの設計であり未実装。
- 検索/watchブラウザ動線、A0全体のfull検証: 未実行。Phase 9の未追跡テストは
  未統合コードを前提とするため、その統合判断とA0対象範囲を照合してから全体を閉じる。
- 実Yahoo通信、本番スケジューラー、多重起動/強制終了: NOT VERIFIED。P0側の確認事項。
- X0の入力範囲・用途確認は未完了。A0.7の局所検証通過だけでX1開始可とはしない。

次は不足する再送・並行実行契約とブラウザ証跡を確認し、対象revisionのCI/full証跡を揃える。
