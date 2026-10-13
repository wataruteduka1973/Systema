# Market Search

## Purpose

Search closed auctions, current listings, or saved snapshots through one screen.

## Inputs and Output

- Inputs: mode, keyword, minimum/maximum price, product condition, sort order
- Output: product name, end/current price, start price, bids, time/date, condition, URL
- Sorting: end/current price, start price, and bid count in both directions
- External search and saved-data refresh send the same normalized criteria to the server.
- Applied criteria are stored on `SearchRun.criteria_snapshot`; UI-only interpretation is not authoritative.
- Each completed attempt stores `SearchRun.duration_ms`. Failed attempts use only the privacy-safe codes
  `external_service_unavailable`, `unexpected_error`, `no_data`, or `insufficient_data`; exception details are not stored.
- A successful search persists its `SearchRun`, legacy item rows, optional search-word entry, and
  history retention in one transaction. Item rows are validated before the write and inserted in
  one bounded batch. If item persistence fails, no successful run or partial item rows remain; the
  existing API error contract records a separate failed run.
- History retention keeps the newest 50 runs per owner, keyword and search type. Pruning deletes
  only the run IDs the saving transaction itself saw beyond the limit; it must never delete by
  "everything except a retained list", because on PostgreSQL READ COMMITTED that also deletes a run
  another transaction committed in between (a returned success would vanish). Concurrent saves can
  briefly exceed the limit by the number of concurrent saves; the next save converges it.
- Until X1 introduces `acquisition_id` (ADR 0003), every execution, including a resend of the same
  criteria, is a new observation with its own `SearchRun` and rows. A successful run is counted
  once in the owner's daily update notification (a re-recorded run is not counted again); a failed
  run has its own notification (`notifications.md`). `tests/integration/test_search_resend_contract.py` fixes this contract, with PostgreSQL
  concurrency cases.
- Marketplace acquisition uses `MarketplaceProvider` and normalized
  `MarketListingObservation` values. Yahoo URL construction, HTTP retrieval, parser coordination,
  and source validation live in `Main/infrastructure/marketplaces/yahoo.py`; the old
  `scrape_data` and `scrape_current_listings` names remain compatibility wrappers.

## Market summary and next actions

After a search (or loading saved data) a 相場の要約 panel sits above the result table. It is
computed in `MarketSearch.js` from the rows currently shown, so price/condition filters update it.

- Closed and saved-data modes: sale count, median, よく売れている価格帯 (Q1–Q3, linear quantiles like
  pandas), and 入札が集まる価格帯 (the histogram bin with the largest bid total).
- Current mode: listing count, current median, the saved closed median, and the number of listings
  15% or more below it. `RealtimeSearch` supplies `closedMarket` and per-item
  `closedMarketComparison` from the owner's newest successful saved closed run
  (`Main/services/closed_market.py`); it never adds a Yahoo request. Without saved closed data the
  panel says so and offers 落札相場を取得して比較, which runs one closed search and then the current
  search again.
- Distribution: up to eight equal-width bins over the prices inside the 1.5×IQR fences (outliers are
  counted in the note, not drawn). One hue (#0f8a70, validated); bins overlapping Q1–Q3 are full
  strength, others lighter. Counts are labelled, bars carry tooltips, and 表で見る gives a table.
- The 相場比 column shows `closedMarketComparison` for current rows and `marketComparison` for
  closed/saved rows.
- Current rows add ウォッチ (registers through the existing watchlist API with the saved closed
  median as `marketMedian`) and, for signed-in users, 仕入れ予算, which registers the watch if needed
  and opens target analysis with `?budget=<watch id>`.
- Panel buttons: 出品中の商品を探す / 落札相場を見る switch mode and search the same keyword;
  相場分析で予想を見る opens `/taskle/Deep_Analysis?source=new&keyword=…`.
- `?keyword=` (from the top page "市場の動き") opens results immediately: in `mode=history` it
  selects the saved keyword and loads it without contacting Yahoo; in other modes it fills the
  keyword and runs one search. The parameter is removed from the URL after use.
- `#closedMarketNote` and `#marketInsights` force `display:none` when `hidden`, because Bootstrap
  `d-flex` otherwise overrides the attribute.

## Boundaries

- This screen searches and filters results.
- Product-to-product market comparison is owned by target analysis.
- Saved-data update and deletion require CSRF-protected requests.

## Related Files

- `Main/templates/market_search.html`
- `Main/static/JS/MarketSearch.js`
- `Main/views/urls.py`
- `Main/views/api.py`
- `Main/views/utils.py`
- `Main/services/search_persistence.py`
- `Main/services/closed_market.py`
- `Main/services/marketplace.py`
- `Main/infrastructure/marketplaces/yahoo.py`
- `Main/domain/market_listing.py`
- `tests/integration/test_market_search.py`
- `tests/integration/test_market_search_insights.py`
- `tests/e2e/test_market_search_insights_browser.py`
- `tests/integration/test_api.py`
- `tests/integration/test_search_persistence.py`
- `tests/unit/test_yahoo_marketplace.py`

## Verification

Run the nearest market-search/API tests, `python manage.py check`, and verify all three modes without live scraping in automated tests.
