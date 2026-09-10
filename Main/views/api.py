import hashlib
import json
import logging

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from Main.domain.product_condition import enrich_market_items, summarize_condition_market
from Main.models.alertrule import AlertRule
from Main.models.inventoryitem import InventoryItem
from Main.models.savedsearch import SavedSearch
from Main.models.searchrun import SearchRun
from Main.models.sellerlisting import SellerListing
from Main.models.watchitem import WatchItem
from Main.scraping.seller_listing import ListingParseError
from Main.services.alert_rules import (
    AlertRuleInputError,
    evaluate_saved_search_alert_rules,
    list_alert_rules,
    save_alert_rule,
    serialize_alert_rule,
)
from Main.services.error_logging import persist_client_error
from Main.services.exceptions import (
    ExternalServiceError,
    SearchInputError,
    SearchRateLimitError,
)
from Main.services.external_search import enforce_search_rate_limit
from Main.services.inventory import (
    convert_watch_to_inventory,
    list_inventory_items,
    save_inventory_item,
    serialize_inventory_item,
    simulate_inventory_profit,
)
from Main.services.market_statistics import (
    analyze_market_prices,
    enrich_items_with_market_comparison,
)
from Main.services.notifications import (
    mark_all_read,
    notification_page,
    notify_saved_search_run,
    serialize_notification,
    set_read_state,
)
from Main.services.ownership import get_request_owner, owner_query
from Main.services.purchase_budget import (
    cost_settings,
    evidence_runs,
    latest_decision,
    save_cost_settings,
    save_decision,
)
from Main.services.saved_searches import (
    criteria_from_saved_search,
    save_saved_search,
    serialize_saved_search,
)
from Main.services.search_criteria import SearchCriteria
from Main.services.search_observability import (
    FAILURE_EXTERNAL_SERVICE,
    FAILURE_UNEXPECTED,
    SearchTimer,
)
from Main.services.seller_listings import (
    ListingConflictError,
    create_listing,
    listing_page,
    owned_listing,
    refresh_listing,
    save_sale_record,
    serialize_listing,
    serialize_sale_record,
    serialize_snapshot,
    update_listing,
)
from Main.services.seller_outcomes import seller_outcome_analytics
from Main.services.watchlist import (
    list_watch_items,
    save_watch_item,
    serialize_watch_item,
    serialize_watch_snapshots,
    update_watch_item,
)

from .utils import (
    complex_market_data_logic,
    delete_market_data_logic,
    get_market_data_logic,
    get_popular_words_logic,
    get_search_words_logic,
    prediction_market_logic,
    record_search_run,
    save_to_database,
    scrape_current_listings,
    scrape_data,
    update_market_data_logic,
    update_search_run_observability,
)

logger = logging.getLogger("search_logger")

EXTERNAL_SERVICE_MESSAGE = "外部サービスからデータを取得できませんでした"
CLIENT_ERROR_KINDS = {"error", "unhandledrejection", "resource"}


@csrf_exempt
def client_errors(request):
    """Accept a bounded browser error signal without client-provided details."""
    if request.method != "POST" or len(request.body) > 256:
        return HttpResponse(status=204)
    try:
        payload = _json_payload(request)
    except (json.JSONDecodeError, ValueError, UnicodeDecodeError):
        return HttpResponse(status=204)
    if set(payload) != {"kind"} or payload["kind"] not in CLIENT_ERROR_KINDS:
        return HttpResponse(status=204)
    remote = str(request.META.get("REMOTE_ADDR", "unknown"))
    identity = hashlib.sha256(f"{settings.SECRET_KEY}:{remote}".encode()).hexdigest()
    key = f"client-error:{identity}"
    if cache.add(key, 1, timeout=settings.CLIENT_ERROR_RATE_WINDOW_SECONDS):
        allowed = True
    else:
        try:
            allowed = cache.incr(key) <= settings.CLIENT_ERROR_RATE_LIMIT
        except ValueError:
            cache.set(key, 1, timeout=settings.CLIENT_ERROR_RATE_WINDOW_SECONDS)
            allowed = True
    if allowed:
        persist_client_error(request, payload["kind"])
    return HttpResponse(status=204)


def _external_search_guard(request, search_type="closed"):
    try:
        criteria = SearchCriteria.from_query(request.GET, search_type)
        enforce_search_rate_limit(request)
        return criteria, None
    except SearchInputError as error:
        return None, JsonResponse({"error": str(error), "code": "invalid_keyword"}, status=400)
    except SearchRateLimitError as error:
        response = JsonResponse({"error": str(error), "code": "rate_limit_exceeded"}, status=429)
        response["Retry-After"] = str(error.retry_after)
        return None, response


def handle_search_response(
    request,
    data_fetch_func,
    save_func=None,
    include_condition_analysis=False,
    search_type="closed",
    criteria=None,
):
    """
    共通の検索処理を行うヘルパー関数。
    """
    logger.info("Logger initialized")
    if request.method != "GET" and criteria is None:
        logger.warning("Invalid request method received")
        return JsonResponse({"error": "Invalid request method"}, status=400)

    if criteria is None:
        criteria, guard_response = _external_search_guard(request, search_type)
        if guard_response is not None:
            return guard_response
    else:
        try:
            enforce_search_rate_limit(request)
        except SearchRateLimitError as error:
            response = JsonResponse(
                {"error": str(error), "code": "rate_limit_exceeded"}, status=429
            )
            response["Retry-After"] = str(error.retry_after)
            return response
    searchname = criteria.keyword
    logger.info("External search started keyword_length=%s", len(searchname))
    timer = SearchTimer.start()
    search_run = None

    try:
        scraped_data_list = criteria.apply(data_fetch_func(searchname))
        logger.info(f"Scraped {len(scraped_data_list)} items for keyword: {searchname}")
        search_run = record_search_run(
            request,
            searchname,
            search_type,
            len(scraped_data_list),
            criteria_snapshot=criteria.snapshot(),
            duration_ms=timer.elapsed_ms(),
        )
        if save_func:
            save_func(searchname, scraped_data_list, search_run)
            logger.info(f"Data saved to database for keyword: {searchname}")
        response_data = {"data": scraped_data_list}
        if include_condition_analysis:
            enriched_items = enrich_market_items(scraped_data_list)
            market_statistics = analyze_market_prices(enriched_items)
            enriched_items = enrich_items_with_market_comparison(
                enriched_items, market_statistics["median"]
            )
            response_data = {
                "data": enriched_items,
                "conditionSummary": summarize_condition_market(enriched_items),
                "marketStatistics": market_statistics,
            }
        update_search_run_observability(search_run, duration_ms=timer.elapsed_ms())
        return JsonResponse(response_data)
    except ExternalServiceError:
        logger.exception("External search failed")
        if search_run is None:
            record_search_run(
                request,
                searchname,
                search_type,
                0,
                succeeded=False,
                criteria_snapshot=criteria.snapshot(),
                duration_ms=timer.elapsed_ms(),
                failure_code=FAILURE_EXTERNAL_SERVICE,
            )
        else:
            update_search_run_observability(
                search_run,
                duration_ms=timer.elapsed_ms(),
                succeeded=False,
                failure_code=FAILURE_EXTERNAL_SERVICE,
            )
        return JsonResponse(
            {"error": EXTERNAL_SERVICE_MESSAGE, "code": "external_service_unavailable"},
            status=503,
        )
    except Exception:
        logger.exception("Unexpected external search error")
        if search_run is None:
            record_search_run(
                request,
                searchname,
                search_type,
                0,
                succeeded=False,
                criteria_snapshot=criteria.snapshot(),
                duration_ms=timer.elapsed_ms(),
                failure_code=FAILURE_UNEXPECTED,
            )
        else:
            update_search_run_observability(
                search_run,
                duration_ms=timer.elapsed_ms(),
                succeeded=False,
                failure_code=FAILURE_UNEXPECTED,
            )
        return JsonResponse(
            {"error": "検索処理中にエラーが発生しました", "code": "search_failed"},
            status=500,
        )


def perform_search(request):
    """
    相場のデータを取得して処理する。
    """
    return handle_search_response(
        request, scrape_data, save_to_database, include_condition_analysis=True
    )


def RealtimeSearch(request):
    """
    現在出品されている商品のデータを取得して処理する。
    """
    return handle_search_response(
        request,
        scrape_current_listings,
        save_to_database,
        include_condition_analysis=True,
        search_type="current",
    )


def get_search_words(request):
    """
    データベースにアクセスして過去の検索履歴を取得する
    """
    return get_search_words_logic(request)


def get_market_data(request):
    """
    データベースにアクセスして過去の検索履歴を取得する。
    """
    return get_market_data_logic(request)


def update_market_data(request):
    """
    フロントエンドから取得した対象を更新する
    """
    if request.method == "POST":
        criteria, guard_response = _external_search_guard(request)
        if guard_response is not None:
            return guard_response
        return update_market_data_logic(request, criteria)
    return update_market_data_logic(request)


def delete_market_data(request):
    """
    フロントエンドから取得した対象を削除する
    """
    return delete_market_data_logic(request)


def complex_market_data(request):
    """
    指定キーワードの落札履歴と現在出品中データを取得し、分析結果を返す
    """
    if request.method == "GET":
        criteria, guard_response = _external_search_guard(request, "target")
        if guard_response is not None:
            return guard_response
        return complex_market_data_logic(request, criteria)
    return complex_market_data_logic(request)


def prediction_market(request):
    """
    過去90日間の価格推移を分析し、異常値を排除した90日移動平均と1ヶ月予測を返す。
    """
    if request.method == "GET":
        criteria, guard_response = _external_search_guard(request, "prediction")
        if guard_response is not None:
            return guard_response
        return prediction_market_logic(request, criteria)
    return prediction_market_logic(request)


def get_popular_words(request):
    """
    使用頻度の高い検索ワードを返す
    """
    return get_popular_words_logic(request)


def watchlist(request):
    """Systema内のウォッチリストを取得、または商品を登録する。"""
    owner = get_request_owner(request)
    if request.method == "GET":
        try:
            priority_value = request.GET.get("priority")
            priority = int(priority_value) if priority_value not in (None, "") else None
            items = list_watch_items(
                owner,
                lifecycle_status=request.GET.get("status") or None,
                priority=priority,
                condition=request.GET.get("condition") or None,
            )
            return JsonResponse({"items": items})
        except (TypeError, ValueError) as error:
            return JsonResponse({"error": str(error)}, status=400)
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)
    try:
        payload = json.loads(request.body or b"{}")
        if not isinstance(payload, dict):
            raise ValueError("リクエスト形式が正しくありません")
        item, created = save_watch_item(payload, owner)
        return JsonResponse(
            {"item": serialize_watch_item(item), "created": created},
            status=201 if created else 200,
        )
    except (json.JSONDecodeError, ValueError) as error:
        return JsonResponse({"error": str(error)}, status=400)


def watchlist_item(request, item_id):
    """ウォッチ商品のユーザー管理情報を更新、または解除する。"""
    owner = get_request_owner(request)
    if request.method == "PATCH":
        try:
            payload = json.loads(request.body or b"{}")
            if not isinstance(payload, dict):
                raise ValueError("リクエスト形式が正しくありません")
            item = update_watch_item(item_id, payload, owner)
            if item is None:
                return JsonResponse({"error": "Watch item not found"}, status=404)
            return JsonResponse({"item": serialize_watch_item(item)})
        except (json.JSONDecodeError, ValueError) as error:
            return JsonResponse({"error": str(error)}, status=400)
    if request.method != "DELETE":
        return JsonResponse({"error": "Invalid request method"}, status=400)
    deleted, _ = WatchItem.objects.filter(owner_query(owner), pk=item_id).delete()
    if not deleted:
        return JsonResponse({"error": "Watch item not found"}, status=404)
    return JsonResponse({"message": "ウォッチを解除しました"})


def watchlist_snapshots(request, item_id):
    """本人所有のウォッチ商品の価格履歴と分析結果を返す。"""
    owner = get_request_owner(request)
    if request.method != "GET":
        return JsonResponse({"error": "Invalid request method"}, status=400)
    try:
        item = WatchItem.objects.prefetch_related("price_snapshots").get(
            owner_query(owner), pk=item_id
        )
    except WatchItem.DoesNotExist:
        return JsonResponse({"error": "Watch item not found"}, status=404)
    return JsonResponse(serialize_watch_snapshots(item))


def _authenticated_json(request):
    if request.user.is_authenticated:
        return None
    return JsonResponse(
        {"error": "ログインが必要です", "code": "authentication_required"}, status=401
    )


def _json_payload(request):
    payload = json.loads(request.body or b"{}")
    if not isinstance(payload, dict):
        raise ValueError("リクエスト形式が正しくありません")
    return payload


def _seller_error(message, code, status):
    return JsonResponse({"error": {"code": code, "message": message}}, status=status)


def purchase_cost_settings(request):
    denied = _authenticated_json(request)
    if denied:
        return denied
    try:
        if request.method == "GET":
            return JsonResponse(
                {"data": cost_settings(request.user), "evidenceRuns": evidence_runs(request.user)}
            )
        if request.method == "PUT":
            return JsonResponse({"data": save_cost_settings(request.user, _json_payload(request))})
        return _seller_error("許可されていないメソッドです", "method_not_allowed", 405)
    except (ValueError, UnicodeDecodeError) as error:
        return _seller_error(str(error), "validation_error", 400)


def purchase_budget(request, item_id):
    denied = _authenticated_json(request)
    if denied:
        return denied
    try:
        watch = WatchItem.objects.get(user=request.user, pk=item_id)
        if request.method == "GET":
            return JsonResponse(
                {
                    "data": latest_decision(watch),
                    "defaults": cost_settings(request.user),
                    "currentPrice": watch.current_price,
                    "locked": hasattr(watch, "inventory_item")
                    or watch.lifecycle_status == "purchased",
                }
            )
        if request.method == "POST":
            return JsonResponse(
                {"data": save_decision(request.user, item_id, _json_payload(request))}
            )
        return _seller_error("許可されていないメソッドです", "method_not_allowed", 405)
    except (WatchItem.DoesNotExist, SearchRun.DoesNotExist):
        return _seller_error("商品または根拠が見つかりません", "not_found", 404)
    except (ValueError, UnicodeDecodeError) as error:
        return _seller_error(str(error), "validation_error", 400)


def _seller_page(request, items, serializer):
    try:
        page = int(request.GET.get("page", "1"))
        size = int(request.GET.get("pageSize", "20"))
        if page < 1 or page > 1_000_000 or size < 1 or size > 100:
            raise ValueError
    except ValueError:
        return _seller_error("ページ指定が正しくありません", "validation_error", 400)
    return JsonResponse(
        {
            "data": [serializer(item) for item in items[(page - 1) * size : page * size]],
            "meta": {"page": page, "pageSize": size, "total": items.count()},
        }
    )


def seller_listings(request):
    if not request.user.is_authenticated:
        return _seller_error("ログインが必要です", "authentication_required", 401)
    try:
        if request.method == "GET":
            page = int(request.GET.get("page", "1"))
            size = int(request.GET.get("pageSize", "20"))
            if not 1 <= page <= 1_000_000 or not 1 <= size <= 100:
                raise ValueError("ページ指定が正しくありません")
            return JsonResponse(
                listing_page(
                    request.user,
                    status=request.GET.get("status", ""),
                    action=request.GET.get("action", ""),
                    sort=request.GET.get("sort", "updated"),
                    page=page,
                    size=size,
                )
            )
        if request.method == "POST":
            item = create_listing(request.user, _json_payload(request))
            return JsonResponse({"data": serialize_listing(item)}, status=201)
        return _seller_error("許可されていないメソッドです", "method_not_allowed", 405)
    except SellerListing.DoesNotExist:
        return _seller_error("在庫が見つかりません", "not_found", 404)
    except ListingConflictError as error:
        return _seller_error(str(error), "conflict", 409)
    except ValueError as error:
        return _seller_error(str(error), "validation_error", 400)


def seller_listing_item(request, listing_id):
    if not request.user.is_authenticated:
        return _seller_error("ログインが必要です", "authentication_required", 401)
    try:
        item = owned_listing(request.user, listing_id)
        if request.method == "GET":
            return JsonResponse({"data": serialize_listing(item)})
        if request.method == "PATCH":
            return JsonResponse(
                {
                    "data": serialize_listing(
                        update_listing(request.user, listing_id, _json_payload(request))
                    )
                }
            )
        if request.method == "DELETE":
            item.delete()
            return JsonResponse({}, status=204)
        return _seller_error("許可されていないメソッドです", "method_not_allowed", 405)
    except SellerListing.DoesNotExist:
        return _seller_error("出品が見つかりません", "not_found", 404)
    except ValueError as error:
        return _seller_error(str(error), "validation_error", 400)


def seller_listing_refresh(request, listing_id):
    if not request.user.is_authenticated:
        return _seller_error("ログインが必要です", "authentication_required", 401)
    if request.method != "POST":
        return _seller_error("許可されていないメソッドです", "method_not_allowed", 405)
    try:
        if _json_payload(request):
            raise ValueError("更新時の追加データや認証情報は受け付けません")
        return JsonResponse({"data": serialize_listing(refresh_listing(request.user, listing_id))})
    except SellerListing.DoesNotExist:
        return _seller_error("出品が見つかりません", "not_found", 404)
    except SearchRateLimitError as error:
        response = _seller_error("出品更新回数の上限に達しました", "rate_limit_exceeded", 429)
        response["Retry-After"] = str(error.retry_after)
        return response
    except ListingConflictError as error:
        return _seller_error(str(error), "conflict", 409)
    except ListingParseError as error:
        return _seller_error(str(error), "listing_parse_failed", 502)
    except ExternalServiceError:
        return _seller_error(
            "公開ページを取得できませんでした。保存済み情報は変更していません",
            "external_service_unavailable",
            502,
        )
    except ValueError as error:
        return _seller_error(str(error), "validation_error", 400)


def seller_listing_snapshots(request, listing_id):
    if not request.user.is_authenticated:
        return _seller_error("ログインが必要です", "authentication_required", 401)
    if request.method != "GET":
        return _seller_error("許可されていないメソッドです", "method_not_allowed", 405)
    try:
        item = owned_listing(request.user, listing_id)
        return _seller_page(request, item.snapshots.all(), serialize_snapshot)
    except SellerListing.DoesNotExist:
        return _seller_error("出品が見つかりません", "not_found", 404)


def seller_listing_sale(request, listing_id):
    if not request.user.is_authenticated:
        return _seller_error("ログインが必要です", "authentication_required", 401)
    if request.method != "PUT":
        return _seller_error("許可されていないメソッドです", "method_not_allowed", 405)
    try:
        record = save_sale_record(request.user, listing_id, _json_payload(request))
        return JsonResponse({"data": serialize_sale_record(record)})
    except SellerListing.DoesNotExist:
        return _seller_error("出品が見つかりません", "not_found", 404)
    except ValueError as error:
        return _seller_error(str(error), "validation_error", 400)


def seller_outcomes(request):
    if not request.user.is_authenticated:
        return _seller_error("ログインが必要です", "authentication_required", 401)
    if request.method != "GET":
        return _seller_error("許可されていないメソッドです", "method_not_allowed", 405)
    return JsonResponse({"data": seller_outcome_analytics(request.user)})


def inventory_items(request):
    """本人の在庫を一覧、または手動登録する。"""
    denied = _authenticated_json(request)
    if denied:
        return denied
    if request.method == "GET":
        try:
            return JsonResponse(
                {"items": list_inventory_items(request.user, request.GET.get("status") or None)}
            )
        except ValueError as error:
            return JsonResponse({"error": str(error), "code": "invalid_inventory"}, status=400)
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)
    try:
        item = save_inventory_item(request.user, _json_payload(request))
        return JsonResponse({"item": serialize_inventory_item(item)}, status=201)
    except (json.JSONDecodeError, ValueError) as error:
        return JsonResponse({"error": str(error), "code": "invalid_inventory"}, status=400)


def inventory_item(request, item_id):
    """本人の在庫だけを参照、更新、削除する。"""
    denied = _authenticated_json(request)
    if denied:
        return denied
    item = InventoryItem.objects.filter(user=request.user, pk=item_id).first()
    if item is None:
        return JsonResponse({"error": "在庫が見つかりません"}, status=404)
    if request.method == "GET":
        return JsonResponse({"item": serialize_inventory_item(item)})
    if request.method == "DELETE":
        item.delete()
        return JsonResponse({"message": "在庫を削除しました"})
    if request.method != "PATCH":
        return JsonResponse({"error": "Invalid request method"}, status=400)
    try:
        item = save_inventory_item(request.user, _json_payload(request), instance=item)
        return JsonResponse({"item": serialize_inventory_item(item)})
    except (json.JSONDecodeError, ValueError) as error:
        return JsonResponse({"error": str(error), "code": "invalid_inventory"}, status=400)


def convert_watch_item_to_inventory(request, watch_item_id):
    """本人の購入候補を重複なく仕入済み在庫へ変換する。"""
    denied = _authenticated_json(request)
    if denied:
        return denied
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)
    try:
        item, created = convert_watch_to_inventory(
            request.user, watch_item_id, _json_payload(request)
        )
        if item is None:
            return JsonResponse({"error": "購入候補が見つかりません"}, status=404)
        return JsonResponse(
            {"item": serialize_inventory_item(item), "created": created},
            status=201 if created else 200,
        )
    except (json.JSONDecodeError, ValueError) as error:
        return JsonResponse({"error": str(error), "code": "invalid_inventory"}, status=400)


def inventory_profit_simulation(request, item_id):
    """本人の在庫について、入力値を保存せず見込み利益を計算する。"""
    denied = _authenticated_json(request)
    if denied:
        return denied
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)
    item = InventoryItem.objects.filter(user=request.user, pk=item_id).first()
    if item is None:
        return JsonResponse({"error": "在庫が見つかりません"}, status=404)
    try:
        return JsonResponse({"data": simulate_inventory_profit(item, _json_payload(request))})
    except (json.JSONDecodeError, ValueError) as error:
        return JsonResponse({"error": str(error), "code": "invalid_profit_input"}, status=400)


def saved_searches(request):
    """本人の保存条件を一覧、または作成する。"""
    denied = _authenticated_json(request)
    if denied:
        return denied
    if request.method == "GET":
        items = SavedSearch.objects.filter(user=request.user)
        return JsonResponse({"items": [serialize_saved_search(item) for item in items]})
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)
    try:
        payload = _json_payload(request)
        existing = None
        if payload.pop("replaceExisting", False) is True:
            name = str(payload.get("name", "")).strip()
            if name:
                existing = SavedSearch.objects.filter(user=request.user, name=name).first()
        item = save_saved_search(request.user, payload, instance=existing)
        return JsonResponse({"item": serialize_saved_search(item)}, status=200 if existing else 201)
    except (json.JSONDecodeError, ValueError, SearchInputError) as error:
        return JsonResponse({"error": str(error), "code": "invalid_saved_search"}, status=400)


def saved_search_item(request, saved_search_id):
    """本人の保存条件だけを参照、更新、削除する。"""
    denied = _authenticated_json(request)
    if denied:
        return denied
    item = SavedSearch.objects.filter(user=request.user, pk=saved_search_id).first()
    if item is None:
        return JsonResponse({"error": "保存条件が見つかりません"}, status=404)
    if request.method == "GET":
        return JsonResponse({"item": serialize_saved_search(item)})
    if request.method == "DELETE":
        item.delete()
        return JsonResponse({"message": "保存条件を削除しました"})
    if request.method != "PATCH":
        return JsonResponse({"error": "Invalid request method"}, status=400)
    try:
        item = save_saved_search(request.user, _json_payload(request), instance=item)
        return JsonResponse({"item": serialize_saved_search(item)})
    except (json.JSONDecodeError, ValueError, SearchInputError) as error:
        return JsonResponse({"error": str(error), "code": "invalid_saved_search"}, status=400)


def run_saved_search(request, saved_search_id):
    """本人の有効な保存条件を共通検索処理で即時実行する。"""
    denied = _authenticated_json(request)
    if denied:
        return denied
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)
    saved_search = SavedSearch.objects.filter(user=request.user, pk=saved_search_id).first()
    if saved_search is None:
        return JsonResponse({"error": "保存条件が見つかりません"}, status=404)
    if not saved_search.is_active:
        return JsonResponse({"error": "無効な保存条件です"}, status=409)

    try:
        criteria = criteria_from_saved_search(saved_search)
    except SearchInputError as error:
        return JsonResponse({"error": str(error), "code": "invalid_saved_search"}, status=400)

    request.saved_search = saved_search
    request.search_trigger = "saved"
    try:
        enforce_search_rate_limit(request)
    except SearchRateLimitError as error:
        response = JsonResponse({"error": str(error), "code": "rate_limit_exceeded"}, status=429)
        response["Retry-After"] = str(error.retry_after)
        return response
    response = complex_market_data_logic(request, criteria)

    recorded_runs = getattr(request, "recorded_search_runs", [])
    if recorded_runs:
        notify_saved_search_run(recorded_runs[-1])
        current_run = next(
            (
                run
                for run in reversed(recorded_runs)
                if run.search_type == SearchRun.CURRENT and run.succeeded
            ),
            None,
        )
        if current_run is not None:
            evaluate_saved_search_alert_rules(current_run)

    SavedSearch.objects.filter(pk=saved_search.pk, user=request.user).update(
        last_run_at=timezone.now()
    )
    return response


def notifications(request):
    """本人の通知一覧と未読件数を返す。"""
    denied = _authenticated_json(request)
    if denied:
        return denied
    if request.method != "GET":
        return JsonResponse({"error": "Invalid request method"}, status=400)
    try:
        unread_value = request.GET.get("unreadOnly", "false").lower()
        if unread_value not in {"true", "false"}:
            raise ValueError("unreadOnlyはtrueまたはfalseで指定してください")
        page = int(request.GET.get("page", "1"))
        page_size = int(request.GET.get("pageSize", "20"))
        if page < 1 or not 1 <= page_size <= 100:
            raise ValueError("pageは1以上、pageSizeは1から100で指定してください")
        return JsonResponse(
            notification_page(
                request.user,
                unread_only=unread_value == "true",
                page=page,
                page_size=page_size,
            )
        )
    except ValueError as error:
        return JsonResponse({"error": str(error)}, status=400)


def notification_item(request, notification_id):
    """本人の通知だけを既読または未読へ更新する。"""
    denied = _authenticated_json(request)
    if denied:
        return denied
    if request.method != "PATCH":
        return JsonResponse({"error": "Invalid request method"}, status=400)
    try:
        payload = _json_payload(request)
        if set(payload) != {"read"} or not isinstance(payload["read"], bool):
            raise ValueError("readにはtrueまたはfalseを指定してください")
        item = set_read_state(request.user, notification_id, read=payload["read"])
        if item is None:
            return JsonResponse({"error": "通知が見つかりません"}, status=404)
        return JsonResponse({"item": serialize_notification(item)})
    except (json.JSONDecodeError, ValueError) as error:
        return JsonResponse({"error": str(error)}, status=400)


def notifications_read_all(request):
    """本人の未読通知を一括で既読にする。"""
    denied = _authenticated_json(request)
    if denied:
        return denied
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)
    return JsonResponse({"updatedCount": mark_all_read(request.user)})


def alert_rules(request):
    """List or create rules owned by the authenticated user."""
    denied = _authenticated_json(request)
    if denied:
        return denied
    if request.method == "GET":
        return JsonResponse({"items": list_alert_rules(request.user)})
    if request.method != "POST":
        return JsonResponse({"error": "Invalid request method"}, status=400)
    try:
        item = save_alert_rule(request.user, _json_payload(request))
        return JsonResponse({"item": serialize_alert_rule(item)}, status=201)
    except (json.JSONDecodeError, AlertRuleInputError) as error:
        return JsonResponse({"error": str(error)}, status=400)


def alert_rule_item(request, alert_rule_id):
    """Read, update, or delete an owner-scoped alert rule."""
    denied = _authenticated_json(request)
    if denied:
        return denied
    item = AlertRule.objects.filter(user=request.user, pk=alert_rule_id).first()
    if item is None:
        return JsonResponse({"error": "アラート条件が見つかりません"}, status=404)
    if request.method == "GET":
        return JsonResponse({"item": serialize_alert_rule(item)})
    if request.method == "PATCH":
        try:
            return JsonResponse(
                {
                    "item": serialize_alert_rule(
                        save_alert_rule(request.user, _json_payload(request), item)
                    )
                }
            )
        except (json.JSONDecodeError, AlertRuleInputError) as error:
            return JsonResponse({"error": str(error)}, status=400)
    if request.method == "DELETE":
        item.delete()
        return JsonResponse({}, status=204)
    return JsonResponse({"error": "Invalid request method"}, status=400)
