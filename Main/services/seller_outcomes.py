"""Owner-scoped summaries of confirmed seller outcomes."""

from datetime import date, datetime, time, timedelta
from typing import Any

from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from django.utils import timezone

from Main.models.sellerlisting import SaleRecord

# Selling-side costs stored on each SaleRecord, in display order.
SELLING_COSTS = (
    ("fee", "販売手数料", "actual_fee"),
    ("shipping", "発送送料", "actual_shipping_cost"),
    ("packaging", "梱包費", "actual_packaging_cost"),
    ("other", "その他費用", "actual_other_cost"),
)


def _summary(records: Any) -> dict[str, int]:
    totals = records.aggregate(
        sale_count=Count("pk"),
        total_sales=Sum("sale_price"),
        total_profit=Sum("confirmed_profit"),
    )
    sale_count = totals["sale_count"] or 0
    total_sales = totals["total_sales"] or 0
    total_profit = totals["total_profit"] or 0
    return {
        "saleCount": sale_count,
        "totalSales": total_sales,
        "totalExpenses": total_sales - total_profit,
        "totalProfit": total_profit,
        "profitableCount": records.filter(confirmed_profit__gt=0).count(),
        "lossCount": records.filter(confirmed_profit__lt=0).count(),
    }


def _local_midnight(day: date) -> datetime:
    return timezone.make_aware(datetime.combine(day, time.min))


def _expense_breakdown(records: Any) -> list[dict[str, Any]]:
    """Expense items for the period.

    Purchase cost (acquisition plus purchase shipping) is not stored on SaleRecord. It is exactly
    sale price - confirmed profit - selling costs, because the profit was computed from those values.
    """
    totals = records.aggregate(
        total_sales=Sum("sale_price"),
        total_profit=Sum("confirmed_profit"),
        **{key: Sum(field) for key, _, field in SELLING_COSTS},
    )
    selling = [(key, label, totals[key] or 0) for key, label, _ in SELLING_COSTS]
    purchase = (
        (totals["total_sales"] or 0)
        - (totals["total_profit"] or 0)
        - sum(amount for _, _, amount in selling)
    )
    return [
        {"key": key, "label": label, "amount": amount}
        for key, label, amount in [
            ("purchase", "仕入れ費用（仕入れ値・仕入れ送料）", purchase),
            *selling,
        ]
    ]


def _month_starts(first: date, last: date) -> list[date]:
    months = []
    current = first.replace(day=1)
    while current <= last:
        months.append(current)
        current = (current + timedelta(days=32)).replace(day=1)
    return months


def _monthly(records: Any, start: date | None, end: date | None) -> list[dict[str, Any]]:
    """Month rows (Asia/Tokyo) for the period; months without sales are zero."""
    rows = {
        (
            timezone.localtime(row["month"]).date()
            if isinstance(row["month"], datetime)
            else row["month"]
        ): row
        for row in records.annotate(month=TruncMonth("sold_at"))
        .values("month")
        .annotate(
            sale_count=Count("pk"),
            total_sales=Sum("sale_price"),
            total_profit=Sum("confirmed_profit"),
        )
        .order_by("month")
    }
    if not rows and (start is None or end is None):
        return []
    first = start or min(rows)
    last = end or max(rows)
    result = []
    for month in _month_starts(first, last):
        row = rows.get(month, {})
        sales = row.get("total_sales") or 0
        profit = row.get("total_profit") or 0
        result.append(
            {
                "month": month.strftime("%Y-%m"),
                "saleCount": row.get("sale_count") or 0,
                "totalSales": sales,
                "totalExpenses": sales - profit,
                "totalProfit": profit,
            }
        )
    return result


def seller_outcome_analytics(
    user: Any, *, start: date | None = None, end: date | None = None
) -> dict[str, Any]:
    """Confirmed sales of ``user``, optionally limited to sale dates ``start``..``end`` (inclusive,
    Asia/Tokyo calendar days)."""
    if start and end and start > end:
        raise ValueError("期間の開始日は終了日以前にしてください")
    records = SaleRecord.objects.filter(seller_listing__user=user)
    if start:
        records = records.filter(sold_at__gte=_local_midnight(start))
    if end:
        records = records.filter(sold_at__lt=_local_midnight(end + timedelta(days=1)))
    categories = []
    for row in (
        records.values("category")
        .annotate(
            sale_count=Count("pk"),
            total_sales=Sum("sale_price"),
            total_profit=Sum("confirmed_profit"),
        )
        .order_by("-total_profit", "category")
    ):
        total_sales = row["total_sales"] or 0
        total_profit = row["total_profit"] or 0
        categories.append(
            {
                "category": row["category"] or "未分類",
                "saleCount": row["sale_count"],
                "totalSales": total_sales,
                "totalExpenses": total_sales - total_profit,
                "totalProfit": total_profit,
            }
        )
    low_profit = list(
        records.select_related("seller_listing").order_by("confirmed_profit", "sold_at", "pk")[:10]
    )
    return {
        "period": {
            "from": start.isoformat() if start else None,
            "to": end.isoformat() if end else None,
        },
        "summary": _summary(records),
        "expenseBreakdown": _expense_breakdown(records),
        "monthly": _monthly(records, start, end),
        "categories": categories,
        "lowProfitSales": [
            {
                "id": record.pk,
                "listingId": record.seller_listing_id,
                "name": record.seller_listing.name,
                "category": record.category or "未分類",
                "salePrice": record.sale_price,
                "totalExpenses": record.sale_price - record.confirmed_profit,
                "confirmedProfit": record.confirmed_profit,
                "soldAt": record.sold_at.isoformat(),
            }
            for record in low_profit
        ],
    }
