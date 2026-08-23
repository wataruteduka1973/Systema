# Market Search

## Purpose

Search closed auctions, current listings, or saved snapshots through one screen.

## Inputs and Output

- Inputs: mode, keyword, minimum/maximum price, product condition, sort order
- Output: product name, end/current price, start price, bids, time/date, condition, URL
- Sorting: end/current price, start price, and bid count in both directions

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
- `tests/integration/test_market_search.py`
- `tests/integration/test_api.py`

## Verification

Run the nearest market-search/API tests, `python manage.py check`, and verify all three modes without live scraping in automated tests.
