# Top Page Recommendations

## Purpose

Show signed-in users, on the top page (`/taskle/`), a short list of buy candidates picked from their
own saved-search results, as image cards they can add to the watchlist.

## Behavior

- Source: the latest successful current-listing `SearchRun.result_snapshot` of each **active** saved
  search owned by the user. The top page never fetches from Yahoo; cards change only when a saved
  search runs (manually, or hourly through the in-app scheduler when `SYSTEMA_ALERT_SCHEDULER` is
  enabled; see `alert-rules.md`).
- Selection reuses the target-analysis buy decision stored in the snapshot: only `strong_buy` and
  `buy` items. Items already in the user's watchlist, items whose estimated end
  (`run.created_at + remainingSeconds`) has passed, items without a positive price, and items whose
  URL is not an allowed Yahoo!/PayPay Flea Market listing (`is_watchable_url`) are excluded. Items with
  an unknown end time are kept.
- "新着" marks items whose URL is not in the previous successful snapshot of the same saved search. The
  first snapshot marks nothing new. Snapshots store the top 30 ranked items, so an item that dropped out
  of the previous top 30 can show as new again.
- Order: new items first, then buy score (high first), then earliest estimated end. The same URL from
  several saved searches appears once, with its highest score. At most 6 cards.
- Empty states: signed out (log in), no active saved search (open target analysis), and no current
  candidates (shows the last fetch time).
- Cards use the same component as the target-analysis results (`Main/static/CSS/target-results.css`,
  see `target-analysis.md`): image, decision and condition badges, name, price with the
  `相場比 ±N%` chip, and a facts row (bids, estimated end, closed-price median), then the decision
  reason and the source line (saved search · fetch time). The top page shows the estimated end
  time instead of the stored remaining time, because snapshots are not live. It adds a "新着" badge
  and has no comparison checkbox. The cards use the top page's own font.
- "ウォッチリストへ追加" posts the card's stored values (including `imageUrl`) to the existing `/taskle/watchlist` API and reports
  through `SystemaFeedback`.

## Images

- The Yahoo parser reads listing images from result cards (`data-src`/`data-original`/`src`, lazy
  attributes first) and from structured data (`imageUrl`, `image`, `thumbnail`, ...). Only `https` URLs on
  `*.yimg.jp` are kept (`Main/domain/listing_image.py`); the value is rendered into `<img src>`, so
  anything else becomes "".
- `MarketListingObservation.image_url` carries the URL into current-listing items (`imageUrl`) and the
  target-analysis `recommend_items`. Closed-search items and the legacy `scraping` rows are unchanged.
- Images load directly from Yahoo's image hosts with `referrerpolicy="no-referrer"` and lazy loading.
  A missing or failed image shows the "画像なし" placeholder. This is acceptable for the current
  personal use; review the image-use terms (see `docs/plans/x0-acquisition-ledger.md`) before offering
  the page to other users.
- Snapshots saved before image support have no images until the saved search runs again.

## Related Files

- `Main/services/recommendations.py`
- `Main/domain/listing_image.py`
- `Main/views/urls.py` (`index`)
- `Main/templates/StartMenu.html`
- `Main/templates/partials/recommendations.html`
- `Main/static/JS/Recommendations.js`
- `Main/static/CSS/start-menu.css`, `Main/static/CSS/target-results.css`
- `Main/scraping/yahoo.py`, `Main/infrastructure/marketplaces/yahoo.py`, `Main/services/market_search.py`
- `tests/unit/test_recommendations.py`
- `tests/unit/test_listing_images.py`
- `tests/integration/test_top_page_recommendations.py`
- `tests/e2e/test_top_page_recommendations_browser.py`

Verification: `python manage.py verify --feature recommendations`.
