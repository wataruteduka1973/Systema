"""Owner-scoped summaries of confirmed seller outcomes."""

from typing import Any

from django.db.models import Count, Sum

from Main.models.sellerlisting import SaleRecord


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


def seller_outcome_analytics(user: Any) -> dict[str, Any]:
    records = SaleRecord.objects.filter(seller_listing__user=user)
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
        "summary": _summary(records),
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
