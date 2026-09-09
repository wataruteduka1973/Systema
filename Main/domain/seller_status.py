"""出品観測から次の作業を判定する。DB・外部I/Oは行わない。"""

from datetime import datetime, timedelta
from typing import Any

from Main.domain.profitability import calculate_profitability

ACTION_LABELS = {
    "sale_result_missing": "販売結果未入力",
    "ending_without_bids": "終了間近・入札なし",
    "ending_soon": "終了間近",
    "status_check": "終了状態の確認",
    "loss_risk": "赤字見込み",
    "cost_incomplete": "費用不足",
    "price_missing": "想定価格不足",
    "needs_refresh": "公開情報未取得",
    "stale": "公開情報が古い",
    "target_unmet": "目標利益未達",
    "bid_stalled": "入札停滞",
    "sold": "落札済み",
    "cancelled": "見送り",
    "relist": "再出品待ち",
    "ok": "通常",
}
ACTION_RANK = {
    key: rank
    for rank, keys in enumerate(
        (
            ("ending_without_bids", "ending_soon", "status_check", "sale_result_missing"),
            ("loss_risk",),
            ("cost_incomplete", "price_missing"),
            ("needs_refresh", "stale"),
            ("target_unmet", "bid_stalled"),
            ("sold", "cancelled", "relist", "ok"),
        )
    )
    for key in keys
}


def listing_price(item: Any) -> tuple[int | None, str]:
    if item.predicted_sale_price is not None:
        return item.predicted_sale_price, "manual"
    if item.last_checked_at is not None:
        return item.current_price, "currentPrice"
    if item.market_median:
        return item.market_median, "manualMarketMedian"
    return None, "unknown"


def assess_listing(
    item: Any,
    *,
    now: datetime,
    baseline_bids: int | None = None,
    sale_record_exists: bool = False,
) -> dict[str, str | int]:
    if item.status == "sold" and not sale_record_exists:
        return _result(
            "sale_result_missing",
            "販売結果を入力",
            "落札済みですが、販売価格と実費がまだ記録されていません",
        )
    if item.status in {"sold", "cancelled", "relist"}:
        return _result(
            item.status,
            "販売結果を確認" if item.status == "sold" else "状態を確認",
            "手動で設定した管理状態です。必要に応じて記録を確認してください",
        )
    stale = item.last_checked_at is None or now - item.last_checked_at >= timedelta(hours=24)
    remaining = (item.ends_at - now).total_seconds() if item.ends_at else None
    if item.status == "ended" or (
        item.status == "active" and remaining is not None and remaining <= 0
    ):
        return _result(
            "status_check",
            "状態を確認",
            "終了を確認してください。公開ページの終了は販売成立を意味しません",
        )
    if not stale and item.status == "active" and remaining is not None and 0 < remaining <= 86400:
        if item.bidding == 0:
            return _result(
                "ending_without_bids",
                "終了前に確認",
                "24時間以内に終了予定で、最終観測時の入札がありません",
            )
        return _result(
            "ending_soon",
            "終了前に確認",
            "24時間以内に終了予定です。最終観測時点の情報を確認してください",
        )
    if item.missing_cost_fields:
        return _result("cost_incomplete", "費用を補完", "不明な費用があるため利益を計算できません")
    price, source = listing_price(item)
    if price is None:
        return _result("price_missing", "想定価格を入力", "利益計算に使う販売価格がありません")
    if stale and source == "currentPrice":
        return _result("stale", "公開情報を更新", "最終取得から24時間以上経過しています")
    profit = calculate_profitability(
        sale_price=price,
        acquisition_cost=item.acquisition_cost,
        shipping_cost=item.shipping_cost_estimate + item.purchase_shipping_cost,
        packaging_cost=item.packaging_cost_estimate,
        other_cost=item.other_cost_estimate,
        fee_rate=item.fee_rate,
    )["estimatedProfit"]
    if profit is not None and profit < 0:
        return _result(
            "loss_risk", "価格・費用を確認", "表示中の想定売価・費用で計算した見込み利益が赤字です"
        )
    if item.last_checked_at is None:
        return _result("needs_refresh", "公開情報を更新", "公開価格・入札・終了日時が未取得です")
    if stale:
        return _result("stale", "公開情報を更新", "最終取得から24時間以上経過しています")
    if profit is not None and profit < item.target_profit:
        return _result("target_unmet", "目標利益を確認", "見込み利益が目標利益を下回っています")
    if item.status == "active" and baseline_bids is not None and item.bidding == baseline_bids:
        return _result(
            "bid_stalled", "入札状況を確認", "24〜48時間前の観測と最終観測で入札数が同じです"
        )
    return _result("ok", "定期確認", "取得済み情報の範囲で優先対応項目はありません")


def _result(status: str, action: str, reason: str) -> dict[str, str | int]:
    return {
        "status": status,
        "label": ACTION_LABELS[status],
        "nextAction": action,
        "reason": reason,
        "priority": ACTION_RANK[status] + 1,
    }
