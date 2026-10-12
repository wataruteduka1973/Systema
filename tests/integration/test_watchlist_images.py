"""Watch items keep a safe listing image across registration and search refreshes."""

import pytest
from django.contrib.auth import get_user_model

from Main.models.watchitem import WatchItem
from Main.services.ownership import RequestOwner
from Main.services.watchlist import refresh_watched_item, save_watch_item, serialize_watch_item

pytestmark = pytest.mark.django_db

URL = "https://auctions.yahoo.co.jp/jp/auction/w10000001"
IMAGE = "https://auctions.c.yimg.jp/images/w10000001.jpg"


def _owner():
    return RequestOwner(user=get_user_model().objects.create_user("watch-image"), session_key="")


def _payload(**extra):
    return {
        "name": "画像付きカメラ",
        "url": URL,
        "currentPrice": 9000,
        "marketMedian": 15000,
        "condition": "used",
        **extra,
    }


def test_registration_stores_only_safe_images_and_serializes_them():
    owner = _owner()
    item, _ = save_watch_item(_payload(imageUrl=IMAGE), owner)
    assert serialize_watch_item(item)["imageUrl"] == IMAGE

    unsafe, _ = save_watch_item(
        _payload(url="https://auctions.yahoo.co.jp/jp/auction/w10000002", imageUrl="javascript:x"),
        owner,
    )
    assert unsafe.primary_image_url == ""


def test_payload_without_image_keeps_the_stored_image():
    owner = _owner()
    save_watch_item(_payload(imageUrl=IMAGE), owner)

    save_watch_item(_payload(currentPrice=8500), owner)
    refresh_watched_item({**_payload(), "price": 8000, "imageUrl": ""}, owner)

    assert WatchItem.objects.get().primary_image_url == IMAGE


def test_search_refresh_fills_a_missing_image():
    owner = _owner()
    save_watch_item(_payload(), owner)
    assert WatchItem.objects.get().primary_image_url == ""

    assert refresh_watched_item({**_payload(), "price": 8800, "imageUrl": IMAGE}, owner)

    assert WatchItem.objects.get().primary_image_url == IMAGE
