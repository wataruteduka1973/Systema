"""Regenerate the guide (introduction page) screenshots in Main/static/jpg/*_screen.jpg.

Not a regular test: it runs only when GUIDE_SCREENSHOT_DIR is set, e.g.

    GUIDE_SCREENSHOT_DIR=Main/static/jpg DB_ENGINE=sqlite \
        python -m pytest -m e2e tests/e2e/test_guide_screenshots.py

Yahoo is never contacted. The HTTP fetch boundary serves generated sample listings (generic names,
no real sellers), and listing images are simple generated SVGs, so the real search, analysis and
rendering code produces the pages. Rerun it whenever the page design changes.
"""

import os
import random
import re
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from playwright.sync_api import sync_playwright

from Main.views import utils

OUTPUT = os.environ.get("GUIDE_SCREENSHOT_DIR")
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(not OUTPUT, reason="set GUIDE_SCREENSHOT_DIR to regenerate guide images"),
]

KEYWORD = "ゲーム機"
# 1600 CSS px at scale 1.6 = 2560 x 1230 images like the originals, with more content per shot.
VIEWPORT = {"width": 1600, "height": 1100}
SCALE = 1.6
CLIP_HEIGHT = 769
# The guide already names each page, so shots start below the hero to show the results.
BELOW_HERO = ".hero-section + *"
NAMES = (
    "携帯ゲーム機 本体 ホワイト 中古 動作確認済み",
    "据え置きゲーム機 本体 ブラック 美品 箱付き",
    "ゲーム機 本体 コントローラー2個 セット",
    "携帯ゲーム機 本体 ネオンカラー 付属品完備",
    "ゲーム機 本体 限定カラー 中古 良品",
    "ジャンク ゲーム機 本体 通電のみ 部品取り",
    "新品 未開封 ゲーム機 本体 グレー",
    "ゲーム機 本体 ソフト3本付き まとめ売り",
)
PALETTE = ("#c2532c", "#2f8f78", "#a9823f", "#5f8a8b", "#8a7d70", "#b0412e")


_fetches = {"closed": 0}


def _closed_html() -> str:
    """Forty closed auctions over ~60 days around 25,000 yen with a slow decline and mild noise.

    Each fetch shifts prices slightly, so repeated updates draw a price history.
    """
    now = datetime.now()
    shift = _fetches["closed"] * 450
    _fetches["closed"] += 1
    noise = random.Random(7)
    cards = []
    for index in range(40):
        ended = now - timedelta(days=60 - index * 1.5, hours=index % 5)
        price = round((26500 - index * 60 + noise.gauss(0, 1600) - shift) / 10) * 10
        name = NAMES[index % len(NAMES)]
        cards.append(
            f'<li class="Product" data-auction-id="g1{index:08d}">'
            f'<h3 class="Product__title"><a href="/jp/auction/g1{index:08d}">{name}</a></h3>'
            f'<span class="Product__priceValue">{price:,}円</span>'
            f'<span class="Product__bid">{index * 13 % 31 + 1}</span>'
            f'<span class="Product__time">{ended:%m/%d %H:%M}</span></li>'
        )
    return f'<!doctype html><html lang="ja"><body><ul>{"".join(cards)}</ul></body></html>'


def _current_html() -> str:
    """Twelve active auctions with images; several are well below the closed-price median."""
    times = ("35分", "2時間", "5時間", "11時間", "1日", "2日")
    prices = (13800, 16500, 19800, 21500, 23800, 24500, 26800, 28000, 9800, 31500, 17200, 22800)
    cards = []
    for index, price in enumerate(prices):
        auction_id = f"g2{index:08d}"
        image = f"https://auctions.c.yimg.jp/images/guide/{index % len(PALETTE)}.jpg"
        cards.append(
            f'<li class="Product" data-auction-id="{auction_id}">'
            f'<div class="Product__image"><a class="Product__imageLink" href="/jp/auction/{auction_id}">'
            f'<img class="Product__imageData" src="{image}" alt=""></a></div>'
            f'<h3 class="Product__title"><a class="Product__titleLink" href="/jp/auction/{auction_id}">'
            f"{NAMES[index % len(NAMES)]}</a></h3>"
            f'<span class="Product__priceValue">{price:,}円</span>'
            f'<span class="Product__bid">{index * 5 % 17}</span>'
            f'<span class="Product__time">{times[index % len(times)]}</span></li>'
        )
    return f'<!doctype html><html lang="ja"><body><ul>{"".join(cards)}</ul></body></html>'


class _Page:
    def __init__(self, text: str) -> None:
        self.text = text


def _fake_fetch(url, headers, max_retries=3, timeout=15):
    if not re.search(r"[?&]b=1(&|$)", url):  # only the first result page has listings
        return _Page("<html></html>")
    return _Page(_closed_html() if "closedsearch" in url else _current_html())


def _product_svg(color: str) -> str:
    """A plain console-like silhouette so cards show an image without real product photos."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300" viewBox="0 0 400 300">'
        '<rect width="400" height="300" fill="#ffffff"/>'
        f'<rect x="70" y="95" width="260" height="120" rx="26" fill="{color}"/>'
        '<rect x="140" y="112" width="120" height="86" rx="8" fill="#2b2622"/>'
        '<circle cx="104" cy="140" r="13" fill="#f3ece1"/>'
        '<circle cx="296" cy="170" r="13" fill="#f3ece1"/>'
        '<rect x="88" y="168" width="32" height="10" rx="5" fill="#f3ece1"/>'
        '<rect x="99" y="157" width="10" height="32" rx="5" fill="#f3ece1"/>'
        "</svg>"
    )


def _serve_image(route):
    index = int(route.request.url.rsplit("/", 1)[-1].split(".")[0]) % len(PALETTE)
    route.fulfill(status=200, content_type="image/svg+xml", body=_product_svg(PALETTE[index]))


def _shoot(page, name: str, start_selector: str) -> None:
    top = page.locator(start_selector).first.bounding_box()["y"] + page.evaluate("window.scrollY")
    page.evaluate("y => window.scrollTo(0, y)", top)
    # Transient feedback toasts (e.g. after updates) are not part of the page being shown.
    page.evaluate("document.getElementById('systemaFeedback')?.replaceChildren()")
    page.wait_for_timeout(500)
    page.screenshot(
        path=str(Path(OUTPUT) / f"{name}.jpg"),
        type="jpeg",
        quality=85,
        clip={"x": 0, "y": top, "width": VIEWPORT["width"], "height": CLIP_HEIGHT},
        full_page=True,
    )


def _search(page, url: str) -> None:
    page.goto(url)
    page.fill("#search", KEYWORD)
    page.click("#button-search")


def test_regenerate_guide_screenshots(db_for_e2e, live_server, monkeypatch):
    monkeypatch.setattr(utils, "_request_with_retry", _fake_fetch)
    get_user_model().objects.create_user("guide", password="password")
    base = live_server.url
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport=VIEWPORT, device_scale_factor=SCALE)
        page.set_default_timeout(20_000)
        page.route("https://*.yimg.jp/**", _serve_image)
        try:
            page.goto(f"{base}/accounts/login/")
            page.fill('input[name="username"]', "guide")
            page.fill('input[name="password"]', "password")
            page.click('button[type="submit"]')

            _search(page, f"{base}/taskle/yahuoku")  # also stores the closed data used below
            page.locator("#dataTable tbody tr").nth(5).wait_for()
            _shoot(page, "yahuoku_screen", BELOW_HERO)

            _search(page, f"{base}/taskle/yahuoku_now")
            page.locator("#dataTable tbody tr").nth(5).wait_for()
            _shoot(page, "yahuoku_now_screen", BELOW_HERO)

            page.goto(f"{base}/taskle/yahuoku_history")
            page.locator(f'#searchWordDropdown option:has-text("{KEYWORD}")').wait_for(
                state="attached"
            )
            page.select_option("#searchWordDropdown", label=KEYWORD)
            page.click("#SearchDBButton")
            page.locator("#dataTable tbody tr").nth(5).wait_for()
            _shoot(page, "yahuoku_history_screen", BELOW_HERO)

            page.goto(f"{base}/taskle/Deep_Analysis")
            page.locator(f'#searchWordDropdown option:has-text("{KEYWORD}")').wait_for(
                state="attached"
            )
            page.select_option("#searchWordDropdown", label=KEYWORD)
            page.click("#predictSavedKeyword")
            page.locator("#predictionTable tbody tr").first.wait_for()
            page.wait_for_timeout(1500)  # chart animation
            _shoot(page, "yahuoku_analysis_screen", "#predictionSection")

            _search(page, f"{base}/taskle/Deep_Analysis_now")
            page.locator("#targetResults .target-result-card").nth(3).wait_for()
            _shoot(page, "yahuoku_analysis_now_screen", "#targetResultsHeader")

        finally:
            browser.close()
