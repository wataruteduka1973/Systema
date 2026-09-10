from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie

from Main.models.savedsearch import SavedSearch
from Main.models.sellerlisting import SellerListing
from Main.models.watchitem import WatchItem

MARKET_SEARCH_MODES = {
    "closed": ("落札相場", "yahuoku"),
    "current": ("現在価格", "yahuoku_now"),
    "history": ("保存済みデータ", "yahuoku_history"),
}


def index(request):
    return render(request, "StartMenu.html")


def Yahuoku(request):
    return render(request, "Yahuoku.html", {"embedded": request.GET.get("embedded") == "1"})


def Yahuoku_now(request):
    return render(
        request,
        "Yahuoku_now.html",
        {"embedded": request.GET.get("embedded") == "1"},
    )


@ensure_csrf_cookie
def Yahuoku_history(request):
    return render(
        request,
        "Yahuoku_history.html",
        {"embedded": request.GET.get("embedded") == "1"},
    )


@ensure_csrf_cookie
def market_search(request):
    mode = request.GET.get("mode", "closed")
    if mode not in MARKET_SEARCH_MODES:
        mode = "closed"
    modes = [
        {
            "key": key,
            "label": label,
            "url": f"{reverse(view_name)}?embedded=1",
        }
        for key, (label, view_name) in MARKET_SEARCH_MODES.items()
    ]
    return render(request, "market_search.html", {"active_mode": mode, "modes": modes})


@ensure_csrf_cookie
def Deep_Analysis(request):
    return render(request, "Deep_Analysis.html")


@ensure_csrf_cookie
def Deep_Analysis_now(request):
    saved_searches = (
        SavedSearch.objects.filter(user=request.user)
        if request.user.is_authenticated
        else SavedSearch.objects.none()
    )
    return render(request, "Deep_Analysis_now.html", {"saved_searches": saved_searches})


def Yahuoku_prediction(request):
    return render(request, "Yahuoku_prediction.html")


def introduction(request):
    return render(request, "introduction.html")


@login_required
@ensure_csrf_cookie
def seller_management(request):
    return render(request, "seller_management.html")


@login_required
@ensure_csrf_cookie
def notifications_page(request):
    return render(request, "notifications.html")


@login_required
@ensure_csrf_cookie
def alert_rules_page(request):
    return render(
        request,
        "alert_rules.html",
        {
            "alert_targets": {
                "savedSearch": [
                    {"id": item.pk, "label": item.name}
                    for item in SavedSearch.objects.filter(user=request.user)
                ],
                "watchItem": [
                    {"id": item.pk, "label": item.name}
                    for item in WatchItem.objects.filter(user=request.user)
                ],
                "sellerListing": [
                    {"id": item.pk, "label": item.name}
                    for item in SellerListing.objects.filter(user=request.user)
                ],
            }
        },
    )
