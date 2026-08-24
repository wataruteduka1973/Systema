# Target Analysis

## Purpose

Compare current listings with the closed-auction market and identify buying opportunities.

## Behavior

- Searches closed and current data for one keyword.
- Calculates the closed-price median and market statistics.
- Adds market difference, condition, and buying-decision data to current items.
- Allows two to four current items to be compared side by side.
- Owns the Systema watchlist workflow.
- Uses one integrated form for keyword and all target-analysis criteria.
- The keyword is the saved condition's display name; the UI does not ask for a separate title.
- The related-feature links, criteria, action, and frequent-word aid share one card.
- Submitting the form by button or Enter starts the same target-analysis flow and shows a loading state until completion.
- Authenticated users can inspect, edit, delete, and rerun their owner-scoped saved conditions without leaving target analysis; rerun results refresh the median and recommendation table in place.
- Authenticated users automatically save the complete criteria and execute it as a saved search, so the same displayed result remains available on the profile; the keyword is the default name, and an existing same-named condition is updated instead of duplicated.
- Profile creation and rerun use the same complete target-analysis criteria contract without involving market search.
- Saved-search execution persists the exact displayed recommendation result for profile-page revisits.

## Related Files

- `Main/templates/Deep_Analysis_now.html`
- `Main/static/JS/Deep_Analysis_now.js`
- `Main/static/JS/MarketComparison.js`
- `Main/views/utils.py` (`complex_market_data_logic`)
- `Main/services/market_statistics.py`
- `Main/domain/buying_opportunity.py`
- `Main/services/watchlist.py`
- `tests/integration/test_api.py`
- `tests/unit/test_buying_opportunity.py`
- `tests/unit/test_market_statistics.py`

## Product Decision

Market comparison is centralized here. See `docs/decisions/0002-centralize-market-comparison.md`.

## Verification

Use mocked scraper results or fixtures. Verify market statistics, comparison labels, buying decisions, unknown remaining time, and watchlist ownership.
