from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.csrf import ensure_csrf_cookie

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
    return render(request, "Deep_Analysis_now.html")


def Yahuoku_prediction(request):
    return render(request, "Yahuoku_prediction.html")


def introduction(request):
    return render(request, "introduction.html")
