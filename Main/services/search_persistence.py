"""検索実行とlegacy商品行を一つの原子的な保存単位として扱う。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from django.db import transaction
from django.utils import timezone

from Main.models.scraping import scraping
from Main.models.searchrun import SearchRun
from Main.models.searchwordlog import searchwordlog
from Main.services.ownership import RequestOwner

MAX_RETAINED_RUNS = 50
MAX_ITEMS_PER_RUN = 200


def _legacy_row(keyword: str, item: Mapping[str, Any], observed_at: str) -> scraping:
    """既存scraping列へ保存する値をDB書込み前に組み立てる。"""
    name = str(item["name"])
    price = item.get("price", item.get("currentPrice", 0))
    start_price = item.get("startPrice", item.get("currentPrice", 0))
    bidding = item.get("bidding", 0)
    if any(isinstance(value, bool) for value in (price, start_price, bidding)):
        raise ValueError("検索結果の数値が正しくありません")
    try:
        normalized_price = int(price)
        normalized_start_price = int(start_price)
        normalized_bidding = int(bidding)
    except (TypeError, ValueError) as error:
        raise ValueError("検索結果の数値が正しくありません") from error
    return scraping(
        SearchWord=keyword,
        SearchDay=observed_at,
        Name=name,
        EndPrice=normalized_price,
        StartPrice=normalized_start_price,
        Bidding=str(normalized_bidding),
        URL=str(item.get("url", "#")),
    )


def _validated_rows(
    keyword: str, items: Sequence[Mapping[str, Any]], observed_at: str
) -> list[scraping]:
    if len(items) > MAX_ITEMS_PER_RUN:
        raise ValueError("検索結果の保存件数が上限を超えています")
    return [_legacy_row(keyword, item, observed_at) for item in items]


def _prune_runs(owner: RequestOwner, keyword: str, search_type: str) -> None:
    retained_ids = list(
        SearchRun.objects.filter(
            **owner.model_values,
            keyword=keyword,
            search_type=search_type,
        ).values_list("id", flat=True)[:MAX_RETAINED_RUNS]
    )
    SearchRun.objects.filter(
        **owner.model_values,
        keyword=keyword,
        search_type=search_type,
    ).exclude(pk__in=retained_ids).delete()


@transaction.atomic
def persist_successful_search(
    *,
    owner: RequestOwner,
    keyword: str,
    search_type: str,
    items: Sequence[Mapping[str, Any]],
    criteria_snapshot: Mapping[str, Any] | None = None,
    trigger: str = "manual",
    duration_ms: int | None = None,
    saved_search: Any | None = None,
    record_word: bool = True,
) -> SearchRun:
    """成功runと全商品行を保存し、1行でも失敗すれば全体を戻す。"""
    observed_at = timezone.localtime(timezone.now()).strftime("%Y-%m-%d %H:%M:%S")
    rows = _validated_rows(keyword, items, observed_at)
    run = SearchRun.objects.create(
        **owner.model_values,
        saved_search=saved_search,
        keyword=keyword,
        search_type=search_type,
        item_count=len(rows),
        succeeded=True,
        criteria_snapshot=dict(criteria_snapshot or {}),
        trigger=trigger,
        duration_ms=duration_ms,
        failure_code="",
    )
    for row in rows:
        row.search_run = run
    scraping.objects.bulk_create(rows)
    if record_word:
        searchwordlog.objects.create(**owner.model_values, word=keyword)

    _prune_runs(owner, keyword, search_type)
    return run


@transaction.atomic
def replace_items_for_existing_run(
    keyword: str,
    items: Sequence[Mapping[str, Any]],
    run: SearchRun,
) -> None:
    """旧呼出し用。既存runの商品行を原子的に置き換える。"""
    observed_at = timezone.localtime(timezone.now()).strftime("%Y-%m-%d %H:%M:%S")
    rows = _validated_rows(keyword, items, observed_at)
    for row in rows:
        row.search_run = run
    run.items.all().delete()
    scraping.objects.bulk_create(rows)
    run.item_count = len(rows)
    run.save(update_fields=("item_count",))
    _prune_runs(RequestOwner(user=run.user, session_key=run.session_key), keyword, run.search_type)
